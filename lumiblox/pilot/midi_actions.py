"""
MIDI Action System

Configurable MIDI message handling with different action types.
Allows mapping arbitrary MIDI messages to actions like phrase sync, sequence switching, etc.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, List, Union

logger = logging.getLogger(__name__)


class MidiActionType(str, Enum):
    """Types of actions that can be triggered by MIDI messages."""

    PHRASE_SYNC = "phrase_sync"  # Align/sync the phrase timing
    SEQUENCE_SWITCH = "sequence_switch"  # Switch to a specific sequence
    # Future actions can be added here:
    # SCENE_TOGGLE = "scene_toggle"
    # TEMPO_TAP = "tempo_tap"
    # etc.


@dataclass
class MidiActionConfig:
    """Configuration for a MIDI message action mapping."""

    name: str  # User-friendly name for this action
    action_type: MidiActionType  # What action to perform
    status: int  # MIDI status byte (e.g., 0x90 for note on, 0xB0 for CC)
    data1: Optional[int] = None  # MIDI data byte 1 (e.g., note number or CC number)
    data2: Optional[Union[int, List[int]]] = None  # MIDI data byte 2(s), None to ignore
    parameters: Optional[dict] = None  # Additional action-specific parameters

    def matches(self, midi_data: list) -> bool:
        """
        Check if a MIDI message matches this action configuration.

        Args:
            midi_data: MIDI message data [status, data1, data2, ...]

        Returns:
            True if the message matches, False otherwise
        """
        if not midi_data or len(midi_data) < 1:
            return False

        # Check status byte
        if midi_data[0] != self.status:
            return False

        # Check data1 if specified
        if self.data1 is not None and len(midi_data) > 1:
            if midi_data[1] != self.data1:
                return False

        # Check data2 if specified
        if self.data2 is not None:
            if len(midi_data) <= 2:
                return False

            if isinstance(self.data2, Sequence) and not isinstance(
                self.data2, (str, bytes)
            ):
                if midi_data[2] not in self.data2:
                    return False
            else:
                if midi_data[2] != self.data2:
                    return False

        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "action_type": self.action_type.value,
            "status": self.status,
            "data1": self.data1,
            "data2": self._serialize_data2(),
            "parameters": self.parameters or {},
        }

    @classmethod
    def from_dict(cls, data: dict) -> MidiActionConfig:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            action_type=MidiActionType(data["action_type"]),
            status=data["status"],
            data1=data.get("data1"),
            data2=data.get("data2"),
            parameters=data.get("parameters"),
        )

    def _serialize_data2(self) -> Optional[Union[int, List[int]]]:
        """Prepare data2 value for serialization."""
        if self.data2 is None:
            return None
        if isinstance(self.data2, Sequence) and not isinstance(
            self.data2, (str, bytes)
        ):
            return list(self.data2)
        return self.data2


class MidiActionHandler:
    """Handles MIDI message action mappings and execution."""

    def __init__(self):
        """Initialize the action handler."""
        self.actions: List[MidiActionConfig] = []
        self.callbacks: dict[MidiActionType, Callable] = {}

    def add_action(self, action: MidiActionConfig) -> None:
        """
        Add a MIDI action configuration.

        Args:
            action: The action configuration to add
        """
        self.actions.append(action)
        logger.info(
            f"Added MIDI action: {action.name} "
            f"(status=0x{action.status:02X}, data1={action.data1}, data2={action.data2}) "
            f"-> {action.action_type.value}"
        )

    def remove_action(self, name: str) -> bool:
        """
        Remove a MIDI action configuration by name.

        Args:
            name: Name of the action to remove

        Returns:
            True if action was found and removed, False otherwise
        """
        for i, action in enumerate(self.actions):
            if action.name == name:
                self.actions.pop(i)
                logger.info(f"Removed MIDI action: {name}")
                return True
        return False

    def clear_actions(self) -> None:
        """Clear all action configurations."""
        self.actions.clear()
        logger.info("Cleared all MIDI actions")

    def register_callback(
        self, action_type: MidiActionType, callback: Callable[[MidiActionConfig], None]
    ) -> None:
        """
        Register a callback for an action type.

        Args:
            action_type: The action type to handle
            callback: Function to call when action is triggered, receives the action config
        """
        self.callbacks[action_type] = callback
        logger.debug(f"Registered callback for {action_type.value}")

    def process_midi_message(self, midi_data: list) -> None:
        """
        Process a MIDI message and trigger matching actions.

        Args:
            midi_data: MIDI message data [status, data1, data2, ...]
        """
        for action in self.actions:
            if action.matches(midi_data):
                logger.debug(
                    f"MIDI action triggered: {action.name} ({action.action_type.value})"
                )
                self._execute_action(action)

    def _execute_action(self, action: MidiActionConfig) -> None:
        """
        Execute a specific action.

        Args:
            action: The action to execute
        """
        callback = self.callbacks.get(action.action_type)
        if callback:
            try:
                callback(action)
            except Exception as e:
                logger.error(
                    f"Error executing action {action.name} ({action.action_type.value}): {e}"
                )
        else:
            logger.warning(
                f"No callback registered for action type: {action.action_type.value}"
            )

    def get_actions(self) -> List[MidiActionConfig]:
        """Get all configured actions."""
        return self.actions.copy()

    def get_action_by_name(self, name: str) -> Optional[MidiActionConfig]:
        """Get an action by name."""
        for action in self.actions:
            if action.name == name:
                return action
        return None
