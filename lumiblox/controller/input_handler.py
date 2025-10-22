"""
Input Handler

Generic button event handling and routing.
Works with any input source (Launchpad, GUI, future controllers).
"""

import logging
import typing as t
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ButtonType(str, Enum):
    """Types of buttons in the system."""
    SCENE = "scene"
    SEQUENCE = "sequence"  # Was "preset"
    CONTROL = "control"  # Top row and right column controls
    UNKNOWN = "unknown"


@dataclass
class ButtonEvent:
    """Generic button event."""
    button_type: ButtonType
    coordinates: t.Tuple[int, int]
    pressed: bool  # True for press, False for release
    source: str = "unknown"  # "launchpad", "gui", etc.


class InputHandler:
    """
    Handles button events from any source and routes them to appropriate handlers.
    """
    
    def __init__(self):
        """Initialize input handler."""
        # Handler callbacks
        self.on_scene_button: t.Optional[t.Callable[[t.Tuple[int, int], bool], None]] = None
        self.on_sequence_button: t.Optional[t.Callable[[t.Tuple[int, int], bool], None]] = None
        self.on_control_button: t.Optional[t.Callable[[str, bool], None]] = None
        
        # Control button mapping (name -> coordinates)
        self.control_buttons: t.Dict[str, t.Tuple[int, int]] = {}
    
    def register_control_button(self, name: str, coordinates: t.Tuple[int, int]) -> None:
        """Register a control button."""
        self.control_buttons[name] = coordinates
        logger.debug(f"Registered control button '{name}' at {coordinates}")
    
    def handle_button_event(self, event: ButtonEvent) -> None:
        """Process a button event and route to appropriate handler."""
        # Only process press events for most buttons
        if not event.pressed and event.button_type != ButtonType.SCENE:
            return
        
        if event.button_type == ButtonType.SCENE:
            if self.on_scene_button:
                self.on_scene_button(event.coordinates, event.pressed)
        
        elif event.button_type == ButtonType.SEQUENCE:
            if self.on_sequence_button and event.pressed:
                self.on_sequence_button(event.coordinates, event.pressed)
        
        elif event.button_type == ButtonType.CONTROL:
            # Look up control button name
            control_name = self._get_control_name(event.coordinates)
            if control_name and self.on_control_button:
                self.on_control_button(control_name, event.pressed)
    
    def _get_control_name(self, coordinates: t.Tuple[int, int]) -> t.Optional[str]:
        """Get control button name from coordinates."""
        for name, coords in self.control_buttons.items():
            if coords == coordinates:
                return name
        return None
    
    def create_event(
        self,
        button_type: ButtonType,
        coordinates: t.Tuple[int, int],
        pressed: bool,
        source: str = "unknown"
    ) -> ButtonEvent:
        """Create a button event."""
        return ButtonEvent(
            button_type=button_type,
            coordinates=coordinates,
            pressed=pressed,
            source=source
        )
