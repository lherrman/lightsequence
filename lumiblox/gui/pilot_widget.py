"""
Pilot Widget

GUI component for displaying and controlling the pilot system
(MIDI clock sync and phrase detection).
"""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, QEventLoop, QPoint, QRect, QSize
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
    QRubberBand,
    QCheckBox,
)

from lumiblox.pilot.phrase_detector import CaptureRegion
from lumiblox.common.config import get_config

logger = logging.getLogger(__name__)


class RegionSelectorOverlay(QWidget):
    """Full-screen overlay for selecting screen capture regions."""

    region_selected = Signal(QRect)
    selection_cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(
            None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)

        # Cover all screens
        geometry = QRect()
        for screen in QGuiApplication.screens():
            geometry = geometry.united(screen.geometry())
        self.setGeometry(geometry)

        self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()
        self._current = QPoint()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._origin = event.globalPosition().toPoint()
        self._current = self._origin
        self._rubber_band.setGeometry(QRect(self._origin, QSize(0, 0)))
        self._rubber_band.show()

    def mouseMoveEvent(self, event) -> None:
        if not self._rubber_band.isVisible():
            return
        self._current = event.globalPosition().toPoint()
        rect = QRect(self._origin, self._current).normalized()
        self._rubber_band.setGeometry(rect)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or not self._rubber_band.isVisible():
            return
        self._rubber_band.hide()
        rect = QRect(self._origin, event.globalPosition().toPoint()).normalized()
        if rect.width() < 5 or rect.height() < 5:
            self.selection_cancelled.emit()
        else:
            self.region_selected.emit(rect)
        self.close()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._rubber_band.hide()
            self.selection_cancelled.emit()
            self.close()


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
        self.phrase_type_label.setAlignment(Qt.AlignCenter)
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

        # Status info (compact)
        self.status_label = QLabel("Not aligned • —")
        self.status_label.setStyleSheet(
            "color: #666666; font-size: 11px; padding: 4px;"
        )
        self.status_label.setAlignment(Qt.AlignCenter)
        controls_layout.addWidget(self.status_label)

        # Position label (compact)
        self.position_label = QLabel("")
        self.position_label.setStyleSheet(
            "color: #888888; font-size: 10px; padding: 2px;"
        )
        self.position_label.setAlignment(Qt.AlignCenter)
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

        # Deck selector
        deck_row = QHBoxLayout()
        deck_row.addWidget(QLabel("Deck:"))
        deck_selector = QComboBox()
        deck_selector.addItems(["A", "B", "C", "D"])
        deck_row.addWidget(deck_selector, 1)
        capture_layout.addLayout(deck_row)

        # Region buttons
        button_btn = QPushButton("Set Master Button Region")
        button_btn.clicked.connect(
            lambda: self._select_region_for_deck("button", deck_selector.currentText())
        )
        capture_layout.addWidget(button_btn)

        timeline_btn = QPushButton("Set Timeline Region")
        timeline_btn.clicked.connect(
            lambda: self._select_region_for_deck(
                "timeline", deck_selector.currentText()
            )
        )
        capture_layout.addWidget(timeline_btn)

        layout.addWidget(capture_group)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
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
        dialog.exec()

    def _select_region_for_deck(self, region_type: str, deck_name: str) -> None:
        """Select region for a specific deck."""
        overlay = RegionSelectorOverlay()
        loop = QEventLoop()
        result: dict[str, Optional[QRect]] = {"rect": None}

        def on_selected(rect: QRect) -> None:
            result["rect"] = rect
            loop.quit()

        def on_cancelled() -> None:
            loop.quit()

        overlay.region_selected.connect(on_selected)
        overlay.selection_cancelled.connect(on_cancelled)
        overlay.show()
        loop.exec()
        overlay.deleteLater()

        if result["rect"]:
            rect = result["rect"]
            capture_region = CaptureRegion(
                x=rect.x(),
                y=rect.y(),
                width=rect.width(),
                height=rect.height(),
            )
            self.deck_region_configured.emit(deck_name, region_type, capture_region)
            logger.info(
                f"Configured deck {deck_name} {region_type}: "
                f"x={rect.x()}, y={rect.y()}, w={rect.width()}, h={rect.height()}"
            )

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
        self.position_label.setText(
            f"P{phrase_index + 1} • {bar_in_phrase + 1}/8 • {beat_in_bar + 1}/4"
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
        self, pilot_state: str, bpm: Optional[float] = None, aligned: bool = False
    ) -> None:
        """
        Update the status label.

        Args:
            pilot_state: Pilot state string
            bpm: Current BPM
            aligned: Whether sync is aligned
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

        self.status_label.setText(" • ".join(status_parts))

    def set_not_aligned(self) -> None:
        """Reset display when not aligned."""
        self.position_label.setText("Not Aligned")
        self.phrase_progress_bar.setValue(0)
