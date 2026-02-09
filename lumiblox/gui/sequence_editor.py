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
    QSpinBox,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

from lumiblox.controller.sequence_controller import SequenceStep, SequenceDurationUnit
from lumiblox.gui.ui_constants import (
    BUTTON_SIZE_MEDIUM,
    BUTTON_SIZE_TINY,
    BUTTON_SIZE_SMALL,
    BUTTON_STYLE,
    CHECKBOX_STYLE,
    COLOR_TEXT_DIM,
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
BAR_DURATION_INCREMENT = 0.25
MIN_BAR_DURATION = 0.25
MAX_BAR_DURATION = 512.0


def quantize_bar_duration(value: float) -> float:
    """Snap a bar duration to the nearest quarter-bar within valid bounds."""
    steps = max(1, int(round(value / BAR_DURATION_INCREMENT)))
    quantized = steps * BAR_DURATION_INCREMENT
    return min(MAX_BAR_DURATION, quantized)


def format_bar_duration(value: float) -> str:
    """Format a bar duration without trailing zeros."""
    quantized = quantize_bar_duration(value)
    if float(quantized).is_integer():
        return str(int(quantized))
    return f"{quantized:.2f}".rstrip("0").rstrip(".")

logger = logging.getLogger(__name__)


class SequenceStepWidget(QFrame):
    """Widget for editing a single sequence step."""

    step_changed = Signal()

    def __init__(self, step: SequenceStep, step_index: int):
        super().__init__()
        self.step = step
        self.step_index = step_index
        self.scene_buttons: t.Dict[t.Tuple[int, int], SceneButton] = {}
        self._unit_buttons: t.Dict[SequenceDurationUnit, QPushButton] = {}
        self.sequence_controls_layout: t.Optional[QHBoxLayout] = None

        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                margin: 0px;
                padding: 2px;
            }
        """)

        # Set size policy to prevent vertical expansion
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.setup_ui()
        self.update_from_step()

    def setup_ui(self):
        # Main horizontal layout - content only
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 4)
        main_layout.setSpacing(10)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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

        controls_container = QWidget()
        self.sequence_controls_layout = QHBoxLayout(controls_container)
        self.sequence_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.sequence_controls_layout.setSpacing(6)
        content_layout.addWidget(controls_container)

        # Scene grid section - aligned to top
        scenes_layout = QGridLayout()
        scenes_layout.setHorizontalSpacing(2)
        scenes_layout.setVerticalSpacing(2)
        scenes_layout.setContentsMargins(0, 0, 0, 0)
        scenes_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Create scene buttons for all pages (e.g. 2 pages × 5 rows = 10 rows)
        from lumiblox.common.config import ROWS_PER_PAGE, NUM_SCENE_PAGES, GUI_SCENE_COLUMNS
        total_rows = ROWS_PER_PAGE * NUM_SCENE_PAGES
        for y in range(total_rows):
            # Calculate grid row with space for dividers between pages
            page_idx = y // ROWS_PER_PAGE
            grid_row = y + page_idx  # Offset by number of dividers above
            for x in range(GUI_SCENE_COLUMNS):
                btn = SceneButton(x, y)
                btn.scene_toggled.connect(self.on_scene_toggled)
                self.scene_buttons[(x, y)] = btn
                scenes_layout.addWidget(btn, grid_row, x)

        # Add visual dividers between pages
        for page in range(1, NUM_SCENE_PAGES):
            divider_row = page * ROWS_PER_PAGE + (page - 1)
            divider = QLabel(f"Page {page + 1}")
            divider.setFixedHeight(14)
            divider.setAlignment(Qt.AlignmentFlag.AlignCenter)
            divider.setStyleSheet("color: #666666; font-size: 9px; background: transparent; border-top: 1px solid #555555; padding-top: 1px;")
            scenes_layout.addWidget(divider, divider_row, 0, 1, GUI_SCENE_COLUMNS)

        content_layout.addLayout(scenes_layout)

        # Duration section - compact design
        duration_layout = QHBoxLayout()
        duration_layout.setSpacing(6)
        duration_layout.setContentsMargins(0, 3, 0, 0)

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
        seconds_btn.setFixedSize(BUTTON_SIZE_MEDIUM.width(), BUTTON_SIZE_SMALL.height())
        seconds_btn.setStyleSheet(BUTTON_STYLE)
        seconds_btn.clicked.connect(
            lambda: self._set_duration_unit(SequenceDurationUnit.SECONDS)
        )
        duration_layout.addWidget(seconds_btn)
        self._unit_buttons[SequenceDurationUnit.SECONDS] = seconds_btn

        bars_btn = QPushButton("Bars")
        bars_btn.setCheckable(True)
        bars_btn.setFixedSize(BUTTON_SIZE_MEDIUM.width(), BUTTON_SIZE_SMALL.height())
        bars_btn.setStyleSheet(BUTTON_STYLE)
        bars_btn.clicked.connect(
            lambda: self._set_duration_unit(SequenceDurationUnit.BARS)
        )
        duration_layout.addWidget(bars_btn)
        self._unit_buttons[SequenceDurationUnit.BARS] = bars_btn

        duration_layout.addStretch()
        content_layout.addLayout(duration_layout)

        main_layout.addLayout(content_layout)

    def set_sequence_controls_widget(self, widget: QWidget) -> None:
        if not self.sequence_controls_layout:
            return
        while self.sequence_controls_layout.count():
            item = self.sequence_controls_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.sequence_controls_layout.addWidget(widget)

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
            normalized = quantize_bar_duration(current)
            new_value = quantize_bar_duration(normalized - BAR_DURATION_INCREMENT)
        else:
            new_value = max(0.1, current - 0.5)
        self.step.duration = new_value
        self._refresh_duration_input()
        self.step_changed.emit()

    def increase_duration(self):
        """Increase duration value using the active unit."""
        current = self.step.duration
        if self.step.duration_unit == SequenceDurationUnit.BARS:
            normalized = quantize_bar_duration(current)
            new_value = quantize_bar_duration(normalized + BAR_DURATION_INCREMENT)
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
            text = self.duration_input.text().strip().replace(",", ".")
            if self.step.duration_unit == SequenceDurationUnit.BARS:
                value = float(text)
                quantized = quantize_bar_duration(value)
                self.step.duration = quantized
                self.duration_input.setText(format_bar_duration(quantized))
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
            quantized = quantize_bar_duration(self.step.duration)
            self.step.duration = quantized
            self.duration_input.setText(format_bar_duration(quantized))
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
                if converted < MIN_BAR_DURATION:
                    converted = DEFAULT_STEP_BARS
                self.step.duration = float(converted)
            else:
                self.step.duration = max(MIN_BAR_DURATION, self.step.duration)
            self.step.duration = quantize_bar_duration(self.step.duration)
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

    followup_edit_mode_changed = Signal(bool)
    followup_candidates_changed = Signal(list)

    def __init__(self, preset_index: t.Tuple[int, int], controller=None):
        super().__init__()
        self.preset_index = preset_index
        self.controller = controller
        self.sequence_steps: t.List[SequenceStep] = []
        self.current_step_index = 0
        self.current_step_widget: t.Optional[SequenceStepWidget] = None
        self.auto_update_enabled = True  # Auto-update during playback
        self.next_sequence_candidates: t.List[t.Tuple[int, int]] = []
        self.next_sequence_jump_edit_mode = False
        self.loop_count = 1

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

        header_layout.addStretch()

        layout.addLayout(header_layout)

        self.sequence_controls_widget = QWidget()
        self.sequence_controls_widget.setStyleSheet("border: none;")
        sequence_controls_layout = QHBoxLayout(self.sequence_controls_widget)
        sequence_controls_layout.setContentsMargins(0, 0, 0, 0)
        sequence_controls_layout.setSpacing(6)

        self.loop_checkbox = QCheckBox("Always Loop")
        self.loop_checkbox.setChecked(True)
        self.loop_checkbox.setStyleSheet(CHECKBOX_STYLE)
        self.loop_checkbox.stateChanged.connect(self._on_loop_changed)
        sequence_controls_layout.addWidget(self.loop_checkbox)

        self.loop_count_spinbox = QSpinBox()
        self.loop_count_spinbox.setRange(1, 999)
        self.loop_count_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self.loop_count_spinbox.setFixedWidth(60)
        self.loop_count_spinbox.setFixedHeight(20)
        self.loop_count_spinbox.setValue(self.loop_count)
        self.loop_count_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #ffffff;
                padding-right: 14px;
                padding-left: 4px;
                padding-top: 0px;
                padding-bottom: 0px;
                font-size: 10px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                subcontrol-origin: padding;
                width: 12px;
                border-left: 1px solid #555555;
                background: #3c3c3c;
            }
            QSpinBox::up-button {
                subcontrol-position: right top;
                height: 9px;
            }
            QSpinBox::down-button {
                subcontrol-position: right bottom;
                height: 9px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #4a4a4a;
            }
        """)
        self.loop_count_spinbox.valueChanged.connect(self._on_loop_count_changed)
        sequence_controls_layout.addWidget(self.loop_count_spinbox)

        loops_label = QLabel("loops")
        loops_label.setStyleSheet(HEADER_LABEL_STYLE)
        sequence_controls_layout.addWidget(loops_label)

        self.followup_toggle_btn = QPushButton("Select")
        self.followup_toggle_btn.setCheckable(True)
        self.followup_toggle_btn.setFixedHeight(20)
        self.followup_toggle_btn.setToolTip(
            "Toggle follow-up selection mode for the sequence grid below"
        )
        self.followup_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                font-size: 10px;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:checked {
                background-color: #0078d4;
                border: 1px solid #005a9e;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
                border: 1px solid #444444;
            }
        """)
        self.followup_toggle_btn.clicked.connect(self._on_followup_toggle_clicked)
        sequence_controls_layout.addWidget(self.followup_toggle_btn)

        followup_label = QLabel("Next")
        followup_label.setStyleSheet(HEADER_LABEL_STYLE)
        sequence_controls_layout.addWidget(followup_label)

        self.followup_display = QLabel("")
        self.followup_display.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 10px;"
        )
        sequence_controls_layout.addWidget(self.followup_display)

        sequence_controls_layout.addStretch()

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
                outline: none;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #333333;
            }
            QListWidget::item:selected {
                background-color: #3f94e9;
                color: white;
                border: none;
                outline: none;
            }
            QListWidget::item:hover {
                background-color: #4a4a4a;
            }
            QListWidget::item:selected:hover {
                background-color: #4aa3ff;
                color: white;
            }
            QListWidget::item:focus {
                outline: none;
            }
        """)
        self.step_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.step_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.step_list.setDragEnabled(True)
        self.step_list.setAcceptDrops(True)
        self.step_list.setDropIndicatorShown(True)
        self.step_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.step_list.currentRowChanged.connect(self._on_step_selected)
        self.step_list.model().rowsMoved.connect(self._on_steps_reordered)
        left_layout.addWidget(self.step_list)

        # Step list buttons - aligned to top
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(3)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        btn_layout.setContentsMargins(0, 0, 0, 0)

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

        set_active_btn = QPushButton()
        set_active_btn.setIcon(qta.icon("fa5s.file-import", color="white"))
        set_active_btn.setFixedSize(BUTTON_SIZE_SMALL)
        set_active_btn.setIconSize(ICON_SIZE_SMALL)
        set_active_btn.setToolTip("Set current step scenes from active")
        set_active_btn.setStyleSheet(BUTTON_STYLE)
        set_active_btn.clicked.connect(self.set_current_step_from_active_scenes)
        set_active_btn.setEnabled(self.controller is not None)
        btn_layout.addWidget(set_active_btn)

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
        self.detail_layout.setContentsMargins(5, 5, 5, 2)
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
        self.loop_checkbox.blockSignals(True)
        self.loop_checkbox.setChecked(loop_setting)
        self.loop_checkbox.blockSignals(False)
        self.loop_count = self.controller.sequence_ctrl.get_loop_count(
            self.preset_index
        )
        self.loop_count_spinbox.blockSignals(True)
        self.loop_count_spinbox.setValue(self.loop_count)
        self.loop_count_spinbox.blockSignals(False)
        self.next_sequence_candidates = self.controller.sequence_ctrl.get_followup_sequences(
            self.preset_index
        )
        self._update_followup_toggle_enabled()
        self._refresh_followup_display()
        self._emit_followup_candidates()

        self.rebuild_step_list()

        # Select first step by default
        if self.step_list.count() > 0:
            self.step_list.setCurrentRow(0)

    def rebuild_step_list(self):
        """Rebuild the step list widget."""
        current_row = self.step_list.currentRow()
        self.step_list.clear()

        for i, step in enumerate(self.sequence_steps):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, step)
            self._update_step_list_item_text(item, step, i)
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
        self._preview_step(row)

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
        self.current_step_widget.set_sequence_controls_widget(
            self.sequence_controls_widget
        )
        self.current_step_widget.step_changed.connect(self._on_step_changed)

        self.detail_layout.addWidget(self.current_step_widget)

    def _on_step_changed(self):
        """Handle step details change."""
        self.rebuild_step_list()
        self.auto_save_sequence()
        self._preview_step(self.current_step_index)

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

    def _get_active_scenes_or_warn(self) -> t.Optional[t.List[t.Tuple[int, int]]]:
        if not self.controller:
            return None

        active_scenes = list(self.controller.scene_ctrl.get_active_scenes())
        if active_scenes:
            return active_scenes

        QMessageBox.information(
            self,
            "No Active Scenes",
            "No scenes are currently active. Activate some scenes on the launchpad first.",
        )
        return None

    def save_sequence(self):
        """Save sequence to sequence controller."""
        if not self.controller:
            return

        try:
            loop_enabled = self.loop_checkbox.isChecked()
            self.controller.sequence_ctrl.save_sequence(
                self.preset_index,
                self.sequence_steps,
                loop_enabled,
                loop_count=self.loop_count,
                next_sequences=self.next_sequence_candidates,
            )
            if getattr(self.controller, "on_sequence_saved", None):
                self.controller.on_sequence_saved()
        except Exception as e:
            logger.error(f"Failed to save sequence: {e}")

    def auto_save_sequence(self):
        """Auto-save sequence after changes."""
        self.save_sequence()

    def _on_loop_changed(self) -> None:
        self._update_followup_toggle_enabled()
        self.auto_save_sequence()

    def _on_loop_count_changed(self, value: int) -> None:
        self.loop_count = max(1, int(value))
        self.auto_save_sequence()

    def _update_followup_toggle_enabled(self) -> None:
        loop_enabled = self.loop_checkbox.isChecked()
        self.followup_toggle_btn.setEnabled(not loop_enabled)
        self.loop_count_spinbox.setEnabled(not loop_enabled)
        if loop_enabled and self.next_sequence_jump_edit_mode:
            self._set_followup_edit_mode(False)

    def _on_followup_toggle_clicked(self) -> None:
        self._set_followup_edit_mode(self.followup_toggle_btn.isChecked())

    def _set_followup_edit_mode(self, enabled: bool) -> None:
        if self.next_sequence_jump_edit_mode == enabled:
            self.followup_toggle_btn.setChecked(enabled)
            return
        self.next_sequence_jump_edit_mode = enabled
        self.followup_toggle_btn.setChecked(enabled)
        self.followup_edit_mode_changed.emit(enabled)

    def toggle_followup_candidate(self, coords: t.Tuple[int, int]) -> None:
        if self.loop_checkbox.isChecked():
            return
        if coords == self.preset_index:
            return
        if coords in self.next_sequence_candidates:
            self.next_sequence_candidates = [
                candidate
                for candidate in self.next_sequence_candidates
                if candidate != coords
            ]
        else:
            self.next_sequence_candidates.append(coords)
        self._refresh_followup_display()
        self._emit_followup_candidates()
        self.auto_save_sequence()

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
        active_scenes = self._get_active_scenes_or_warn()
        if not active_scenes:
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

    def set_current_step_from_active_scenes(self):
        """Replace the current step's scenes with the active controller scenes."""
        if not (0 <= self.current_step_index < len(self.sequence_steps)):
            return

        active_scenes = self._get_active_scenes_or_warn()
        if not active_scenes:
            return

        step = self.sequence_steps[self.current_step_index]
        step.scenes = active_scenes

        if self.current_step_widget:
            self.current_step_widget.update_from_step()

        self.rebuild_step_list()
        self.auto_save_sequence()
        self._preview_step(self.current_step_index)

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

    def _update_step_list_item_text(
        self, item: QListWidgetItem, step: SequenceStep, index: int
    ) -> None:
        display_text = (
            f"{index + 1}. {step.name}" if step.name else f"{index + 1}. Step {index + 1}"
        )
        if step.duration_unit == SequenceDurationUnit.BARS:
            duration_text = f" ({format_bar_duration(step.duration)} bars)"
        else:
            duration_text = f" ({step.duration:.1f}s)"
        scene_count = f" [{len(step.scenes)} scenes]" if step.scenes else " [empty]"

        item_text = display_text + duration_text + scene_count
        item.setText(item_text)

    def _sync_steps_from_list(self) -> None:
        steps: t.List[SequenceStep] = []
        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            step = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(step, SequenceStep):
                steps.append(step)
        if steps:
            self.sequence_steps = steps

        for i in range(self.step_list.count()):
            item = self.step_list.item(i)
            step = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(step, SequenceStep):
                self._update_step_list_item_text(item, step, i)

    def _on_steps_reordered(self, parent, start: int, end: int, destination, row: int) -> None:
        self._sync_steps_from_list()

        if row > start:
            new_row = row - (end - start + 1)
        else:
            new_row = row

        new_row = max(0, min(new_row, self.step_list.count() - 1))
        self.step_list.setCurrentRow(new_row)
        self.auto_save_sequence()

    def _preview_step(self, step_index: int) -> None:
        """Trigger live preview for the specified step."""
        if (
            not self.controller
            or not hasattr(self.controller, "scene_ctrl")
            or step_index < 0
            or step_index >= len(self.sequence_steps)
        ):
            return

        step = self.sequence_steps[step_index]
        try:
            self.controller.scene_ctrl.activate_scenes(step.scenes, controlled=True)
        except Exception as exc:
            logger.warning(f"Failed to preview step {step_index}: {exc}")

    def _refresh_followup_display(self) -> None:
        text = "; ".join(
            f"{coords[0]},{coords[1]}" for coords in self.next_sequence_candidates
        )
        self.followup_display.setText(text if text else "None")

    def _emit_followup_candidates(self) -> None:
        self.followup_candidates_changed.emit(list(self.next_sequence_candidates))
