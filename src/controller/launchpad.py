import logging
import typing as t
from enum import Enum
import launchpad_py as lp
import numpy as np
from background_animator import BackgroundAnimator as Animator
from config import get_config_manager

logger = logging.getLogger(__name__)


class ButtonType(str, Enum):
    SCENE = "scene"
    PRESET = "preset"
    TOP = "top"
    RIGHT = "right"
    UNKNOWN = "unknown"


class LaunchpadMK2:
    def __init__(self):
        self.BOUNDS_SCENES = np.array([[0, 1], [8, 5]])
        self.BOUNDS_PRESETS = np.array([[0, 6], [7, 8]])
        self.BOUNDS_TOP = np.array([[0, 0], [7, 0]])
        self.BOUNDS_RIGHT = np.array([[8, 1], [8, 8]])

        self.pixel_buffer_output = np.zeros(
            (9, 9, 3), dtype=float
        )  # 9x9 grid for Launchpad MK2
        
        # Track previous state to detect when LEDs are turned off
        self.previous_pixel_buffer = np.zeros((9, 9, 3), dtype=float)

        # Track pressed buttons state: {(button_type, rel_x, rel_y): True}
        self._pressed_buttons: t.Dict[t.Tuple[ButtonType, int, int], bool] = {}
        self.animator = Animator()
        self.config_manager = get_config_manager()

        self.connect()

    def connect(self) -> bool:
        """Connect to Launchpad MK2 hardware."""
        self.device = lp.LaunchpadMk2()  # type: ignore
        self.is_connected = False
        if self.device.Open():
            self.device.Reset()  # Clear all LEDs
            self.is_connected = True
            logger.info("Connected to Launchpad MK2")
            return True
        else:
            logger.warning("Could not open Launchpad MK2")
            return False

    def set_led(self, x: int, y: int, color: t.List[float]) -> None:
        """Set LED at absolute (x, y) coordinates to specified color. rgb values float 0-1.0"""
        if not self.is_connected:
            return
        
        # Scale to 0-63 (Launchpad MK2 range)
        color_scaled = [int(c * 63) for c in color]
        self.device.LedCtrlXY(x, y, *color_scaled)

    def set_button_led(
        self,
        button_type: ButtonType,
        relative_coords: t.List[int],
        color: t.List[float],
    ) -> None:
        """Set LED using button type and relative coordinates."""
        if not self.is_connected:
            return

        if len(relative_coords) < 2:
            logger.warning(f"Invalid coordinates {relative_coords}")
            return

        # Convert relative coordinates to absolute coordinates
        abs_x, abs_y = self._relative_to_absolute_coords(button_type, relative_coords)
        if abs_x is not None and abs_y is not None:
            # Apply foreground brightness multiplier
            brightness_multiplier = self.config_manager.get_brightness_foreground()
            adjusted_color = [c * brightness_multiplier for c in color]
            
            # Store previous state before updating
            self.previous_pixel_buffer[abs_x, abs_y] = self.pixel_buffer_output[abs_x, abs_y].copy()
            
            self.pixel_buffer_output[abs_x, abs_y] = color
            self.set_led(abs_x, abs_y, adjusted_color)
        else:
            logger.warning(
                f"Could not convert coordinates for {button_type}: {relative_coords}"
            )

    def _relative_to_absolute_coords(
        self, button_type: ButtonType, relative_coords: t.List[int]
    ) -> t.Tuple[t.Optional[int], t.Optional[int]]:
        """Convert relative coordinates to absolute coordinates based on button type."""
        rel_x, rel_y = relative_coords[0], relative_coords[1]

        if button_type == ButtonType.SCENE:
            abs_x = self.BOUNDS_SCENES[0][0] + rel_x
            abs_y = self.BOUNDS_SCENES[0][1] + rel_y
            return abs_x, abs_y

        elif button_type == ButtonType.PRESET:
            abs_x = self.BOUNDS_PRESETS[0][0] + rel_x
            abs_y = self.BOUNDS_PRESETS[0][1] + rel_y
            return abs_x, abs_y

        elif button_type == ButtonType.TOP:
            abs_x = self.BOUNDS_TOP[0][0] + rel_x
            abs_y = self.BOUNDS_TOP[0][1] + rel_y
            return abs_x, abs_y

        elif button_type == ButtonType.RIGHT:
            abs_x = self.BOUNDS_RIGHT[0][0] + rel_x
            abs_y = self.BOUNDS_RIGHT[0][1] + rel_y
            return abs_x, abs_y

        return None, None

    def clear_leds(self) -> None:
        """Clear all LEDs on the Launchpad."""
        if self.is_connected:
            self.device.Reset()
            self.pixel_buffer_output.fill(0)  # Clear pixel buffer

    def close(self) -> None:
        """Close connection to Launchpad MK2."""
        if self.is_connected:
            self.device.Reset()
            self.device.Close()
            self.is_connected = False
            logger.info("Disconnected from Launchpad MK2")

    def get_button_events(
        self,
    ) -> t.Optional[t.Dict[str, t.Any]]:
        """Get button events with smart type classification and relative coordinates."""
        if not self.is_connected:
            return None

        button = self.device.ButtonStateXY()
        if button:
            x, y, state = button
            state = bool(state)

            # Determine button type and calculate relative coordinates
            button_type = ButtonType.UNKNOWN
            relative_coords = [0, 0]

            # Check if button is in scenes area
            if (
                self.BOUNDS_SCENES[0][0] <= x <= self.BOUNDS_SCENES[1][0]
                and self.BOUNDS_SCENES[0][1] <= y <= self.BOUNDS_SCENES[1][1]
            ):
                button_type = ButtonType.SCENE
                relative_coords = [
                    x - self.BOUNDS_SCENES[0][0],
                    y - self.BOUNDS_SCENES[0][1],
                ]

            # Check if button is in presets area
            elif (
                self.BOUNDS_PRESETS[0][0] <= x <= self.BOUNDS_PRESETS[1][0]
                and self.BOUNDS_PRESETS[0][1] <= y <= self.BOUNDS_PRESETS[1][1]
            ):
                button_type = ButtonType.PRESET
                relative_coords = [
                    x - self.BOUNDS_PRESETS[0][0],
                    y - self.BOUNDS_PRESETS[0][1],
                ]

            # Check if button is in top area
            elif (
                self.BOUNDS_TOP[0][0] <= x <= self.BOUNDS_TOP[1][0]
                and self.BOUNDS_TOP[0][1] <= y <= self.BOUNDS_TOP[1][1]
            ):
                button_type = ButtonType.TOP
                relative_coords = [x - self.BOUNDS_TOP[0][0], y - self.BOUNDS_TOP[0][1]]

            # Check if button is in right area
            elif (
                self.BOUNDS_RIGHT[0][0] <= x <= self.BOUNDS_RIGHT[1][0]
                and self.BOUNDS_RIGHT[0][1] <= y <= self.BOUNDS_RIGHT[1][1]
            ):
                button_type = ButtonType.RIGHT
                relative_coords = [
                    x - self.BOUNDS_RIGHT[0][0],
                    y - self.BOUNDS_RIGHT[0][1],
                ]

            # Update button state tracking
            button_key = (button_type, relative_coords[0], relative_coords[1])
            if state:
                self._pressed_buttons[button_key] = True
            else:
                self._pressed_buttons.pop(button_key, None)

            return {"type": button_type, "index": relative_coords, "active": state}

        return None

    def get_pressed_buttons(self) -> t.List[t.Dict[str, t.Any]]:
        """
        Get all currently pressed buttons.

        Returns:
            List of button dictionaries with 'type' and 'index' keys
        """
        pressed = []
        for button_type, rel_x, rel_y in self._pressed_buttons.keys():
            pressed.append({"type": button_type, "index": [rel_x, rel_y]})
        return pressed

    def is_button_pressed(self, button_type: ButtonType, coords: t.List[int]) -> bool:
        """
        Check if a specific button is currently pressed.

        Args:
            button_type: The type of button
            coords: Relative coordinates [x, y]

        Returns:
            True if the button is currently pressed
        """
        if len(coords) < 2:
            return False
        button_key = (button_type, coords[0], coords[1])
        return button_key in self._pressed_buttons

    def clear_pressed_buttons(self) -> None:
        """Clear all tracked pressed button states."""
        self._pressed_buttons.clear()

    def _detect_leds_turned_off(self) -> bool:
        """Detect if any LEDs were turned off (active to inactive) since last check.
        
        Returns:
            bool: True if any LEDs were turned off, False otherwise
        """
        # Check each position in the scene and preset areas for LEDs that went from active to off
        for x in range(8):  # Columns 0-7
            for y in range(1, 9):  # Rows 1-8
                # Check if this position had an active LED before but is now off
                previous_active = self.previous_pixel_buffer[x, y, :].any()
                current_active = self.pixel_buffer_output[x, y, :].any()
                
                if previous_active and not current_active:
                    # LED was turned off - update our tracking and return True
                    self.previous_pixel_buffer[x, y] = [0.0, 0.0, 0.0]
                    return True
        
        return False

    def draw_background(self, animation_type: str = "ocean_waves", force_update: bool = False) -> bool:
        """Fill entire Launchpad with complete background (animation + zones + brightness).
        
        Args:
            animation_type: Type of background animation to use
            force_update: Force background update regardless of needs_update flag
            
        Returns:
            bool: True if background was actually updated, False if skipped
        """
        if not self.is_connected:
            return False

        # Check if any LEDs were turned off (changed from active to inactive)
        leds_turned_off = self._detect_leds_turned_off()
        
        # Force update if requested or if LEDs were turned off
        if force_update or leds_turned_off:
            self.animator.force_background_update()

        # Get complete background buffer with animation, zone colors, and brightness already applied
        background_buffer, needs_update = self.animator.get_background(animation_type)
        
        if not needs_update:
            return False  # Skip update - background hasn't changed
        # Apply the background buffer directly to all non-active LEDs
        for x in range(8):
            for y in range(1, 9):
                if not self.pixel_buffer_output[x, y, :].any():
                    # Background buffer already contains everything: animation + zone colors + brightness
                    color = background_buffer[x, y, :].tolist()
                    self.set_led(x, y, color)
        
        return True  # Background was updated


if __name__ == "__main__":
    pixel_buffer = np.zeros((9, 9, 3), dtype=float)
    pixel_buffer[0, 0] = [1.0, 0.0, 0.0]
    for x in range(9):
        for y in range(9):
            if pixel_buffer[x, y, :].any():
                print(f"Setting LED at ({x}, {y}) to {pixel_buffer[x, y, :]}")
