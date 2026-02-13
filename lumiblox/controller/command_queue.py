"""
Command Queue – Thread-safe communication between GUI and controller.

The GUI posts ``ControllerCommand`` instances via ``CommandQueue.post`` and the
controller drains them each tick via ``CommandQueue.process_all``.
"""

import enum
import queue
import typing as t
from dataclasses import dataclass, field


class CommandType(enum.Enum):
    """Types of commands the GUI can post to the controller."""

    TOGGLE_PLAYBACK = "toggle_playback"
    NEXT_STEP = "next_step"
    CLEAR = "clear"
    ACTIVATE_SEQUENCE = "activate_sequence"
    SAVE_SEQUENCE = "save_sequence"
    DELETE_SEQUENCE = "delete_sequence"
    SWITCH_PILOT = "switch_pilot"
    ACTIVATE_SCENES = "activate_scenes"
    BUTTON_EVENT = "button_event"


@dataclass
class ControllerCommand:
    """A single command destined for the controller thread."""

    command_type: CommandType
    data: dict[str, t.Any] = field(default_factory=dict)


class CommandQueue:
    """Thread-safe command queue wrapping :class:`queue.Queue`."""

    def __init__(self) -> None:
        self._queue: queue.Queue[ControllerCommand] = queue.Queue()

    def post(self, command: ControllerCommand) -> None:
        """Enqueue a command (safe to call from any thread)."""
        self._queue.put(command)

    def process_all(self, handler: t.Callable[[ControllerCommand], None]) -> None:
        """Drain the queue, calling *handler* for every pending command."""
        while True:
            try:
                cmd = self._queue.get_nowait()
            except queue.Empty:
                break
            handler(cmd)
