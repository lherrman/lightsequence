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
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
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
    deck_region_configured = Signal(str, str, CaptureRegion)  # deck, region_type, region

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setup_ui()
        self.pilot_enabled = False
        self.phrase_detection_enabled = False

    def setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # === Title ===
        title = QLabel("🎯 PILOT")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #00aaff; padding: 5px;"
        )
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # === Progress Bar (Phrase Position) ===
        progress_group = QGroupBox("Phrase Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.phrase_progress_bar = QProgressBar()
        self.phrase_progress_bar.setRange(0, 100)
        self.phrase_progress_bar.setValue(0)
        self.phrase_progress_bar.setTextVisible(True)
        self.phrase_progress_bar.setFormat("%p%")
        self.phrase_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #555555;
                border-radius: 5px;
                text-align: center;
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #00aaff;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.phrase_progress_bar)

        # Position info label
        self.position_label = QLabel("Not Aligned")
        self.position_label.setStyleSheet("color: #888888; padding: 2px;")
        self.position_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.position_label)

        layout.addWidget(progress_group)

        # === Phrase Type Display ===
        phrase_group = QGroupBox("Current Phrase")
        phrase_layout = QVBoxLayout(phrase_group)
        self.phrase_type_label = QLabel("—")
        self.phrase_type_label.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #ffffff; "
            "padding: 10px; background-color: #3d3d3d; border-radius: 5px;"
        )
        self.phrase_type_label.setAlignment(Qt.AlignCenter)
        phrase_layout.addWidget(self.phrase_type_label)

        # Next phrase indicator
        self.next_phrase_label = QLabel("Next: —")
        self.next_phrase_label.setStyleSheet("color: #888888; font-size: 11px; padding: 2px;")
        self.next_phrase_label.setAlignment(Qt.AlignCenter)
        phrase_layout.addWidget(self.next_phrase_label)

        layout.addWidget(phrase_group)

        # === Control Buttons ===
        control_group = QGroupBox("Control")
        control_layout = QVBoxLayout(control_group)

        # Enable pilot in config checkbox
        self.enable_pilot_checkbox = QCheckBox("Enable Pilot in Config")
        self.enable_pilot_checkbox.setToolTip("Enable/disable pilot system in configuration (requires restart)")
        self.enable_pilot_checkbox.clicked.connect(self._on_enable_pilot_checkbox_changed)
        control_layout.addWidget(self.enable_pilot_checkbox)
        
        # Load initial state from config
        try:
            config = get_config()
            pilot_config = config.data.get("pilot", {})
            self.enable_pilot_checkbox.setChecked(pilot_config.get("enabled", False))
        except Exception as e:
            logger.warning(f"Failed to load pilot config state: {e}")

        # Pilot on/off button
        self.pilot_toggle_btn = QPushButton("Start Pilot")
        self.pilot_toggle_btn.setCheckable(True)
        self.pilot_toggle_btn.setStyleSheet(self._get_toggle_button_style())
        self.pilot_toggle_btn.clicked.connect(self._on_pilot_toggle)
        control_layout.addWidget(self.pilot_toggle_btn)

        # Align button
        self.align_btn = QPushButton("⏱ Align to Beat")
        self.align_btn.setEnabled(False)
        self.align_btn.clicked.connect(self._on_align_requested)
        control_layout.addWidget(self.align_btn)

        # Phrase detection toggle
        self.phrase_detection_btn = QPushButton("Enable Phrase Detection")
        self.phrase_detection_btn.setCheckable(True)
        self.phrase_detection_btn.setEnabled(False)
        self.phrase_detection_btn.setStyleSheet(self._get_toggle_button_style())
        self.phrase_detection_btn.clicked.connect(self._on_phrase_detection_toggle)
        control_layout.addWidget(self.phrase_detection_btn)

        layout.addWidget(control_group)

        # === Screen Capture Configuration ===
        capture_group = QGroupBox("Screen Capture Setup")
        capture_layout = QVBoxLayout(capture_group)

        # Deck selector
        deck_layout = QHBoxLayout()
        deck_layout.addWidget(QLabel("Deck:"))
        self.deck_selector = QComboBox()
        self.deck_selector.addItems(["A", "B", "C", "D"])
        deck_layout.addWidget(self.deck_selector)
        capture_layout.addLayout(deck_layout)

        # Region buttons
        self.set_button_btn = QPushButton("Set Master Button Region")
        self.set_button_btn.clicked.connect(lambda: self._select_region("button"))
        capture_layout.addWidget(self.set_button_btn)

        self.set_timeline_btn = QPushButton("Set Timeline Region")
        self.set_timeline_btn.clicked.connect(lambda: self._select_region("timeline"))
        capture_layout.addWidget(self.set_timeline_btn)

        layout.addWidget(capture_group)

        # === Status ===
        self.status_label = QLabel("Pilot: Stopped | BPM: —")
        self.status_label.setStyleSheet(
            "color: #888888; font-size: 10px; padding: 5px; "
            "background-color: #2d2d2d; border-radius: 3px;"
        )
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _get_toggle_button_style(self) -> str:
        """Get stylesheet for toggle buttons."""
        return """
            QPushButton {
                padding: 8px;
                font-weight: bold;
                border-radius: 5px;
                background-color: #3d3d3d;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:checked {
                background-color: #00aa00;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """

    # Control Handlers ------------------------------------------------------
    def _on_enable_pilot_checkbox_changed(self, checked: bool) -> None:
        """Handle enable pilot checkbox change - updates config."""
        try:
            config = get_config()
            config.set_pilot_enabled(checked)
            logger.info(f"Pilot {'enabled' if checked else 'disabled'} in configuration")
        except Exception as e:
            logger.error(f"Failed to update pilot config: {e}")
            # Revert checkbox state on error
            self.enable_pilot_checkbox.setChecked(not checked)
    
    def _on_pilot_toggle(self, checked: bool) -> None:
        """Handle pilot enable/disable."""
        self.pilot_enabled = checked
        if checked:
            self.pilot_toggle_btn.setText("Stop Pilot")
            self.align_btn.setEnabled(True)
            self.phrase_detection_btn.setEnabled(True)
        else:
            self.pilot_toggle_btn.setText("Start Pilot")
            self.align_btn.setEnabled(False)
            self.phrase_detection_btn.setEnabled(False)
            self.phrase_detection_btn.setChecked(False)
            self.phrase_detection_enabled = False

        self.pilot_enable_requested.emit(checked)

    def _on_phrase_detection_toggle(self, checked: bool) -> None:
        """Handle phrase detection enable/disable."""
        self.phrase_detection_enabled = checked
        if checked:
            self.phrase_detection_btn.setText("Disable Phrase Detection")
        else:
            self.phrase_detection_btn.setText("Enable Phrase Detection")

        self.phrase_detection_enable_requested.emit(checked)

    def _on_align_requested(self) -> None:
        """Handle align button click."""
        self.align_requested.emit()

    def _select_region(self, region_type: str) -> None:
        """
        Open region selector overlay.

        Args:
            region_type: "button" or "timeline"
        """
        deck_name = self.deck_selector.currentText()
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

    # Update Methods --------------------------------------------------------
    def update_phrase_progress(self, progress: float) -> None:
        """
        Update the phrase progress bar.

        Args:
            progress: Progress through phrase (0.0 to 1.0)
        """
        self.phrase_progress_bar.setValue(int(progress * 100))

    def update_position(self, beat_in_bar: int, bar_in_phrase: int, bar_index: int, phrase_index: int) -> None:
        """
        Update the position display.

        Args:
            beat_in_bar: Beat within bar (0-3)
            bar_in_phrase: Bar within phrase (0-7)
            bar_index: Absolute bar index
            phrase_index: Absolute phrase index
        """
        self.position_label.setText(
            f"Phrase {phrase_index + 1} | Bar {bar_in_phrase + 1}/8 | Beat {beat_in_bar + 1}/4"
        )

    def update_phrase_type(self, current_type: Optional[str], next_type: Optional[str] = None) -> None:
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
            self.next_phrase_label.setStyleSheet("color: #ffaa00; font-size: 11px; padding: 2px;")
        else:
            self.next_phrase_label.setText("Next: —")
            self.next_phrase_label.setStyleSheet("color: #888888; font-size: 11px; padding: 2px;")

    def update_status(self, pilot_state: str, bpm: Optional[float] = None, aligned: bool = False) -> None:
        """
        Update the status label.

        Args:
            pilot_state: Pilot state string
            bpm: Current BPM
            aligned: Whether sync is aligned
        """
        status_parts = [f"Pilot: {pilot_state}"]

        if bpm:
            status_parts.append(f"BPM: {bpm:.1f}")
        else:
            status_parts.append("BPM: —")

        if aligned:
            status_parts.append("✓ Aligned")
        elif pilot_state != "Stopped":
            status_parts.append("⚠ Not Aligned")

        self.status_label.setText(" | ".join(status_parts))

    def set_not_aligned(self) -> None:
        """Reset display when not aligned."""
        self.position_label.setText("Not Aligned")
        self.phrase_progress_bar.setValue(0)
