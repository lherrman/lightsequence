"""
Simple simulator for testing without hardware - simulates DasLight behavior
"""

import logging
from typing import Set, Optional, Callable

logger = logging.getLogger(__name__)


class Simulator:
    """Simple lighting simulator with feedback that mimics DasLight behavior."""

    def __init__(self, midi_feedback_callback: Optional[Callable[[int, int], None]] = None):
        self.active_scenes: Set[int] = set()  # Track scene indices, not names
        self.running = False
        self.midi_feedback_callback = midi_feedback_callback  # Callback to send MIDI feedback

    def toggle_scene(self, scene_idx: int, midi_note: int):
        """Toggle scene and send MIDI feedback like DasLight would."""
        if scene_idx in self.active_scenes:
            # Scene is currently on, turn it off
            self.active_scenes.discard(scene_idx)
            logger.info(f"🟢➡️⚫ Simulator: Scene {scene_idx} OFF (note {midi_note})")
            
            # Send MIDI feedback: velocity 0 = off
            if self.midi_feedback_callback:
                self.midi_feedback_callback(midi_note, 0)
        else:
            # Scene is currently off, turn it on
            self.active_scenes.add(scene_idx)
            logger.info(f"⚫➡️🟢 Simulator: Scene {scene_idx} ON (note {midi_note})")
            
            # Send MIDI feedback: velocity 127 = on
            if self.midi_feedback_callback:
                self.midi_feedback_callback(midi_note, 127)

    def activate_scene(self, scene_idx: int, midi_note: int):
        """Activate scene and send feedback."""
        if scene_idx not in self.active_scenes:
            self.active_scenes.add(scene_idx)
            logger.info(f"🔴 Simulator: Scene {scene_idx} ON (note {midi_note})")
            
            # Send MIDI feedback: velocity 127 = on
            if self.midi_feedback_callback:
                self.midi_feedback_callback(midi_note, 127)

    def deactivate_scene(self, scene_idx: int, midi_note: int):
        """Deactivate scene and send feedback."""
        if scene_idx in self.active_scenes:
            self.active_scenes.discard(scene_idx)
            logger.info(f"⚫ Simulator: Scene {scene_idx} OFF (note {midi_note})")
            
            # Send MIDI feedback: velocity 0 = off
            if self.midi_feedback_callback:
                self.midi_feedback_callback(midi_note, 0)

    def get_active_scenes(self) -> Set[int]:
        """Get active scene indices."""
        return self.active_scenes.copy()

    def is_scene_active(self, scene_idx: int) -> bool:
        """Check if scene is active."""
        return scene_idx in self.active_scenes

    def blackout(self):
        """Blackout all scenes."""
        logger.warning("🚨 SIMULATOR BLACKOUT!")
        # Turn off all active scenes
        for scene_idx in list(self.active_scenes):
            # We need the MIDI note for feedback, but for blackout we'll use a generic approach
            self.active_scenes.discard(scene_idx)
            logger.info(f"⚫ Simulator blackout: Scene {scene_idx} OFF")
            
            # For blackout, we could send feedback for each scene, but this might be too much
            # Let the controller handle the feedback for blackout
