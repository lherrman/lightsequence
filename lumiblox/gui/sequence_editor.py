"""
Sequence Editor Components

Widgets for editing sequences and their steps.
"""

import logging
import typing as t

from PySide6.QtWidgets import (
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
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from lumiblox.controller.sequence_controller import SequenceStep
from lumiblox.gui.widgets import SelectAllLineEdit, SceneButton

# Configuration constants
DEFAULT_STEP_DURATION = 2.0  # Default duration in seconds for new steps

logger = logging.getLogger(__name__)


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

    def __init__(self, preset_index: t.Tuple[int, int], controller=None):
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
        loop_setting = self.controller.sequence_ctrl.loop_settings.get(
            self.preset_index, True
        )
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
