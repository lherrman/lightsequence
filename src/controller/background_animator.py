import numpy as np
import logging
from config import get_config_manager

logger = logging.getLogger(__name__)


class BackgroundAnimator:
    """Generates animated backgrounds with zone colors."""

    def __init__(self):
        self.pixel_buffer = np.zeros((9, 9, 3), dtype=float)
        self.frame = 0
        self.time = 0.0
        self.speed = 1.0
        self.config_manager = get_config_manager()

        self.BOUNDS_SCENES = np.array([[0, 1], [8, 5]])
        self.BOUNDS_PRESETS = np.array([[0, 6], [7, 8]])

        self.last_animation_type = None
        self.force_update = False
        self.last_update_time = 0.0

    def get_background(
        self, animation_type: str = "expanding_waves"
    ) -> tuple[np.ndarray, bool]:
        """Generate background animation frame.

        Returns (pixel_buffer, needs_update) tuple.
        """
        needs_update = animation_type != self.last_animation_type or self.force_update

        if needs_update:
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
                    self.time += (
                        time_until_next_cycle + 0.01
                    )  # Small epsilon to cross threshold
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
        """Periodic blue wave animation."""
        cycle_length = 38.0
        cycle_time = self.time % cycle_length

        if cycle_time < 5.0:
            swoosh_progress = cycle_time / 5.0

            cycle_number = int(self.time // cycle_length)
            np.random.seed(cycle_number)
            angle_radians = np.radians(np.random.uniform(0, 360))

            dir_x = np.cos(angle_radians)
            dir_y = np.sin(angle_radians)

            grid_center_x, grid_center_y = 3.5, 4.5
            max_grid_distance = 8.0

            wave_start_distance = -max_grid_distance - 2.0
            wave_end_distance = max_grid_distance + 2.0
            wave_distance = wave_start_distance + swoosh_progress * (
                wave_end_distance - wave_start_distance
            )

            for x in range(8):
                for y in range(1, 9):
                    px = x - grid_center_x
                    py = y - grid_center_y
                    point_projection = px * dir_x + py * dir_y
                    distance_from_front = point_projection - wave_distance

                    if -3.0 <= distance_from_front <= 1.0:
                        if distance_from_front <= 0:
                            wave_intensity = (3.0 + distance_from_front) / 3.0
                        else:
                            wave_intensity = (1.0 - distance_from_front) / 1.0

                        wave_intensity = max(0.0, min(1.0, wave_intensity))
                        wave_texture = (
                            np.sin((px + py) * 0.8 + swoosh_progress * 10.0) * 0.2 + 0.8
                        )
                        final_intensity = wave_intensity * wave_texture * 0.9

                        if final_intensity > 0.1:
                            self.pixel_buffer[x, y] = [
                                0.0,
                                final_intensity * 0.4,
                                final_intensity,
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

    def _apply_zone_colors_and_brightness(self):
        """Apply zone colors and brightness to animation buffer."""
        brightness_static = self.config_manager.get_brightness_background()
        brightness_effect = self.config_manager.get_brightness_background_effect()

        for x in range(8):
            for y in range(1, 9):
                base_color = self.pixel_buffer[x, y, :].copy()
                
                # Apply effect brightness to the animated content first
                effect_color = [c * brightness_effect for c in base_color]

                if self.BOUNDS_SCENES[0][1] <= y <= self.BOUNDS_SCENES[1][1]:
                    column_color = self.config_manager.get_column_color(x)
                    if column_color:
                        # Apply static brightness to column colors
                        static_color = [c * brightness_static for c in column_color]
                        # Combine effect and static colors
                        combined_color = [
                            min(1.0, effect_color[0] + static_color[0]),
                            min(1.0, effect_color[1] + static_color[1]),
                            min(1.0, effect_color[2] + static_color[2]),
                        ]
                        self.pixel_buffer[x, y] = combined_color
                        continue

                elif self.BOUNDS_PRESETS[0][1] <= y <= self.BOUNDS_PRESETS[1][1]:
                    preset_bg_color = self.config_manager.get_presets_background_color()
                    # Apply static brightness to preset background colors
                    static_color = [c * brightness_static for c in preset_bg_color]
                    # Combine effect and static colors
                    combined_color = [
                        min(1.0, effect_color[0] + static_color[0]),
                        min(1.0, effect_color[1] + static_color[1]),
                        min(1.0, effect_color[2] + static_color[2]),
                    ]
                    self.pixel_buffer[x, y] = combined_color
                    continue

                # For areas without zone colors, just use the effect brightness
                self.pixel_buffer[x, y] = effect_color

    def force_background_update(self):
        """Force next background update."""
        self.force_update = True


class BackgroundManager:
    """Manages background animation cycling."""

    def __init__(self):
        self.animator = BackgroundAnimator()
        self.background_animations = [
            "default",
            "none",
            "stellar_pulse",
            "shadow_waves",
            "plasma_storm",
            "deep_pulse",
        ]
        self.current_background_index = 0
        self.current_background = self.background_animations[0]

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
