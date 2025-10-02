import numpy as np
import logging
from config import get_config_manager

logger = logging.getLogger(__name__)


class BackgroundAnimator:
    """Handles animated backgrounds for the Launchpad display."""

    def __init__(self):
        self.pixel_buffer = np.zeros((9, 9, 3), dtype=float)
        self.frame = 0
        self.time = 0.0
        self.speed = 1.0
        self.config_manager = get_config_manager()
        
        # Define zone boundaries (same as launchpad)
        self.BOUNDS_SCENES = np.array([[0, 1], [8, 5]])  # Scene area: columns 0-7, rows 1-4
        self.BOUNDS_PRESETS = np.array([[0, 6], [7, 8]])  # Preset area: columns 0-7, rows 6-7
        
        # Update tracking for optimization
        self.last_animation_type = None
        self.force_update = False  # Flag to force update when foreground changes
        self.last_update_time = 0.0

    def get_background(self, animation_type: str = "expanding_waves") -> tuple[np.ndarray, bool]:
        """
        Update animation and return the current pixel buffer with update flag.

        Args:
            animation_type: Type of animation to generate
                - "default": Mostly black void with rare electric blue ripples
                - "none": No background animation - completely black

        Returns:
            tuple: (pixel_buffer: 9x9x3 array with RGB values 0.0-1.0, needs_update: bool)
        """
        needs_update = False
        
        # Check if we need to update due to animation type change or forced update
        if (animation_type != self.last_animation_type or 
            self.force_update):
            needs_update = True
            self.last_animation_type = animation_type
            self.force_update = False
        
        # Clear buffer
        self.pixel_buffer.fill(0.0)

        if animation_type == "default":
            # Only update time when we're in the default animation
            # Check if we need to animate (during swoosh period)
            cycle_length = 38.0
            cycle_time = self.time % cycle_length
            if cycle_time < 5.0:
                # During swoosh - update time and animate
                old_time = self.time
                self.time += 0.2 * self.speed
                self.frame += 1
                self._generate_void_ripples()
                needs_update = True
            else:
                # During silent period - check if we should start next cycle
                # Only update time at the very end of cycle to avoid micro-changes
                time_until_next_cycle = cycle_length - cycle_time
                if time_until_next_cycle < 0.2 * self.speed:
                    # Close enough to next cycle, advance to it
                    self.time += time_until_next_cycle + 0.01  # Small epsilon to cross threshold
                    needs_update = True
                # Don't generate anything - buffer stays black
        elif animation_type == "none":
            # No animation - buffer stays black, only update if forced or type changed
            pass
        elif animation_type == "stellar_pulse":
            self.time += 0.2 * self.speed
            self.frame += 1
            self._generate_stellar_pulse()
            needs_update = True
        elif animation_type == "shadow_waves":
            self.time += 0.2 * self.speed
            self.frame += 1
            self._generate_shadow_waves()
            needs_update = True
        elif animation_type == "plasma_storm":
            self.time += 0.2 * self.speed
            self.frame += 1
            self._generate_plasma_storm()
            needs_update = True
        elif animation_type == "deep_pulse":
            self.time += 0.2 * self.speed
            self.frame += 1
            self._generate_deep_pulse()
            needs_update = True
        else:
            animation_type = "default"
            needs_update = True

        # Apply zone colors and brightness to the completed animation buffer
        # (only if we need to update)
        if needs_update:
            self._apply_zone_colors_and_brightness()
            self.last_update_time = self.time

        return self.pixel_buffer.copy(), needs_update

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
        # When not in swoosh period (cycle_time >= 5.0), buffer remains filled with zeros
        # This ensures completely static background during silent periods

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

    def _apply_zone_colors_and_brightness(self):
        """Apply zone-specific colors and brightness to the animation buffer."""
        brightness_multiplier = self.config_manager.get_brightness_background()
        
        for x in range(8):  # Columns 0-7
            for y in range(1, 9):  # Rows 1-8 (excluding top row 0)
                # Get the base animation color
                base_color = self.pixel_buffer[x, y, :].copy()
                
                # Check if this is a scene area (rows 1-4) and add column colors
                if self.BOUNDS_SCENES[0][1] <= y <= self.BOUNDS_SCENES[1][1]:
                    # This is in the scene area - layer column color on top of animation
                    column_color = self.config_manager.get_column_color(x)
                    if column_color:
                        # Combine the animation color with column color (additive)
                        combined_color = [
                            min(1.0, base_color[0] + column_color[0]),
                            min(1.0, base_color[1] + column_color[1]), 
                            min(1.0, base_color[2] + column_color[2])
                        ]
                        # Apply background brightness and store
                        final_color = [c * brightness_multiplier for c in combined_color]
                        self.pixel_buffer[x, y] = final_color
                        continue
                
                # Check if this is preset area (rows 6-7)
                elif self.BOUNDS_PRESETS[0][1] <= y <= self.BOUNDS_PRESETS[1][1]:
                    # This is in the preset area - layer preset background color on animation
                    preset_bg_color = self.config_manager.get_presets_background_color()
                    combined_color = [
                        min(1.0, base_color[0] + preset_bg_color[0]),
                        min(1.0, base_color[1] + preset_bg_color[1]),
                        min(1.0, base_color[2] + preset_bg_color[2])
                    ]
                    # Apply background brightness and store
                    final_color = [c * brightness_multiplier for c in combined_color]
                    self.pixel_buffer[x, y] = final_color
                    continue
                
                # For all other areas (top row and right column), just apply background brightness
                final_color = [c * brightness_multiplier for c in base_color]
                self.pixel_buffer[x, y] = final_color

    def force_background_update(self):
        """Force the next background update regardless of animation state."""
        self.force_update = True


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

    def generate_background(self) -> tuple[np.ndarray, bool]:
        """Generate the current background animation frame."""
        return self.animator.get_background(self.current_background)
    
    def force_background_update(self):
        """Force the next background update."""
        self.animator.force_background_update()
