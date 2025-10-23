"""
Pilot Widget

GUI component for displaying and controlling the pilot system
(MIDI clock sync and phrase detection).
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, QRect
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
    QCheckBox,
    QDialog,
    QDialogButtonBox,
)

from lumiblox.pilot.phrase_detector import CaptureRegion
from lumiblox.common.config import get_config

logger = logging.getLogger(__name__)


class FixedSizeRegionSelector(QWidget):
    """Transparent overlay window with fixed size for positioning capture regions."""

    region_confirmed = Signal(QRect)
    selection_cancelled = Signal()

    # Region size constants (must match capture requirements)
    MASTER_BUTTON_WIDTH = 64
    MASTER_BUTTON_HEIGHT = 22
    TIMELINE_WIDTH = 220
    TIMELINE_HEIGHT = 88

    def __init__(self, region_type: str, parent=None) -> None:
        """
        Create a fixed-size transparent overlay window.

        Args:
            region_type: Either "button" or "timeline"
        """
        # Create as a standalone window with no parent, stays on top
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        # Don't use WA_TranslucentBackground - it blocks mouse events
        # Instead use a semi-transparent background color via stylesheet
        self.setWindowOpacity(0.7)  # Make whole window semi-transparent

        self.region_type = region_type

        # Set fixed size based on region type
        if region_type == "button":
            width = self.MASTER_BUTTON_WIDTH
            height = self.MASTER_BUTTON_HEIGHT
            title = "Master Button Region"
        else:  # timeline
            width = self.TIMELINE_WIDTH
            height = self.TIMELINE_HEIGHT
            title = "Timeline Region"

        self.setFixedSize(width, height)

        # Position at center of primary screen initially
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(screen.center().x() - width // 2, screen.center().y() - height // 2)

        # Store title for display
        self._title = title

        # Set background color
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 170, 255, 150);
                border: 3px solid #00aaff;
            }
        """)

        # Make window draggable
        self._drag_position = None

    def paintEvent(self, event) -> None:
        """Draw title bar at top."""
        painter = QPainter(self)

        # Draw title bar at top
        title_height = 20
        painter.fillRect(0, 0, self.width(), title_height, QColor(0, 120, 200))

        # Draw title text
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.width(), title_height), Qt.AlignmentFlag.AlignCenter, self._title
        )

        painter.end()

    def mousePressEvent(self, event) -> None:
        """Start dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:
        """Handle dragging."""
        if event.buttons() == Qt.LeftButton and self._drag_position is not None:
            self.move(event.globalPosition().toPoint() - self._drag_position)

    def mouseReleaseEvent(self, event) -> None:
        """Stop dragging."""
        self._drag_position = None

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Escape:
            self.selection_cancelled.emit()
            self.close()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.confirm_region()

    def confirm_region(self) -> None:
        """Confirm the current position and emit the region."""
        geometry = self.frameGeometry()
        self.region_confirmed.emit(geometry)
        self.close()


class RegionConfigDialog(QDialog):
    """Dialog for configuring both capture regions for a deck."""

    regions_configured = Signal(
        str, QRect, QRect
    )  # deck_name, button_rect, timeline_rect

    def __init__(self, deck_name: str, parent=None):
        super().__init__(parent)
        self.deck_name = deck_name
        self.button_rect = None
        self.timeline_rect = None

        self.setWindowTitle(f"Configure Deck {deck_name} Capture Regions")
        self.setModal(False)  # Non-modal so overlays can be dragged

        # Ensure the dialog doesn't block input to other windows
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)

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
        # Connect directly to button clicked signals for modeless dialog
        self.ok_button.clicked.connect(self.accept)
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(button_box)

        self.button_box = button_box

    def _show_overlays(self) -> None:
        """Show both overlay windows for positioning."""
        # Create button region overlay
        self.button_overlay = FixedSizeRegionSelector("button")
        self.button_overlay.region_confirmed.connect(self._on_button_confirmed)
        self.button_overlay.selection_cancelled.connect(self._on_cancelled)

        # Create timeline region overlay
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

        # Show both and ensure they're raised above everything
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
        logger.info(
            f"Button region confirmed: {rect.x()}, {rect.y()}, {rect.width()}x{rect.height()}"
        )
        self._check_completion()

    def _on_timeline_confirmed(self, rect: QRect) -> None:
        """Handle timeline region confirmation."""
        self.timeline_rect = rect
        self.timeline_status.setText(f"Timeline: Set at ({rect.x()}, {rect.y()})")
        logger.info(
            f"Timeline region confirmed: {rect.x()}, {rect.y()}, {rect.width()}x{rect.height()}"
        )
        self._check_completion()

    def _check_completion(self) -> None:
        """Check if both regions are set and enable save button."""
        logger.info(
            f"Checking completion: button={self.button_rect is not None}, timeline={self.timeline_rect is not None}"
        )
        if self.button_rect and self.timeline_rect:
            logger.info("Both regions set, enabling Save & Close button")
            self.ok_button.setEnabled(True)
            self.ok_button.update()  # Force visual update
            # Bring dialog to front so user can click the button
            self.raise_()
            self.activateWindow()

    def _on_cancelled(self) -> None:
        """Handle cancellation of region selection."""
        # Close any open overlays
        if hasattr(self, "button_overlay"):
            self.button_overlay.close()
        if hasattr(self, "timeline_overlay"):
            self.timeline_overlay.close()

    def reject(self) -> None:
        """Override reject to clean up overlays."""
        # Close any open overlays
        if hasattr(self, "button_overlay") and self.button_overlay:
            self.button_overlay.close()
        if hasattr(self, "timeline_overlay") and self.timeline_overlay:
            self.timeline_overlay.close()
        super().reject()

    def accept(self) -> None:
        """Override accept to clean up overlays."""
        # Close any open overlays
        if hasattr(self, "button_overlay") and self.button_overlay:
            self.button_overlay.close()
        if hasattr(self, "timeline_overlay") and self.timeline_overlay:
            self.timeline_overlay.close()
        super().accept()


class PilotWidget(QWidget):
    """Widget for controlling and monitoring the pilot system."""

    # Signals for requesting actions from the controller
    pilot_enable_requested = Signal(bool)
    phrase_detection_enable_requested = Signal(bool)
    align_requested = Signal()
    deck_region_configured = Signal(
        str, str, CaptureRegion
    )  # deck, region_type, region

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        self.pilot_enabled = False
        self.phrase_detection_enabled = False

    def setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # === Progress Bar (Top, no label) ===
        self.phrase_progress_bar = QProgressBar()
        self.phrase_progress_bar.setRange(0, 100)
        self.phrase_progress_bar.setValue(0)
        self.phrase_progress_bar.setTextVisible(False)
        self.phrase_progress_bar.setFixedHeight(6)
        self.phrase_progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background-color: #1a1a1a;
            }
            QProgressBar::chunk {
                background-color: #00aaff;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.phrase_progress_bar)

        # === Main Content Area ===
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Left side: Phrase type display
        self.phrase_type_label = QLabel("—")
        self.phrase_type_label.setStyleSheet(
            "font-size: 32px; font-weight: 600; color: #ffffff; "
            "padding: 20px; background-color: #1a1a1a; border-radius: 8px;"
        )
        self.phrase_type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phrase_type_label.setMinimumWidth(180)
        content_layout.addWidget(self.phrase_type_label, 1)

        # Right side: Controls
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(6)

        # Control buttons row
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(6)

        # Pilot toggle button
        self.pilot_toggle_btn = QPushButton("Pilot")
        self.pilot_toggle_btn.setCheckable(True)
        self.pilot_toggle_btn.setFixedHeight(40)
        self.pilot_toggle_btn.setStyleSheet(self._get_modern_toggle_style())
        self.pilot_toggle_btn.clicked.connect(self._on_pilot_toggle)
        buttons_row.addWidget(self.pilot_toggle_btn)

        # Phrase detection toggle
        self.phrase_detection_btn = QPushButton("Detect")
        self.phrase_detection_btn.setCheckable(True)
        self.phrase_detection_btn.setEnabled(False)
        self.phrase_detection_btn.setFixedHeight(40)
        self.phrase_detection_btn.setStyleSheet(self._get_modern_toggle_style())
        self.phrase_detection_btn.clicked.connect(self._on_phrase_detection_toggle)
        buttons_row.addWidget(self.phrase_detection_btn)

        # Settings button
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(40, 40)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                color: #888888;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """)
        self.settings_btn.setToolTip("Open pilot settings")
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        buttons_row.addWidget(self.settings_btn)

        controls_layout.addLayout(buttons_row)

        # Align button (full width, below main buttons)
        self.align_btn = QPushButton("⏱ Align to Beat")
        self.align_btn.setFixedHeight(32)
        self.align_btn.setEnabled(False)
        self.align_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                font-weight: 500;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                background-color: #2d2d2d;
                color: #888888;
            }
            QPushButton:hover:enabled {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            QPushButton:pressed:enabled {
                background-color: #1a1a1a;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #444444;
            }
        """)
        self.align_btn.setToolTip("Tap this button on the downbeat to sync with music")
        self.align_btn.clicked.connect(self._on_align_requested)
        controls_layout.addWidget(self.align_btn)

        # Status info (compact) - shows BPM and active deck
        self.status_label = QLabel("Not aligned")
        self.status_label.setStyleSheet(
            "color: #666666; font-size: 11px; padding: 2px;"
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.status_label)

        # Position and detection in one line (compact)
        self.position_label = QLabel("")
        self.position_label.setStyleSheet(
            "color: #888888; font-size: 10px; padding: 2px;"
        )
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.addWidget(self.position_label)

        controls_layout.addStretch()

        content_layout.addLayout(controls_layout, 1)

        layout.addLayout(content_layout)

        # Hidden elements (no longer visible but keep for compatibility)
        self.next_phrase_label = QLabel("")  # Keep for update methods
        self.deck_selector = QComboBox()  # For settings dialog
        self.deck_selector.addItems(["A", "B", "C", "D"])

    def _get_modern_toggle_style(self) -> str:
        """Get modern stylesheet for toggle buttons."""
        return """
            QPushButton {
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
                border: none;
                border-radius: 8px;
                background-color: #2d2d2d;
                color: #888888;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #00aaff;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #444444;
            }
            QPushButton:pressed {
                background-color: #0088cc;
            }
        """

    # Settings Dialog -------------------------------------------------------
    def _on_settings_clicked(self) -> None:
        """Open settings dialog for pilot configuration."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Pilot Settings")
        dialog.setMinimumWidth(400)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)

        # Enable in config checkbox
        enable_checkbox = QCheckBox("Enable Pilot in Config")
        enable_checkbox.setToolTip(
            "Enable/disable pilot system (will take effect on restart)"
        )
        try:
            config = get_config()
            pilot_config = config.data.get("pilot", {})
            enable_checkbox.setChecked(pilot_config.get("enabled", False))
        except Exception:
            pass
        layout.addWidget(enable_checkbox)

        # Align button
        align_group = QGroupBox("Alignment")
        align_layout = QVBoxLayout(align_group)
        align_btn = QPushButton("⏱ Align to Beat (Tap on downbeat)")
        align_btn.clicked.connect(self._on_align_requested)
        align_layout.addWidget(align_btn)
        layout.addWidget(align_group)

        # Screen capture configuration
        capture_group = QGroupBox("Screen Capture Regions")
        capture_layout = QVBoxLayout(capture_group)

        # Instructions
        info_label = QLabel(
            "Configure capture regions for each deck.\n"
            "Click 'Configure Deck' to position transparent overlays on your screen."
        )
        info_label.setWordWrap(True)
        capture_layout.addWidget(info_label)

        # Container for region status (will be updated dynamically)
        regions_status_container = QWidget()
        regions_status_layout = QVBoxLayout(regions_status_container)
        regions_status_layout.setContentsMargins(0, 0, 0, 0)
        regions_status_layout.setSpacing(4)
        capture_layout.addWidget(regions_status_container)

        # Function to update region display
        def update_regions_display():
            # Clear existing labels
            while regions_status_layout.count():
                item = regions_status_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Add current regions
            try:
                config = get_config()
                pilot_config = config.data.get("pilot", {})
                decks = pilot_config.get("decks", {})

                for deck_name in ["A", "B", "C", "D"]:
                    deck_config = decks.get(deck_name, {})
                    button_region = deck_config.get("master_button_region")
                    timeline_region = deck_config.get("timeline_region")

                    if button_region or timeline_region:
                        deck_info = QLabel()
                        deck_info.setStyleSheet(
                            "color: #00aa00; font-size: 11px; padding: 4px;"
                        )

                        status_parts = [f"<b>Deck {deck_name}:</b>"]
                        if button_region:
                            status_parts.append(
                                f"Button ({button_region['x']}, {button_region['y']})"
                            )
                        if timeline_region:
                            status_parts.append(
                                f"Timeline ({timeline_region['x']}, {timeline_region['y']})"
                            )

                        deck_info.setText(" • ".join(status_parts))
                        regions_status_layout.addWidget(deck_info)
            except Exception as e:
                logger.error(f"Failed to load deck regions: {e}")

        # Initial display
        update_regions_display()

        # Deck selector and configure button
        deck_row = QHBoxLayout()
        deck_row.addWidget(QLabel("Deck:"))
        deck_selector = QComboBox()
        deck_selector.addItems(["A", "B", "C", "D"])
        deck_row.addWidget(deck_selector, 1)

        configure_deck_btn = QPushButton("Configure Deck Regions")
        configure_deck_btn.clicked.connect(
            lambda: self._configure_deck_regions(
                deck_selector.currentText(), update_regions_display
            )
        )
        deck_row.addWidget(configure_deck_btn)

        capture_layout.addLayout(deck_row)
        layout.addWidget(capture_group)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        # Save config on close
        def on_accept():
            try:
                config = get_config()
                config.set_pilot_enabled(enable_checkbox.isChecked())
            except Exception as e:
                logger.error(f"Failed to save pilot config: {e}")

        button_box.accepted.connect(on_accept)
        dialog.show()  # Use show() instead of exec() to avoid blocking

    def _configure_deck_regions(self, deck_name: str, on_regions_updated=None) -> None:
        """Open dialog to configure both regions for a deck.

        Args:
            deck_name: Name of the deck (A, B, C, D)
            on_regions_updated: Optional callback to call after regions are saved
        """
        config_dialog = RegionConfigDialog(deck_name, self)

        def on_accepted():
            if config_dialog.button_rect and config_dialog.timeline_rect:
                # Convert button region
                button_region = CaptureRegion(
                    x=config_dialog.button_rect.x(),
                    y=config_dialog.button_rect.y(),
                    width=config_dialog.button_rect.width(),
                    height=config_dialog.button_rect.height(),
                )
                self.deck_region_configured.emit(deck_name, "button", button_region)

                # Convert timeline region
                timeline_region = CaptureRegion(
                    x=config_dialog.timeline_rect.x(),
                    y=config_dialog.timeline_rect.y(),
                    width=config_dialog.timeline_rect.width(),
                    height=config_dialog.timeline_rect.height(),
                )
                self.deck_region_configured.emit(deck_name, "timeline", timeline_region)

                logger.info(f"Configured deck {deck_name} regions:")
                logger.info(f"  Button: x={button_region.x}, y={button_region.y}")
                logger.info(f"  Timeline: x={timeline_region.x}, y={timeline_region.y}")

                # Save to config
                try:
                    config = get_config()
                    config.set_deck_region(
                        deck_name,
                        "master_button_region",
                        {
                            "x": button_region.x,
                            "y": button_region.y,
                            "width": button_region.width,
                            "height": button_region.height,
                        },
                    )
                    config.set_deck_region(
                        deck_name,
                        "timeline_region",
                        {
                            "x": timeline_region.x,
                            "y": timeline_region.y,
                            "width": timeline_region.width,
                            "height": timeline_region.height,
                        },
                    )
                    logger.info(f"Saved deck {deck_name} regions to config")

                    # Call the update callback if provided
                    if on_regions_updated:
                        on_regions_updated()
                except Exception as e:
                    logger.error(f"Failed to save deck regions to config: {e}")

        config_dialog.accepted.connect(on_accepted)
        config_dialog.show()  # Use show() instead of exec() to avoid blocking input

    # Control Handlers ------------------------------------------------------
    def _on_pilot_toggle(self, checked: bool) -> None:
        """Handle pilot enable/disable."""
        self.pilot_enabled = checked
        if checked:
            self.phrase_detection_btn.setEnabled(True)
            self.align_btn.setEnabled(True)
        else:
            self.phrase_detection_btn.setEnabled(False)
            self.phrase_detection_btn.setChecked(False)
            self.phrase_detection_enabled = False
            self.align_btn.setEnabled(False)

        self.pilot_enable_requested.emit(checked)

    def _on_phrase_detection_toggle(self, checked: bool) -> None:
        """Handle phrase detection enable/disable."""
        self.phrase_detection_enabled = checked
        self.phrase_detection_enable_requested.emit(checked)

    def _on_align_requested(self) -> None:
        """Handle align button click."""
        self.align_requested.emit()

    # Update Methods --------------------------------------------------------
    def update_phrase_progress(self, progress: float) -> None:
        """
        Update the phrase progress bar.

        Args:
            progress: Progress through phrase (0.0 to 1.0)
        """
        self.phrase_progress_bar.setValue(int(progress * 100))

    def update_position(
        self, beat_in_bar: int, bar_in_phrase: int, bar_index: int, phrase_index: int
    ) -> None:
        """
        Update the position display.

        Args:
            beat_in_bar: Beat within bar (0-3)
            bar_in_phrase: Bar within phrase (0-7)
            bar_index: Absolute bar index
            phrase_index: Absolute phrase index
        """
        # Compact display: position only
        self.position_label.setText(
            f"P{phrase_index + 1} • Bar {bar_in_phrase + 1}/8 • Beat {beat_in_bar + 1}/4"
        )

    def update_phrase_type(
        self, current_type: Optional[str], next_type: Optional[str] = None
    ) -> None:
        """
        Update the phrase type display.

        Args:
            current_type: Current phrase type ("body" or "breakdown")
            next_type: Detected next phrase type
        """
        if current_type:
            display_text = current_type.upper()
            if current_type == "body":
                bg_color = "#0066aa"
            else:  # breakdown
                bg_color = "#aa6600"

            self.phrase_type_label.setText(display_text)
            self.phrase_type_label.setStyleSheet(
                f"font-size: 24px; font-weight: bold; color: #ffffff; "
                f"padding: 10px; background-color: {bg_color}; border-radius: 5px;"
            )
        else:
            self.phrase_type_label.setText("—")
            self.phrase_type_label.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #ffffff; "
                "padding: 10px; background-color: #3d3d3d; border-radius: 5px;"
            )

        if next_type and next_type != current_type:
            self.next_phrase_label.setText(f"Next: {next_type.upper()}")
            self.next_phrase_label.setStyleSheet(
                "color: #ffaa00; font-size: 11px; padding: 2px;"
            )
        else:
            self.next_phrase_label.setText("Next: —")
            self.next_phrase_label.setStyleSheet(
                "color: #888888; font-size: 11px; padding: 2px;"
            )

    def update_status(
        self,
        pilot_state: str,
        bpm: Optional[float] = None,
        aligned: bool = False,
        active_deck: Optional[str] = None,
    ) -> None:
        """
        Update the status label.

        Args:
            pilot_state: Pilot state string
            bpm: Current BPM
            aligned: Whether sync is aligned
            active_deck: Currently active deck (A, B, C, D) or None
        """
        status_parts = []

        if aligned:
            status_parts.append("Aligned")
        else:
            status_parts.append("Not aligned")

        if bpm:
            status_parts.append(f"{bpm:.1f} BPM")
        else:
            status_parts.append("—")

        # Add active deck if detection is running
        if active_deck and self.phrase_detection_enabled:
            status_parts.append(f"Deck {active_deck}")

        self.status_label.setText(" • ".join(status_parts))

    def set_not_aligned(self) -> None:
        """Reset display when not aligned."""
        self.position_label.setText("Not Aligned")
        self.phrase_progress_bar.setValue(0)
