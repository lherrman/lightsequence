"""
Pilot Widget (Redesigned)

Modern, compact GUI for MIDI clock sync and phrase detection with automation rules.
"""

import logging
from typing import Optional, Callable

import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QGroupBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QToolButton,
    QFrame,
)

from lumiblox.pilot.phrase_detector import CaptureRegion
from lumiblox.pilot.pilot_preset import PilotPresetManager
from lumiblox.gui.rule_editor import PresetEditorDialog
from lumiblox.common.config import get_config

logger = logging.getLogger(__name__)


# Region selector and config dialog remain the same
class FixedSizeRegionSelector(QWidget):
    """Draggable fixed-size overlay window for region selection."""

    region_confirmed = Signal(QRect)
    selection_cancelled = Signal()

    def __init__(self, region_type: str):
        """
        Create a fixed-size region selector.

        Args:
            region_type: Either "button" or "timeline"
        """
        super().__init__(
            None, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint
        )
        self.setWindowOpacity(0.7)
        self.region_type = region_type

        # Set fixed size based on region type
        if region_type == "button":
            self.setFixedSize(64, 22)  # Master button size
            self._title = "Master Button"
        else:
            self.setFixedSize(220, 88)  # Timeline size
            self._title = "Timeline"

        # Blue background
        self.setStyleSheet("background-color: #0078d4;")

        # Dragging state
        self._drag_position = None

    def paintEvent(self, event) -> None:
        """Draw title bar."""
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), 20, QColor(0, 120, 200))

        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.width(), 20), Qt.AlignmentFlag.AlignCenter, self._title
        )
        painter.end()

    def mousePressEvent(self, event) -> None:
        """Start dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:
        """Handle dragging."""
        if (
            event.buttons() == Qt.MouseButton.LeftButton
            and self._drag_position is not None
        ):
            self.move(event.globalPosition().toPoint() - self._drag_position)

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Escape:
            self.selection_cancelled.emit()
            self.close()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.confirm_region()

    def confirm_region(self) -> None:
        """Confirm the current position and emit the region."""
        geometry = self.frameGeometry()
        self.region_confirmed.emit(geometry)
        self.close()


class RegionConfigDialog(QDialog):
    """Dialog for configuring both capture regions for a deck."""

    regions_configured = Signal(str, QRect, QRect)

    def __init__(self, deck_name: str, parent=None):
        super().__init__(parent)
        self.deck_name = deck_name
        self.button_rect = None
        self.timeline_rect = None

        self.setWindowTitle(f"Configure Deck {deck_name} Capture Regions")
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            f"1. Click 'Show Overlay Windows' below\n"
            f"2. Drag the blue overlay windows to align with Deck {deck_name}\n"
            f"3. Press Enter on each window when positioned correctly\n"
            f"4. Click 'Save & Close' when both are set\n"
            f"(Press Escape on a window to cancel)"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "padding: 10px; background-color: #2d2d2d; border-radius: 5px;"
        )
        layout.addWidget(instructions)

        # Button to show overlays
        show_btn = QPushButton("Show Overlay Windows")
        show_btn.clicked.connect(self._show_overlays)
        layout.addWidget(show_btn)

        # Status labels
        self.button_status = QLabel("Master Button: Not set")
        self.timeline_status = QLabel("Timeline: Not set")
        layout.addWidget(self.button_status)
        layout.addWidget(self.timeline_status)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Save & Close")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(button_box)

        self.button_box = button_box

    def _show_overlays(self) -> None:
        """Show both overlay windows for positioning."""
        self.button_overlay = FixedSizeRegionSelector("button")
        self.button_overlay.region_confirmed.connect(self._on_button_confirmed)
        self.button_overlay.selection_cancelled.connect(self._on_cancelled)

        self.timeline_overlay = FixedSizeRegionSelector("timeline")
        self.timeline_overlay.region_confirmed.connect(self._on_timeline_confirmed)
        self.timeline_overlay.selection_cancelled.connect(self._on_cancelled)

        # Try to load existing regions from config
        config = get_config()
        button_region = config.get_deck_region(self.deck_name, "button")
        timeline_region = config.get_deck_region(self.deck_name, "timeline")

        # Position overlays at configured locations if available, otherwise center them
        screen = QGuiApplication.primaryScreen().geometry()
        center_x = screen.center().x()
        center_y = screen.center().y()

        if button_region:
            self.button_overlay.move(button_region["x"], button_region["y"])
        else:
            self.button_overlay.move(center_x - 200, center_y - 50)

        if timeline_region:
            self.timeline_overlay.move(timeline_region["x"], timeline_region["y"])
        else:
            self.timeline_overlay.move(center_x + 50, center_y - 50)

        # Show both
        self.button_overlay.show()
        self.button_overlay.raise_()
        self.button_overlay.activateWindow()

        self.timeline_overlay.show()
        self.timeline_overlay.raise_()
        self.timeline_overlay.activateWindow()

    def _on_button_confirmed(self, rect: QRect) -> None:
        """Handle button region confirmation."""
        self.button_rect = rect
        self.button_status.setText(f"Master Button: Set at ({rect.x()}, {rect.y()})")
        logger.info(f"Button region confirmed: {rect.x()}, {rect.y()}")
        self._check_completion()

    def _on_timeline_confirmed(self, rect: QRect) -> None:
        """Handle timeline region confirmation."""
        self.timeline_rect = rect
        self.timeline_status.setText(f"Timeline: Set at ({rect.x()}, {rect.y()})")
        logger.info(f"Timeline region confirmed: {rect.x()}, {rect.y()}")
        self._check_completion()

    def _check_completion(self) -> None:
        """Check if both regions are set."""
        if self.button_rect and self.timeline_rect:
            self.ok_button.setEnabled(True)

    def _on_cancelled(self) -> None:
        """Handle cancellation."""
        self.reject()

    def accept(self) -> None:
        """Handle dialog acceptance."""
        if self.button_rect and self.timeline_rect:
            self.regions_configured.emit(
                self.deck_name, self.button_rect, self.timeline_rect
            )
        super().accept()


class PilotWidget(QWidget):
    """Compact pilot control widget with automation rules."""

    pilot_enable_requested = Signal(bool)
    phrase_detection_enable_requested = Signal(bool)
    align_requested = Signal()
    deck_region_configured = Signal(str, str, CaptureRegion)

    def __init__(self, refresh_callback: Optional[Callable[[], None]] = None):
        super().__init__()
        self.refresh_callback = refresh_callback
        self.phrase_detection_enabled = False
        self.preset_manager = PilotPresetManager()
        self.setup_ui()
        self._load_presets()

    def setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # === HEADER: Control buttons + Status bar ===
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Button style for consistent appearance
        button_style = """
            QPushButton {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
                color: white;
                font-size: 14px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
            QPushButton:checked {
                background-color: #0078d4;
                border: 1px solid #005a9e;
            }
        """

        # Control buttons (proper QPushButton style with icons)
        self.pilot_toggle_btn = QPushButton()
        self.pilot_toggle_btn.setCheckable(True)
        self.pilot_toggle_btn.setToolTip("Start/Stop Pilot")
        self.pilot_toggle_btn.setFixedSize(QSize(32, 32))
        self.pilot_toggle_btn.setStyleSheet(button_style)
        self.pilot_toggle_btn.setIcon(qta.icon("fa5s.play", color="white"))
        self.pilot_toggle_btn.setIconSize(QSize(16, 16))
        self.pilot_toggle_btn.toggled.connect(self._on_pilot_toggle)
        header_layout.addWidget(self.pilot_toggle_btn)

        self.phrase_detection_btn = QPushButton()
        self.phrase_detection_btn.setCheckable(True)
        self.phrase_detection_btn.setToolTip("Enable/Disable Phrase Detection")
        self.phrase_detection_btn.setFixedSize(QSize(32, 32))
        self.phrase_detection_btn.setStyleSheet(button_style)
        self.phrase_detection_btn.setIcon(qta.icon("fa5s.eye", color="white"))
        self.phrase_detection_btn.setIconSize(QSize(16, 16))
        self.phrase_detection_btn.toggled.connect(self._on_phrase_detection_toggle)
        header_layout.addWidget(self.phrase_detection_btn)

        self.align_btn = QPushButton()
        self.align_btn.setToolTip("Align to Beat (Tap)")
        self.align_btn.setFixedSize(QSize(32, 32))
        self.align_btn.setStyleSheet(button_style)
        self.align_btn.setIcon(qta.icon("fa5s.crosshairs", color="white"))
        self.align_btn.setIconSize(QSize(16, 16))
        self.align_btn.clicked.connect(self._on_align_requested)
        header_layout.addWidget(self.align_btn)

        settings_btn = QPushButton()
        settings_btn.setToolTip("Configure Deck Regions")
        settings_btn.setFixedSize(QSize(32, 32))
        settings_btn.setStyleSheet(button_style)
        settings_btn.setIcon(qta.icon("fa5s.cog", color="white"))
        settings_btn.setIconSize(QSize(16, 16))
        settings_btn.clicked.connect(self._on_settings_requested)
        header_layout.addWidget(settings_btn)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setFixedWidth(2)
        header_layout.addWidget(separator)

        # Status info (compact, only needed space)
        status_layout = QVBoxLayout()
        status_layout.setSpacing(1)
        status_layout.setContentsMargins(4, 0, 0, 0)

        # Line 1: BPM + Phrase type + Duration
        self.status_line1 = QLabel("Not aligned")
        self.status_line1.setStyleSheet(
            "color: #888888; font-size: 11px; font-weight: bold;"
        )
        status_layout.addWidget(self.status_line1)

        # Line 2: Position (Phrase, Bar, Beat)
        self.status_line2 = QLabel("")
        self.status_line2.setStyleSheet("color: #666666; font-size: 10px;")
        status_layout.addWidget(self.status_line2)

        header_layout.addLayout(status_layout)
        header_layout.addStretch()  # Push everything to the left

        main_layout.addLayout(header_layout)

        # Progress bar (horizontal, below controls)
        self.phrase_progress_bar = QProgressBar()
        self.phrase_progress_bar.setOrientation(Qt.Orientation.Horizontal)
        self.phrase_progress_bar.setTextVisible(False)
        self.phrase_progress_bar.setFixedHeight(6)
        self.phrase_progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                background-color: #2a2a2a;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 2px;
            }
            """
        )
        main_layout.addWidget(self.phrase_progress_bar)

        # === PILOT PRESETS LIST ===
        presets_group = QGroupBox("Pilot Presets")
        presets_layout = QVBoxLayout(presets_group)
        presets_layout.setSpacing(4)

        # Preset selector
        preset_header = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_header.addWidget(self.preset_combo, 1)

        self.add_preset_btn = QToolButton()
        self.add_preset_btn.setText("+")
        self.add_preset_btn.setToolTip("Add New Pilot")
        self.add_preset_btn.setFixedSize(QSize(24, 24))
        self.add_preset_btn.clicked.connect(self._on_add_preset)
        preset_header.addWidget(self.add_preset_btn)

        self.edit_preset_btn = QToolButton()
        self.edit_preset_btn.setText("✎")
        self.edit_preset_btn.setToolTip("Edit Pilot Rules")
        self.edit_preset_btn.setFixedSize(QSize(24, 24))
        self.edit_preset_btn.clicked.connect(self._on_edit_preset)
        preset_header.addWidget(self.edit_preset_btn)

        self.delete_preset_btn = QToolButton()
        self.delete_preset_btn.setText("✕")
        self.delete_preset_btn.setToolTip("Delete Pilot")
        self.delete_preset_btn.setFixedSize(QSize(24, 24))
        self.delete_preset_btn.clicked.connect(self._on_delete_preset)
        preset_header.addWidget(self.delete_preset_btn)

        presets_layout.addLayout(preset_header)

        # Rules list with flash indicators
        self.rules_container = QVBoxLayout()
        self.rules_container.setSpacing(2)
        self.rule_widgets = {}  # rule_name -> QLabel widget
        presets_layout.addLayout(self.rules_container)

        main_layout.addWidget(presets_group, 1)  # Give presets stretch to fill space

    def _on_pilot_toggle(self, checked: bool) -> None:
        """Handle pilot enable/disable."""
        self.pilot_enable_requested.emit(checked)
        if checked:
            self.pilot_toggle_btn.setIcon(qta.icon("fa5s.pause", color="white"))
            # Auto-align after a short delay to allow MIDI clock to start
            from PySide6.QtCore import QTimer

            QTimer.singleShot(200, self.align_requested.emit)
        else:
            self.pilot_toggle_btn.setIcon(qta.icon("fa5s.play", color="white"))

    def _on_phrase_detection_toggle(self, checked: bool) -> None:
        """Handle phrase detection enable/disable."""
        self.phrase_detection_enabled = checked
        self.phrase_detection_enable_requested.emit(checked)

    def _on_align_requested(self) -> None:
        """Handle manual alignment request."""
        self.align_requested.emit()

    def _on_settings_requested(self) -> None:
        """Show deck configuration dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Configure Deck Regions")
        layout = QVBoxLayout(dialog)

        label = QLabel("Select which deck to configure:")
        layout.addWidget(label)

        for deck in ["A", "B", "C", "D"]:
            btn = QPushButton(f"Deck {deck}")
            btn.clicked.connect(lambda checked, d=deck: self._configure_deck(d, dialog))
            layout.addWidget(btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _configure_deck(self, deck_name: str, parent_dialog: QDialog) -> None:
        """Open region configuration for a specific deck."""
        config_dialog = RegionConfigDialog(deck_name, parent_dialog)
        config_dialog.regions_configured.connect(self._on_regions_configured)
        result = config_dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            if self.refresh_callback:
                self.refresh_callback()

    def _on_regions_configured(
        self, deck_name: str, button_rect: QRect, timeline_rect: QRect
    ) -> None:
        """Handle deck region configuration."""
        # Save to config
        config = get_config()
        config.set_deck_region(
            deck_name,
            "button",
            {
                "x": button_rect.x(),
                "y": button_rect.y(),
                "width": button_rect.width(),
                "height": button_rect.height(),
            },
        )
        config.set_deck_region(
            deck_name,
            "timeline",
            {
                "x": timeline_rect.x(),
                "y": timeline_rect.y(),
                "width": timeline_rect.width(),
                "height": timeline_rect.height(),
            },
        )

        # Emit signals for controller
        self.deck_region_configured.emit(
            deck_name,
            "button",
            CaptureRegion(
                button_rect.x(),
                button_rect.y(),
                button_rect.width(),
                button_rect.height(),
            ),
        )
        self.deck_region_configured.emit(
            deck_name,
            "timeline",
            CaptureRegion(
                timeline_rect.x(),
                timeline_rect.y(),
                timeline_rect.width(),
                timeline_rect.height(),
            ),
        )

        logger.info(f"Configured regions for deck {deck_name}")

    # Update methods
    def update_position(
        self, beat_in_bar: int, bar_in_phrase: int, bar_index: int, phrase_index: int
    ) -> None:
        """Update position display."""
        self.status_line2.setText(
            f"P{phrase_index + 1} • Bar {bar_in_phrase + 1}/8 • Beat {beat_in_bar + 1}/4"
        )

    def update_status(
        self,
        pilot_state: str,
        bpm: Optional[float] = None,
        aligned: bool = False,
        active_deck: Optional[str] = None,
        phrase_type: Optional[str] = None,
        phrase_duration: Optional[tuple[int, int]] = None,
    ) -> None:
        """Update status display."""
        parts = []

        if aligned:
            if bpm:
                parts.append(f"{bpm:.1f} BPM")

            if phrase_type:
                parts.append(f"{phrase_type.upper()}")

                if phrase_duration:
                    bars, phrases = phrase_duration
                    if phrases > 0:
                        parts.append(f"({phrases}×8+{bars % 8} bars)")
                    else:
                        parts.append(f"({bars} bars)")

            if active_deck and self.phrase_detection_enabled:
                parts.append(f"Deck {active_deck}")
        else:
            parts.append("Not aligned")

        self.status_line1.setText(" • ".join(parts) if parts else "Not aligned")

    def update_phrase_progress(self, progress: float) -> None:
        """Update phrase progress bar."""
        self.phrase_progress_bar.setValue(int(progress * 100))

    def set_not_aligned(self) -> None:
        """Reset display when not aligned."""
        self.status_line1.setText("Not aligned")
        self.status_line2.setText("")
        self.phrase_progress_bar.setValue(0)

    # Preset management methods
    def _load_presets(self) -> None:
        """Load presets from preset manager into combo box."""
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()

        for i, preset in enumerate(self.preset_manager.presets):
            status = "✓" if preset.enabled else "✗"
            self.preset_combo.addItem(f"{status} {preset.name}", i)

        # Select first enabled preset
        for i, preset in enumerate(self.preset_manager.presets):
            if preset.enabled:
                self.preset_combo.setCurrentIndex(i)
                break

        self.preset_combo.blockSignals(False)
        self._update_rules_preview()

    def _update_rules_preview(self) -> None:
        """Update the rules list with individual rule widgets."""
        # Clear existing rule widgets from layout
        while self.rules_container.count():
            item = self.rules_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.rule_widgets.clear()

        current_index = self.preset_combo.currentIndex()
        if 0 <= current_index < len(self.preset_manager.presets):
            preset = self.preset_manager.presets[current_index]
            if preset.rules:
                for rule in preset.rules:
                    # Create rule label
                    rule_label = QLabel()
                    rule_label.setWordWrap(True)
                    rule_label.setStyleSheet(
                        "color: #999999; font-size: 10px; padding: 2px 4px; "
                        "background: #2a2a2a; border-radius: 3px; margin: 1px;"
                    )
                    self._update_rule_label(rule_label, rule, False)

                    self.rules_container.addWidget(rule_label)
                    self.rule_widgets[rule.name] = rule_label
            else:
                # Show "no rules" message
                no_rules_label = QLabel("No rules defined")
                no_rules_label.setStyleSheet(
                    "color: #666666; font-size: 10px; padding: 4px;"
                )
                self.rules_container.addWidget(no_rules_label)
        else:
            # Show "no preset" message
            no_preset_label = QLabel("No preset selected")
            no_preset_label.setStyleSheet(
                "color: #666666; font-size: 10px; padding: 4px;"
            )
            self.rules_container.addWidget(no_preset_label)

    def _update_rule_label(self, label: QLabel, rule, is_firing: bool) -> None:
        """Update rule label text and style."""
        status = "✓" if rule.enabled else "✗"
        condition_str = f"{rule.condition.condition_type.value}"
        if rule.condition.phrase_type:
            condition_str += f" ({rule.condition.phrase_type})"
        if rule.condition.duration_bars:
            condition_str += f" {rule.condition.duration_bars}bars"

        label.setText(f"{status} {rule.name}: {condition_str}")

        # Flash effect when firing
        if is_firing:
            label.setStyleSheet(
                "color: #00ff00; font-size: 10px; padding: 2px 4px; "
                "background: #004400; border: 1px solid #00ff00; border-radius: 3px; margin: 1px;"
            )
        elif rule.enabled:
            label.setStyleSheet(
                "color: #cccccc; font-size: 10px; padding: 2px 4px; "
                "background: #2a2a2a; border-radius: 3px; margin: 1px;"
            )
        else:
            label.setStyleSheet(
                "color: #666666; font-size: 10px; padding: 2px 4px; "
                "background: #1a1a1a; border-radius: 3px; margin: 1px;"
            )

    def flash_rule(self, rule_name: str) -> None:
        """Flash a rule indicator when it fires."""
        # Only flash if we have a widget and the rule is enabled
        widget = self.rule_widgets.get(rule_name)
        if not widget:
            return

        current_index = self.preset_combo.currentIndex()
        if not (0 <= current_index < len(self.preset_manager.presets)):
            return

        preset = self.preset_manager.presets[current_index]
        # Find the matching rule object
        matched_rule = None
        for rule in preset.rules:
            if rule.name == rule_name:
                matched_rule = rule
                break

        if not matched_rule or not matched_rule.enabled:
            return

        # Flash on
        self._update_rule_label(widget, matched_rule, True)

        # Safe closure: capture widget and rule into defaults
        from PySide6.QtCore import QTimer

        def _flash_off(w=widget, r=matched_rule, rn=rule_name):
            if rn in self.rule_widgets:
                self._update_rule_label(w, r, False)

        QTimer.singleShot(200, _flash_off)

    def _on_preset_changed(self, index: int) -> None:
        """Handle preset selection change."""
        if 0 <= index < len(self.preset_manager.presets):
            # Enable this preset, disable others
            for i, preset in enumerate(self.preset_manager.presets):
                preset.enabled = i == index
            self.preset_manager.save()
            self._update_rules_preview()
            logger.info(f"Switched to preset: {self.preset_combo.currentText()}")

    def _on_add_preset(self) -> None:
        """Show dialog to create a new preset."""
        dialog = PresetEditorDialog(preset=None, parent=self)
        if dialog.exec():
            # Get the new preset from dialog
            new_preset = dialog.get_preset()
            if new_preset:
                self.preset_manager.add_preset(new_preset)
                self._load_presets()
                # Select the newly added preset (last one)
                self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)

    def _on_edit_preset(self) -> None:
        """Show dialog to edit the current preset."""
        current_index = self.preset_combo.currentIndex()
        if 0 <= current_index < len(self.preset_manager.presets):
            current_preset = self.preset_manager.presets[current_index]
            dialog = PresetEditorDialog(preset=current_preset, parent=self)
            if dialog.exec():
                # Update the preset
                updated_preset = dialog.get_preset()
                if updated_preset:
                    self.preset_manager.update_preset(current_index, updated_preset)
                    self._load_presets()
                    # Restore selection
                    self.preset_combo.setCurrentIndex(current_index)

    def _on_delete_preset(self) -> None:
        """Delete the current preset."""
        current_index = self.preset_combo.currentIndex()
        if 0 <= current_index < len(self.preset_manager.presets):
            preset = self.preset_manager.presets[current_index]
            # Confirm deletion
            from PySide6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "Delete Preset",
                f"Are you sure you want to delete '{preset.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.preset_manager.remove_preset(current_index)
                self._load_presets()
