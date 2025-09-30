import logging
import typing as t
import launchpad_py as lp

logger = logging.getLogger(__name__)


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

    def get_buttons(self) -> t.Optional[t.Tuple[int, int, bool]]:
        """Get button press. Returns (x, y, state) or None if no press."""
        if not self.is_connected:
            return None

        button = self.device.ButtonStateXY()
        if button:
            x, y, state = button
            state = True if state else False
            return (x, y, state)
        return None


if __name__ == "__main__":
    lp = LaunchpadMK2()
    lp.set_led(1, 1, [0.5, 0.0, 0.0])  # Example: Light up the first button in red
    lp.close()
