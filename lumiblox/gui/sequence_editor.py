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
import qtawesome as qta

from lumiblox.controller.sequence_controller import SequenceStep, SequenceDurationUnit
from lumiblox.gui.ui_constants import (
    BUTTON_SIZE_MEDIUM,
    BUTTON_SIZE_TINY,
    BUTTON_SIZE_SMALL,
    BUTTON_STYLE,
    CHECKBOX_STYLE,
    EDIT_FIELD_STYLE,
    HEADER_LABEL_STYLE,
    INPUT_FIELD_HEIGHT_SMALL,
    INPUT_FIELD_WIDTH_SMALL,
    ICON_SIZE_SMALL,
)
from lumiblox.gui.widgets import SelectAllLineEdit, SceneButton

# Configuration constants
DEFAULT_STEP_DURATION = 2.0  # Default duration in seconds for new steps
DEFAULT_STEP_BARS = 4  # Default duration in bars for new steps

logger = logging.getLogger(__name__)


class SequenceStepWidget(QFrame):
    """Widget for editing a single sequence step."""

    step_changed = Signal()
    move_up = Signal(object)
    move_down = Signal(object)

    def __init__(self, step: SequenceStep, step_index: int):
        super().__init__()
        self.step = step
        self.step_index = step_index
        self.scene_buttons: t.Dict[t.Tuple[int, int], SceneButton] = {}
        self._unit_buttons: t.Dict[SequenceDurationUnit, QPushButton] = {}

        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                margin: 0px;
                padding: 3px;
            }
        """)

        # Set size policy to prevent vertical expansion
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.setup_ui()
        self.update_from_step()

    def setup_ui(self):
        # Main horizontal layout - buttons on left, content on right
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Left side: Move buttons (vertical)
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(5)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Move up button with icon
        self.move_up_btn = QPushButton()
        self.move_up_btn.setIcon(qta.icon("fa5s.chevron-up", color="#cccccc"))
        self.move_up_btn.setFixedSize(BUTTON_SIZE_TINY)
        self.move_up_btn.setToolTip("Move step up")
        self.move_up_btn.setStyleSheet(BUTTON_STYLE)
        self.move_up_btn.clicked.connect(lambda: self.move_up.emit(self))
        buttons_layout.addWidget(self.move_up_btn)

        # Move down button with icon
        self.move_down_btn = QPushButton()
        self.move_down_btn.setIcon(qta.icon("fa5s.chevron-down", color="#cccccc"))
        self.move_down_btn.setFixedSize(BUTTON_SIZE_TINY)
        self.move_down_btn.setToolTip("Move step down")
        self.move_down_btn.setStyleSheet(BUTTON_STYLE)
        self.move_down_btn.clicked.connect(lambda: self.move_down.emit(self))
        buttons_layout.addWidget(self.move_down_btn)

        buttons_layout.addStretch()
        main_layout.addLayout(buttons_layout)

        # Right side: Content (name, scenes, duration)
        content_layout = QVBoxLayout()

        # Step name (editable label style)
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.step.name)
        self.name_edit.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #e0e0e0;
                font-size: 14px;
                font-weight: bold;
                padding: 2px;
            }
            QLineEdit:focus {
                background: #3a3a3a;
                border: 1px solid #4a9eff;
                border-radius: 2px;
            }
        """)
        self.name_edit.setPlaceholderText(f"Step {self.step_index + 1}")
        self.name_edit.textChanged.connect(self.on_step_changed)
        content_layout.addWidget(self.name_edit)

        # Scene grid section - aligned to top
        scenes_layout = QGridLayout()
        scenes_layout.setHorizontalSpacing(2)
        scenes_layout.setVerticalSpacing(2)
        scenes_layout.setContentsMargins(0, 0, 0, 0)
        scenes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Create 8x5 grid of scene buttons
        for y in range(5):
            for x in range(8):
                btn = SceneButton(x, y)
                btn.setFixedSize(BUTTON_SIZE_TINY)
                btn.scene_toggled.connect(self.on_scene_toggled)
                self.scene_buttons[(x, y)] = btn
                scenes_layout.addWidget(btn, y, x)

        content_layout.addLayout(scenes_layout)

        # Duration section - compact design
        duration_layout = QHBoxLayout()
        duration_layout.setSpacing(6)
        duration_layout.setContentsMargins(0, 5, 0, 0)

        # Minus button
        minus_btn = QPushButton()
        minus_btn.setIcon(qta.icon("fa5s.minus", color="white"))
        minus_btn.setIconSize(ICON_SIZE_SMALL)
        minus_btn.setFixedSize(BUTTON_SIZE_SMALL)
        minus_btn.setStyleSheet(BUTTON_STYLE)
        minus_btn.clicked.connect(self.decrease_duration)
        duration_layout.addWidget(minus_btn)

        # Duration input field (editable)
        self.duration_input = SelectAllLineEdit()
        self.duration_input.setFixedWidth(INPUT_FIELD_WIDTH_SMALL)
        self.duration_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.duration_input.setStyleSheet(EDIT_FIELD_STYLE)
        self.duration_input.setFixedHeight(INPUT_FIELD_HEIGHT_SMALL)
        self.duration_input.textChanged.connect(self.on_duration_text_changed)
        self.duration_input.editingFinished.connect(self.on_duration_editing_finished)
        duration_layout.addWidget(self.duration_input)

        # Plus button
        plus_btn = QPushButton()
        plus_btn.setFixedSize(BUTTON_SIZE_SMALL)
        plus_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        plus_btn.setIconSize(ICON_SIZE_SMALL)
        plus_btn.setStyleSheet(BUTTON_STYLE)
        plus_btn.clicked.connect(self.increase_duration)
        duration_layout.addWidget(plus_btn)

        seconds_btn = QPushButton("Sec")
        seconds_btn.setCheckable(True)
        seconds_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        seconds_btn.setStyleSheet(BUTTON_STYLE)
        seconds_btn.clicked.connect(
            lambda: self._set_duration_unit(SequenceDurationUnit.SECONDS)
        )
        duration_layout.addWidget(seconds_btn)
        self._unit_buttons[SequenceDurationUnit.SECONDS] = seconds_btn

        bars_btn = QPushButton("Bars")
        bars_btn.setCheckable(True)
        bars_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        bars_btn.setStyleSheet(BUTTON_STYLE)
        bars_btn.clicked.connect(
            lambda: self._set_duration_unit(SequenceDurationUnit.BARS)
        )
        duration_layout.addWidget(bars_btn)
        self._unit_buttons[SequenceDurationUnit.BARS] = bars_btn

        duration_layout.addStretch()
        content_layout.addLayout(duration_layout)

        main_layout.addLayout(content_layout)

    def update_from_step(self):
        """Update widget from step data."""
        self.name_edit.setText(self.step.name)
        self._refresh_duration_input()
        self._update_unit_buttons()

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
        """Decrease duration value using the active unit."""
        current = self.step.duration
        if self.step.duration_unit == SequenceDurationUnit.BARS:
            new_value = max(1.0, current - 1)
        else:
            new_value = max(0.1, current - 0.5)
        self.step.duration = new_value
        self._refresh_duration_input()
        self.step_changed.emit()

    def increase_duration(self):
        """Increase duration value using the active unit."""
        current = self.step.duration
        if self.step.duration_unit == SequenceDurationUnit.BARS:
            new_value = min(512.0, current + 1)
        else:
            new_value = min(3600.0, current + 0.5)
        self.step.duration = new_value
        self._refresh_duration_input()
        self.step_changed.emit()

    def on_duration_text_changed(self):
        """Called when duration text is being changed."""
        # Optional: Add real-time validation visual feedback here
        pass

    def on_duration_editing_finished(self):
        """Called when user finishes editing duration text."""
        try:
            text = self.duration_input.text().strip()
            if self.step.duration_unit == SequenceDurationUnit.BARS:
                value = int(round(float(text)))
                if value < 1:
                    value = 1
                elif value > 512:
                    value = 512
                self.step.duration = float(value)
                self.duration_input.setText(str(value))
            else:
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
            self._refresh_duration_input()
            QMessageBox.warning(
                self,
                "Invalid Duration",
                "Please enter a valid duration value.",
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
        return [coord for coord, btn in self.scene_buttons.items() if btn.is_active]

    def _refresh_duration_input(self) -> None:
        if self.step.duration_unit == SequenceDurationUnit.BARS:
            value = max(1, int(round(self.step.duration)))
            self.step.duration = float(value)
            self.duration_input.setText(str(value))
        else:
            self.duration_input.setText(f"{self.step.duration:.1f}")

    def _update_unit_buttons(self) -> None:
        for unit, button in self._unit_buttons.items():
            button.setChecked(unit == self.step.duration_unit)

    def _set_duration_unit(self, unit: SequenceDurationUnit) -> None:
        if self.step.duration_unit == unit:
            self._update_unit_buttons()
            return

        if unit == SequenceDurationUnit.BARS:
            if self.step.duration_unit == SequenceDurationUnit.SECONDS:
                converted = round(self.step.duration)
                if converted < 1:
                    converted = DEFAULT_STEP_BARS
                self.step.duration = float(converted)
            else:
                self.step.duration = max(1.0, self.step.duration)
        else:
            new_value = max(0.1, float(self.step.duration))
            if new_value > 3600.0:
                new_value = 3600.0
            self.step.duration = new_value

        self.step.duration_unit = unit
        self._update_unit_buttons()
        self._refresh_duration_input()
        self.step_changed.emit()


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
        if self.controller and hasattr(self.controller, "sequence_ctrl"):
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
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header with compact controls
        header_layout = QHBoxLayout()

        # Tiny reload button with icon
        reload_btn = QPushButton()
        reload_btn.setIcon(qta.icon("fa5s.sync-alt", color="#cccccc"))
        reload_btn.setFixedSize(BUTTON_SIZE_TINY)
        reload_btn.setToolTip("Reload sequence from file")
        reload_btn.setStyleSheet(BUTTON_STYLE)
        reload_btn.clicked.connect(self.load_sequence)
        header_layout.addWidget(reload_btn)

        # Auto-update checkbox
        self.auto_update_cb = QCheckBox("Auto-update")
        self.auto_update_cb.setChecked(True)
        self.auto_update_cb.setStyleSheet(CHECKBOX_STYLE)
        self.auto_update_cb.setToolTip(
            "Automatically show current step during playback"
        )
        self.auto_update_cb.stateChanged.connect(self._on_auto_update_changed)
        header_layout.addWidget(self.auto_update_cb)

        # Loop checkbox
        self.loop_checkbox = QCheckBox("Loop")
        self.loop_checkbox.setChecked(True)
        self.loop_checkbox.setStyleSheet(CHECKBOX_STYLE)
        self.loop_checkbox.stateChanged.connect(self.auto_save_sequence)
        header_layout.addWidget(self.loop_checkbox)

        header_layout.addStretch()

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
                border: none;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(3)

        # Step list header
        list_header = QHBoxLayout()
        list_header.setAlignment(Qt.AlignmentFlag.AlignTop)
        list_label = QLabel("Steps")
        list_label.setStyleSheet(HEADER_LABEL_STYLE)
        list_header.addWidget(list_label)
        list_header.addStretch()
        left_layout.addLayout(list_header)

        # Step list widget
        self.step_list = QListWidget()
        self.step_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: none;
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

        # Step list buttons - aligned to top
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(3)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        add_btn = QPushButton()
        add_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        add_btn.setIconSize(ICON_SIZE_SMALL)
        add_btn.setFixedSize(BUTTON_SIZE_SMALL)
        add_btn.setToolTip("Add empty step")
        add_btn.setStyleSheet(BUTTON_STYLE)
        add_btn.clicked.connect(self.add_empty_step)
        btn_layout.addWidget(add_btn)

        add_active_btn = QPushButton()
        add_active_btn.setIcon(qta.icon("fa5s.play-circle", color="white"))
        add_active_btn.setFixedSize(BUTTON_SIZE_SMALL)
        add_active_btn.setIconSize(ICON_SIZE_SMALL)
        add_active_btn.setToolTip("Add from active scenes")
        add_active_btn.setStyleSheet(BUTTON_STYLE)
        add_active_btn.clicked.connect(self.add_step_from_active_scenes)
        add_active_btn.setEnabled(self.controller is not None)
        btn_layout.addWidget(add_active_btn)

        btn_layout.addStretch()

        remove_btn = QPushButton()
        remove_btn.setIcon(qta.icon("fa5s.minus", color="white"))
        remove_btn.setFixedSize(BUTTON_SIZE_SMALL)
        remove_btn.setToolTip("Remove selected step")
        remove_btn.setStyleSheet(BUTTON_STYLE)
        remove_btn.clicked.connect(self.remove_current_step)
        btn_layout.addWidget(remove_btn)

        left_layout.addLayout(btn_layout)

        main_splitter.addWidget(left_panel)

        # === RIGHT: Step Detail Panel ===
        self.detail_panel = QFrame()
        self.detail_panel.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
        self.detail_layout = QVBoxLayout(self.detail_panel)
        self.detail_layout.setContentsMargins(5, 5, 5, 5)
        self.detail_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        # Placeholder message - aligned to top
        self.placeholder_label = QLabel("Select a step to edit")
        self.placeholder_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.placeholder_label.setStyleSheet(HEADER_LABEL_STYLE)
        self.detail_layout.addWidget(self.placeholder_label)
        self.detail_layout.addStretch()  # Push placeholder to top

        main_splitter.addWidget(self.detail_panel, 1)  # Give more space to detail panel

        layout.addLayout(main_splitter, 1)  # Main content takes most space

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
            display_text = (
                f"{i + 1}. {step.name}" if step.name else f"{i + 1}. Step {i + 1}"
            )
            if step.duration_unit == SequenceDurationUnit.BARS:
                duration_text = f" ({int(step.duration)} bars)"
            else:
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

        # Clear all items from layout
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Clear reference
        self.current_step_widget = None

        # Add stretch at top to push content to bottom
        self.detail_layout.addStretch()

        # Create new step widget
        step = self.sequence_steps[step_index]
        self.current_step_widget = SequenceStepWidget(step, step_index)
        self.current_step_widget.step_changed.connect(self._on_step_changed)
        self.current_step_widget.move_up.connect(lambda: self.move_step_up(step_index))
        self.current_step_widget.move_down.connect(
            lambda: self.move_step_down(step_index)
        )

        # Update move button states
        self.current_step_widget.move_up_btn.setEnabled(step_index > 0)
        self.current_step_widget.move_down_btn.setEnabled(
            step_index < len(self.sequence_steps) - 1
        )

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
        if not self.controller or not hasattr(self.controller, "sequence_ctrl"):
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

    def _current_duration_unit(self) -> SequenceDurationUnit:
        if 0 <= self.current_step_index < len(self.sequence_steps):
            return self.sequence_steps[self.current_step_index].duration_unit
        return SequenceDurationUnit.SECONDS

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
        unit = self._current_duration_unit()
        default_duration = (
            float(DEFAULT_STEP_BARS)
            if unit == SequenceDurationUnit.BARS
            else DEFAULT_STEP_DURATION
        )
        step = SequenceStep(
            scenes=[],
            duration=default_duration,
            name=f"Step {len(self.sequence_steps) + 1}",
            duration_unit=unit,
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

        unit = self._current_duration_unit()
        duration = (
            float(DEFAULT_STEP_BARS)
            if unit == SequenceDurationUnit.BARS
            else DEFAULT_STEP_DURATION
        )
        step = SequenceStep(
            scenes=active_scenes,
            duration=duration,
            name=f"Step {len(self.sequence_steps) + 1}",
            duration_unit=unit,
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
