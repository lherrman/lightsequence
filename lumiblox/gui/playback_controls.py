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

from lumiblox.gui.ui_constants import BUTTON_SIZE_MEDIUM


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
        self.play_pause_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border-radius: 3px;
                border: 1px solid #666666;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        self.play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        layout.addWidget(self.play_pause_btn)

        # Next Step button with icon
        next_icon = qta.icon("fa5s.step-forward", color="white")
        self.next_step_btn = QPushButton()
        self.next_step_btn.setIcon(next_icon)
        self.next_step_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        self.next_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border-radius: 3px;
                border: 1px solid #666666;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        self.next_step_btn.clicked.connect(self.next_step_clicked.emit)
        layout.addWidget(self.next_step_btn)

        # Clear button with icon
        clear_icon = qta.icon("fa5s.stop", color="white")
        self.clear_btn = QPushButton()
        self.clear_btn.setIcon(clear_icon)
        self.clear_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border-radius: 3px;
                border: 1px solid #666666;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
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
            self.play_pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a9eff;
                    border-radius: 3px;
                    border: 1px solid #5fadff;
                }
                QPushButton:hover {
                    background-color: #5fadff;
                }
                QPushButton:pressed {
                    background-color: #3a8eef;
                }
            """)
        else:
            self.play_pause_btn.setIcon(self.play_icon)
            self.play_pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    border-radius: 3px;
                    border: 1px solid #666666;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
                QPushButton:pressed {
                    background-color: #444444;
                }
            """)

    def set_playing(self, playing: bool):
        """Set the playing state externally."""
        if self.is_playing != playing:
            self.is_playing = playing
            self.update_play_pause_button()
