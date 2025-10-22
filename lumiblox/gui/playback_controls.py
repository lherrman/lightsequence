"""
Playback Controls Widget

Compact control bar for sequence playback.
"""

import typing as t
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Signal


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
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(8)
        
        # Label
        label = QLabel("Playback:")
        label.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 11px;")
        layout.addWidget(label)
        
        # Play/Pause button
        self.play_pause_btn = QPushButton("▶ Play")
        self.play_pause_btn.setFixedHeight(28)
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 3px;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #5fadff;
            }
            QPushButton:pressed {
                background-color: #3a8eef;
            }
        """)
        self.play_pause_btn.clicked.connect(self._on_play_pause_clicked)
        layout.addWidget(self.play_pause_btn)
        
        # Next Step button
        self.next_step_btn = QPushButton("⏭ Next")
        self.next_step_btn.setFixedHeight(28)
        self.next_step_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 3px;
                padding: 0 12px;
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
        
        # Clear button
        self.clear_btn = QPushButton("✕ Clear")
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #cc4444;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 3px;
                padding: 0 12px;
            }
            QPushButton:hover {
                background-color: #dd5555;
            }
            QPushButton:pressed {
                background-color: #bb3333;
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
            self.play_pause_btn.setText("⏸ Pause")
            self.play_pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff9944;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 3px;
                    padding: 0 15px;
                }
                QPushButton:hover {
                    background-color: #ffaa55;
                }
                QPushButton:pressed {
                    background-color: #ee8833;
                }
            """)
        else:
            self.play_pause_btn.setText("▶ Play")
            self.play_pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a9eff;
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 3px;
                    padding: 0 15px;
                }
                QPushButton:hover {
                    background-color: #5fadff;
                }
                QPushButton:pressed {
                    background-color: #3a8eef;
                }
            """)
    
    def set_playing(self, playing: bool):
        """Set the playing state externally."""
        if self.is_playing != playing:
            self.is_playing = playing
            self.update_play_pause_button()
