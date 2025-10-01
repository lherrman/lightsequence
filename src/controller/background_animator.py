import numpy as np
import logging

logger = logging.getLogger(__name__)


class BackgroundAnimator:
    """Handles animated backgrounds for the Launchpad display."""
    
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


class BackgroundManager:
    """Manages background animations and cycling."""
    
    def __init__(self):
        self.animator = BackgroundAnimator()
        self.background_animations = [
            "expanding_waves",
            "ripple_effect",
            "ocean_waves",
            "pulse_gradient",
            "spiral_waves",
            "breathing",
        ]
        self.current_background_index = 2  # Start with "ocean_waves"
        self.current_background = self.background_animations[self.current_background_index]
    
    def cycle_background(self) -> str:
        """Cycle to the next background animation and return its name."""
        self.current_background_index = (self.current_background_index + 1) % len(
            self.background_animations
        )
        self.current_background = self.background_animations[self.current_background_index]
        logger.info(f"Switched to background: {self.current_background}")
        return self.current_background
    
    def get_current_background(self) -> str:
        """Get the current background animation name."""
        return self.current_background
    
    def generate_background(self) -> np.ndarray:
        """Generate the current background animation frame."""
        return self.animator.get_background(self.current_background)