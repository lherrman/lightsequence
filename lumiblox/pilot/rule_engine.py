"""
Pilot Rule Engine

Evaluates automation rules and triggers actions based on phrase detection.
"""

from __future__ import annotations

import logging
import random
from typing import Optional, Callable, Dict
from lumiblox.pilot.pilot_preset import (
    PilotPreset,
    AutomationRule,
    SequenceChoice,
    ActionType,
    ConditionType,
)

logger = logging.getLogger(__name__)


class RuleEngine:
    """Evaluate and execute automation rules."""

    def __init__(
        self,
        on_sequence_switch: Optional[Callable[[str], None]] = None,
        on_rule_fired: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize rule engine.

        Args:
            on_sequence_switch: Callback when activating a sequence (string format "x.y")
            on_rule_fired: Callback when a rule fires (receives rule name)
        """
        self.on_sequence_switch = on_sequence_switch
        self.on_rule_fired = on_rule_fired

        # State tracking
        self.current_phrase_type: Optional[str] = None
        self.previous_phrase_type: Optional[str] = None
        self.bars_elapsed: int = 0
        self.previous_phrase_bars: int = 0  # Duration of previous phrase
        self.current_bar: int = 0
        self._pending_change_bar: Optional[int] = None
        self._pending_change_previous_type: Optional[str] = None
        self._pending_change_previous_bars: int = 0

        # Cooldown tracking: rule_name -> last_bar_executed
        self.rule_cooldowns: Dict[str, int] = {}

    def update_state(
        self,
        current_phrase_type: Optional[str],
        bars_elapsed: int,
        current_bar: int,
    ) -> None:
        """Update bar-related state."""
        self.current_phrase_type = current_phrase_type
        self.bars_elapsed = bars_elapsed
        self.current_bar = current_bar

        # Once a change has been processed we track the current type as the new "previous" baseline
        if self._pending_change_bar is None:
            self.previous_phrase_type = current_phrase_type

    def notify_phrase_change(
        self,
        new_phrase_type: Optional[str],
        previous_phrase_type: Optional[str],
        previous_phrase_bars: int,
        change_bar: int,
    ) -> None:
        """Record a phrase change detected at the phrase boundary."""
        if new_phrase_type is None:
            logger.debug("Phrase change notification ignored (no new phrase type)")
            self.current_phrase_type = None
            self._pending_change_bar = None
            self._pending_change_previous_type = None
            self._pending_change_previous_bars = 0
            return

        self.current_phrase_type = new_phrase_type
        self.previous_phrase_type = previous_phrase_type
        self.previous_phrase_bars = previous_phrase_bars
        self.bars_elapsed = 0
        self.current_bar = change_bar
        self._pending_change_bar = change_bar
        self._pending_change_previous_type = previous_phrase_type
        self._pending_change_previous_bars = previous_phrase_bars

    def evaluate_preset(self, preset: PilotPreset) -> None:
        """
        Evaluate all rules in a preset and execute matching ones.

        Args:
            preset: Pilot preset to evaluate
        """
        if not preset.enabled:
            logger.debug(f"Preset '{preset.name}' disabled, skipping")
            return

        if self.current_phrase_type is None:
            logger.debug("No phrase type detected yet, skipping rules")
            return

        logger.debug(
            f"Evaluating preset '{preset.name}' - "
            f"phrase: {self.current_phrase_type}, "
            f"bars_elapsed: {self.bars_elapsed}, "
            f"bar: {self.current_bar}"
        )

        phrase_just_changed = (
            self._pending_change_bar is not None
            and self.current_bar == self._pending_change_bar
        )

        previous_phrase_type = (
            self._pending_change_previous_type
            if phrase_just_changed
            else self.previous_phrase_type
        )
        previous_phrase_bars = (
            self._pending_change_previous_bars
            if phrase_just_changed
            else self.previous_phrase_bars
        )

        for rule in preset.rules:
            if not rule.enabled:
                logger.debug(f"Rule '{rule.name}' disabled, skipping")
                continue

            # Check cooldown
            if rule.name in self.rule_cooldowns:
                last_executed = self.rule_cooldowns[rule.name]
                bars_since = self.current_bar - last_executed
                if bars_since < rule.cooldown_bars:
                    logger.debug(
                        f"Rule '{rule.name}' on cooldown "
                        f"({bars_since}/{rule.cooldown_bars} bars)"
                    )
                    continue

            # Evaluate condition
            if (
                rule.condition.condition_type == ConditionType.ON_PHRASE_CHANGE
                and not phrase_just_changed
            ):
                logger.debug(
                    f"Rule '{rule.name}' waiting for phrase boundary (on change condition)"
                )
                continue

            logger.debug(
                f"Evaluating rule '{rule.name}': "
                f"type={rule.condition.condition_type.value}, "
                f"phrase_type={rule.condition.phrase_type}, "
                f"duration_bars={rule.condition.duration_bars}"
            )

            if rule.condition.evaluate(
                self.current_phrase_type,
                previous_phrase_type,
                self.bars_elapsed,
                previous_phrase_bars,
            ):
                logger.info(f"🔥 Rule FIRED: {rule.name}")

                # Notify that rule fired (for UI flash)
                if self.on_rule_fired:
                    self.on_rule_fired(rule.name)

                self._execute_action(rule)
                self.rule_cooldowns[rule.name] = self.current_bar
            else:
                logger.debug(f"Rule '{rule.name}' condition not met")

        if phrase_just_changed:
            self._pending_change_bar = None
            self._pending_change_previous_type = None
            self._pending_change_previous_bars = 0
            self.previous_phrase_type = self.current_phrase_type

    def _execute_action(self, rule: AutomationRule) -> None:
        """
        Execute a rule's action.

        Args:
            rule: Rule to execute
        """
        action = rule.action

        if action.action_type == ActionType.ACTIVATE_SEQUENCE:
            if action.sequences:
                sequence_index = self._select_weighted_sequence(action.sequences)
                logger.info(f"Activating sequence {sequence_index}")
                if self.on_sequence_switch:
                    self.on_sequence_switch(sequence_index)

    def _select_weighted_sequence(self, choices: list[SequenceChoice]) -> str:
        """
        Select a sequence based on weighted random selection.

        Args:
            choices: List of weighted sequence choices

        Returns:
            Selected sequence index (as string "x.y")
        """
        if not choices:
            return "0.0"

        if len(choices) == 1:
            return choices[0].sequence_index

        # Normalize weights
        total_weight = sum(c.weight for c in choices)
        if total_weight <= 0:
            return choices[0].sequence_index

        # Weighted random selection
        r = random.random() * total_weight
        cumulative = 0.0

        for choice in choices:
            cumulative += choice.weight
            if r <= cumulative:
                return choice.sequence_index

        # Fallback (shouldn't happen)
        return choices[-1].sequence_index

    def reset_cooldowns(self) -> None:
        """Reset all rule cooldowns."""
        self.rule_cooldowns.clear()
        logger.info("All rule cooldowns reset")
