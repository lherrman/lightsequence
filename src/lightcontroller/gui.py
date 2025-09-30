"""
Professional GUI for the lighting controller with 8x8 pad visualization
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
    QGridLayout,
    QPushButton,
    QListWidget,
    QGroupBox,
    QTextEdit,
    QLabel,
    QFrame,
    QComboBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from .config import load_config
from .controller import LightController
from .launchpad import LaunchpadColor

logger = logging.getLogger(__name__)


class LaunchpadButton(QPushButton):
    """Custom button to represent a Launchpad pad."""

    button_pressed = Signal(int, int)  # x, y coordinates

    def __init__(self, x: int, y: int, parent=None):
        super().__init__(parent)
        self.grid_x = x
        self.grid_y = y
        self.setFixedSize(40, 40)
        self.setCheckable(True)
        self.clicked.connect(self._on_clicked)
        self.set_color(LaunchpadColor.OFF)

    def _on_clicked(self):
        """Handle button click."""
        self.button_pressed.emit(self.grid_x, self.grid_y)

    def set_color(self, color: LaunchpadColor):
        """Set button color based on LaunchpadColor."""
        if color == LaunchpadColor.OFF:
            bg_color = "#2a2a2a"
        elif color in [
            LaunchpadColor.RED_LOW,
            LaunchpadColor.RED_MID,
            LaunchpadColor.RED_FULL,
        ]:
            intensity = (
                ["#4a0000", "#8a0000", "#ff0000"][color - 1]
                if color <= 3
                else "#ff0000"
            )
            bg_color = intensity
        elif color in [
            LaunchpadColor.GREEN_LOW,
            LaunchpadColor.GREEN_MID,
            LaunchpadColor.GREEN_FULL,
        ]:
            bg_color = "#00ff00"
        elif color in [
            LaunchpadColor.AMBER_LOW,
            LaunchpadColor.AMBER_MID,
            LaunchpadColor.AMBER_FULL,
        ]:
            bg_color = "#ffaa00"
        elif color in [
            LaunchpadColor.YELLOW_LOW,
            LaunchpadColor.YELLOW_MID,
            LaunchpadColor.YELLOW_FULL,
        ]:
            bg_color = "#ffff00"
        else:
            bg_color = "#404040"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                border: 1px solid #666;
                border-radius: 4px;
                font-weight: bold;
                color: white;
            }}
            QPushButton:hover {{
                border: 2px solid #fff;
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
                border: 2px solid #ffff00;
            }}
        """)


class LaunchpadVisualization(QFrame):
    """8x8 Launchpad visualization widget."""

    button_pressed = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)

        # Create grid layout
        layout = QGridLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(10, 10, 10, 10)

        # Create 8x8 grid of buttons
        self.buttons = []
        for y in range(8):
            row = []
            for x in range(8):
                button = LaunchpadButton(x, y)
                button.button_pressed.connect(self.button_pressed.emit)

                # Add labels for scene and preset areas
                if y < 5:
                    scene_idx = y * 8 + x
                    button.setText(f"S{scene_idx}")
                    button.setToolTip(f"Scene {scene_idx} ({x}, {y})")
                else:
                    preset_idx = (y - 5) * 8 + x
                    button.setText(f"P{preset_idx}")
                    button.setToolTip(f"Preset {preset_idx} ({x}, {y})")

                layout.addWidget(button, y, x)
                row.append(button)
            self.buttons.append(row)

        # Add title
        title = QLabel("Launchpad MK2 Visualization")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))

        # Main layout for this widget
        main_layout = QVBoxLayout()
        main_layout.addWidget(title)
        main_layout.addLayout(layout)

        self.setLayout(main_layout)

    def set_button_color(self, x: int, y: int, color: LaunchpadColor):
        """Set color of specific button."""
        if 0 <= x < 8 and 0 <= y < 8:
            self.buttons[y][x].set_color(color)

    def clear_all_buttons(self):
        """Clear all buttons to off state."""
        for y in range(8):
            for x in range(8):
                self.buttons[y][x].set_color(LaunchpadColor.OFF)


class ControlPanel(QFrame):
    """Control panel with scenes and presets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)

        layout = QVBoxLayout()

        # Device selection
        device_group = QGroupBox("Device Selection")
        device_layout = QVBoxLayout()

        self.device_combo = QComboBox()
        self.device_combo.addItems(["Simulator", "Launchpad MK2", "loopMIDI Port"])
        device_layout.addWidget(QLabel("Output Device:"))
        device_layout.addWidget(self.device_combo)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # Scene controls (simplified - no scene list, scenes are automatic)
        scene_group = QGroupBox("Scene Controls")
        scene_layout = QHBoxLayout()

        self.blackout_btn = QPushButton("Blackout")
        scene_layout.addWidget(self.blackout_btn)

        scene_group.setLayout(scene_layout)
        layout.addWidget(scene_group)

        # Preset controls
        preset_group = QGroupBox("Presets")
        preset_layout = QVBoxLayout()

        self.preset_list = QListWidget()
        self.preset_list.setMaximumHeight(150)

        preset_buttons = QHBoxLayout()
        self.activate_preset_btn = QPushButton("Activate Preset")
        self.stop_preset_btn = QPushButton("Stop Preset")

        preset_buttons.addWidget(self.activate_preset_btn)
        preset_buttons.addWidget(self.stop_preset_btn)

        preset_layout.addWidget(self.preset_list)
        preset_layout.addLayout(preset_buttons)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Effects
        effects_group = QGroupBox("Effects")
        effects_layout = QVBoxLayout()

        effects_buttons = QHBoxLayout()
        self.wave_btn = QPushButton("Wave")
        self.pulse_btn = QPushButton("Pulse")
        self.rainbow_btn = QPushButton("Rainbow")
        self.chase_btn = QPushButton("Chase")

        effects_buttons.addWidget(self.wave_btn)
        effects_buttons.addWidget(self.pulse_btn)
        effects_buttons.addWidget(self.rainbow_btn)
        effects_buttons.addWidget(self.chase_btn)

        effects_layout.addLayout(effects_buttons)
        effects_group.setLayout(effects_layout)
        layout.addWidget(effects_group)

        layout.addStretch()
        self.setLayout(layout)


class StatusPanel(QFrame):
    """Status panel showing controller state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)

        layout = QVBoxLayout()

        # Title
        title = QLabel("Status")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Status text
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(200)
        self.status_text.setFont(QFont("Consolas", 9))

        layout.addWidget(self.status_text)
        self.setLayout(layout)

    def append_status(self, message: str):
        """Append status message."""
        self.status_text.append(message)
        # Keep only last 100 lines
        text = self.status_text.toPlainText()
        lines = text.split("\n")
        if len(lines) > 100:
            self.status_text.setPlainText("\n".join(lines[-100:]))

        # Scroll to bottom
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.status_text.setTextCursor(cursor)


class MainWindow(QMainWindow):
    """Professional main GUI window."""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.controller: Optional[LightController] = None

        self.setWindowTitle("Light Controller Professional")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 600)

        self._setup_ui()
        self._apply_professional_theme()
        self._setup_connections()
        self._update_lists()

        # Status timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_status)
        self.timer.start(1000)

    def _setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout()

        # Left side: Launchpad visualization
        self.launchpad_viz = LaunchpadVisualization()
        self.launchpad_viz.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        # Right side: Controls and status
        right_panel = QWidget()
        right_layout = QVBoxLayout()

        # Control panel
        self.control_panel = ControlPanel()

        # Status panel
        self.status_panel = StatusPanel()

        right_layout.addWidget(self.control_panel)
        right_layout.addWidget(self.status_panel)
        right_panel.setLayout(right_layout)

        # Add to main layout
        main_layout.addWidget(self.launchpad_viz, 0)
        main_layout.addWidget(right_panel, 1)

        central_widget.setLayout(main_layout)

    def _apply_professional_theme(self):
        """Apply professional dark theme."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 5px;
                margin: 2px;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: #404040;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }
            QPushButton {
                background-color: #4a4a4a;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 5px 15px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border: 1px solid #888;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QListWidget {
                background-color: #353535;
                border: 1px solid #555;
                border-radius: 3px;
                selection-background-color: #0078d4;
            }
            QTextEdit {
                background-color: #1e1e1e;
                border: 1px solid #555;
                border-radius: 3px;
                color: #ffffff;
            }
            QComboBox {
                background-color: #4a4a4a;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 3px;
                color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                border: none;
            }
            QLabel {
                color: #ffffff;
            }
        """)

    def _setup_connections(self):
        """Set up signal connections."""
        # Launchpad visualization
        self.launchpad_viz.button_pressed.connect(self._on_pad_button_pressed)

        # Control panel buttons
        self.control_panel.blackout_btn.clicked.connect(self._blackout)

        self.control_panel.activate_preset_btn.clicked.connect(
            self._activate_selected_preset
        )
        self.control_panel.stop_preset_btn.clicked.connect(self._stop_preset)

        # Effects
        self.control_panel.wave_btn.clicked.connect(lambda: self._play_effect("wave"))
        self.control_panel.pulse_btn.clicked.connect(lambda: self._play_effect("pulse"))
        self.control_panel.rainbow_btn.clicked.connect(
            lambda: self._play_effect("rainbow")
        )
        self.control_panel.chase_btn.clicked.connect(lambda: self._play_effect("chase"))

    def _update_lists(self):
        """Update preset list."""
        # Update presets
        self.control_panel.preset_list.clear()
        for preset_name in self.config.presets.keys():
            self.control_panel.preset_list.addItem(preset_name)

    def _on_pad_button_pressed(self, x: int, y: int):
        """Handle pad button press from visualization."""
        self.status_panel.append_status(f"Pad pressed: ({x}, {y})")

        if self.controller:
            # Simulate button press to controller
            self.controller._handle_button_press_xy(x, y, True)

    def _blackout(self):
        """Trigger blackout."""
        if self.controller:
            self.controller.blackout()
            self.status_panel.append_status("Blackout activated")

    def _activate_selected_preset(self):
        """Activate selected preset."""
        current_item = self.control_panel.preset_list.currentItem()
        if current_item and self.controller:
            preset_name = current_item.text()
            if preset_name in self.config.presets:
                preset = self.config.presets[preset_name]
                self.controller.activate_preset(preset)
                self.status_panel.append_status(f"Activated preset: {preset_name}")

    def _stop_preset(self):
        """Stop current preset."""
        if self.controller:
            self.controller._deactivate_current_preset()
            self.status_panel.append_status("Preset stopped")

    def _play_effect(self, effect_name: str):
        """Play RGB effect."""
        if self.controller and self.controller.launchpad.is_connected:
            self.status_panel.append_status(f"Playing effect: {effect_name}")
            # Run effect in a separate thread to avoid blocking GUI
            import threading

            thread = threading.Thread(
                target=self.controller.launchpad.play_rgb_effect,
                args=(effect_name, 3.0),
                daemon=True,
            )
            thread.start()

    def _update_status(self):
        """Update status display."""
        if not self.controller:
            return

        # Update launchpad visualization based on controller state
        self.launchpad_viz.clear_all_buttons()

        # Light up active scenes using automatic scene system
        for scene_idx in range(40):
            if self.controller.scene_manager.is_scene_active(scene_idx):
                coords = self.controller.launchpad.scene_coords_from_index(scene_idx)
                if coords:
                    x, y = coords
                    self.launchpad_viz.set_button_color(x, y, LaunchpadColor.GREEN_FULL)

        # Light up active preset
        # Light up active preset using automatic preset system
        active_preset_idx = self.controller.preset_manager.active_preset
        if active_preset_idx is not None:
            coords = self.controller.launchpad.preset_coords_from_index(
                active_preset_idx
            )
            if coords:
                x, y = coords
                self.launchpad_viz.set_button_color(x, y, LaunchpadColor.AMBER_FULL)

    def start_controller(self):
        """Start the lighting controller."""
        if not self.controller:
            self.controller = LightController(self.config)
            if self.controller.start():
                self.status_panel.append_status("Controller started successfully")
            else:
                self.status_panel.append_status("Failed to start controller")

    def stop_controller(self):
        """Stop the lighting controller."""
        if self.controller:
            self.controller.stop()
            self.controller = None
            self.status_panel.append_status("Controller stopped")

    def closeEvent(self, event):
        """Handle window close event."""
        self.stop_controller()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Light Controller Professional")

    window = MainWindow()
    window.show()
    window.start_controller()

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        window.stop_controller()
        sys.exit(0)


if __name__ == "__main__":
    main()
