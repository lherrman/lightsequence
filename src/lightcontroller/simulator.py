"""
Simple simulator for testing without hardware
"""

import logging
from typing import Set, Dict

logger = logging.getLogger(__name__)


class Simulator:
    """Simple lighting simulator with feedback."""

    def __init__(self, feedback_callback=None):
        self.active_scenes: Set[str] = set()
        self.scene_notes: Dict[str, int] = {}
        self.running = False
        self.feedback_callback = (
            feedback_callback  # Callback to send feedback to Launchpad
        )

    def add_scene(self, name: str, note: int):
        """Add scene to simulator."""
        self.scene_notes[name] = note
        logger.info(f"Added scene: {name} (note {note})")

    def activate_scene(self, name: str):
        """Activate scene and send feedback."""
        self.active_scenes.add(name)
        note = self.scene_notes.get(name, 0)
        logger.info(f"🔴 Scene ON: {name} (note {note})")

        # Send feedback to light up Launchpad button
        if self.feedback_callback:
            self.feedback_callback(note, True)

    def deactivate_scene(self, name: str):
        """Deactivate scene and send feedback."""
        self.active_scenes.discard(name)
        note = self.scene_notes.get(name, 0)
        logger.info(f"⚫ Scene OFF: {name} (note {note})")

        # Send feedback to turn off Launchpad button
        if self.feedback_callback:
            self.feedback_callback(note, False)

    def get_active_scenes(self) -> Set[str]:
        """Get active scenes."""
        return self.active_scenes.copy()

    def blackout(self):
        """Blackout all scenes."""
        logger.warning("🚨 SIMULATOR BLACKOUT!")
        for scene in list(self.active_scenes):
            self.deactivate_scene(scene)
