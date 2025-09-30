import logging
import typing as t
from enum import Enum
import launchpad_py as lp
import numpy as np

logger = logging.getLogger(__name__)


class ButtonType(Enum):
    SCENE = "scene"
    PRESET = "preset"
    TOP = "top"
    RIGHT = "right"
    UNKNOWN = "unknown"


class LaunchpadMK2:
    def __init__(self):
        self.connect()

    def connect(self) -> bool:
        """Connect to Launchpad MK2 hardware."""
        self.device = lp.LaunchpadMk2()
        if self.device.Open():
            self.device.Reset()  # Clear all LEDs
            self.is_connected = True
            logger.info("Connected to Launchpad MK2")
            return True
        else:
            logger.warning("Could not open Launchpad MK2")
            return False

    def set_led(self, x: int, y: int, color: t.List[float]) -> None:
        """Set LED at (x, y) to specified color. rgb values float 0-1.0"""

        if not self.is_connected:
            return

        color = [int(c * 63) for c in color]  # Scale to 0-127
        self.device.LedCtrlXY(x, y, *color)

    def clear_leds(self) -> None:
        """Clear all LEDs on the Launchpad."""
        if self.is_connected:
            self.device.Reset()

    def close(self) -> None:
        """Close connection to Launchpad MK2."""
        if self.is_connected:
            self.device.Close()
            self.is_connected = False
            logger.info("Disconnected from Launchpad MK2")

    def get_button_events(
        self,
    ) -> t.Optional[t.Dict[str, t.Any]]:
        """Get button events with smart type classification and relative coordinates."""
        if not self.is_connected:
            return None

        # Define button regions (format: [[min_x, min_y], [max_x, max_y]])
        BOUNDS_SCENES = np.array([[0, 1], [7, 5]])
        BOUNDS_PRESETS = np.array([[0, 6], [7, 8]])
        BOUNDS_TOP = np.array([[0, 0], [7, 0]])
        BOUNDS_RIGHT = np.array([[8, 1], [8, 8]])

        button = self.device.ButtonStateXY()
        if button:
            x, y, state = button
            state = bool(state)

            # Determine button type and calculate relative coordinates
            button_type = ButtonType.UNKNOWN
            relative_coords = [0, 0]

            # Check if button is in scenes area
            if (
                BOUNDS_SCENES[0][0] <= x <= BOUNDS_SCENES[1][0]
                and BOUNDS_SCENES[0][1] <= y <= BOUNDS_SCENES[1][1]
            ):
                button_type = ButtonType.SCENE
                relative_coords = [x - BOUNDS_SCENES[0][0], y - BOUNDS_SCENES[0][1]]

            # Check if button is in presets area
            elif (
                BOUNDS_PRESETS[0][0] <= x <= BOUNDS_PRESETS[1][0]
                and BOUNDS_PRESETS[0][1] <= y <= BOUNDS_PRESETS[1][1]
            ):
                button_type = ButtonType.PRESET
                relative_coords = [x - BOUNDS_PRESETS[0][0], y - BOUNDS_PRESETS[0][1]]

            # Check if button is in top area
            elif (
                BOUNDS_TOP[0][0] <= x <= BOUNDS_TOP[1][0]
                and BOUNDS_TOP[0][1] <= y <= BOUNDS_TOP[1][1]
            ):
                button_type = ButtonType.TOP
                relative_coords = [x - BOUNDS_TOP[0][0], y - BOUNDS_TOP[0][1]]

            # Check if button is in right area
            elif (
                BOUNDS_RIGHT[0][0] <= x <= BOUNDS_RIGHT[1][0]
                and BOUNDS_RIGHT[0][1] <= y <= BOUNDS_RIGHT[1][1]
            ):
                button_type = ButtonType.RIGHT
                relative_coords = [x - BOUNDS_RIGHT[0][0], y - BOUNDS_RIGHT[0][1]]

            return {"type": button_type, "index": relative_coords, "active": state}

        return None


if __name__ == "__main__":
    lp = LaunchpadMK2()
    lp.set_led(1, 1, [0.5, 0.0, 0.0])  # Example: Light up the first button in red

    # Example of smart button event handling
    import time

    print("Press buttons on the Launchpad. Press Ctrl+C to exit.")
    try:
        while True:
            button_event = lp.get_button_events()
            if button_event:
                print(f"Button event: {button_event}")
                # Example output: {'type': ButtonType.SCENE, 'button': [2, 1], 'active': True}
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nExiting...")

    lp.close()
