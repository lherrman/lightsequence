"""
Playback Controls Widget

Compact control bar for sequence playback.
"""

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import Signal

from lumiblox.gui.ui_constants import (
    BUTTON_SIZE_LARGE,
    BUTTON_SIZE_MEDIUM,
    BUTTON_STYLE,
    BUTTON_STYLE_ACTIVE,
)


class PlaybackControls(QWidget):
    """Compact playback control bar."""

    play_pause_clicked = Signal()
    next_step_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.is_playing = False
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Play/Pause button with icon
        self.play_icon = qta.icon("fa5s.play", color="white")
        self.pause_icon = qta.icon("fa5s.pause", color="white")

        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(self.play_icon)
        self.play_pause_btn.setFixedSize(BUTTON_SIZE_LARGE)
        self.play_pause_btn.setStyleSheet(BUTTON_STYLE)
        self.play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        layout.addWidget(self.play_pause_btn)

        # Next Step button with icon
        next_icon = qta.icon("fa5s.step-forward", color="white")
        self.next_step_btn = QPushButton()
        self.next_step_btn.setIcon(next_icon)
        self.next_step_btn.setFixedSize(BUTTON_SIZE_LARGE)
        self.next_step_btn.setStyleSheet(BUTTON_STYLE)
        self.next_step_btn.clicked.connect(self.next_step_clicked.emit)
        layout.addWidget(self.next_step_btn)

        # Clear button with icon
        clear_icon = qta.icon("fa5s.stop", color="white")
        self.clear_btn = QPushButton()
        self.clear_btn.setIcon(clear_icon)
        self.clear_btn.setFixedSize(BUTTON_SIZE_LARGE)
        self.clear_btn.setStyleSheet(BUTTON_STYLE)
        self.clear_btn.clicked.connect(self.clear_clicked.emit)
        layout.addWidget(self.clear_btn)

        layout.addStretch()

    def _on_play_pause_clicked(self):
        """Handle play/pause button click."""
        self.is_playing = not self.is_playing
        self.update_play_pause_button()
        self.play_pause_clicked.emit()

    def update_play_pause_button(self):
        """Update play/pause button appearance."""
        if self.is_playing:
            self.play_pause_btn.setIcon(self.pause_icon)
            self.play_pause_btn.setFixedSize(BUTTON_SIZE_LARGE)
            self.play_pause_btn.setStyleSheet(BUTTON_STYLE_ACTIVE)
        else:
            self.play_pause_btn.setIcon(self.play_icon)
            self.play_pause_btn.setFixedSize(BUTTON_SIZE_LARGE)
            self.play_pause_btn.setStyleSheet(BUTTON_STYLE)

    def set_playing(self, playing: bool):
        """Set the playing state externally."""
        if self.is_playing != playing:
            self.is_playing = playing
            self.update_play_pause_button()
