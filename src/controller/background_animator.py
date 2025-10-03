import numpy as np
import logging
import time
from config import get_config
from utils import hex_to_rgb
from enums import AppState

logger = logging.getLogger(__name__)


class BackgroundAnimator:
    """Generates animated backgrounds with zone colors."""

    def __init__(self, preset_manager=None):
        self.pixel_buffer = np.zeros((9, 9, 3), dtype=float)
        self.frame = 0
        self.time = 0.0
        self.speed = 1.0
        self.config = get_config()
        self.preset_manager = preset_manager
        self.start_time = time.time()
        self.last_real_time = self.start_time

        self.BOUNDS_SCENES = np.array([[0, 1], [8, 5]])
        self.BOUNDS_PRESETS = np.array([[0, 6], [7, 8]])

        self.last_animation_type = None
        self.force_update = False
        self.last_update_time = 0.0

    def get_background(
        self,
        animation_type: str = "expanding_waves",
        app_state: AppState = AppState.NORMAL,
    ) -> np.ndarray:
        """Generate background animation frame.

        Returns pixel_buffer.
        """
        # Always update now since hardware-level optimization handles redundant updates
        self.last_animation_type = animation_type
        self.force_update = False

        # Clear buffer
        self.pixel_buffer.fill(0.0)

        if animation_type == "default":
            # Use real time for default animation
            current_real_time = time.time()
            real_elapsed = current_real_time - self.start_time
            self.time = real_elapsed * self.speed

            cycle_length = 38.0
            cycle_time = self.time % cycle_length

            # Check if we're in the swoosh period (first 5 seconds of cycle)
            if cycle_time < 5.0:
                # During swoosh - generate animation
                self._generate_default_effect()
        elif animation_type == "none":
            # No animation - buffer stays black
            pass
        else:
            animation_type = "default"

        # Apply zone colors and brightness to the completed animation buffer
        self._apply_zone_colors_and_brightness(app_state)
        self.last_update_time = self.time

        return self.pixel_buffer.copy()

    def _generate_default_effect(self):
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

    def _apply_zone_colors_and_brightness(self, app_state: AppState):
        """Apply zone colors and brightness to animation buffer."""
        brightness_static = self.config.data["brightness_background"]
        brightness_effect = self.config.data["brightness_background_effect"]

        # Get preset indices that have actual presets programmed
        preset_indices = set()
        if self.preset_manager:
            preset_indices = set(self.preset_manager.get_all_preset_indices().keys())

        for x in range(8):
            for y in range(9):
                base_color = self.pixel_buffer[x, y, :].copy()
                effect_color = base_color * brightness_effect

                # Apply column color to row 0
                print(app_state)
                if y == 0 and app_state == AppState.NORMAL:
                    if self.config.data["scene_on_color_from_column"]:
                        column_color_hex = self.config.data["colors"][
                            "column_colors"
                        ].get(str(x), "#ff0000")
                        column_color_rgb = hex_to_rgb(column_color_hex)
                        combined_color = [
                            min(
                                1.0,
                                column_color_rgb[0] * brightness_effect,
                            ),
                            min(
                                1.0,
                                column_color_rgb[1] * brightness_effect,
                            ),
                            min(
                                1.0,
                                column_color_rgb[2] * brightness_effect,
                            ),
                        ]
                        self.pixel_buffer[x, y] = combined_color
                        continue

                elif self.BOUNDS_PRESETS[0][1] <= y <= self.BOUNDS_PRESETS[1][1]:
                    # Only apply background color to preset buttons that have presets programmed
                    preset_coords = (
                        x,
                        y - 6,
                    )  # Convert to preset coordinate system (y 6-8 -> 0-2)
                    if preset_coords in preset_indices:
                        preset_bg_color = self.config.data["colors"][
                            "presets_background"
                        ]
                        # Apply static brightness to preset background colors
                        preset_bg_color_rgb = hex_to_rgb(preset_bg_color)
                        static_color = [
                            c * brightness_static for c in preset_bg_color_rgb
                        ]
                        # Combine effect and static colors
                        combined_color = [
                            min(1.0, effect_color[0] + static_color[0]),
                            min(1.0, effect_color[1] + static_color[1]),
                            min(1.0, effect_color[2] + static_color[2]),
                        ]
                        self.pixel_buffer[x, y] = combined_color
                        continue
                    # If no preset programmed, fall through to just use effect brightness

                # For areas without zone colors, just use the effect brightness
                self.pixel_buffer[x, y] = effect_color

    def force_background_update(self):
        """Force next background update."""
        self.force_update = True

    def reset_animation_timer(self):
        """Reset the animation timer to start a new cycle."""
        self.start_time = time.time()
        self.time = 0.0


class BackgroundManager:
    """Manages background animation cycling."""

    def __init__(self, preset_manager=None):
        self.animator = BackgroundAnimator(preset_manager)
        self.background_animations = [
            "default",
            "none",
            # "stellar_pulse",
            # "shadow_waves",
            # "plasma_storm",
            # "deep_pulse",
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

    def generate_background(self) -> np.ndarray:
        """Generate the current background animation frame."""
        return self.animator.get_background(self.current_background)

    def force_background_update(self):
        """Force the next background update."""
        self.animator.force_background_update()
