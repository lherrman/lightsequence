"""
Simple GUI for the lighting controller
"""

import sys
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QTextEdit,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from .config import load_config
from .controller import LightController

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main GUI window."""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.controller: Optional[LightController] = None

        self.setWindowTitle("Light Controller")
        self.setGeometry(100, 100, 800, 600)

        self._setup_ui()
        self._apply_theme()
        self._update_lists()

        # Status timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.start(1000)

    def _setup_ui(self):
        """Setup UI."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Left panel
        left = QWidget()
        left_layout = QVBoxLayout(left)

        # Scenes
        scenes_group = QGroupBox("Scenes")
        scenes_layout = QVBoxLayout(scenes_group)
        self.scenes_list = QListWidget()
        scenes_layout.addWidget(self.scenes_list)
        left_layout.addWidget(scenes_group)

        # Presets
        presets_group = QGroupBox("Presets")
        presets_layout = QVBoxLayout(presets_group)
        self.presets_list = QListWidget()
        self.presets_list.itemDoubleClicked.connect(self._activate_preset)
        presets_layout.addWidget(self.presets_list)
        left_layout.addWidget(presets_group)

        layout.addWidget(left)

        # Right panel
        right = QWidget()
        right_layout = QVBoxLayout(right)

        # Controls
        controls_group = QGroupBox("Control")
        controls_layout = QVBoxLayout(controls_group)

        self.start_btn = QPushButton("START")
        self.start_btn.clicked.connect(self._start)
        controls_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)

        self.blackout_btn = QPushButton("BLACKOUT")
        self.blackout_btn.clicked.connect(self._blackout)
        controls_layout.addWidget(self.blackout_btn)

        right_layout.addWidget(controls_group)

        # Status
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(150)
        status_layout.addWidget(self.status_text)
        right_layout.addWidget(status_group)

        # Active scenes
        active_group = QGroupBox("Active Scenes")
        active_layout = QVBoxLayout(active_group)
        self.active_list = QListWidget()
        active_layout.addWidget(self.active_list)
        right_layout.addWidget(active_group)

        layout.addWidget(right)

    def _apply_theme(self):
        """Apply dark theme."""
        self.setStyleSheet("""
            QMainWindow { background-color: #2C3E50; color: white; }
            QWidget { background-color: #2C3E50; color: white; }
            QGroupBox { 
                font-weight: bold; border: 2px solid #34495E; 
                border-radius: 8px; margin-top: 10px; 
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton { 
                background-color: #3498DB; border: none; border-radius: 8px; 
                color: white; font-weight: bold; padding: 10px; min-height: 20px;
            }
            QPushButton:hover { background-color: #2980B9; }
            QPushButton:disabled { background-color: #7F8C8D; }
            QListWidget { 
                background-color: #34495E; border: 2px solid #2C3E50; 
                border-radius: 8px; padding: 4px; 
            }
            QListWidget::item { 
                background-color: #2C3E50; border-radius: 4px; 
                padding: 8px; margin: 2px; 
            }
            QListWidget::item:selected { background-color: #3498DB; }
            QTextEdit { 
                background-color: #34495E; border: 2px solid #2C3E50; 
                border-radius: 8px; font-family: monospace; 
            }
        """)

    def _update_lists(self):
        """Update scene and preset lists."""
        # Scenes
        self.scenes_list.clear()
        for name, scene in self.config.scenes.items():
            item = QListWidgetItem(f"{name} (Note {scene.midi_note})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            try:
                color = QColor(scene.color)
                item.setBackground(color)
                item.setForeground(
                    QColor("white" if color.lightness() < 128 else "black")
                )
            except Exception:
                pass
            self.scenes_list.addItem(item)

        # Presets
        self.presets_list.clear()
        for name, preset in self.config.presets.items():
            item = QListWidgetItem(f"{name} ({len(preset.scenes)} scenes)")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.presets_list.addItem(item)

    def _start(self):
        """Start controller."""
        if self.controller:
            return

        self.controller = LightController(self.config)
        if self.controller.start():
            self.status_text.append("✅ Controller started")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_text.append("❌ Failed to start controller")
            self.controller = None

    def _stop(self):
        """Stop controller."""
        if self.controller:
            self.controller.stop()
            self.controller = None
            self.status_text.append("⏹️ Controller stopped")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def _blackout(self):
        """Emergency blackout."""
        if self.controller:
            self.controller.blackout()
            self.status_text.append("🚨 BLACKOUT!")

    def _activate_preset(self, item: QListWidgetItem):
        """Activate selected preset."""
        if not self.controller:
            return

        preset_name = item.data(Qt.ItemDataRole.UserRole)
        if preset_name in self.config.presets:
            preset = self.config.presets[preset_name]
            self.controller.activate_preset(preset)
            self.status_text.append(f"▶️ Activated: {preset_name}")

    def _update_status(self):
        """Update status display."""
        if not self.controller:
            return

        status = self.controller.get_status()

        # Update active scenes list
        self.active_list.clear()
        for scene_name in status["active_scenes"]:
            if scene_name in self.config.scenes:
                scene = self.config.scenes[scene_name]
                item = QListWidgetItem(f"{scene_name} (Note {scene.midi_note})")
                try:
                    color = QColor(scene.color)
                    item.setBackground(color)
                    item.setForeground(
                        QColor("white" if color.lightness() < 128 else "black")
                    )
                except Exception:
                    pass
                self.active_list.addItem(item)

    def closeEvent(self, event):
        """Handle close."""
        self._stop()
        event.accept()


def main():
    """Main entry point."""
    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
