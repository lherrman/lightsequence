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
        """Create empty presets - they will be recorded by the user."""
        # Create 24 empty presets for the 24 preset buttons (8x3 grid)
        for index in range(24):
            x = index % 8
            y = (index // 8) + 5  # Preset area starts at y=5

            self.presets[index] = AutoPreset(
                index=index,
                x=x,
                y=y,
                name=f"Preset {index+1}",
                description=f"User preset {index+1}",
                scene_indices=[],  # Start empty
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

    def record_preset(self, preset_index: int, active_scene_indices: List[int]) -> bool:
        """
        Record a preset with the current scene state.
        
        Args:
            preset_index: Preset index (0-23)
            active_scene_indices: List of currently active scene indices
            
        Returns:
            True if preset was recorded successfully
        """
        if preset_index not in self.presets:
            logger.warning(f"Invalid preset index: {preset_index}")
            return False

        preset = self.presets[preset_index]
        preset.scene_indices = active_scene_indices.copy()
        
        # Update name to indicate it has content
        if active_scene_indices:
            preset.name = f"Preset {preset_index+1} ({len(active_scene_indices)} scenes)"
            preset.description = f"User recorded preset with {len(active_scene_indices)} scenes"
        else:
            preset.name = f"Preset {preset_index+1} (Empty)"
            preset.description = f"Empty user preset {preset_index+1}"
        
        logger.info(f"🎙️ Recorded preset {preset_index+1}: {len(active_scene_indices)} scenes")
        return True

    def is_preset_programmed(self, preset_index: int) -> bool:
        """Check if a preset has been programmed (has content)."""
        if preset_index not in self.presets:
            return False
        return len(self.presets[preset_index].scene_indices) > 0

    def get_programmed_preset_indices(self) -> List[int]:
        """Get list of preset indices that have been programmed."""
        return [idx for idx in self.presets.keys() if self.is_preset_programmed(idx)]

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
