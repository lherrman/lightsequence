"""
Scene Controller

Manages scene activation, deactivation, and transitions.
Tracks active scenes and handles smart transitions to prevent flicker.
"""

import logging
import typing as t
import threading

logger = logging.getLogger(__name__)


class SceneController:
    """
    Handles all scene-related operations.
    
    Responsibilities:
    - Track currently active scenes
    - Smart scene transitions (diff-based)
    - Scene activation/deactivation
    """
    
    def __init__(self):
        """Initialize scene controller."""
        self.active_scenes: t.Set[t.Tuple[int, int]] = set()
        self.controlled_scenes: t.Set[t.Tuple[int, int]] = set()  # Scenes controlled by sequences
        self._recently_deactivated: t.Set[t.Tuple[int, int]] = set()
        self._lock = threading.RLock()
        
        # Callbacks
        self.on_scene_activate: t.Optional[t.Callable[[t.Tuple[int, int]], None]] = None
        self.on_scene_deactivate: t.Optional[t.Callable[[t.Tuple[int, int]], None]] = None
    
    def activate_scenes(self, scenes: t.List[t.Tuple[int, int]], controlled: bool = True) -> None:
        """
        Activate a list of scenes using smart diff-based transitions.
        
        Args:
            scenes: List of scene coordinates to activate
            controlled: If True, mark these scenes as controlled (will be deactivated on clear)
        """
        target_scenes = set(scenes)

        with self._lock:
            # Determine what needs to change. When controlled, only deactivate
            # scenes that belonged to the previous step; allow manual/uncontrolled
            # scenes to stay lit.
            if controlled:
                scenes_to_deactivate = self.controlled_scenes - target_scenes
            else:
                scenes_to_deactivate = set()

            scenes_to_activate = target_scenes - self.active_scenes

            # Deactivate scenes
            for scene in scenes_to_deactivate:
                self._deactivate_scene(scene)

            # Activate scenes
            for scene in scenes_to_activate:
                self._activate_scene(scene, controlled)

            # Update controlled scenes
            if controlled:
                if target_scenes:
                    self.controlled_scenes = target_scenes.copy()
                    self.active_scenes.update(target_scenes)
                else:
                    self.controlled_scenes.clear()
                self._recently_deactivated = scenes_to_deactivate.copy()
            
        if not controlled:
            # Clear any stale deactivation guards when changes are manual
            with self._lock:
                self._recently_deactivated.clear()
    
    def _activate_scene(self, scene: t.Tuple[int, int], controlled: bool = True) -> None:
        """Activate a single scene."""
        if self.on_scene_activate:
            self.on_scene_activate(scene)
        
        self.active_scenes.add(scene)
        if controlled:
            self.controlled_scenes.add(scene)
    
    def _deactivate_scene(self, scene: t.Tuple[int, int]) -> None:
        """Deactivate a single scene."""
        before_active = scene in self.active_scenes
        if self.on_scene_deactivate:
            self.on_scene_deactivate(scene)
        
        self.active_scenes.discard(scene)
        self.controlled_scenes.discard(scene)
        # No debug logging to keep runtime logs quiet
    
    def toggle_scene(self, scene: t.Tuple[int, int]) -> bool:
        """
        Toggle a scene on/off.
        
        Returns:
            True if scene is now active, False if deactivated
        """
        with self._lock:
            if scene in self.active_scenes:
                self._deactivate_scene(scene)
                return False
            self._activate_scene(scene, controlled=False)
            return True
    
    def clear_all(self) -> None:
        """Clear all active scenes."""
        with self._lock:
            scenes_to_clear = list(self.active_scenes)
            for scene in scenes_to_clear:
                self._deactivate_scene(scene)

            self.active_scenes.clear()
            self.controlled_scenes.clear()
            logger.debug("Cleared all scenes")
    
    def clear_controlled(self) -> None:
        """Clear only controlled scenes (from sequences)."""
        with self._lock:
            for scene in list(self.controlled_scenes):
                self._deactivate_scene(scene)
    
    def mark_scene_active(self, scene: t.Tuple[int, int], active: bool) -> None:
        """
        Mark a scene as active/inactive (for external feedback, e.g., MIDI).
        
        This updates internal state without triggering callbacks.
        """
        with self._lock:
            if active:
                self.active_scenes.add(scene)
            else:
                self.active_scenes.discard(scene)
                self.controlled_scenes.discard(scene)
                self._recently_deactivated.discard(scene)
    
    def get_active_scenes(self) -> t.Set[t.Tuple[int, int]]:
        """Get currently active scenes."""
        with self._lock:
            return self.active_scenes.copy()
    
    def is_scene_active(self, scene: t.Tuple[int, int]) -> bool:
        """Check if a scene is currently active."""
        with self._lock:
            return scene in self.active_scenes
    
    def has_active_scenes(self) -> bool:
        """Check if any scenes are active."""
        with self._lock:
            return len(self.active_scenes) > 0

    def get_sequence_guard_scenes(self) -> t.Set[t.Tuple[int, int]]:
        """Scenes owned by the active sequence (current step plus just-deactivated)."""
        with self._lock:
            return set(self.controlled_scenes) | set(self._recently_deactivated)
