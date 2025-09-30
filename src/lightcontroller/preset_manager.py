"""
Preset management for the lighting controller
Manages presets that activate combinations of the 40 automatic scenes
"""

import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AutoPreset:
    """Represents a preset that activates multiple scenes."""

    index: int
    x: int
    y: int
    name: str
    description: str
    scene_indices: List[int]
    cycle_mode: bool = False
    cycle_interval: float = 2.0
    active: bool = False

    @property
    def button_description(self) -> str:
        """Get button description."""
        return f"Preset {self.index}: {self.name}"


class PresetManager:
    """Manages presets for the 24 preset buttons (8x3 grid)."""

    def __init__(
        self, feedback_callback: Optional[Callable[[int, int, bool], None]] = None
    ):
        self.presets: Dict[int, AutoPreset] = {}
        self.active_preset: Optional[int] = None
        self.feedback_callback = feedback_callback

        # Create default presets
        self._create_default_presets()

        logger.info(f"Initialized {len(self.presets)} presets")

    def _create_default_presets(self):
        """Create some default presets."""
        default_presets = [
            # Row 0 (y=5 in grid coordinates)
            {"name": "Full Wash", "desc": "All scenes", "scenes": list(range(40))},
            {"name": "Front Row", "desc": "First row only", "scenes": list(range(8))},
            {
                "name": "Back Row",
                "desc": "Last row only",
                "scenes": list(range(32, 40)),
            },
            {
                "name": "Alternating",
                "desc": "Every other scene",
                "scenes": [i for i in range(40) if i % 2 == 0],
            },
            {
                "name": "Center",
                "desc": "Center scenes",
                "scenes": [18, 19, 20, 21, 26, 27, 28, 29],
            },
            {"name": "Corners", "desc": "Corner scenes", "scenes": [0, 7, 32, 39]},
            {
                "name": "Cross",
                "desc": "Cross pattern",
                "scenes": [3, 4, 11, 12, 19, 20, 27, 28, 35, 36],
            },
            {"name": "Blackout", "desc": "All off", "scenes": []},
            # Row 1 (y=6 in grid coordinates)
            {
                "name": "Rows 1&3",
                "desc": "First and third rows",
                "scenes": list(range(8)) + list(range(16, 24)),
            },
            {
                "name": "Rows 2&4",
                "desc": "Second and fourth rows",
                "scenes": list(range(8, 16)) + list(range(24, 32)),
            },
            {
                "name": "Left Half",
                "desc": "Left columns",
                "scenes": [i for i in range(40) if i % 8 < 4],
            },
            {
                "name": "Right Half",
                "desc": "Right columns",
                "scenes": [i for i in range(40) if i % 8 >= 4],
            },
            {
                "name": "Checkerboard",
                "desc": "Checkerboard pattern",
                "scenes": [i for i in range(40) if (i % 8 + i // 8) % 2 == 0],
            },
            {
                "name": "Border",
                "desc": "Border only",
                "scenes": [
                    0,
                    1,
                    2,
                    3,
                    4,
                    5,
                    6,
                    7,
                    8,
                    15,
                    16,
                    23,
                    24,
                    31,
                    32,
                    33,
                    34,
                    35,
                    36,
                    37,
                    38,
                    39,
                ],
            },
            {
                "name": "Inside",
                "desc": "Inside only",
                "scenes": [
                    9,
                    10,
                    11,
                    12,
                    13,
                    14,
                    17,
                    18,
                    19,
                    20,
                    21,
                    22,
                    25,
                    26,
                    27,
                    28,
                    29,
                    30,
                ],
            },
            {"name": "Custom 1", "desc": "Custom preset 1", "scenes": []},
            # Row 2 (y=7 in grid coordinates)
            {"name": "Custom 2", "desc": "Custom preset 2", "scenes": []},
            {"name": "Custom 3", "desc": "Custom preset 3", "scenes": []},
            {"name": "Custom 4", "desc": "Custom preset 4", "scenes": []},
            {"name": "Custom 5", "desc": "Custom preset 5", "scenes": []},
            {"name": "Custom 6", "desc": "Custom preset 6", "scenes": []},
            {"name": "Custom 7", "desc": "Custom preset 7", "scenes": []},
            {"name": "Custom 8", "desc": "Custom preset 8", "scenes": []},
            {"name": "Emergency", "desc": "Emergency blackout", "scenes": []},
        ]

        for index, preset_data in enumerate(default_presets[:24]):  # Max 24 presets
            x = index % 8
            y = (index // 8) + 5  # Preset area starts at y=5

            self.presets[index] = AutoPreset(
                index=index,
                x=x,
                y=y,
                name=preset_data["name"],
                description=preset_data["desc"],
                scene_indices=preset_data["scenes"],
            )

    def activate_preset(self, preset_index: int) -> bool:
        """
        Activate a preset.

        Args:
            preset_index: Preset index (0-23)

        Returns:
            True if preset was activated, False if toggled off
        """
        if preset_index not in self.presets:
            logger.warning(f"Invalid preset index: {preset_index}")
            return False

        preset = self.presets[preset_index]

        # If this preset is already active, deactivate it
        if self.active_preset == preset_index:
            self.deactivate_current_preset()
            return False

        # Deactivate current preset first
        if self.active_preset is not None:
            self.deactivate_current_preset()

        # Activate new preset
        self.active_preset = preset_index
        preset.active = True

        logger.info(f"🎯 Activated preset: {preset.name}")

        # Light up preset button
        if self.feedback_callback:
            preset_y = preset.y - 5  # Convert to 0-2 range for preset buttons
            self.feedback_callback(preset.x, preset_y, True)

        return True

    def deactivate_current_preset(self):
        """Deactivate the currently active preset."""
        if self.active_preset is None:
            return

        preset = self.presets[self.active_preset]
        preset.active = False

        logger.info(f"⚫ Deactivated preset: {preset.name}")

        # Turn off preset button
        if self.feedback_callback:
            preset_y = preset.y - 5  # Convert to 0-2 range for preset buttons
            self.feedback_callback(preset.x, preset_y, False)

        self.active_preset = None

    def get_active_preset(self) -> Optional[AutoPreset]:
        """Get the currently active preset."""
        if self.active_preset is not None:
            return self.presets.get(self.active_preset)
        return None

    def get_preset(self, preset_index: int) -> Optional[AutoPreset]:
        """Get preset by index."""
        return self.presets.get(preset_index)

    def get_preset_by_coords(self, x: int, y: int) -> Optional[AutoPreset]:
        """Get preset by coordinates."""
        if 0 <= x <= 7 and 5 <= y <= 7:
            index = (y - 5) * 8 + x
            return self.presets.get(index)
        return None

    def update_preset_scenes(self, preset_index: int, scene_indices: List[int]):
        """Update the scenes for a preset."""
        if preset_index in self.presets:
            self.presets[preset_index].scene_indices = scene_indices
            logger.info(
                f"Updated preset {preset_index} with {len(scene_indices)} scenes"
            )

    def get_all_presets(self) -> List[AutoPreset]:
        """Get all presets."""
        return list(self.presets.values())

    def get_status(self) -> dict:
        """Get status information."""
        active_preset = self.get_active_preset()
        return {
            "total_presets": len(self.presets),
            "active_preset": self.active_preset,
            "active_preset_name": active_preset.name if active_preset else None,
        }
