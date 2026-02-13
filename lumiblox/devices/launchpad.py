import logging
import typing as t

import launchpad_py as lp
import numpy as np
from lumiblox.common.config import get_config
from lumiblox.common.enums import ButtonType
from lumiblox.common.utils import hex_to_rgb
from lumiblox.common.device_state import DeviceManager, DeviceType

logger = logging.getLogger(__name__)


class LaunchpadMK2:
    def __init__(self, device_manager: t.Optional[DeviceManager] = None):
        self.BOUNDS_SCENES = np.array([[0, 1], [8, 5]])
        self.BOUNDS_PRESETS = np.array([[0, 6], [7, 8]])
        self.BOUNDS_TOP = np.array([[0, 0], [7, 0]])
        self.BOUNDS_RIGHT = np.array([[8, 1], [8, 8]])

        self.pixel_buffer_output = np.zeros(
            (9, 9, 3), dtype=float
        )  # 9x9 grid for Launchpad MK2

        # Track hardware LED state (0-63 range) to avoid unnecessary updates
        self.hardware_led_state = np.zeros((9, 9, 3), dtype=int)

        self.config = get_config()
        
        # Device state management
        self.device_manager = device_manager
        self.device = None  # Will be set on successful connection
        self.is_connected = False

        # Attempt initial connection
        self.connect()

    def connect(self) -> bool:
        """Connect to Launchpad MK2 hardware."""
        try:
            if self.device_manager:
                self.device_manager.set_connecting(DeviceType.LAUNCHPAD)
            
            self.device = lp.LaunchpadMk2()  # type: ignore
            
            if self.device.Open():
                self.device.Reset()  # Clear all LEDs
                self.hardware_led_state.fill(0)  # Reset hardware state tracking
                self.is_connected = True
                
                if self.device_manager:
                    self.device_manager.set_connected(DeviceType.LAUNCHPAD)
                
                logger.info("Connected to Launchpad MK2")
                return True
            else:
                self.is_connected = False
                
                if self.device_manager:
                    self.device_manager.set_disconnected(DeviceType.LAUNCHPAD)
                
                logger.warning("Could not open Launchpad MK2")
                return False
                
        except Exception as e:
            self.is_connected = False
            
            if self.device_manager:
                self.device_manager.set_error(DeviceType.LAUNCHPAD, str(e))
            
            logger.error(f"Error connecting to Launchpad: {e}")
            return False

    def set_led(self, x: int, y: int, color: t.List[float]) -> None:
        """Set LED at absolute (x, y) coordinates to specified color. rgb values float 0-1.0"""
        if not self.is_connected:
            return

        max_x, max_y = self.pixel_buffer_output.shape[0], self.pixel_buffer_output.shape[1]
        if not (0 <= x < max_x and 0 <= y < max_y):
            logger.warning("LED coordinates out of bounds: (%s, %s)", x, y)
            return

        # Scale to 0-63 (Launchpad MK2 range)
        color_scaled = [int(c * 63) for c in color]

        # Check if the hardware state already matches the desired color
        current_hardware_color = self.hardware_led_state[x, y]
        if np.array_equal(current_hardware_color, color_scaled):
            return  # Skip update - LED is already at the correct color

        # Update hardware and track the new state
        self.device.LedCtrlXY(x, y, *color_scaled)
        self.hardware_led_state[x, y] = color_scaled

    def set_button_led(
        self,
        button_type: ButtonType,
        relative_coords: t.List[int],
        color: t.List[float] | str,
    ) -> None:
        """Set LED using button type and relative coordinates."""
        if not self.is_connected:
            return

        if len(relative_coords) < 2:
            logger.warning(f"Invalid coordinates {relative_coords}")
            return

        abs_x, abs_y = self._relative_to_absolute_coords(button_type, relative_coords)
        if abs_x is None or abs_y is None:
            logger.warning(f"Invalid coordinates for {button_type}: {relative_coords}")
            return

        if isinstance(color, str):
            color = hex_to_rgb(color)

        # multiply with foreground brightness
        brightness = self.config.data["brightness_foreground"]
        adjusted_color = [c * brightness for c in color]

        self.pixel_buffer_output[abs_x, abs_y] = color
        self.set_led(abs_x, abs_y, adjusted_color)

    def _relative_to_absolute_coords(
        self, button_type: ButtonType, relative_coords: t.List[int]
    ) -> t.Tuple[t.Optional[int], t.Optional[int]]:
        """Convert relative coordinates to absolute coordinates based on button type."""
        rel_x, rel_y = relative_coords[0], relative_coords[1]

        if button_type == ButtonType.SCENE:
            abs_x = self.BOUNDS_SCENES[0][0] + rel_x
            abs_y = self.BOUNDS_SCENES[0][1] + rel_y
            return abs_x, abs_y

        if button_type == ButtonType.SEQUENCE:
            abs_x = self.BOUNDS_PRESETS[0][0] + rel_x
            abs_y = self.BOUNDS_PRESETS[0][1] + rel_y
            return abs_x, abs_y

        if button_type == ButtonType.CONTROL:
            return rel_x, rel_y

        return None, None

    def clear_leds(self) -> None:
        """Clear all LEDs on the Launchpad."""
        if self.is_connected:
            self.device.Reset()
            self.pixel_buffer_output.fill(0)  # Clear pixel buffer
            self.hardware_led_state.fill(0)  # Clear hardware state tracking

    def close(self) -> None:
        """Close connection to Launchpad MK2."""
        if self.is_connected and self.device:
            try:
                self.device.Reset()
                self.device.Close()
                self.is_connected = False
                self.hardware_led_state.fill(0)  # Reset hardware state tracking
                
                if self.device_manager:
                    self.device_manager.set_disconnected(DeviceType.LAUNCHPAD)
                
                logger.info("Disconnected from Launchpad MK2")
            except Exception as e:
                logger.error(f"Error closing Launchpad connection: {e}")
                self.is_connected = False
                if self.device_manager:
                    self.device_manager.set_disconnected(DeviceType.LAUNCHPAD)

    def get_button_events(
        self,
    ) -> t.Optional[t.Dict[str, t.Any]]:
        """Get button events with smart type classification and relative coordinates."""
        if not self.is_connected or not self.device:
            return None

        try:
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
                    button_type = ButtonType.SEQUENCE
                    relative_coords = [
                        x - self.BOUNDS_PRESETS[0][0],
                        y - self.BOUNDS_PRESETS[0][1],
                    ]

                # Check if button is in top area
                elif (
                    self.BOUNDS_TOP[0][0] <= x <= self.BOUNDS_TOP[1][0]
                    and self.BOUNDS_TOP[0][1] <= y <= self.BOUNDS_TOP[1][1]
                ):
                    button_type = ButtonType.CONTROL
                    relative_coords = [x, y]

                # Check if button is in right area
                elif (
                    self.BOUNDS_RIGHT[0][0] <= x <= self.BOUNDS_RIGHT[1][0]
                    and self.BOUNDS_RIGHT[0][1] <= y <= self.BOUNDS_RIGHT[1][1]
                ):
                    button_type = ButtonType.CONTROL
                    relative_coords = [x, y]

                return {"type": button_type, "index": relative_coords, "active": state}

        except Exception as e:
            logger.error(f"Error reading button events: {e}")
            # Mark device as disconnected if we get errors
            self.is_connected = False
            if self.device_manager:
                self.device_manager.set_error(DeviceType.LAUNCHPAD, f"Button read error: {e}")
            return None

        return None


