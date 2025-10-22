"""
GUI Module - Main Entry Point

Imports from modular GUI components.
"""

from lumiblox.gui.main_window import main, LightSequenceGUI

__all__ = ['main', 'LightSequenceGUI']


if __name__ == "__main__":
    main()

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

    def __init__(self, simulation: bool = False):
        super().__init__()
        self.controller: t.Optional[LightController] = None
        self.should_stop = False
        self.simulation = simulation

    def run(self):
        """Run the controller in a separate thread."""
        try:
            self.controller = LightController(simulation=self.simulation)
            # Initialize hardware connections (non-blocking)
            self.controller.initialize()
            
            # Always emit ready signal - app works without hardware
            self.controller_ready.emit()

            # Modified run loop to work with threading
            logger.info("Light controller started in thread.")

            import time

            while not self.should_stop:
                try:
                    # Process inputs
                    self.controller._process_launchpad_input()
                    self.controller._process_midi_feedback()

                    # Update outputs
                    self.controller._update_leds()

                    time.sleep(0.02)  # Small delay to prevent excessive CPU usage
                except Exception as e:
                    logger.error(f"Error in controller loop: {e}")
                    # Continue running instead of breaking to prevent crashes
                    time.sleep(0.1)  # Wait a bit longer on error

        except Exception as e:
            self.controller_error.emit(f"Controller error: {e}")
        finally:
            if self.controller:
                self.controller.cleanup()

    def stop(self):
        """Stop the controller thread."""
        self.should_stop = True
        if self.controller:
            try:
                # Clear any callbacks to prevent cross-thread calls during shutdown
                self.controller.on_sequence_changed = None
                self.controller.on_sequence_saved = None
                # Don't call cleanup here - it's called in the thread's run() finally block
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
        scene_coord = (x, y)  # Use tuple for consistency

        if active:
            if scene_coord not in self.step.scenes:
                self.step.scenes.append(scene_coord)
        else:
            self.step.scenes = [s for s in self.step.scenes if s != scene_coord]

        self.step_changed.emit()

    def get_active_scenes(self) -> t.List[t.Tuple[int, int]]:
        """Get currently active scenes."""
        return [
            coord for coord, btn in self.scene_buttons.items() if btn.is_active
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
        """Load sequence from sequence controller."""
        if not self.controller:
            return

        steps = self.controller.sequence_ctrl.get_sequence(self.preset_index)
        if steps:
            self.sequence_steps = steps
        else:
            # Create default single step
            self.sequence_steps = [
                SequenceStep(scenes=[], duration=DEFAULT_STEP_DURATION, name="Step 1")
            ]

        # Load loop setting from loop_settings dict
        loop_setting = self.controller.sequence_ctrl.loop_settings.get(self.preset_index, True)
        self.loop_checkbox.setChecked(loop_setting)

        self.rebuild_step_widgets()

    def save_sequence(self):
        """Save sequence to sequence controller."""
        if not self.controller:
            return

        try:
            loop_enabled = self.loop_checkbox.isChecked()
            self.controller.sequence_ctrl.save_sequence(
                self.preset_index, self.sequence_steps, loop_enabled
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

        # Get active scenes from scene controller (keep as tuples)
        active_scenes = list(self.controller.scene_ctrl.get_active_scenes())

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

    # Custom signals for thread-safe sequence updates and device status updates
    sequence_changed_signal = Signal(object)
    sequence_saved_signal = Signal()
    device_status_update_signal = Signal()

    def __init__(self, simulation: bool = False):
        super().__init__()
        self.controller: t.Optional[LightController] = None
        self.controller_thread: t.Optional[ControllerThread] = None
        self.current_editor: t.Optional[PresetSequenceEditor] = None
        self._updating_from_launchpad = False  # Flag to prevent infinite loops
        self.simulation = simulation

        # Connect the signals to the slots
        self.sequence_changed_signal.connect(self._update_sequence_from_launchpad)
        self.sequence_saved_signal.connect(self._handle_sequence_saved)
        self.device_status_update_signal.connect(self._update_device_status_display)

        self.setWindowTitle("Light Sequence Controller")
        self.setMinimumSize(470, 200)
        self.resize(600, 800)
        self.setup_ui()
        self.apply_dark_theme()
        self.start_controller()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout - device status, sequence editor, preset grid
        main_layout = QVBoxLayout(central_widget)
        
        # === Device Status Bar (Top) ===
        status_bar_widget = QFrame()
        status_bar_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        status_bar_widget.setMaximumHeight(45)
        status_bar_widget.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        status_bar_layout = QHBoxLayout(status_bar_widget)
        status_bar_layout.setContentsMargins(10, 5, 10, 5)
        
        # Device status label
        status_label = QLabel("Devices:")
        status_label.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 11px;")
        status_bar_layout.addWidget(status_label)
        
        # Launchpad status indicator
        launchpad_container = QHBoxLayout()
        launchpad_label = QLabel("Launchpad:")
        launchpad_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        launchpad_container.addWidget(launchpad_label)
        
        self.launchpad_status_indicator = QLabel("●")
        self.launchpad_status_indicator.setStyleSheet("color: #888888; font-size: 16px; font-weight: bold;")
        self.launchpad_status_text = QLabel("Disconnected")
        self.launchpad_status_text.setStyleSheet("color: #888888; font-size: 10px;")
        launchpad_container.addWidget(self.launchpad_status_indicator)
        launchpad_container.addWidget(self.launchpad_status_text)
        launchpad_container.addStretch()
        
        status_bar_layout.addLayout(launchpad_container)
        status_bar_layout.addSpacing(20)
        
        # LightSoftware status indicator
        lightsw_container = QHBoxLayout()
        lightsw_label = QLabel("LightSoftware:")
        lightsw_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        lightsw_container.addWidget(lightsw_label)
        
        self.lightsw_status_indicator = QLabel("●")
        self.lightsw_status_indicator.setStyleSheet("color: #888888; font-size: 16px; font-weight: bold;")
        self.lightsw_status_text = QLabel("Disconnected")
        self.lightsw_status_text.setStyleSheet("color: #888888; font-size: 10px;")
        lightsw_container.addWidget(self.lightsw_status_indicator)
        lightsw_container.addWidget(self.lightsw_status_text)
        lightsw_container.addStretch()
        
        status_bar_layout.addLayout(lightsw_container)
        status_bar_layout.addStretch()
        
        main_layout.addWidget(status_bar_widget)

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
        self.controller_thread = ControllerThread(simulation=self.simulation)
        self.controller_thread.controller_ready.connect(self.on_controller_ready)
        self.controller_thread.controller_error.connect(self.on_controller_error)
        self.controller_thread.start()

    def on_controller_ready(self):
        """Called when controller is ready."""
        if self.controller_thread:
            self.controller = self.controller_thread.controller
            # Set up callbacks for sequence changes and saves
            if self.controller:
                self.controller.on_sequence_changed = self.on_launchpad_sequence_changed
                self.controller.on_sequence_saved = self.on_sequence_saved
                
                # Register device state change callback
                if hasattr(self.controller, 'device_manager'):
                    self.controller.device_manager.register_state_change_callback(
                        self._on_device_state_changed
                    )
                    # Update initial device statuses
                    self._update_device_status_display()
                    
            self.statusBar().showMessage("Controller connected successfully")
            self.refresh_presets()

    def on_controller_error(self, error: str):
        """Called when controller fails."""
        self.statusBar().showMessage(f"Controller error: {error}")
        QMessageBox.critical(
            self, "Controller Error", f"Failed to start light controller:\n{error}"
        )

    def on_sequence_saved(self):
        """Called when a sequence is saved from the launchpad (thread-unsafe callback)."""
        # Use signal to handle this in a thread-safe way
        self.sequence_saved_signal.emit()

    def _handle_sequence_saved(self):
        """Handle sequence saved signal (runs on GUI thread)."""
        # Refresh presets list to show the new/updated sequence
        self.refresh_presets()

    def refresh_presets(self):
        """Refresh the preset grid."""
        if not self.controller:
            return

        # Get all sequence indices
        sequence_indices = self.controller.sequence_ctrl.get_all_indices()

        # Update all preset buttons
        for (x, y), btn in self.preset_buttons.items():
            sequence_tuple = (x, y)
            if sequence_tuple in sequence_indices:
                # Check if it's a single-step sequence (preset) or multi-step
                seq_steps = self.controller.sequence_ctrl.get_sequence(sequence_tuple)
                has_sequence = len(seq_steps) > 1 if seq_steps else False
                btn.set_preset_info(True, has_sequence)
            else:
                btn.set_preset_info(False, False)

    def on_preset_button_selected(self, x: int, y: int):
        """Handle preset button selection."""
        if not self.controller:
            return

        sequence_tuple = (x, y)

        # Show sequence editor for this sequence
        self.show_sequence_editor(sequence_tuple)

        # Update button states - clear all first
        for btn in self.preset_buttons.values():
            btn.set_active_preset(False)

        # Set selected button as active
        if (x, y) in self.preset_buttons:
            self.preset_buttons[(x, y)].set_active_preset(True)

        # Also activate on the launchpad using new input system
        from lumiblox.controller.input_handler import ButtonEvent, ButtonType
        event = ButtonEvent(
            button_type=ButtonType.SEQUENCE,
            coordinates=sequence_tuple,
            pressed=True,
            source="gui"
        )
        self.controller.input_handler.handle_button_event(event)

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

    def on_launchpad_sequence_changed(self, sequence_coords: t.Optional[t.Tuple[int, int]]):
        """Called when sequence selection changes on the launchpad."""
        # Emit signal to handle on GUI thread
        self.sequence_changed_signal.emit(sequence_coords)

    def _update_sequence_from_launchpad(self, sequence_coords: t.Optional[t.Tuple[int, int]]):
        """Update sequence selection from launchpad (runs on GUI thread)."""
        self._updating_from_launchpad = True
        try:
            # Clear all preset button selections first
            for btn in self.preset_buttons.values():
                btn.set_active_preset(False)

            if sequence_coords is None:
                # No sequence selected - hide editor and show default message
                if self.current_editor:
                    self.current_editor.deleteLater()
                    self.current_editor = None
                self.default_label.show()
                return

            # Select the matching sequence button
            if sequence_coords in self.preset_buttons:
                self.preset_buttons[sequence_coords].set_active_preset(True)
                # Also show the editor for this sequence
                self.show_sequence_editor(sequence_coords)
        finally:
            self._updating_from_launchpad = False
    
    def _on_device_state_changed(self, device_type: DeviceType, new_state: DeviceState):
        """Handle device state changes (called from device manager)."""
        # Emit signal to update GUI on main thread
        self.device_status_update_signal.emit()
    
    def _update_device_status_display(self):
        """Update device status indicators in GUI."""
        if not self.controller or not hasattr(self.controller, 'device_manager'):
            return
        
        device_manager = self.controller.device_manager
        
        # Update Launchpad status
        launchpad_state = device_manager.get_state(DeviceType.LAUNCHPAD)
        self._update_status_indicator(
            self.launchpad_status_indicator,
            self.launchpad_status_text,
            launchpad_state
        )
        
        # Update LightSoftware status
        lightsw_state = device_manager.get_state(DeviceType.LIGHT_SOFTWARE)
        self._update_status_indicator(
            self.lightsw_status_indicator,
            self.lightsw_status_text,
            lightsw_state
        )
    
    def _update_status_indicator(
        self,
        indicator_label: QLabel,
        text_label: QLabel,
        state: DeviceState
    ):
        """Update a single status indicator based on device state."""
        if state == DeviceState.CONNECTED:
            indicator_label.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold;")
            text_label.setStyleSheet("color: #4CAF50; font-size: 10px;")
            text_label.setText("Connected")
        elif state == DeviceState.CONNECTING:
            indicator_label.setStyleSheet("color: #FFA726; font-size: 16px; font-weight: bold;")
            text_label.setStyleSheet("color: #FFA726; font-size: 10px;")
            text_label.setText("Connecting...")
        elif state == DeviceState.ERROR:
            indicator_label.setStyleSheet("color: #F44336; font-size: 16px; font-weight: bold;")
            text_label.setStyleSheet("color: #F44336; font-size: 10px;")
            text_label.setText("Error")
        else:  # DISCONNECTED
            indicator_label.setStyleSheet("color: #888888; font-size: 16px; font-weight: bold;")
            text_label.setStyleSheet("color: #888888; font-size: 10px;")
            text_label.setText("Disconnected")

    def closeEvent(self, event):
        """Handle application close."""
        if self.controller_thread:
            self.controller_thread.stop()
        event.accept()


def main(simulation: bool = False):
    """Main entry point for GUI application.

    Args:
        simulation: If True, use simulated lighting software instead of real one
    """
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Light Sequence Controller")
    app.setApplicationVersion("1.0")

    # Create and show main window
    window = LightSequenceGUI(simulation=simulation)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
