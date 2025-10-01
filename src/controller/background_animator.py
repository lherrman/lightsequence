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
                - "default": Mostly black void with rare electric blue ripples
                - "none": No background animation - completely black


        Returns:
            np.ndarray: 9x9x3 pixel buffer with RGB values (0.0-1.0)
        """
        self.time += 0.2 * self.speed
        self.frame += 1

        # Clear buffer
        self.pixel_buffer.fill(0.0)

        if animation_type == "default":
            self._generate_void_ripples()
        elif animation_type == "none":
            # No animation - buffer stays black
            pass
        elif animation_type == "stellar_pulse":
            self._generate_stellar_pulse()
        elif animation_type == "shadow_waves":
            self._generate_shadow_waves()
        elif animation_type == "plasma_storm":
            self._generate_plasma_storm()
        elif animation_type == "deep_pulse":
            self._generate_deep_pulse()
        else:
            # Default to void ripples
            self._generate_void_ripples()

        return self.pixel_buffer.copy()

    def _generate_void_ripples(self):
        """Generate blank background with 5-second wave swooshes every 30-40 seconds."""
        # Calculate time within each 38-second cycle
        
        cycle_length = 38.0  # seconds (5 for wave + 33 for silence)
        cycle_time = self.time % cycle_length

        # Only activate during first 5 seconds of each cycle
        if cycle_time < 5.0:
            # Slower swoosh progress over 5 seconds (0 to 1)
            swoosh_progress = cycle_time / 5.0

            # Generate random direction for this cycle (0-360 degrees)
            cycle_number = int(self.time // cycle_length)
            np.random.seed(
                cycle_number
            )  # Use cycle as seed for consistent direction within wave
            angle_degrees = np.random.uniform(0, 360)
            angle_radians = np.radians(angle_degrees)

            # Calculate direction vector (unit vector)
            dir_x = np.cos(angle_radians)
            dir_y = np.sin(angle_radians)

            # Calculate the grid bounds to ensure wave starts off-screen
            # Grid center is at (3.5, 4.5), extends roughly -4 to +4 in each direction
            grid_center_x, grid_center_y = 3.5, 4.5
            max_grid_distance = 8.0  # Maximum distance from center to corner

            # Wave starts well off-screen and sweeps across
            wave_start_distance = -max_grid_distance - 2.0
            wave_end_distance = max_grid_distance + 2.0
            wave_distance = wave_start_distance + swoosh_progress * (
                wave_end_distance - wave_start_distance
            )

            for x in range(8):
                for y in range(1, 9):
                    # Calculate position relative to grid center
                    px = x - grid_center_x
                    py = y - grid_center_y

                    # Project point onto wave direction vector
                    point_projection = px * dir_x + py * dir_y

                    # Distance from the moving wave front
                    distance_from_front = point_projection - wave_distance

                    # Create wave with smooth front and tail
                    if -3.0 <= distance_from_front <= 1.0:  # Wave width (longer tail)
                        if distance_from_front <= 0:
                            # Bright front of wave
                            wave_intensity = (3.0 + distance_from_front) / 3.0
                        else:
                            # Sharp falloff behind wave
                            wave_intensity = (1.0 - distance_from_front) / 1.0

                        # Ensure intensity is within bounds
                        wave_intensity = max(0.0, min(1.0, wave_intensity))

                        # Add flowing wave pattern for texture
                        wave_texture = (
                            np.sin((px + py) * 0.8 + swoosh_progress * 10.0) * 0.2 + 0.8
                        )
                        final_intensity = wave_intensity * wave_texture * 0.9

                        if final_intensity > 0.1:
                            self.pixel_buffer[x, y] = [
                                0.0,  # No red
                                final_intensity * 0.4,  # Cyan component
                                final_intensity,  # Strong blue wave
                            ]

    def _generate_stellar_pulse(self):
        """Generate dark space with pulsing star-like points."""
        # Create sparse starfield with pulsing stars
        star_positions = [(1, 2), (6, 3), (2, 6), (5, 7), (3, 4), (7, 2)]

        for star_x, star_y in star_positions:
            # Each star pulses at different rates
            star_phase = self.time * (0.5 + (star_x + star_y) * 0.1)
            pulse = (np.sin(star_phase) + 1.0) * 0.5  # 0 to 1

            # Only show bright pulses occasionally
            if pulse > 0.7:
                brightness = (pulse - 0.7) / 0.3  # Normalize to 0-1

                # Create small star with glow
                for x in range(8):
                    for y in range(1, 9):
                        distance = abs(x - star_x) + abs(
                            y - star_y
                        )  # Manhattan distance

                        if distance == 0:  # Center of star
                            intensity = brightness * 0.8
                        elif distance == 1:  # Adjacent pixels
                            intensity = brightness * 0.4
                        elif distance == 2:  # Outer glow
                            intensity = brightness * 0.15
                        else:
                            continue

                        # Bright blue-white star
                        existing = self.pixel_buffer[x, y]
                        self.pixel_buffer[x, y] = [
                            max(existing[0], intensity * 0.8),  # White component
                            max(existing[1], intensity * 0.9),
                            max(existing[2], intensity),  # Strong blue
                        ]

    def _generate_shadow_waves(self):
        """Generate flowing dark waves with subtle blue highlights."""
        for x in range(8):  # 0 to 7
            for y in range(1, 9):  # 1 to 8
                # Create flowing wave pattern
                wave1 = np.sin(y * 0.5 + self.time * 1.5)
                wave2 = np.sin(x * 0.3 + y * 0.2 + self.time * 1.0)

                # Combine waves and make mostly negative (dark)
                combined = (wave1 + wave2 * 0.5) * 0.3

                # Only show positive values as blue highlights
                if combined > 0.1:
                    intensity = (combined - 0.1) * 1.5  # Amplify positive values
                    intensity = min(intensity, 0.6)  # Cap intensity for darkness

                    # Subtle blue highlights on dark background
                    self.pixel_buffer[x, y] = [
                        0.0,  # No red
                        intensity * 0.3,  # Minimal cyan
                        intensity * 0.7,  # Subdued blue
                    ]

    def _generate_plasma_storm(self):
        """Generate dark background with electric plasma bursts."""
        # Create plasma storm centers
        storm_centers = [(1.5, 3.0), (5.5, 6.5), (6.0, 2.0)]

        for center_x, center_y in storm_centers:
            # Each storm has different timing and intensity
            storm_phase = self.time * (1.2 + center_x * 0.2) + center_y
            storm_intensity = np.sin(storm_phase) ** 2  # Square for sharp bursts

            # Only create plasma when intensity is high
            if storm_intensity > 0.4:
                plasma_strength = (storm_intensity - 0.4) / 0.6

                for x in range(8):
                    for y in range(1, 9):
                        distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)

                        # Electric plasma effect - irregular and sharp
                        if distance < 3.0:
                            # Add some chaos to the plasma
                            chaos = np.sin(self.time * 4.0 + x * 2.5 + y * 1.8) * 0.3
                            plasma_falloff = max(0, 1.0 - distance / 3.0) + chaos
                            plasma_falloff = max(0, plasma_falloff)

                            final_intensity = plasma_falloff * plasma_strength * 0.7

                            if final_intensity > 0.1:
                                # Electric blue-white plasma
                                existing = self.pixel_buffer[x, y]
                                self.pixel_buffer[x, y] = [
                                    max(
                                        existing[0], final_intensity * 0.6
                                    ),  # Some white
                                    max(existing[1], final_intensity * 0.9),  # Cyan
                                    max(existing[2], final_intensity),  # Strong blue
                                ]

    def _generate_deep_pulse(self):
        """Generate slow deep pulsing from the abyss."""
        # Very slow, deep breathing pattern
        deep_breath = np.sin(self.time * 0.2) ** 2  # Very slow, squared for sharpness

        # Only show when the pulse is strong enough
        if deep_breath > 0.3:
            pulse_strength = (deep_breath - 0.3) / 0.7  # Normalize

            # Create pulsing from multiple deep points
            abyss_points = [(2.0, 7.0), (6.0, 3.0), (4.0, 5.0)]

            for abyss_x, abyss_y in abyss_points:
                for x in range(8):
                    for y in range(1, 9):
                        distance = np.sqrt((x - abyss_x) ** 2 + (y - abyss_y) ** 2)

                        # Deep, slow falloff
                        if distance < 4.0:
                            depth_intensity = max(0, 1.0 - distance / 4.0) ** 2
                            final_intensity = depth_intensity * pulse_strength * 0.5

                            if final_intensity > 0.05:
                                # Deep blue pulsing
                                existing = self.pixel_buffer[x, y]
                                self.pixel_buffer[x, y] = [
                                    existing[0],  # No red
                                    max(
                                        existing[1], final_intensity * 0.2
                                    ),  # Minimal cyan
                                    max(
                                        existing[2], final_intensity * 0.7
                                    ),  # Deep blue
                                ]


class BackgroundManager:
    """Manages background animations and cycling."""

    def __init__(self):
        self.animator = BackgroundAnimator()
        self.background_animations = [
            "default",  # Index 0 - Default effect (void ripples)
            "none",  # Index 1 - No background animation
            "stellar_pulse",  # Index 2
            "shadow_waves",  # Index 3
            "plasma_storm",  # Index 4
            "deep_pulse",  # Index 5
        ]
        self.current_background_index = 0  # Start with "default"
        self.current_background = self.background_animations[
            self.current_background_index
        ]

    def cycle_background(self) -> str:
        """Cycle to the next background animation and return its name."""
        self.current_background_index = (self.current_background_index + 1) % len(
            self.background_animations
        )
        self.current_background = self.background_animations[
            self.current_background_index
        ]
        logger.info(f"Switched to background: {self.current_background}")
        return self.current_background

    def get_current_background(self) -> str:
        """Get the current background animation name."""
        return self.current_background

    def generate_background(self) -> np.ndarray:
        """Generate the current background animation frame."""
        return self.animator.get_background(self.current_background)
