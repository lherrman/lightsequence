import sys
import logging
import typing as t

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QGroupBox,
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

# Configuration constants
DEFAULT_STEP_DURATION = 2.0  # Default duration in seconds for new steps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SelectAllLineEdit(QLineEdit):
    """QLineEdit that automatically selects all text when clicked or focused."""

    def mousePressEvent(self, event):
        """Override mouse press to select all text."""
        super().mousePressEvent(event)
        self.selectAll()

    def focusInEvent(self, event):
        """Override focus in to select all text."""
        super().focusInEvent(event)
        self.selectAll()


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
            if self.controller.initialize_hardware_connections():
                self.controller_ready.emit()

                # Modified run loop to work with threading
                logger.info("Light controller started in thread.")

                import time

                while not self.should_stop:
                    try:
                        # Handle button events
                        button_event = (
                            self.controller.launchpad_controller.get_button_events()
                        )
                        if button_event:
                            self.controller._route_button_event_to_handler(button_event)

                        # Update connection status from software monitoring
                        self.controller._update_connection_status_from_software()

                        # Process MIDI feedback
                        self.controller.process_midi_feedback_from_external()

                        self.controller.launchpad_controller.draw_background(
                            self.controller.background_manager.get_current_background()
                        )

                        time.sleep(0.02)  # Small delay to prevent excessive CPU usage
                    except Exception as e:
                        logger.error(f"Error in controller loop: {e}")
                        # Continue running instead of breaking to prevent crashes
                        time.sleep(0.1)  # Wait a bit longer on error

            else:
                self.controller_error.emit("Failed to connect to devices")
        except Exception as e:
            self.controller_error.emit(f"Controller error: {e}")
        finally:
            if self.controller:
                self.controller.cleanup_resources()

    def stop(self):
        """Stop the controller thread."""
        self.should_stop = True
        if self.controller:
            try:
                # Clear any callbacks to prevent cross-thread calls during shutdown
                self.controller.on_preset_changed = None
                self.controller.on_preset_saved = None
            except Exception as e:
                logger.error(f"Error clearing callbacks: {e}")
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


class PresetButton(QPushButton):
    """Custom button for preset grid."""

    preset_selected = Signal(int, int)

    def __init__(self, x: int, y: int):
        super().__init__()
        self.coord_x = x
        self.coord_y = y
        self.preset_coords = [x, y]
        self.has_preset = False
        self.has_sequence = False
        self.is_active_preset = False

        self.setFixedHeight(32)
        self.setMinimumWidth(10)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )  # Expand horizontally
        self.setCheckable(True)
        self.clicked.connect(self._on_preset_clicked)
        self.update_appearance()

    def _on_preset_clicked(self):
        """Handle button click."""
        self.preset_selected.emit(self.coord_x, self.coord_y)

    def set_preset_info(self, has_preset: bool, has_sequence: bool = False):
        """Update preset information."""
        self.has_preset = has_preset
        self.has_sequence = has_sequence
        self.update_appearance()

    def set_active_preset(self, is_active: bool):
        """Set whether this preset is currently active."""
        self.is_active_preset = is_active
        self.setChecked(is_active)
        self.update_appearance()

    def update_appearance(self):
        """Update button appearance based on state."""
        if not self.has_preset:
            self.setText(f"{self.coord_x},{self.coord_y}")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3c3c3c;
                    color: #666666;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
            """)
        else:
            # Show preset type indicator
            if self.has_sequence:
                self.setText(f"{self.coord_x},{self.coord_y}")
                base_color = "#3f94e9" if not self.is_active_preset else "#569de4"
            else:
                self.setText(f"{self.coord_x},{self.coord_y}")
                base_color = "#03519e" if not self.is_active_preset else "#1b5c9c"

            # Generate hover color more safely
            if self.has_sequence:
                hover_color = "#3f94e9" if not self.is_active_preset else "#569de4"
            else:
                hover_color = "#03519e" if not self.is_active_preset else "#1b5c9c"

            # Set border color based on active state
            border_color = "ffffff" if self.is_active_preset else "666666"

            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {base_color};
                    color: #ffffff;
                    border: 2px solid #{border_color};
                    border-radius: 3px;
                    font-size: 9px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:checked {{
                    border: 2px solid #ffffff;
                }}
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
                border-radius: 3px;
                margin: 1px;
                padding: 3px;
            }
        """)
        self.setMaximumHeight(160)  # More height to prevent text cutoff

        self.setup_ui()
        self.update_from_step()

    def setup_ui(self):
        # Main horizontal layout - scenes on left, parameters on right
        main_layout = QHBoxLayout(self)

        # Left side: Scene grid widget (no container box)
        scenes_widget = QWidget()
        scenes_widget.setFixedWidth(150)
        scenes_layout = QGridLayout(scenes_widget)
        scenes_layout.setHorizontalSpacing(2)
        scenes_layout.setVerticalSpacing(2)
        scenes_layout.setContentsMargins(5, 5, 5, 5)

        # Create 8x5 grid of scene buttons
        for y in range(5):
            for x in range(8):
                btn = SceneButton(x, y)
                btn.setFixedSize(14, 14)  # Compact buttons
                btn.scene_toggled.connect(self.on_scene_toggled)
                self.scene_buttons[(x, y)] = btn
                scenes_layout.addWidget(btn, y, x)

        main_layout.addWidget(scenes_widget)

        # Right side: Parameters and controls (compact)
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(8, 5, 5, 5)
        controls_layout.setSpacing(4)  # Tighter spacing

        # Step number label
        step_label = QLabel(f"Step {self.step_index + 1}")
        step_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #cccccc;")
        controls_layout.addWidget(step_label)

        # Step name (more compact)
        name_layout = QHBoxLayout()
        name_layout.setSpacing(5)
        name_label = QLabel("Name:")
        name_label.setFixedWidth(70)
        name_layout.addWidget(name_label)
        self.name_edit = QLineEdit()
        self.name_edit.setMaximumHeight(25)  # Taller input field to prevent cutoff
        self.name_edit.textChanged.connect(self.on_step_changed)
        name_layout.addWidget(self.name_edit)
        controls_layout.addLayout(name_layout)

        # Duration with +/- buttons and manual input
        duration_layout = QHBoxLayout()
        duration_layout.setSpacing(5)
        duration_label = QLabel("Duration:")
        duration_label.setFixedWidth(70)
        duration_layout.addWidget(duration_label)

        # Minus button
        minus_btn = QPushButton("-")
        minus_btn.setFixedSize(25, 25)
        minus_btn.setStyleSheet("font-weight: bold; font-size: 12px;")
        minus_btn.clicked.connect(self.decrease_duration)
        duration_layout.addWidget(minus_btn)

        # Duration input field (editable)
        self.duration_input = SelectAllLineEdit()
        self.duration_input.setFixedWidth(60)
        self.duration_input.setMaximumHeight(25)
        self.duration_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration_input.setStyleSheet(
            "border: 1px solid #555; padding: 3px; background: #1e1e1e;"
        )
        self.duration_input.textChanged.connect(self.on_duration_text_changed)
        self.duration_input.editingFinished.connect(self.on_duration_editing_finished)
        duration_layout.addWidget(self.duration_input)

        # Seconds label
        sec_label = QLabel("sec")
        sec_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        duration_layout.addWidget(sec_label)

        # Plus button
        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(25, 25)
        plus_btn.setStyleSheet("font-weight: bold; font-size: 12px;")
        plus_btn.clicked.connect(self.increase_duration)
        duration_layout.addWidget(plus_btn)

        duration_layout.addStretch()
        controls_layout.addLayout(duration_layout)

        # Bottom: Move and remove buttons (compact)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(3)

        # Move buttons with proper triangles
        self.move_up_btn = QPushButton("▲")
        self.move_up_btn.setFixedSize(30, 28)
        self.move_up_btn.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.move_up_btn.clicked.connect(lambda: self.move_up.emit(self))
        button_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("▼")
        self.move_down_btn.setFixedSize(30, 28)
        self.move_down_btn.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.move_down_btn.clicked.connect(lambda: self.move_down.emit(self))
        button_layout.addWidget(self.move_down_btn)

        button_layout.addStretch()

        # Remove button with proper height
        remove_btn = QPushButton("Remove")
        remove_btn.setFixedHeight(28)
        remove_btn.setStyleSheet(
            "background-color: #cc4444; color: white; font-weight: bold; font-size: 12px;"
        )
        remove_btn.clicked.connect(lambda: self.remove_step.emit(self))
        button_layout.addWidget(remove_btn)

        controls_layout.addLayout(button_layout)

        main_layout.addWidget(controls_widget)

        # Set proportional sizes - scenes get more space
        main_layout.setStretch(0, 2)  # Scenes
        main_layout.setStretch(1, 1)  # Controls

    def update_from_step(self):
        """Update widget from step data."""
        self.name_edit.setText(self.step.name)
        self.duration_input.setText(f"{self.step.duration:.1f}")

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
        # Update the scenes group title instead
        for child in self.findChildren(QGroupBox):
            if "Step" in child.title():
                child.setTitle(f"Step {new_index + 1} - Scenes")
                break

    def decrease_duration(self):
        """Decrease duration by 0.5 seconds."""
        current = self.step.duration
        new_value = max(0.1, current - 0.5)
        self.step.duration = new_value
        self.duration_input.setText(f"{new_value:.1f}")
        self.step_changed.emit()

    def increase_duration(self):
        """Increase duration by 0.5 seconds."""
        current = self.step.duration
        new_value = min(3600.0, current + 0.5)
        self.step.duration = new_value
        self.duration_input.setText(f"{new_value:.1f}")
        self.step_changed.emit()

    def on_duration_text_changed(self):
        """Called when duration text is being changed."""
        # Optional: Add real-time validation visual feedback here
        pass

    def on_duration_editing_finished(self):
        """Called when user finishes editing duration text."""
        try:
            text = self.duration_input.text().strip()
            value = float(text)

            # Validate range
            if value < 0.1:
                value = 0.1
            elif value > 3600.0:
                value = 3600.0

            # Update step and display
            self.step.duration = value
            self.duration_input.setText(f"{value:.1f}")
            self.step_changed.emit()

        except ValueError:
            # Invalid input - restore previous value
            self.duration_input.setText(f"{self.step.duration:.1f}")
            QMessageBox.warning(
                self,
                "Invalid Duration",
                "Please enter a valid number for duration (0.1 - 3600.0 seconds).",
            )

    def on_step_changed(self):
        """Called when step details change."""
        self.step.name = self.name_edit.text()
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
        self.add_from_scenes_btn = QPushButton("Add from Active")
        self.add_from_scenes_btn.clicked.connect(self.add_step_from_active_scenes)
        self.add_from_scenes_btn.setEnabled(self.controller is not None)
        header_layout.addWidget(self.add_from_scenes_btn)

        # Add empty step button
        add_step_btn = QPushButton("Add Empty")
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
            self.sequence_steps = [
                SequenceStep(scenes=[], duration=DEFAULT_STEP_DURATION, name="Step 1")
            ]

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
            scenes=[],
            duration=DEFAULT_STEP_DURATION,
            name=f"Step {len(self.sequence_steps) + 1}",
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
            [scene[0], scene[1]] for scene in self.controller.currently_active_scenes
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
            duration=DEFAULT_STEP_DURATION,
            name=f"Step {len(self.sequence_steps) + 1}",
        )
        self.sequence_steps.append(step)
        self.rebuild_step_widgets()
        self.auto_save_sequence()

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

    # Custom signals for thread-safe preset updates
    preset_changed_signal = Signal(object)
    preset_saved_signal = Signal()

    def __init__(self):
        super().__init__()
        self.controller: t.Optional[LightController] = None
        self.controller_thread: t.Optional[ControllerThread] = None
        self.current_editor: t.Optional[PresetSequenceEditor] = None
        self._updating_from_launchpad = False  # Flag to prevent infinite loops

        # Connect the signals to the slots
        self.preset_changed_signal.connect(self._update_preset_from_launchpad)
        self.preset_saved_signal.connect(self._handle_preset_saved)

        self.setWindowTitle("Light Sequence Controller")
        self.setMinimumSize(470, 200)
        self.resize(600, 800)
        self.setup_ui()
        self.apply_dark_theme()
        self.start_controller()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout - sequence editor on top, preset grid on bottom
        main_layout = QVBoxLayout(central_widget)

        # Top area - Sequence editor (takes most space)
        self.editor_stack = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_stack)

        # Default message
        self.default_label = QLabel(
            "Select a preset from the grid below to edit its sequence."
        )
        self.default_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.default_label.setStyleSheet("color: #888888; font-size: 14px;")
        self.editor_layout.addWidget(self.default_label)

        main_layout.addWidget(self.editor_stack, 3)  # Give most space to editor

        # Bottom area - Preset grid (3 rows x 8 columns) - more compact
        preset_panel = QWidget()  # Use plain widget instead of GroupBox
        preset_panel.setMaximumHeight(125)  # Slightly more height for better spacing
        preset_panel.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        preset_layout = QVBoxLayout(preset_panel)
        preset_layout.setContentsMargins(3, 3, 3, 3)  # Very tight margins
        preset_layout.setSpacing(2)

        # Header with title and refresh button in one line
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)

        # Title label
        title_label = QLabel("Presets")
        title_label.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 11px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()  # Push refresh button to right

        # Small refresh icon button in corner
        refresh_btn = QPushButton("🔄")
        refresh_btn.clicked.connect(self.refresh_presets)
        refresh_btn.setFixedSize(18, 18)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                border: 1px solid #666666;
                border-radius: 9px;
                font-size: 10px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        header_layout.addWidget(refresh_btn)
        preset_layout.addLayout(header_layout)

        # Preset grid
        self.preset_grid_widget = QWidget()
        preset_grid_layout = QGridLayout(self.preset_grid_widget)
        preset_grid_layout.setHorizontalSpacing(3)  # Horizontal spacing between columns
        preset_grid_layout.setVerticalSpacing(6)  # More vertical spacing between rows
        preset_grid_layout.setContentsMargins(0, 2, 0, 2)  # Small top/bottom margins

        # Create 3x8 grid of preset buttons
        self.preset_buttons: t.Dict[t.Tuple[int, int], PresetButton] = {}
        for y in range(3):  # 3 rows
            for x in range(8):  # 8 columns
                btn = PresetButton(x, y)
                btn.preset_selected.connect(self.on_preset_button_selected)
                self.preset_buttons[(x, y)] = btn
                preset_grid_layout.addWidget(btn, y, x)

                # Make columns stretch equally to use full width
                preset_grid_layout.setColumnStretch(x, 1)

        preset_layout.addWidget(self.preset_grid_widget)
        main_layout.addWidget(preset_panel, 1)  # Give less space to preset grid

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
            # Set up callbacks for preset changes and saves
            if self.controller:
                self.controller.on_preset_changed = self.on_launchpad_preset_changed
                self.controller.on_preset_saved = self.on_preset_saved
            self.statusBar().showMessage("Controller connected successfully")
            self.refresh_presets()

    def on_controller_error(self, error: str):
        """Called when controller fails."""
        self.statusBar().showMessage(f"Controller error: {error}")
        QMessageBox.critical(
            self, "Controller Error", f"Failed to start light controller:\n{error}"
        )

    def on_preset_saved(self):
        """Called when a preset is saved from the launchpad (thread-unsafe callback)."""
        # Use signal to handle this in a thread-safe way
        self.preset_saved_signal.emit()

    def _handle_preset_saved(self):
        """Handle preset saved signal (runs on GUI thread)."""
        # Refresh presets list to show the new/updated preset
        self.refresh_presets()

    def refresh_presets(self):
        """Refresh the preset grid."""
        if not self.controller:
            return

        # Get all preset indices
        preset_indices = self.controller.preset_manager.get_all_preset_indices()

        # Update all preset buttons
        for (x, y), btn in self.preset_buttons.items():
            preset_tuple = (x, y)
            if preset_tuple in preset_indices:
                preset_list = [x, y]
                has_sequence = self.controller.preset_manager.has_sequence(preset_list)
                btn.set_preset_info(True, has_sequence)
            else:
                btn.set_preset_info(False, False)

    def on_preset_button_selected(self, x: int, y: int):
        """Handle preset button selection."""
        if not self.controller:
            return

        preset_coords = [x, y]
        preset_tuple = (x, y)

        # Show sequence editor for this preset
        self.show_sequence_editor(preset_tuple)

        # Update button states - clear all first
        for btn in self.preset_buttons.values():
            btn.set_active_preset(False)

        # Set selected button as active
        if (x, y) in self.preset_buttons:
            self.preset_buttons[(x, y)].set_active_preset(True)

        # Also activate on the launchpad
        self.select_preset_on_launchpad(preset_coords)

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

    def on_launchpad_preset_changed(self, preset_coords: t.Optional[t.List[int]]):
        """Called when preset selection changes on the launchpad."""
        # Emit signal to handle on GUI thread
        self.preset_changed_signal.emit(preset_coords)

    def _update_preset_from_launchpad(self, preset_coords: t.Optional[t.List[int]]):
        """Update preset selection from launchpad (runs on GUI thread)."""
        self._updating_from_launchpad = True
        try:
            # Clear all preset button selections first
            for btn in self.preset_buttons.values():
                btn.set_active_preset(False)

            if preset_coords is None:
                # No preset selected - hide editor and show default message
                if self.current_editor:
                    self.current_editor.deleteLater()
                    self.current_editor = None
                self.default_label.show()
                return

            # Select the matching preset button
            preset_tuple = (preset_coords[0], preset_coords[1])
            if preset_tuple in self.preset_buttons:
                self.preset_buttons[preset_tuple].set_active_preset(True)
                # Also show the editor for this preset
                self.show_sequence_editor(preset_tuple)
        finally:
            self._updating_from_launchpad = False

    def select_preset_on_launchpad(self, preset_coords: t.List[int]):
        """Programmatically select a preset on the launchpad (called from GUI)."""
        if self.controller and self.controller.currently_active_preset != preset_coords:
            # Simulate a preset button press
            self.controller._activate_preset(preset_coords)

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
