"""
Automatic scene management for the lighting controller
Provides 40 implicit scenes (8x5 grid) that can be toggled
"""

import logging
from typing import Set, Dict, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AutoScene:
    """Represents an automatic scene in the 8x5 grid."""

    index: int
    x: int
    y: int
    active: bool = False

    @property
    def name(self) -> str:
        """Get scene name."""
        return f"scene_{self.index}"

    @property
    def description(self) -> str:
        """Get scene description."""
        return f"Scene {self.index} ({self.x}, {self.y})"


class SceneManager:
    """Manages the 40 automatic scenes (8x5 grid)."""

    def __init__(
        self, feedback_callback: Optional[Callable[[int, int, bool], None]] = None
    ):
        self.scenes: Dict[int, AutoScene] = {}
        self.active_scenes: Set[int] = set()
        self.feedback_callback = (
            feedback_callback  # Callback to update Launchpad lights
        )

        # Create 40 scenes (8 columns × 5 rows)
        for index in range(40):
            x = index % 8
            y = index // 8
            self.scenes[index] = AutoScene(index, x, y)

        logger.info(f"Initialized {len(self.scenes)} automatic scenes")

    def toggle_scene(self, scene_index: int) -> bool:
        """
        Toggle scene by index.

        Args:
            scene_index: Scene index (0-39)

        Returns:
            True if scene is now active, False if deactivated
        """
        if scene_index not in self.scenes:
            logger.warning(f"Invalid scene index: {scene_index}")
            return False

        scene = self.scenes[scene_index]

        if scene_index in self.active_scenes:
            # Deactivate scene
            self.active_scenes.remove(scene_index)
            scene.active = False
            logger.info(f"⚫ Deactivated {scene.name}")

            # Send feedback to turn off button
            if self.feedback_callback:
                self.feedback_callback(scene.x, scene.y, False)

            return False
        else:
            # Activate scene
            self.active_scenes.add(scene_index)
            scene.active = True
            logger.info(f"🔴 Activated {scene.name}")

            # Send feedback to light up button
            if self.feedback_callback:
                self.feedback_callback(scene.x, scene.y, True)

            return True

    def activate_scene(self, scene_index: int):
        """Activate a scene (without toggling)."""
        if scene_index not in self.scenes:
            logger.warning(f"Invalid scene index: {scene_index}")
            return

        if scene_index not in self.active_scenes:
            self.toggle_scene(scene_index)

    def deactivate_scene(self, scene_index: int):
        """Deactivate a scene (without toggling)."""
        if scene_index not in self.scenes:
            logger.warning(f"Invalid scene index: {scene_index}")
            return

        if scene_index in self.active_scenes:
            self.toggle_scene(scene_index)

    def activate_scenes(self, scene_indices: list[int]):
        """Activate multiple scenes."""
        for scene_index in scene_indices:
            self.activate_scene(scene_index)

    def deactivate_all_scenes(self):
        """Deactivate all scenes."""
        active_indices = list(self.active_scenes)
        for scene_index in active_indices:
            self.deactivate_scene(scene_index)

    def get_active_scenes(self) -> Set[int]:
        """Get set of active scene indices."""
        return self.active_scenes.copy()

    def get_scene(self, scene_index: int) -> Optional[AutoScene]:
        """Get scene by index."""
        return self.scenes.get(scene_index)

    def get_scene_by_coords(self, x: int, y: int) -> Optional[AutoScene]:
        """Get scene by coordinates."""
        if 0 <= x <= 7 and 0 <= y <= 4:
            index = y * 8 + x
            return self.scenes.get(index)
        return None

    def is_scene_active(self, scene_index: int) -> bool:
        """Check if scene is active."""
        return scene_index in self.active_scenes

    def handle_midi_feedback(self, scene_index: int, active: bool):
        """
        Handle MIDI feedback from DasLight.
        This updates scene state based on external changes.
        """
        if scene_index not in self.scenes:
            return

        scene = self.scenes[scene_index]

        if active and scene_index not in self.active_scenes:
            # Scene was activated externally
            self.active_scenes.add(scene_index)
            scene.active = True
            logger.info(f"🔴 Scene {scene.name} activated via MIDI feedback")

            if self.feedback_callback:
                self.feedback_callback(scene.x, scene.y, True)

        elif not active and scene_index in self.active_scenes:
            # Scene was deactivated externally
            self.active_scenes.remove(scene_index)
            scene.active = False
            logger.info(f"⚫ Scene {scene.name} deactivated via MIDI feedback")

            if self.feedback_callback:
                self.feedback_callback(scene.x, scene.y, False)

    def get_status(self) -> dict:
        """Get status information."""
        return {
            "total_scenes": len(self.scenes),
            "active_scenes": len(self.active_scenes),
            "active_scene_indices": list(self.active_scenes),
        }
