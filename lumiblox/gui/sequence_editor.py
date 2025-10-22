"""
Sequence Editor Components

Widgets for editing sequences and their steps.
Redesigned with compact list view + detail panel layout.
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
    QGridLayout,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
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

        # Remove frame border - no visible border
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                margin: 0px;
                padding: 3px;
            }
        """)
        self.setMaximumHeight(160)  # More height to prevent text cutoff

        self.setup_ui()
        self.update_from_step()

    def setup_ui(self):
        # Main horizontal layout - scenes on left, parameters on right
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # Left side: Scene grid (directly in main layout, no wrapper widget)
        scenes_layout = QGridLayout()
        scenes_layout.setHorizontalSpacing(2)
        scenes_layout.setVerticalSpacing(2)
        scenes_layout.setContentsMargins(0, 0, 0, 0)

        # Create 8x5 grid of scene buttons
        for y in range(5):
            for x in range(8):
                btn = SceneButton(x, y)
                btn.setFixedSize(14, 14)  # Compact buttons
                btn.scene_toggled.connect(self.on_scene_toggled)
                self.scene_buttons[(x, y)] = btn
                scenes_layout.addWidget(btn, y, x)

        main_layout.addLayout(scenes_layout)

        # Right side: Parameters and controls (directly in main layout)
        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
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

        main_layout.addLayout(controls_layout)

        # Set proportional sizes - scenes get less space than controls
        main_layout.setStretch(0, 0)  # Scenes - natural width
        main_layout.setStretch(1, 1)  # Controls - stretch to fill

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
    """Widget for editing sequences - compact list + detail view."""

    def __init__(self, preset_index: t.Tuple[int, int], controller=None):
        super().__init__()
        self.preset_index = preset_index
        self.controller = controller
        self.sequence_steps: t.List[SequenceStep] = []
        self.current_step_index = 0
        self.current_step_widget: t.Optional[SequenceStepWidget] = None
        self.auto_update_enabled = True  # Auto-update during playback

        self.setup_ui()
        self.load_sequence()
        
        # Connect to controller's step change callback if available
        if self.controller and hasattr(self.controller, 'sequence_ctrl'):
            original_callback = self.controller.sequence_ctrl.on_step_change
            
            def wrapped_callback(scenes):
                if original_callback:
                    original_callback(scenes)
                # Only update if widget still exists and auto-update is enabled
                try:
                    if self.auto_update_enabled and not self.isHidden():
                        self._on_playback_step_change()
                except RuntimeError:
                    # Widget has been deleted, ignore
                    pass
            
            self.controller.sequence_ctrl.on_step_change = wrapped_callback

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Header with compact controls
        header_layout = QHBoxLayout()
        title = QLabel(f"Sequence [{self.preset_index[0]}, {self.preset_index[1]}]")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Auto-update checkbox
        self.auto_update_cb = QCheckBox("Auto-update")
        self.auto_update_cb.setChecked(True)
        self.auto_update_cb.setToolTip("Automatically show current step during playback")
        self.auto_update_cb.stateChanged.connect(self._on_auto_update_changed)
        header_layout.addWidget(self.auto_update_cb)
        
        # Loop checkbox
        self.loop_checkbox = QCheckBox("Loop")
        self.loop_checkbox.setChecked(True)
        self.loop_checkbox.stateChanged.connect(self.auto_save_sequence)
        header_layout.addWidget(self.loop_checkbox)
        
        layout.addLayout(header_layout)

        # Main horizontal split: Step list (left) | Step details (right)
        main_splitter = QHBoxLayout()
        main_splitter.setSpacing(5)
        
        # === LEFT: Step List ===
        left_panel = QFrame()
        left_panel.setMaximumWidth(200)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(3)
        
        # Step list header
        list_header = QHBoxLayout()
        list_label = QLabel("Steps")
        list_label.setStyleSheet("font-weight: bold; color: #cccccc;")
        list_header.addWidget(list_label)
        list_header.addStretch()
        left_layout.addLayout(list_header)
        
        # Step list widget
        self.step_list = QListWidget()
        self.step_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #cccccc;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #3f94e9;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #4a4a4a;
            }
        """)
        self.step_list.currentRowChanged.connect(self._on_step_selected)
        left_layout.addWidget(self.step_list)
        
        # Step list buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(3)
        
        add_btn = QPushButton("+")
        add_btn.setFixedSize(30, 25)
        add_btn.setToolTip("Add empty step")
        add_btn.clicked.connect(self.add_empty_step)
        btn_layout.addWidget(add_btn)
        
        add_active_btn = QPushButton("⊕")
        add_active_btn.setFixedSize(30, 25)
        add_active_btn.setToolTip("Add from active scenes")
        add_active_btn.clicked.connect(self.add_step_from_active_scenes)
        add_active_btn.setEnabled(self.controller is not None)
        btn_layout.addWidget(add_active_btn)
        
        btn_layout.addStretch()
        
        remove_btn = QPushButton("−")
        remove_btn.setFixedSize(30, 25)
        remove_btn.setToolTip("Remove selected step")
        remove_btn.clicked.connect(self.remove_current_step)
        btn_layout.addWidget(remove_btn)
        
        left_layout.addLayout(btn_layout)
        
        main_splitter.addWidget(left_panel)
        
        # === RIGHT: Step Detail Panel ===
        self.detail_panel = QFrame()
        self.detail_panel.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        self.detail_layout = QVBoxLayout(self.detail_panel)
        self.detail_layout.setContentsMargins(5, 5, 5, 5)
        
        # Placeholder message
        self.placeholder_label = QLabel("Select a step to edit")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.detail_layout.addWidget(self.placeholder_label)
        
        main_splitter.addWidget(self.detail_panel, 1)  # Give more space to detail panel
        
        layout.addLayout(main_splitter, 1)  # Main content takes most space
        
        # Bottom: Quick actions
        bottom_layout = QHBoxLayout()
        
        reload_btn = QPushButton("Reload")
        reload_btn.setFixedHeight(25)
        reload_btn.clicked.connect(self.load_sequence)
        bottom_layout.addWidget(reload_btn)
        
        bottom_layout.addStretch()
        
        layout.addLayout(bottom_layout)

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

        self.rebuild_step_list()
        
        # Select first step by default
        if self.step_list.count() > 0:
            self.step_list.setCurrentRow(0)

    def rebuild_step_list(self):
        """Rebuild the step list widget."""
        current_row = self.step_list.currentRow()
        self.step_list.clear()
        
        for i, step in enumerate(self.sequence_steps):
            display_text = f"{i+1}. {step.name}" if step.name else f"{i+1}. Step {i+1}"
            duration_text = f" ({step.duration:.1f}s)"
            scene_count = f" [{len(step.scenes)} scenes]" if step.scenes else " [empty]"
            
            item_text = display_text + duration_text + scene_count
            item = QListWidgetItem(item_text)
            self.step_list.addItem(item)
        
        # Restore selection or select first
        if current_row >= 0 and current_row < self.step_list.count():
            self.step_list.setCurrentRow(current_row)
        elif self.step_list.count() > 0:
            self.step_list.setCurrentRow(0)
    
    def _on_step_selected(self, row: int):
        """Handle step selection from list."""
        if row < 0 or row >= len(self.sequence_steps):
            return
        
        self.current_step_index = row
        self._show_step_details(row)
    
    def _show_step_details(self, step_index: int):
        """Show details for the specified step."""
        if step_index < 0 or step_index >= len(self.sequence_steps):
            return
        
        # Clear current widget
        if self.current_step_widget:
            self.current_step_widget.deleteLater()
            self.current_step_widget = None
        
        # Hide placeholder
        self.placeholder_label.hide()
        
        # Create new step widget
        step = self.sequence_steps[step_index]
        self.current_step_widget = SequenceStepWidget(step, step_index)
        self.current_step_widget.step_changed.connect(self._on_step_changed)
        self.current_step_widget.remove_step.connect(lambda: self.remove_step(step_index))
        self.current_step_widget.move_up.connect(lambda: self.move_step_up(step_index))
        self.current_step_widget.move_down.connect(lambda: self.move_step_down(step_index))
        
        # Update move button states
        self.current_step_widget.move_up_btn.setEnabled(step_index > 0)
        self.current_step_widget.move_down_btn.setEnabled(step_index < len(self.sequence_steps) - 1)
        
        self.detail_layout.addWidget(self.current_step_widget)
    
    def _on_step_changed(self):
        """Handle step details change."""
        self.rebuild_step_list()
        self.auto_save_sequence()
    
    def _on_auto_update_changed(self, state):
        """Handle auto-update checkbox change."""
        self.auto_update_enabled = state == Qt.CheckState.Checked.value
    
    def _on_playback_step_change(self):
        """Called during playback when step changes."""
        if not self.controller or not hasattr(self.controller, 'sequence_ctrl'):
            return
        
        # Check if this sequence is currently playing
        if self.controller.active_sequence != self.preset_index:
            return
        
        # Get current step index from controller
        current_step = self.controller.sequence_ctrl.current_step_index
        if 0 <= current_step < len(self.sequence_steps):
            # Update selection in list (will trigger detail update)
            try:
                self.step_list.setCurrentRow(current_step)
            except RuntimeError:
                # Widget has been deleted
                pass

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
        self.rebuild_step_list()
        self.auto_save_sequence()
        
        # Select the new step
        self.step_list.setCurrentRow(len(self.sequence_steps) - 1)

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
        self.rebuild_step_list()
        self.auto_save_sequence()
        
        # Select the new step
        self.step_list.setCurrentRow(len(self.sequence_steps) - 1)
    
    def remove_current_step(self):
        """Remove the currently selected step."""
        current_row = self.step_list.currentRow()
        if current_row >= 0:
            self.remove_step(current_row)
    
    def remove_step(self, step_index: int):
        """Remove a specific step."""
        if len(self.sequence_steps) <= 1:
            QMessageBox.warning(self, "Cannot Remove", "Cannot remove the last step.")
            return
        
        if 0 <= step_index < len(self.sequence_steps):
            del self.sequence_steps[step_index]
            self.rebuild_step_list()
            self.auto_save_sequence()

    def move_step_up(self, step_index: int):
        """Move step up."""
        if step_index > 0:
            self.sequence_steps[step_index], self.sequence_steps[step_index - 1] = (
                self.sequence_steps[step_index - 1],
                self.sequence_steps[step_index],
            )
            self.rebuild_step_list()
            self.auto_save_sequence()
            self.step_list.setCurrentRow(step_index - 1)

    def move_step_down(self, step_index: int):
        """Move step down."""
        if step_index < len(self.sequence_steps) - 1:
            self.sequence_steps[step_index], self.sequence_steps[step_index + 1] = (
                self.sequence_steps[step_index + 1],
                self.sequence_steps[step_index],
            )
            self.rebuild_step_list()
            self.auto_save_sequence()
            self.step_list.setCurrentRow(step_index + 1)
