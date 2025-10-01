import sys
import logging
import typing as t

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QDoubleSpinBox,
    QLineEdit,
    QLabel,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QFrame,
    QScrollArea,
    QGridLayout,
    QCheckBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont

from main import LightController
from sequence_manager import SequenceStep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ControllerThread(QThread):
    """Thread to run the LightController without blocking the GUI."""

    controller_ready = Signal()
    controller_error = Signal(str)

    def __init__(self):
        super().__init__()
        self.controller: t.Optional[LightController] = None
        self.should_stop = False

    def run(self):
        """Run the controller in a separate thread."""
        try:
            self.controller = LightController()
            if self.controller.connect():
                self.controller_ready.emit()

                # Modified run loop to work with threading
                logger.info("Light controller started in thread.")

                import time

                while not self.should_stop:
                    try:
                        # Handle button events
                        button_event = self.controller.launchpad.get_button_events()
                        if button_event:
                            self.controller._process_button_event(button_event)

                        # Process MIDI feedback
                        self.controller._process_midi_feedback()

                        self.controller.launchpad.draw_background(
                            self.controller.background_manager.get_current_background()
                        )

                        time.sleep(0.02)  # Small delay to prevent excessive CPU usage
                    except Exception as e:
                        logger.error(f"Error in controller loop: {e}")
                        break

            else:
                self.controller_error.emit("Failed to connect to devices")
        except Exception as e:
            self.controller_error.emit(f"Controller error: {e}")
        finally:
            if self.controller:
                self.controller.cleanup()

    def stop(self):
        """Stop the controller thread."""
        self.should_stop = True
        self.wait(3000)  # Wait up to 3 seconds for thread to finish


class SceneButton(QPushButton):
    """Custom button for scene grid."""

    scene_toggled = Signal(int, int, bool)

    def __init__(self, x: int, y: int):
        super().__init__(f"{x},{y}")
        self.coord_x = x
        self.coord_y = y
        self.is_active = False
        self.setCheckable(True)
        self.setMinimumSize(35, 35)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.clicked.connect(self._on_clicked)
        self.update_style()

    def _on_clicked(self):
        self.is_active = self.isChecked()
        self.update_style()
        self.scene_toggled.emit(self.coord_x, self.coord_y, self.is_active)

    def set_active(self, active: bool):
        self.is_active = active
        self.setChecked(active)
        self.update_style()

    def update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 2px solid #45a049;
                    border-radius: 5px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3c3c3c;
                    color: #cccccc;
                    border: 1px solid #555555;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
            """)


class SequenceStepWidget(QFrame):
    """Widget for editing a single sequence step."""

    step_changed = Signal()
    remove_step = Signal(object)  # Pass self as parameter
    move_up = Signal(object)
    move_down = Signal(object)

    def __init__(self, step: SequenceStep, step_index: int):
        super().__init__()
        self.step = step
        self.step_index = step_index
        self.scene_buttons: t.Dict[t.Tuple[int, int], SceneButton] = {}

        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 5px;
                margin: 2px;
                padding: 5px;
            }
        """)

        self.setup_ui()
        self.update_from_step()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header with step info and controls
        header_layout = QHBoxLayout()

        self.step_label = QLabel(f"Step {self.step_index + 1}")
        self.step_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(self.step_label)

        header_layout.addStretch()

        # Move buttons
        self.move_up_btn = QPushButton("↑")
        self.move_up_btn.setFixedSize(25, 25)
        self.move_up_btn.clicked.connect(lambda: self.move_up.emit(self))
        header_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("↓")
        self.move_down_btn.setFixedSize(25, 25)
        self.move_down_btn.clicked.connect(lambda: self.move_down.emit(self))
        header_layout.addWidget(self.move_down_btn)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(25, 25)
        remove_btn.setStyleSheet(
            "background-color: #cc4444; color: white; font-weight: bold;"
        )
        remove_btn.clicked.connect(lambda: self.remove_step.emit(self))
        header_layout.addWidget(remove_btn)

        layout.addLayout(header_layout)

        # Step details
        details_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.on_step_changed)
        details_layout.addRow("Name:", self.name_edit)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.5, 3600.0)
        self.duration_spin.setSingleStep(0.5)
        self.duration_spin.setValue(1.0)  # Default 1 second
        self.duration_spin.setSuffix(" sec")
        self.duration_spin.valueChanged.connect(self.on_step_changed)
        details_layout.addRow("Duration:", self.duration_spin)

        layout.addLayout(details_layout)

        # Scene grid
        scenes_group = QGroupBox("Scenes")
        scenes_layout = QGridLayout(scenes_group)
        scenes_layout.setSpacing(4)  # Equal spacing between buttons

        # Create 8x5 grid of scene buttons (matching the launchpad scene area)
        for y in range(5):
            for x in range(8):
                btn = SceneButton(x, y + 1)  # y+1 because scenes start at row 1
                btn.scene_toggled.connect(self.on_scene_toggled)
                self.scene_buttons[(x, y + 1)] = btn
                scenes_layout.addWidget(btn, y, x)

        # Make all columns and rows have equal stretch
        for i in range(8):
            scenes_layout.setColumnStretch(i, 1)
        for i in range(5):
            scenes_layout.setRowStretch(i, 1)

        layout.addWidget(scenes_group)

    def update_from_step(self):
        """Update widget from step data."""
        self.name_edit.setText(self.step.name)
        self.duration_spin.setValue(self.step.duration)

        # Clear all scene buttons first
        for btn in self.scene_buttons.values():
            btn.set_active(False)

        # Set active scenes
        for scene in self.step.scenes:
            if len(scene) >= 2:
                key = (scene[0], scene[1])
                if key in self.scene_buttons:
                    self.scene_buttons[key].set_active(True)

    def update_step_index(self, new_index: int):
        """Update the step index display."""
        self.step_index = new_index
        self.step_label.setText(f"Step {new_index + 1}")

    def on_step_changed(self):
        """Called when step details change."""
        self.step.name = self.name_edit.text()
        self.step.duration = self.duration_spin.value()
        self.step_changed.emit()

    def on_scene_toggled(self, x: int, y: int, active: bool):
        """Called when a scene button is toggled."""
        scene_coord = [x, y]

        if active:
            if scene_coord not in self.step.scenes:
                self.step.scenes.append(scene_coord)
        else:
            self.step.scenes = [s for s in self.step.scenes if s != scene_coord]

        self.step_changed.emit()

    def get_active_scenes(self) -> t.List[t.List[int]]:
        """Get currently active scenes."""
        return [
            list(coord) for coord, btn in self.scene_buttons.items() if btn.is_active
        ]


class PresetSequenceEditor(QWidget):
    """Widget for editing sequences for a specific preset."""

    def __init__(
        self,
        preset_index: t.Tuple[int, int],
        controller: t.Optional[LightController] = None,
    ):
        super().__init__()
        self.preset_index = preset_index
        self.controller = controller
        self.sequence_steps: t.List[SequenceStep] = []
        self.step_widgets: t.List[SequenceStepWidget] = []

        self.setup_ui()
        self.load_sequence()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel(
            f"Preset [{self.preset_index[0]}, {self.preset_index[1]}] Sequence"
        )
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Add step from current scenes button
        self.add_from_scenes_btn = QPushButton("Add Step from Active Scenes")
        self.add_from_scenes_btn.clicked.connect(self.add_step_from_active_scenes)
        self.add_from_scenes_btn.setEnabled(self.controller is not None)
        header_layout.addWidget(self.add_from_scenes_btn)

        # Add empty step button
        add_step_btn = QPushButton("Add Empty Step")
        add_step_btn.clicked.connect(self.add_empty_step)
        header_layout.addWidget(add_step_btn)

        layout.addLayout(header_layout)

        # Loop checkbox
        loop_layout = QHBoxLayout()
        self.loop_checkbox = QCheckBox("Loop sequence")
        self.loop_checkbox.setChecked(True)  # Default to loop
        self.loop_checkbox.stateChanged.connect(self.auto_save_sequence)
        loop_layout.addWidget(self.loop_checkbox)
        loop_layout.addStretch()
        layout.addLayout(loop_layout)

        # Scroll area for steps
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.steps_widget = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_widget)
        self.steps_layout.addStretch()  # Push steps to top

        scroll.setWidget(self.steps_widget)
        layout.addWidget(scroll)

        # Control buttons
        button_layout = QHBoxLayout()

        load_btn = QPushButton("Reload from File")
        load_btn.clicked.connect(self.load_sequence)
        button_layout.addWidget(load_btn)

        button_layout.addStretch()

        # Test sequence button
        self.test_btn = QPushButton("Test Sequence")
        self.test_btn.clicked.connect(self.test_sequence)
        self.test_btn.setEnabled(self.controller is not None)
        button_layout.addWidget(self.test_btn)

        layout.addLayout(button_layout)

    def load_sequence(self):
        """Load sequence from preset manager."""
        if not self.controller:
            return

        steps = self.controller.preset_manager.get_sequence(list(self.preset_index))
        if steps:
            self.sequence_steps = steps
        else:
            # Create default single step
            self.sequence_steps = [SequenceStep(scenes=[], duration=1.0, name="Step 1")]

        # Load loop setting
        loop_setting = self.controller.preset_manager.get_loop_setting(
            list(self.preset_index)
        )
        self.loop_checkbox.setChecked(loop_setting)

        self.rebuild_step_widgets()

    def save_sequence(self):
        """Save sequence to preset manager."""
        if not self.controller:
            return

        try:
            loop_enabled = self.loop_checkbox.isChecked()
            self.controller.preset_manager.save_sequence(
                list(self.preset_index), self.sequence_steps, loop_enabled
            )
        except Exception as e:
            logger.error(f"Failed to save sequence: {e}")

    def auto_save_sequence(self):
        """Auto-save sequence after changes."""
        self.save_sequence()

    def add_empty_step(self):
        """Add an empty step."""
        step = SequenceStep(
            scenes=[], duration=1.0, name=f"Step {len(self.sequence_steps) + 1}"
        )
        self.sequence_steps.append(step)
        self.rebuild_step_widgets()
        self.auto_save_sequence()

    def add_step_from_active_scenes(self):
        """Add a step with currently active scenes from the controller."""
        if not self.controller:
            return

        # Get active scenes from controller
        active_scenes = [
            [scene[0], scene[1]] for scene in self.controller.active_scenes
        ]

        if not active_scenes:
            QMessageBox.information(
                self,
                "No Active Scenes",
                "No scenes are currently active. Activate some scenes on the launchpad first.",
            )
            return

        step = SequenceStep(
            scenes=active_scenes,
            duration=1.0,
            name=f"Step {len(self.sequence_steps) + 1}",
        )
        self.sequence_steps.append(step)
        self.rebuild_step_widgets()
        self.auto_save_sequence()

    def test_sequence(self):
        """Test the current sequence."""
        if not self.controller or not self.sequence_steps:
            return

        # TODO: Implement sequence testing
        QMessageBox.information(self, "Test", "Sequence testing not yet implemented.")

    def rebuild_step_widgets(self):
        """Rebuild all step widgets."""
        # Clear existing widgets
        for widget in self.step_widgets:
            widget.deleteLater()
        self.step_widgets.clear()

        # Create new widgets
        for i, step in enumerate(self.sequence_steps):
            widget = SequenceStepWidget(step, i)
            widget.step_changed.connect(self.on_step_changed)
            widget.remove_step.connect(self.remove_step)
            widget.move_up.connect(self.move_step_up)
            widget.move_down.connect(self.move_step_down)

            self.step_widgets.append(widget)
            self.steps_layout.insertWidget(i, widget)

        self.update_move_buttons()

    def on_step_changed(self):
        """Called when any step changes."""
        self.auto_save_sequence()

    def remove_step(self, step_widget: SequenceStepWidget):
        """Remove a step."""
        if len(self.sequence_steps) <= 1:
            QMessageBox.warning(self, "Cannot Remove", "Cannot remove the last step.")
            return

        index = self.step_widgets.index(step_widget)
        del self.sequence_steps[index]
        self.rebuild_step_widgets()
        self.auto_save_sequence()

    def move_step_up(self, step_widget: SequenceStepWidget):
        """Move step up."""
        index = self.step_widgets.index(step_widget)
        if index > 0:
            self.sequence_steps[index], self.sequence_steps[index - 1] = (
                self.sequence_steps[index - 1],
                self.sequence_steps[index],
            )
            self.rebuild_step_widgets()
            self.auto_save_sequence()

    def move_step_down(self, step_widget: SequenceStepWidget):
        """Move step down."""
        index = self.step_widgets.index(step_widget)
        if index < len(self.sequence_steps) - 1:
            self.sequence_steps[index], self.sequence_steps[index + 1] = (
                self.sequence_steps[index + 1],
                self.sequence_steps[index],
            )
            self.rebuild_step_widgets()
            self.auto_save_sequence()

    def update_move_buttons(self):
        """Update move button states."""
        for i, widget in enumerate(self.step_widgets):
            widget.move_up_btn.setEnabled(i > 0)
            widget.move_down_btn.setEnabled(i < len(self.step_widgets) - 1)


class LightSequenceGUI(QMainWindow):
    """Main GUI application for light sequence configuration."""

    def __init__(self):
        super().__init__()
        self.controller: t.Optional[LightController] = None
        self.controller_thread: t.Optional[ControllerThread] = None
        self.current_editor: t.Optional[PresetSequenceEditor] = None

        self.setWindowTitle("Light Sequence Controller")
        self.setMinimumSize(1200, 800)

        self.setup_ui()
        self.apply_dark_theme()
        self.start_controller()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)

        # Left panel - Preset list
        left_panel = QWidget()
        left_panel.setMaximumWidth(300)
        left_layout = QVBoxLayout(left_panel)

        # Preset list
        left_layout.addWidget(QLabel("Presets:"))

        self.preset_tree = QTreeWidget()
        self.preset_tree.setHeaderLabels(["Preset", "Type"])
        self.preset_tree.itemClicked.connect(self.on_preset_selected)
        left_layout.addWidget(self.preset_tree)

        # Refresh button
        refresh_btn = QPushButton("Refresh Presets")
        refresh_btn.clicked.connect(self.refresh_presets)
        left_layout.addWidget(refresh_btn)

        layout.addWidget(left_panel)

        # Right panel - Sequence editor
        self.editor_stack = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_stack)

        # Default message
        self.default_label = QLabel(
            "Select a preset from the list to edit its sequence."
        )
        self.default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_label.setStyleSheet("color: #888888; font-size: 14px;")
        self.editor_layout.addWidget(self.default_label)

        layout.addWidget(self.editor_stack)

        # Status bar
        self.statusBar().showMessage("Starting controller...")

    def apply_dark_theme(self):
        """Apply dark theme to the application."""
        dark_stylesheet = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QTreeWidget {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            selection-background-color: #4a4a4a;
        }
        QTreeWidget::item:selected {
            background-color: #4a4a4a;
        }
        QPushButton {
            background-color: #4a4a4a;
            color: #ffffff;
            border: 1px solid #666666;
            padding: 8px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #5a5a5a;
        }
        QPushButton:pressed {
            background-color: #3a3a3a;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            padding: 4px;
            border-radius: 4px;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #555555;
            border-radius: 5px;
            margin: 10px 0px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QLabel {
            color: #ffffff;
        }
        QScrollArea {
            border: none;
        }
        """
        self.setStyleSheet(dark_stylesheet)

    def start_controller(self):
        """Start the light controller in a separate thread."""
        self.controller_thread = ControllerThread()
        self.controller_thread.controller_ready.connect(self.on_controller_ready)
        self.controller_thread.controller_error.connect(self.on_controller_error)
        self.controller_thread.start()

    def on_controller_ready(self):
        """Called when controller is ready."""
        if self.controller_thread:
            self.controller = self.controller_thread.controller
            self.statusBar().showMessage("Controller connected successfully")
            self.refresh_presets()

    def on_controller_error(self, error: str):
        """Called when controller fails."""
        self.statusBar().showMessage(f"Controller error: {error}")
        QMessageBox.critical(
            self, "Controller Error", f"Failed to start light controller:\n{error}"
        )

    def refresh_presets(self):
        """Refresh the preset list."""
        self.preset_tree.clear()

        if not self.controller:
            return

        preset_indices = self.controller.preset_manager.get_all_preset_indices()

        for preset_tuple in preset_indices.keys():
            preset_list = list(preset_tuple)
            has_sequence = self.controller.preset_manager.has_sequence(preset_list)

            item = QTreeWidgetItem(self.preset_tree)
            item.setText(0, f"[{preset_tuple[0]}, {preset_tuple[1]}]")
            item.setText(1, "Sequence" if has_sequence else "Simple")
            item.setData(0, Qt.ItemDataRole.UserRole, preset_tuple)

            if has_sequence:
                from PySide6.QtWidgets import QStyle

                item.setIcon(
                    0, self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
                )

    def on_preset_selected(self, item: QTreeWidgetItem, column: int):
        """Called when a preset is selected."""
        preset_tuple = item.data(0, Qt.ItemDataRole.UserRole)
        if preset_tuple and self.controller:
            self.show_sequence_editor(preset_tuple)

    def show_sequence_editor(self, preset_index: t.Tuple[int, int]):
        """Show sequence editor for the selected preset."""
        # Clear current editor
        if self.current_editor:
            self.current_editor.deleteLater()
            self.current_editor = None

        # Hide default label
        self.default_label.hide()

        # Create new editor
        self.current_editor = PresetSequenceEditor(preset_index, self.controller)
        self.editor_layout.addWidget(self.current_editor)

    def closeEvent(self, event):
        """Handle application close."""
        if self.controller_thread:
            self.controller_thread.stop()
        event.accept()


def main():
    """Main entry point for GUI application."""
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Light Sequence Controller")
    app.setApplicationVersion("1.0")

    # Create and show main window
    window = LightSequenceGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
