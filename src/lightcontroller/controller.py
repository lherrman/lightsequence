"""
Core lighting controller with MIDI integration
"""

import logging
import threading
from typing import Set, Optional
from dataclasses import dataclass

try:
    import pygame
    import pygame.midi

    MIDI_AVAILABLE = True
    PYGAME_MIDI = pygame.midi  # Store reference for type hints
except ImportError:
    MIDI_AVAILABLE = False
    pygame = None
    PYGAME_MIDI = None
    logging.warning("pygame not available - MIDI functionality disabled")

from .config import Config, Scene, Preset
from .midi import note_to_coord, is_preset_note, get_preset_index
from .simulator import Simulator

logger = logging.getLogger(__name__)


@dataclass
class ControllerState:
    """Current controller state."""

    active_scenes: Set[str]
    active_preset: Optional[str] = None
    cycling: bool = False
    blackout: bool = False


class LightController:
    """Main lighting controller."""

    def __init__(self, config: Config):
        self.config = config
        self.state = ControllerState(set())
        self.running = False

        # MIDI and Simulator
        self.midi_in = None
        self.midi_out = None
        self.launchpad_out = None  # Separate output for Launchpad feedback
        self.simulator = Simulator(self._light_launchpad_button)

        # Threading
        self.cycle_thread = None
        self.cycle_stop = threading.Event()

        # Preset tracking
        self.active_preset_button = None  # Which preset button is currently lit

    def start(self) -> bool:
        """Start the controller."""
        # Add scenes to simulator
        for scene in self.config.scenes.values():
            self.simulator.add_scene(scene.name, scene.midi_note)

        # Try MIDI if available
        if MIDI_AVAILABLE and pygame:
            try:
                # Initialize pygame MIDI
                pygame.midi.init()

                # Find MIDI devices
                device_count = pygame.midi.get_count()
                launchpad_in_id = None
                launchpad_out_id = None
                loopmidi_out_id = None

                logger.info("Available MIDI devices:")
                for i in range(device_count):
                    info = pygame.midi.get_device_info(i)
                    name = info[1].decode() if info[1] else "Unknown"
                    is_input = info[2]
                    is_output = info[3]
                    logger.info(f"  {i}: {name} (In: {is_input}, Out: {is_output})")

                    if "launchpad" in name.lower():
                        if is_input:
                            launchpad_in_id = i
                        if is_output:
                            launchpad_out_id = i
                    elif "loopmidi" in name.lower() and is_output:
                        loopmidi_out_id = i

                # Set up MIDI input from Launchpad
                if launchpad_in_id is not None:
                    self.midi_in = pygame.midi.Input(launchpad_in_id)
                    logger.info(
                        f"Connected MIDI IN: Launchpad (device {launchpad_in_id})"
                    )
                else:
                    logger.warning("No Launchpad input found")

                # Set up MIDI output to loopMIDI for DasLight
                if loopmidi_out_id is not None:
                    self.midi_out = pygame.midi.Output(loopmidi_out_id)
                    logger.info(
                        f"Connected MIDI OUT: loopMIDI (device {loopmidi_out_id})"
                    )
                else:
                    logger.warning(
                        "No loopMIDI output found - scenes won't reach DasLight"
                    )

                # Set up direct Launchpad output for button lighting
                if launchpad_out_id is not None:
                    self.launchpad_out = pygame.midi.Output(launchpad_out_id)
                    logger.info(
                        f"Connected Launchpad feedback (device {launchpad_out_id})"
                    )
                else:
                    logger.warning("No Launchpad output found - buttons won't light up")

            except Exception as e:
                logger.warning(f"MIDI setup failed: {e} - using simulator only")
        else:
            logger.info("MIDI not available - using simulator only")

        self.running = True
        logger.info("Controller started")
        return True

    def stop(self):
        """Stop the controller."""
        self.running = False
        self._stop_cycling()

        if self.midi_in:
            self.midi_in.close()
        if self.midi_out:
            self.midi_out.close()
        if self.launchpad_out:
            self.launchpad_out.close()

        if MIDI_AVAILABLE and pygame:
            pygame.midi.quit()

        logger.info("Controller stopped")

    def _midi_callback(self, message, data):
        """Handle MIDI input."""
        if not message or len(message[0]) < 3:
            return

        status, note, velocity = message[0][:3]

        if status == 144 and velocity > 0:  # Note on
            self._handle_button_press(note)

    def _handle_button_press(self, note: int):
        """Handle button press."""
        if is_preset_note(note):
            preset_idx = get_preset_index(note)
            if preset_idx is not None:
                self._activate_preset_by_index(preset_idx)
        else:
            coord = note_to_coord(note)
            if coord:
                self._toggle_scene_by_note(note)

    def _activate_preset_by_index(self, preset_idx: int):
        """Activate preset by index."""
        presets = list(self.config.presets.values())
        if 0 <= preset_idx < len(presets):
            preset = presets[preset_idx]

            # If this preset is already active, deactivate it (toggle)
            if self.state.active_preset == preset.name:
                self._deactivate_current_preset()
            else:
                self.activate_preset(preset)
                # Store which preset button index this is
                preset._button_index = preset_idx

    def _get_preset_index(self, preset: Preset) -> Optional[int]:
        """Get preset index for button lighting."""
        if hasattr(preset, "_button_index"):
            return preset._button_index
        # Fallback: find index in config
        presets = list(self.config.presets.values())
        try:
            return presets.index(preset)
        except ValueError:
            return None

    def _deactivate_current_preset(self):
        """Deactivate current preset."""
        if self.state.active_preset:
            logger.info(f"Deactivating preset: {self.state.active_preset}")
            self._stop_cycling()
            self._deactivate_all_scenes()

            # Turn off preset button
            if self.active_preset_button:
                self._light_preset_button(self.active_preset_button, False)

            self.state.active_preset = None

    def activate_preset(self, preset: Preset):
        """Activate a preset."""
        logger.info(f"Activating preset: {preset.name}")

        self._stop_cycling()
        self._deactivate_all_scenes()

        # Activate preset scenes
        for scene_name in preset.scenes:
            if scene_name in self.config.scenes:
                self._activate_scene(scene_name)

        self.state.active_preset = preset.name

        # Light up preset button (find which preset button was pressed)
        preset_index = self._get_preset_index(preset)
        if preset_index is not None:
            from .midi import PRESET_NOTES

            preset_note = PRESET_NOTES.get(preset_index)
            if preset_note:
                self._light_preset_button(preset_note, True)

        # Start cycling if multiple scenes
        if len(preset.scenes) > 1:
            self._start_cycling(preset)

    def _toggle_scene_by_note(self, note: int):
        """Toggle scene by MIDI note."""
        scene = self._find_scene_by_note(note)
        if scene:
            if scene.name in self.state.active_scenes:
                self._deactivate_scene(scene.name)
            else:
                self._activate_scene(scene.name)

    def _find_scene_by_note(self, note: int) -> Optional[Scene]:
        """Find scene by MIDI note."""
        for scene in self.config.scenes.values():
            if scene.midi_note == note:
                return scene
        return None

    def _activate_scene(self, scene_name: str):
        """Activate a scene."""
        if scene_name in self.config.scenes:
            self.state.active_scenes.add(scene_name)
            scene = self.config.scenes[scene_name]
            self._send_scene_midi(scene, True)
            logger.info(f"Activated scene: {scene_name}")

    def _deactivate_scene(self, scene_name: str):
        """Deactivate a scene."""
        self.state.active_scenes.discard(scene_name)
        if scene_name in self.config.scenes:
            scene = self.config.scenes[scene_name]
            self._send_scene_midi(scene, False)
            logger.info(f"Deactivated scene: {scene_name}")

    def _deactivate_all_scenes(self):
        """Deactivate all scenes."""
        for scene_name in list(self.state.active_scenes):
            self._deactivate_scene(scene_name)

    def _send_scene_midi(self, scene: Scene, active: bool):
        """Send MIDI for scene activation to DasLight."""
        # Update simulator (which will handle its own feedback)
        if active:
            self.simulator.activate_scene(scene.name)
        else:
            self.simulator.deactivate_scene(scene.name)

        # Send to DasLight via loopMIDI if available
        if self.midi_out:
            try:
                velocity = 127 if active else 0
                # pygame.midi uses write() method with timestamp
                timestamp = pygame.midi.time() if (pygame and MIDI_AVAILABLE) else 0
                self.midi_out.write([[[0x90, scene.midi_note, velocity], timestamp]])
                logger.debug(
                    f"Sent to DasLight: Note {scene.midi_note}, Vel {velocity}"
                )
            except Exception as e:
                logger.error(f"MIDI send error: {e}")
        else:
            # No DasLight - simulate feedback directly to Launchpad
            self._light_launchpad_button(scene.midi_note, active)

    def _start_cycling(self, preset: Preset):
        """Start scene cycling."""
        if self.cycle_thread and self.cycle_thread.is_alive():
            return

        self.state.cycling = True
        self.cycle_stop.clear()

        self.cycle_thread = threading.Thread(
            target=self._cycle_worker, args=(preset,), daemon=True
        )
        self.cycle_thread.start()

    def _stop_cycling(self):
        """Stop scene cycling."""
        if self.cycle_thread:
            self.cycle_stop.set()
            self.cycle_thread.join(timeout=1.0)
        self.state.cycling = False

    def _cycle_worker(self, preset: Preset):
        """Cycling worker thread."""
        scene_idx = 0

        while not self.cycle_stop.is_set() and self.running:
            if not preset.scenes:
                break

            # Deactivate current
            self._deactivate_all_scenes()

            # Activate next
            scene_name = preset.scenes[scene_idx]
            self._activate_scene(scene_name)

            scene_idx = (scene_idx + 1) % len(preset.scenes)

            # Wait
            self.cycle_stop.wait(preset.cycle_interval)

    def blackout(self):
        """Emergency blackout."""
        logger.warning("BLACKOUT!")
        self.state.blackout = True
        self._stop_cycling()
        self._deactivate_all_scenes()
        self.simulator.blackout()

    def reset_blackout(self):
        """Reset blackout."""
        self.state.blackout = False
        logger.info("Blackout reset")

    def _light_launchpad_button(self, note: int, on: bool):
        """Light up button on Launchpad (direct control)."""
        if self.launchpad_out:
            try:
                # Use different colors for different states
                velocity = 127 if on else 0
                # Note: Real Launchpad uses different velocity values for colors
                # 127 = full brightness, 0 = off
                # pygame.midi uses write() method with timestamp
                timestamp = pygame.midi.time() if (pygame and MIDI_AVAILABLE) else 0
                self.launchpad_out.write([[[0x90, note, velocity], timestamp]])
                logger.debug(f"Launchpad button {note}: {'ON' if on else 'OFF'}")
            except Exception as e:
                logger.error(f"Launchpad lighting error: {e}")

    def _light_preset_button(self, preset_note: int, on: bool):
        """Light up preset button (right column)."""
        if on and self.active_preset_button != preset_note:
            # Turn off previous preset button
            if self.active_preset_button is not None:
                self._light_launchpad_button(self.active_preset_button, False)

            # Turn on new preset button
            self._light_launchpad_button(preset_note, True)
            self.active_preset_button = preset_note
        elif not on and self.active_preset_button == preset_note:
            # Turn off current preset button
            self._light_launchpad_button(preset_note, False)
            self.active_preset_button = None

    def get_status(self) -> dict:
        """Get controller status."""
        return {
            "running": self.running,
            "active_scenes": list(self.state.active_scenes),
            "active_preset": self.state.active_preset,
            "cycling": self.state.cycling,
            "blackout": self.state.blackout,
            "active_preset_button": self.active_preset_button,
        }
