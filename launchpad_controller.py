"""
Launchpad MK2 Controller - RGB-focused controller for Novation Launchpad MK2

Clean, minimal interface focused on RGB control and button events.
"""

import logging
from typing import Optional, Callable, List
import threading
import time

try:
    import launchpad_py as launchpad
except ImportError:
    raise ImportError("launchpad_py is required. Install with: uv add launchpad-py")

from button_matrix import ButtonMatrix

logger = logging.getLogger(__name__)


class LaunchpadController:
    """
    Minimal RGB-focused controller for Novation Launchpad MK2.

    Provides:
    - Device connection and management
    - RGB LED control
    - Button event handling
    """

    def __init__(self, device_name: str = "Mk2"):
        """Initialize the Launchpad controller."""
        self.device_name = device_name
        self.launchpad: Optional[launchpad.LaunchpadMk2] = None
        self.button_matrix = ButtonMatrix()

        # Event handling
        self._button_callbacks: List[Callable[[int, int, bool], None]] = []
        self._running = False
        self._event_thread: Optional[threading.Thread] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Connect to the Launchpad device.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.launchpad = launchpad.LaunchpadMk2()

            # Try to open the device
            if self.launchpad.Open(name=self.device_name):
                self._connected = True
                logger.info(f"Connected to Launchpad {self.device_name}")

                # Clear all LEDs on startup
                self.clear_all()

                return True
            else:
                logger.error(f"Failed to open Launchpad {self.device_name}")
                return False

        except Exception as e:
            logger.error(f"Error connecting to Launchpad: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from the Launchpad device."""
        self.stop_event_loop()

        if self.launchpad and self._connected:
            try:
                self.clear_all()
                self.launchpad.Close()
                self._connected = False
                logger.info("Disconnected from Launchpad")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")

    def is_connected(self) -> bool:
        """Check if device is connected."""
        return self._connected and self.launchpad is not None

    def clear_all(self) -> None:
        """Turn off all LEDs."""
        if not self.is_connected() or self.launchpad is None:
            return

        try:
            self.launchpad.Reset()
        except Exception as e:
            logger.error(f"Error clearing LEDs: {e}")

    def set_led_rgb(self, x: int, y: int, r: int, g: int, b: int) -> None:
        """
        Set LED at coordinates using RGB values.

        Args:
            x: X coordinate (0-7)
            y: Y coordinate (0-7)
            r: Red value (0-255, will be scaled to 0-63)
            g: Green value (0-255, will be scaled to 0-63)
            b: Blue value (0-255, will be scaled to 0-63)
        """
        if not self.is_connected() or self.launchpad is None:
            return

        if not self.button_matrix.is_valid_coordinate(x, y):
            logger.warning(f"Invalid coordinates: ({x}, {y})")
            return

        try:
            # Scale RGB values from 0-255 to 0-63 for Launchpad
            scaled_r = int((r / 255.0) * 63)
            scaled_g = int((g / 255.0) * 63)
            scaled_b = int((b / 255.0) * 63)

            self.launchpad.LedCtrlXY(x, y, scaled_r, scaled_g, scaled_b)
        except Exception as e:
            logger.error(f"Error setting LED RGB at ({x}, {y}): {e}")

    def set_led_rgb_normalized(
        self, x: int, y: int, r: float, g: float, b: float
    ) -> None:
        """
        Set LED at coordinates using normalized RGB values (0.0-1.0).

        Args:
            x: X coordinate (0-7)
            y: Y coordinate (0-7)
            r: Red value (0.0-1.0)
            g: Green value (0.0-1.0)
            b: Blue value (0.0-1.0)
        """
        # Convert normalized values to 0-255 range
        r_255 = int(max(0, min(255, r * 255)))
        g_255 = int(max(0, min(255, g * 255)))
        b_255 = int(max(0, min(255, b * 255)))

        self.set_led_rgb(x, y, r_255, g_255, b_255)

    def set_grid_rgb(self, rgb_array) -> None:
        """
        Set entire 8x8 grid using RGB array.

        Args:
            rgb_array: numpy array of shape (8, 8, 3) with RGB values 0.0-1.0
        """
        if not self.is_connected():
            return

        try:
            # Ensure we have the right shape
            if rgb_array.shape != (8, 8, 3):
                logger.error(
                    f"RGB array must be shape (8, 8, 3), got {rgb_array.shape}"
                )
                return

            # Assume normalized values (0.0-1.0)
            for y in range(8):
                for x in range(8):
                    r, g, b = rgb_array[y, x]  # Note: array is [y, x] for row, col
                    self.set_led_rgb_normalized(x, y, float(r), float(g), float(b))

        except Exception as e:
            logger.error(f"Error setting grid RGB: {e}")

    def add_button_callback(self, callback: Callable[[int, int, bool], None]) -> None:
        """
        Add callback for button events.

        Args:
            callback: Function to call with (x, y, pressed) when button is pressed/released
        """
        self._button_callbacks.append(callback)

    def start_event_loop(self) -> None:
        """Start the event loop for button handling."""
        if self._running or not self.is_connected():
            return

        self._running = True
        self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_thread.start()
        logger.info("Started event loop")

    def stop_event_loop(self) -> None:
        """Stop the event loop."""
        self._running = False
        if self._event_thread:
            self._event_thread.join()
            self._event_thread = None
        logger.info("Stopped event loop")

    def _event_loop(self) -> None:
        """Internal event loop for processing button events."""
        while self._running and self.is_connected() and self.launchpad is not None:
            try:
                # Check for button events
                events = self.launchpad.ButtonStateXY()

                if events:
                    x, y, pressed = events
                    is_pressed = pressed > 0

                    # Validate coordinates
                    if self.button_matrix.is_valid_coordinate(x, y):
                        # Call all registered callbacks
                        for callback in self._button_callbacks:
                            try:
                                callback(x, y, is_pressed)
                            except Exception as e:
                                logger.error(f"Error in button callback: {e}")

                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Error in event loop: {e}")
                time.sleep(0.1)

    def __enter__(self):
        """Context manager entry."""
        if not self.connect():
            raise RuntimeError("Failed to connect to Launchpad")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
