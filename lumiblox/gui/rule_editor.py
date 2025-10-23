"""
Rule Editor Dialog

UI for creating and editing pilot automation rules.
"""

import logging
from typing import Optional
import qtawesome as qta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
    QCheckBox,
    QWidget,
    QFormLayout,
)

from lumiblox.pilot.pilot_preset import (
    PilotPreset,
    AutomationRule,
    RuleCondition,
    RuleAction,
    SequenceChoice,
    ConditionType,
    ActionType,
)
from lumiblox.gui.ui_constants import (
    BUTTON_SIZE_MEDIUM,
    BUTTON_STYLE,
)

logger = logging.getLogger(__name__)


class SequenceChoiceWidget(QWidget):
    """Widget for editing a weighted sequence choice."""

    remove_requested = Signal()

    def __init__(self, choice: Optional[SequenceChoice] = None):
        super().__init__()
        self.setup_ui(choice)

    def setup_ui(self, choice: Optional[SequenceChoice]) -> None:
        """Set up UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(QLabel("Sequence:"))

        # Sequence text input (format: "x.y" or "x")
        self.sequence_edit = QLineEdit()
        self.sequence_edit.setPlaceholderText("e.g. 0.0 or 1.2")
        self.sequence_edit.setFixedWidth(80)
        if choice:
            self.sequence_edit.setText(str(choice.sequence_index))
        else:
            self.sequence_edit.setText("0.0")
        layout.addWidget(self.sequence_edit)

        layout.addSpacing(10)
        layout.addWidget(QLabel("Weight:"))

        # Weight spinbox with external buttons
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setMinimum(0.0)
        self.weight_spin.setMaximum(1.0)
        self.weight_spin.setSingleStep(0.1)
        self.weight_spin.setDecimals(2)
        self.weight_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.weight_spin.setFixedWidth(60)
        if choice:
            self.weight_spin.setValue(choice.weight)
        else:
            self.weight_spin.setValue(1.0)
        layout.addWidget(self.weight_spin)

        weight_minus_btn = QPushButton()
        weight_minus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        weight_minus_btn.setIcon(qta.icon("fa5s.minus", color="white"))
        weight_minus_btn.setStyleSheet(BUTTON_STYLE)
        weight_minus_btn.clicked.connect(lambda: self.weight_spin.stepDown())
        layout.addWidget(weight_minus_btn)

        weight_plus_btn = QPushButton()
        weight_plus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        weight_plus_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        weight_plus_btn.setStyleSheet(BUTTON_STYLE)
        weight_plus_btn.clicked.connect(lambda: self.weight_spin.stepUp())
        layout.addWidget(weight_plus_btn)

        weight_plus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        weight_plus_btn.clicked.connect(lambda: self.weight_spin.stepUp())
        layout.addWidget(weight_plus_btn)

        layout.addStretch()

        remove_btn = QPushButton("✕")
        remove_btn.setFixedWidth(30)
        remove_btn.clicked.connect(self.remove_requested.emit)
        layout.addWidget(remove_btn)

    def get_choice(self) -> SequenceChoice:
        """Get the sequence choice."""
        return SequenceChoice(
            sequence_index=self.sequence_edit.text().strip() or "0.0",
            weight=self.weight_spin.value(),
        )


class RuleEditorDialog(QDialog):
    """Dialog for editing an automation rule."""

    def __init__(self, rule: Optional[AutomationRule] = None, parent=None):
        super().__init__(parent)
        self.rule = rule
        self.sequence_widgets: list[SequenceChoiceWidget] = []

        self.setWindowTitle("Edit Rule" if rule else "New Rule")
        self.setMinimumWidth(500)
        self.setup_ui()

        if rule:
            self.load_rule(rule)

    def setup_ui(self) -> None:
        """Set up UI."""
        layout = QVBoxLayout(self)

        # Basic info
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Rule name")
        basic_layout.addRow("Name:", self.name_edit)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        basic_layout.addRow("", self.enabled_check)

        layout.addWidget(basic_group)

        # Condition
        condition_group = QGroupBox("Condition")
        condition_layout = QFormLayout(condition_group)

        self.condition_type_combo = QComboBox()
        self.condition_type_combo.addItem(
            "After phrase type duration", ConditionType.AFTER_PHRASE_TYPE.value
        )
        self.condition_type_combo.addItem(
            "On phrase change", ConditionType.ON_PHRASE_CHANGE.value
        )
        self.condition_type_combo.currentIndexChanged.connect(self._update_condition_ui)
        condition_layout.addRow("Type:", self.condition_type_combo)

        self.phrase_type_combo = QComboBox()
        self.phrase_type_combo.addItem("Any", "")
        self.phrase_type_combo.addItem("Body", "body")
        self.phrase_type_combo.addItem("Breakdown", "breakdown")
        condition_layout.addRow("Phrase Type:", self.phrase_type_combo)

        # Duration bars with external buttons
        bars_widget = QWidget()
        bars_layout = QHBoxLayout(bars_widget)
        bars_layout.setContentsMargins(0, 0, 0, 0)
        bars_layout.setSpacing(4)

        self.duration_bars_spin = QSpinBox()
        self.duration_bars_spin.setMinimum(0)
        self.duration_bars_spin.setMaximum(999)
        self.duration_bars_spin.setSpecialValueText("(not used)")
        self.duration_bars_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.duration_bars_spin.setFixedWidth(80)
        bars_layout.addWidget(self.duration_bars_spin)

        bars_minus_btn = QPushButton()
        bars_minus_btn.setIcon(qta.icon("fa5s.minus", color="white"))
        bars_minus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        bars_minus_btn.setStyleSheet(BUTTON_STYLE)
        bars_minus_btn.clicked.connect(lambda: self.duration_bars_spin.stepDown())
        bars_layout.addWidget(bars_minus_btn)

        bars_plus_btn = QPushButton()
        bars_plus_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        bars_plus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        bars_plus_btn.setStyleSheet(BUTTON_STYLE)
        bars_plus_btn.clicked.connect(lambda: self.duration_bars_spin.stepUp())
        bars_layout.addWidget(bars_plus_btn)

        bars_layout.addStretch()
        condition_layout.addRow("Min Bars:", bars_widget)

        # Duration phrases with external buttons
        phrases_widget = QWidget()
        phrases_layout = QHBoxLayout(phrases_widget)
        phrases_layout.setContentsMargins(0, 0, 0, 0)
        phrases_layout.setSpacing(4)

        self.duration_phrases_spin = QSpinBox()
        self.duration_phrases_spin.setMinimum(0)
        self.duration_phrases_spin.setMaximum(99)
        self.duration_phrases_spin.setSpecialValueText("(not used)")
        self.duration_phrases_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.duration_phrases_spin.setFixedWidth(80)
        phrases_layout.addWidget(self.duration_phrases_spin)

        phrases_minus_btn = QPushButton()
        phrases_minus_btn.setIcon(qta.icon("fa5s.minus", color="white"))
        phrases_minus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        phrases_minus_btn.setStyleSheet(BUTTON_STYLE)
        phrases_minus_btn.clicked.connect(lambda: self.duration_phrases_spin.stepDown())
        phrases_layout.addWidget(phrases_minus_btn)

        phrases_plus_btn = QPushButton()
        phrases_plus_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        phrases_plus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        phrases_plus_btn.setStyleSheet(BUTTON_STYLE)
        phrases_plus_btn.clicked.connect(lambda: self.duration_phrases_spin.stepUp())
        phrases_layout.addWidget(phrases_plus_btn)

        phrases_layout.addStretch()
        condition_layout.addRow("Min Phrases:", phrases_widget)

        layout.addWidget(condition_group)

        # Action
        action_group = QGroupBox("Action")
        action_layout = QVBoxLayout(action_group)

        # Sequence choices (weighted random)
        sequences_label = QLabel("Sequences to Activate (weighted random):")
        action_layout.addWidget(sequences_label)

        self.sequences_container = QVBoxLayout()
        action_layout.addLayout(self.sequences_container)

        add_sequence_btn = QPushButton("+ Add Sequence")
        add_sequence_btn.clicked.connect(self._add_sequence_choice)
        action_layout.addWidget(add_sequence_btn)

        layout.addWidget(action_group)

        # Cooldown with external buttons
        cooldown_layout = QFormLayout()

        cooldown_control_widget = QWidget()
        cooldown_control_layout = QHBoxLayout(cooldown_control_widget)
        cooldown_control_layout.setContentsMargins(0, 0, 0, 0)
        cooldown_control_layout.setSpacing(4)

        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setMinimum(0)
        self.cooldown_spin.setMaximum(999)
        self.cooldown_spin.setSuffix(" bars")
        self.cooldown_spin.setSpecialValueText("No cooldown")
        self.cooldown_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.cooldown_spin.setFixedWidth(120)
        cooldown_control_layout.addWidget(self.cooldown_spin)

        cooldown_minus_btn = QPushButton("-")
        cooldown_minus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        cooldown_minus_btn.setStyleSheet(BUTTON_STYLE)
        cooldown_minus_btn.clicked.connect(lambda: self.cooldown_spin.stepDown())
        cooldown_control_layout.addWidget(cooldown_minus_btn)

        cooldown_plus_btn = QPushButton("+")
        cooldown_plus_btn.setFixedSize(BUTTON_SIZE_MEDIUM)
        cooldown_plus_btn.setStyleSheet(BUTTON_STYLE)
        cooldown_plus_btn.clicked.connect(lambda: self.cooldown_spin.stepUp())
        cooldown_control_layout.addWidget(cooldown_plus_btn)

        cooldown_control_layout.addStretch()
        cooldown_layout.addRow("Cooldown:", cooldown_control_widget)
        layout.addLayout(cooldown_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Initial UI state
        self._update_condition_ui()

    def _update_condition_ui(self) -> None:
        """Update condition UI based on selected type."""
        # Duration bars always enabled (interpretation changes per condition type)
        # For AFTER_PHRASE_TYPE: interval to repeat
        # For ON_PHRASE_CHANGE: minimum duration of previous phrase
        self.duration_bars_spin.setEnabled(True)
        self.duration_phrases_spin.setEnabled(False)  # Removed phrases parameter

    def _add_sequence_choice(self, choice: Optional[SequenceChoice] = None) -> None:
        """Add a sequence choice widget."""
        widget = SequenceChoiceWidget(choice)
        widget.remove_requested.connect(lambda: self._remove_sequence_choice(widget))
        self.sequences_container.addWidget(widget)
        self.sequence_widgets.append(widget)

    def _remove_sequence_choice(self, widget: SequenceChoiceWidget) -> None:
        """Remove a sequence choice widget."""
        self.sequence_widgets.remove(widget)
        self.sequences_container.removeWidget(widget)
        widget.deleteLater()

    def load_rule(self, rule: AutomationRule) -> None:
        """Load rule data into UI."""
        self.name_edit.setText(rule.name)
        self.enabled_check.setChecked(rule.enabled)

        # Condition
        self.condition_type_combo.setCurrentIndex(
            self.condition_type_combo.findData(rule.condition.condition_type.value)
        )

        if rule.condition.phrase_type:
            self.phrase_type_combo.setCurrentIndex(
                self.phrase_type_combo.findData(rule.condition.phrase_type)
            )

        if rule.condition.duration_bars is not None:
            self.duration_bars_spin.setValue(rule.condition.duration_bars)

        # Action - load sequences
        if rule.action.sequences:
            for choice in rule.action.sequences:
                self._add_sequence_choice(choice)

        self.cooldown_spin.setValue(rule.cooldown_bars)

    def get_rule(self) -> AutomationRule:
        """Get the edited rule."""
        # Condition
        condition_type = ConditionType(self.condition_type_combo.currentData())
        phrase_type_data = self.phrase_type_combo.currentData()
        phrase_type = phrase_type_data if phrase_type_data else None

        duration_bars = (
            self.duration_bars_spin.value()
            if self.duration_bars_spin.value() > 0
            else None
        )

        condition = RuleCondition(
            condition_type=condition_type,
            phrase_type=phrase_type,
            duration_bars=duration_bars,
        )

        # Action - always ACTIVATE_SEQUENCE
        sequences = (
            [w.get_choice() for w in self.sequence_widgets]
            if self.sequence_widgets
            else None
        )

        action = RuleAction(
            action_type=ActionType.ACTIVATE_SEQUENCE,
            sequences=sequences,
        )

        return AutomationRule(
            name=self.name_edit.text() or "Unnamed Rule",
            enabled=self.enabled_check.isChecked(),
            condition=condition,
            action=action,
            cooldown_bars=self.cooldown_spin.value(),
        )


class PresetEditorDialog(QDialog):
    """Dialog for editing a pilot preset with multiple rules."""

    def __init__(self, preset: Optional[PilotPreset] = None, parent=None):
        super().__init__(parent)
        self.preset = preset

        self.setWindowTitle("Edit Pilot Preset" if preset else "New Pilot Preset")
        self.setMinimumSize(600, 500)
        self.setup_ui()

        if preset:
            self.load_preset(preset)

    def setup_ui(self) -> None:
        """Set up UI."""
        layout = QVBoxLayout(self)

        # Preset info
        info_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Preset name")
        info_layout.addRow("Name:", self.name_edit)

        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        info_layout.addRow("", self.enabled_check)

        layout.addLayout(info_layout)

        # Rules list
        rules_label = QLabel("Automation Rules:")
        layout.addWidget(rules_label)

        self.rules_list = QListWidget()
        self.rules_list.itemDoubleClicked.connect(self._edit_rule)
        layout.addWidget(self.rules_list)

        # Rule buttons
        rules_buttons = QHBoxLayout()

        add_rule_btn = QPushButton("+ Add Rule")
        add_rule_btn.clicked.connect(self._add_rule)
        rules_buttons.addWidget(add_rule_btn)

        edit_rule_btn = QPushButton("Edit Rule")
        edit_rule_btn.clicked.connect(
            lambda: self._edit_rule(self.rules_list.currentItem())
        )
        rules_buttons.addWidget(edit_rule_btn)

        remove_rule_btn = QPushButton("Remove Rule")
        remove_rule_btn.clicked.connect(self._remove_rule)
        rules_buttons.addWidget(remove_rule_btn)

        rules_buttons.addStretch()
        layout.addLayout(rules_buttons)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def load_preset(self, preset: PilotPreset) -> None:
        """Load preset data into UI."""
        self.name_edit.setText(preset.name)
        self.enabled_check.setChecked(preset.enabled)

        for rule in preset.rules:
            self._add_rule_to_list(rule)

    def _add_rule(self) -> None:
        """Add a new rule."""
        dialog = RuleEditorDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            rule = dialog.get_rule()
            self._add_rule_to_list(rule)

    def _edit_rule(self, item: QListWidgetItem) -> None:
        """Edit an existing rule."""
        if not item:
            return

        rule = item.data(Qt.ItemDataRole.UserRole)
        dialog = RuleEditorDialog(rule, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_rule = dialog.get_rule()
            item.setData(Qt.ItemDataRole.UserRole, updated_rule)
            item.setText(self._format_rule_text(updated_rule))

    def _remove_rule(self) -> None:
        """Remove selected rule."""
        current_row = self.rules_list.currentRow()
        if current_row >= 0:
            self.rules_list.takeItem(current_row)

    def _add_rule_to_list(self, rule: AutomationRule) -> None:
        """Add a rule to the list."""
        item = QListWidgetItem(self._format_rule_text(rule))
        item.setData(Qt.ItemDataRole.UserRole, rule)
        self.rules_list.addItem(item)

    def _format_rule_text(self, rule: AutomationRule) -> str:
        """Format rule for display."""
        status = "✓" if rule.enabled else "✗"
        return f"{status} {rule.name}"

    def get_preset(self) -> PilotPreset:
        """Get the edited preset."""
        rules = []
        for i in range(self.rules_list.count()):
            item = self.rules_list.item(i)
            rule = item.data(Qt.ItemDataRole.UserRole)
            rules.append(rule)

        return PilotPreset(
            name=self.name_edit.text() or "Unnamed Preset",
            enabled=self.enabled_check.isChecked(),
            rules=rules,
        )
