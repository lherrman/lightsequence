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


class Animator:
    def __init__(self):
        self.pixel_buffer = np.zeros((9, 9, 3), dtype=float)
        self.frame = 0
        self.time = 0.0
        self.speed = 1.0

    def get_background(self, animation_type: str = "expanding_waves") -> np.ndarray:
        """
        Update animation and return the current pixel buffer.

        Args:
            animation_type: Type of animation to generate
                - "expanding_waves": Concentric blue waves expanding from center
                - "ripple_effect": Multiple ripple sources with blue tones
                - "ocean_waves": Flowing horizontal waves in ocean blues
                - "pulse_gradient": Pulsing blue gradient from center
                - "spiral_waves": Spiral blue waves rotating outward
                - "breathing": Gentle breathing effect in blue tones

        Returns:
            np.ndarray: 9x9x3 pixel buffer with RGB values (0.0-1.0)
        """
        self.time += 0.2 * self.speed
        self.frame += 1

        # Clear buffer
        self.pixel_buffer.fill(0.0)

        if animation_type == "expanding_waves":
            self._generate_expanding_waves()
        elif animation_type == "ripple_effect":
            self._generate_ripple_effect()
        elif animation_type == "ocean_waves":
            self._generate_ocean_waves()
        elif animation_type == "pulse_gradient":
            self._generate_pulse_gradient()
        elif animation_type == "spiral_waves":
            self._generate_spiral_waves()
        elif animation_type == "breathing":
            self._generate_breathing()
        else:
            # Default to expanding waves
            self._generate_expanding_waves()

        return self.pixel_buffer.copy()

    def _generate_expanding_waves(self):
        """Generate concentric blue waves expanding from center."""
        center_x, center_y = 3.5, 4.5  # Center of 8x8 area (0,1) to (7,8)

        for x in range(8):  # 0 to 7
            for y in range(1, 9):  # 1 to 8
                # Calculate distance from center
                distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)

                # Create wave pattern
                wave = np.sin(distance * 1.5 - self.time * 2.0) * 0.5 + 0.5

                # Multiple wave frequencies for complexity
                wave2 = np.sin(distance * 0.8 - self.time * 1.5) * 0.3 + 0.3
                wave3 = np.sin(distance * 2.2 - self.time * 2.5) * 0.2 + 0.2

                combined_wave = (wave + wave2 + wave3) / 3.0

                # Blue color variations
                blue_intensity = combined_wave
                cyan_mix = np.sin(self.time * 0.5) * 0.3 + 0.3

                self.pixel_buffer[x, y] = [
                    blue_intensity * 0.1,  # Slight red tint
                    blue_intensity * cyan_mix,  # Cyan component
                    blue_intensity,  # Full blue
                ]

    def _generate_ripple_effect(self):
        """Generate multiple ripple sources creating interference patterns."""
        # Multiple ripple centers adjusted for 8x8 area (0,1) to (7,8)
        ripple_centers = [(2, 3), (6, 7), (2, 7), (6, 3)]

        for x in range(8):  # 0 to 7
            for y in range(1, 9):  # 1 to 8
                total_wave = 0.0

                for cx, cy in ripple_centers:
                    distance = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    # Each ripple has slightly different frequency and phase
                    ripple = np.sin(
                        distance * 1.2 - self.time * 1.8 + hash((cx, cy)) % 10
                    )
                    total_wave += ripple * 0.25

                # Normalize and create blue variations
                intensity = (total_wave + 1.0) * 0.5

                # Create depth with darker and lighter blues
                deep_blue = intensity * 0.8
                light_blue = intensity * 1.2

                self.pixel_buffer[x, y] = [
                    deep_blue * 0.05,  # Minimal red
                    light_blue * 0.6,  # Cyan component
                    light_blue,  # Main blue
                ]

    def _generate_ocean_waves(self):
        """Generate flowing horizontal waves like ocean."""
        for x in range(8):  # 0 to 7
            for y in range(1, 9):  # 1 to 8
                # Horizontal wave with vertical variation
                wave1 = np.sin(y * 0.8 + self.time * 2.0) * 0.4 + 0.6
                wave2 = np.sin(y * 1.2 + x * 0.3 + self.time * 1.5) * 0.3 + 0.3
                wave3 = np.sin(y * 0.5 + x * 0.1 + self.time * 2.5) * 0.2 + 0.2

                combined = (wave1 + wave2 + wave3) / 3.0

                # Ocean-like blue gradient (adjusted for y range 1-8)
                depth_factor = (9 - y) / 8.0  # Deeper blues at bottom

                self.pixel_buffer[x, y] = [
                    combined * 0.05,  # Minimal red
                    combined * (0.3 + depth_factor * 0.4),  # Varying cyan
                    combined * (0.6 + depth_factor * 0.4),  # Varying blue
                ]

    def _generate_pulse_gradient(self):
        """Generate pulsing blue gradient from center."""
        center_x, center_y = 3.5, 4.5  # Center of 8x8 area (0,1) to (7,8)
        max_distance = np.sqrt(3.5**2 + 3.5**2)

        # Pulsing intensity
        pulse = np.sin(self.time * 1.5) * 0.3 + 0.7

        for x in range(8):  # 0 to 7
            for y in range(1, 9):  # 1 to 8
                distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)

                # Gradient based on distance from center
                gradient = 1.0 - (distance / max_distance)
                gradient = max(0.0, gradient)

                # Apply pulse
                intensity = gradient * pulse

                # Blue gradient with slight variations
                self.pixel_buffer[x, y] = [
                    intensity * 0.1,  # Slight red
                    intensity * 0.7,  # Cyan component
                    intensity,  # Full blue intensity
                ]

    def _generate_spiral_waves(self):
        """Generate spiral blue waves rotating outward."""
        center_x, center_y = 3.5, 4.5  # Center of 8x8 area (0,1) to (7,8)

        for x in range(8):  # 0 to 7
            for y in range(1, 9):  # 1 to 8
                dx = x - center_x
                dy = y - center_y
                distance = np.sqrt(dx**2 + dy**2)
                angle = np.arctan2(dy, dx)

                # Spiral wave pattern
                spiral = np.sin(distance * 1.5 - angle * 3.0 + self.time * 2.0)
                wave_intensity = (spiral + 1.0) * 0.5

                # Add rotation effect
                rotation_effect = np.sin(angle * 2.0 + self.time * 1.0) * 0.2 + 0.2

                combined_intensity = (wave_intensity + rotation_effect) / 2.0

                self.pixel_buffer[x, y] = [
                    combined_intensity * 0.08,  # Minimal red
                    combined_intensity * 0.6,  # Cyan
                    combined_intensity * 0.9,  # Strong blue
                ]

    def _generate_breathing(self):
        """Generate gentle breathing effect in blue tones."""
        # Slow breathing pattern
        breath = np.sin(self.time * 0.8) * 0.5 + 0.5

        # Secondary gentle wave
        secondary = np.sin(self.time * 0.5 + np.pi / 4) * 0.2 + 0.2

        for x in range(8):  # 0 to 7
            for y in range(1, 9):  # 1 to 8
                # Distance from center for gradient (adjusted for 8x8 area)
                distance = np.sqrt((x - 3.5) ** 2 + (y - 4.5) ** 2)
                gradient = 1.0 - (distance / 5.0)  # Adjusted max distance
                gradient = max(0.1, gradient)

                # Combine breathing with gradient
                intensity = gradient * (breath + secondary)

                # Soft blue tones
                self.pixel_buffer[x, y] = [
                    intensity * 0.05,  # Minimal red
                    intensity * 0.4,  # Soft cyan
                    intensity * 0.8,  # Gentle blue
                ]


class LaunchpadMK2:
    def __init__(self):
        self.BOUNDS_SCENES = np.array([[0, 1], [7, 5]])
        self.BOUNDS_PRESETS = np.array([[0, 6], [7, 8]])
        self.BOUNDS_TOP = np.array([[0, 0], [7, 0]])
        self.BOUNDS_RIGHT = np.array([[8, 1], [8, 8]])

        self.pixel_buffer_output = np.zeros(
            (9, 9, 3), dtype=float
        )  # 9x9 grid for Launchpad MK2

        # Track pressed buttons state: {(button_type, rel_x, rel_y): True}
        self._pressed_buttons: t.Dict[t.Tuple[ButtonType, int, int], bool] = {}
        self.animator = Animator()

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

        color = [int(c * 63) for c in color]  # Scale to 0-127
        self.device.LedCtrlXY(x, y, *color)

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
            self.pixel_buffer_output[abs_x, abs_y] = color
            self.set_led(abs_x, abs_y, color)
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

    def draw_background(self, animation_type: str = "ocean_waves") -> None:
        """Fill entire Launchpad with animated background or solid color."""
        if not self.is_connected:
            return

        # Use animator to generate background
        background_buffer = self.animator.get_background(animation_type)
        for x in range(8):
            for y in range(1, 9):
                if not self.pixel_buffer_output[x, y, :].any():
                    # Use animated background where no other LED is set
                    color = background_buffer[x, y, :].tolist()
                    self.set_led(x, y, color)


if __name__ == "__main__":
    pixel_buffer = np.zeros((9, 9, 3), dtype=float)
    pixel_buffer[0, 0] = [1.0, 0.0, 0.0]
    for x in range(9):
        for y in range(9):
            if pixel_buffer[x, y, :].any():
                print(f"Setting LED at ({x}, {y}) to {pixel_buffer[x, y, :]}")
