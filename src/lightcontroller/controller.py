"""
Core lighting controller with MIDI integration
"""

import logging
import threading
from typing import Optional
from dataclasses import dataclass

try:
    import pygame
    import pygame.midi

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None
    logging.warning("pygame not available - loopMIDI functionality disabled")

try:
    import launchpad_py as launchpad

    LAUNCHPAD_AVAILABLE = True
except ImportError:
    LAUNCHPAD_AVAILABLE = False
    launchpad = None
    logging.warning("launchpad_py not available - hardware control disabled")

from .config import Config, Scene, Preset
from .launchpad import LaunchpadMK2, LaunchpadColor

# Simulator removed - now using automatic scene system
from .scene_manager import SceneManager
from .preset_manager import PresetManager

logger = logging.getLogger(__name__)


@dataclass
class ControllerState:
    """Current controller state."""

    blackout: bool = False
    cycling: bool = False


class LightController:
    """Main lighting controller."""

    def __init__(self, config: Config):
        self.config = config
        self.state = ControllerState()
        self.running = False

        # Hardware and MIDI
        self.launchpad = LaunchpadMK2()  # Hardware abstraction
        self.midi_out = None  # pygame MIDI for loopMIDI output
        self.midi_in = None   # pygame MIDI for loopMIDI input (feedback)

        # Automatic scene and preset management
        self.scene_manager = SceneManager(self._update_scene_button)
        self.preset_manager = PresetManager(self._update_preset_button)

        # Threading
        self.cycle_thread = None
        self.cycle_stop = threading.Event()
        self.input_thread = None
        self.input_stop = threading.Event()

    def _update_scene_button(self, x: int, y: int, active: bool):
        """Update scene button on Launchpad."""
        if active:
            self.launchpad.light_scene_button(x, y, LaunchpadColor.GREEN_FULL)
        else:
            self.launchpad.light_scene_button(x, y, LaunchpadColor.OFF)

    def _update_preset_button(self, x: int, y: int, active: bool):
        """Update preset button on Launchpad."""
        if active:
            self.launchpad.light_preset_button(x, y, LaunchpadColor.AMBER_FULL)
        else:
            self.launchpad.light_preset_button(x, y, LaunchpadColor.OFF)

    def start(self) -> bool:
        """Start the controller."""
        logger.info("Starting light controller with automatic scenes and presets")
        logger.info(f"Scene manager: {self.scene_manager.get_status()}")
        logger.info(f"Preset manager: {self.preset_manager.get_status()}")

        # Connect to Launchpad hardware
        if self.launchpad.connect():
            self.launchpad.set_button_callback(self._handle_button_press_xy)
            logger.info("Launchpad connected successfully")

            # Start input polling thread
            self._start_input_polling()
        else:
            logger.warning("Could not connect to Launchpad - using simulator only")

        # Try pygame MIDI for loopMIDI communication
        if PYGAME_AVAILABLE and pygame:
            try:
                pygame.midi.init()
                device_count = pygame.midi.get_count()
                loopmidi_out_id = None

                logger.info("Looking for loopMIDI devices:")
                for i in range(device_count):
                    info = pygame.midi.get_device_info(i)
                    name = info[1].decode() if info[1] else "Unknown"
                    is_output = info[3]
                    if "loopmidi" in name.lower() and is_output:
                        loopmidi_out_id = i
                        logger.info(f"  Found loopMIDI: {name} (device {i})")

                if loopmidi_out_id is not None:
                    self.midi_out = pygame.midi.Output(loopmidi_out_id)
                    logger.info("Connected to loopMIDI for DasLight communication")
                    
                    # Also set up MIDI input for feedback from DasLight
                    loopmidi_in_id = None
                    for i in range(device_count):
                        info = pygame.midi.get_device_info(i)
                        name = info[1].decode() if info[1] else "Unknown"
                        is_input = info[2]
                        if "loopmidi" in name.lower() and is_input:
                            loopmidi_in_id = i
                            logger.info(f"  Found loopMIDI input: {name} (device {i})")
                            break
                    
                    if loopmidi_in_id is not None:
                        self.midi_in = pygame.midi.Input(loopmidi_in_id)
                        logger.info("Connected to loopMIDI for DasLight feedback")
                        self._start_midi_feedback_polling()
                    else:
                        logger.warning("No loopMIDI input found - feedback disabled")
                else:
                    logger.warning(
                        "No loopMIDI found - DasLight communication disabled"
                    )

            except Exception as e:
                logger.warning(f"loopMIDI setup failed: {e}")
        else:
            logger.info("pygame not available - loopMIDI disabled")

        self.running = True
        logger.info("Controller started")
        return True

    def stop(self):
        """Stop the controller."""
        self.running = False
        self._stop_cycling()
        self._stop_input_polling()
        self._stop_midi_feedback_polling()

        # Close MIDI connections
        if self.midi_out:
            self.midi_out.close()
        if self.midi_in:
            self.midi_in.close()

        # Disconnect launchpad
        if self.launchpad:
            self.launchpad.disconnect()

        if PYGAME_AVAILABLE and pygame:
            pygame.midi.quit()

        logger.info("Controller stopped")

    def _start_input_polling(self):
        """Start input polling thread."""
        if self.input_thread and self.input_thread.is_alive():
            return

        self.input_stop.clear()
        self.input_thread = threading.Thread(
            target=self._input_poll_worker, daemon=True
        )
        self.input_thread.start()
        logger.info("Input polling started")

    def _stop_input_polling(self):
        """Stop input polling thread."""
        if self.input_thread and self.input_thread.is_alive():
            self.input_stop.set()
            self.input_thread.join(timeout=1.0)
            logger.info("Input polling stopped")

    def _input_poll_worker(self):
        """Input polling worker thread."""
        while not self.input_stop.is_set():
            try:
                if self.launchpad and self.launchpad.is_connected:
                    self.launchpad.poll_buttons()
                self.input_stop.wait(0.05)  # Poll at 20Hz
            except Exception as e:
                logger.error(f"Input polling error: {e}")
                self.input_stop.wait(0.1)

    def _start_midi_feedback_polling(self):
        """Start MIDI feedback polling thread."""
        if not hasattr(self, 'midi_feedback_thread'):
            self.midi_feedback_thread = None
            self.midi_feedback_stop = threading.Event()
        
        if self.midi_feedback_thread and self.midi_feedback_thread.is_alive():
            return
        
        self.midi_feedback_stop.clear()
        self.midi_feedback_thread = threading.Thread(
            target=self._midi_feedback_worker, daemon=True
        )
        self.midi_feedback_thread.start()
        logger.info("MIDI feedback polling started")

    def _stop_midi_feedback_polling(self):
        """Stop MIDI feedback polling thread."""
        if hasattr(self, 'midi_feedback_thread') and self.midi_feedback_thread and self.midi_feedback_thread.is_alive():
            self.midi_feedback_stop.set()
            self.midi_feedback_thread.join(timeout=1.0)
            logger.info("MIDI feedback polling stopped")

    def _midi_feedback_worker(self):
        """MIDI feedback polling worker thread."""
        while not self.midi_feedback_stop.is_set():
            try:
                if self.midi_in and self.midi_in.poll():
                    midi_events = self.midi_in.read(100)  # Read up to 100 events
                    for event in midi_events:
                        msg_data = event[0]
                        if isinstance(msg_data, list) and len(msg_data) >= 3:
                            status, note, velocity = msg_data[0], msg_data[1], msg_data[2]
                            if status == 0x90:  # Note on message
                                self._handle_midi_feedback(note, velocity)
                self.midi_feedback_stop.wait(0.01)  # Poll at 100Hz
            except Exception as e:
                logger.error(f"MIDI feedback polling error: {e}")
                self.midi_feedback_stop.wait(0.1)

    def _handle_midi_feedback(self, note: int, velocity: int):
        """Handle MIDI feedback from DasLight/simulator."""
        try:
            # Convert MIDI note to scene index
            scene_idx = self.launchpad.midi_note_to_scene_index(note)
            if scene_idx is not None:
                active = velocity > 0  # 127 = on, 0 = off
                logger.debug(f"MIDI feedback: Scene {scene_idx} -> {'ON' if active else 'OFF'} (note={note}, vel={velocity})")
                
                # Update scene manager state based on feedback
                self.scene_manager.handle_midi_feedback(scene_idx, active)
        except Exception as e:
            logger.error(f"Error handling MIDI feedback: {e}")

    def _handle_button_press_xy(self, x: int, y: int, pressed: bool):
        """Handle button press with x,y coordinates."""
        logger.info(f"Button press detected: ({x}, {y}) pressed={pressed}")

        if not pressed:  # Only handle button presses, not releases
            return

        if self.launchpad.is_scene_button(x, y):
            # Scene button pressed - toggle scene
            scene_idx = self.launchpad.get_scene_index(x, y)
            logger.info(f"Scene button pressed: idx={scene_idx}")
            if scene_idx is not None:
                self.scene_manager.toggle_scene(scene_idx)
                # Send MIDI for DasLight
                self._send_scene_midi(
                    scene_idx, self.scene_manager.is_scene_active(scene_idx)
                )

        elif self.launchpad.is_preset_button(x, y):
            # Preset button pressed - activate preset
            preset_idx = self.launchpad.get_preset_index(x, y)
            logger.info(f"Preset button pressed: idx={preset_idx}")
            if preset_idx is not None:
                self._activate_preset_by_index(preset_idx)

    def _activate_preset_by_index(self, preset_idx: int):
        """Activate preset by index."""
        preset = self.preset_manager.get_preset(preset_idx)
        if preset:
            if self.preset_manager.activate_preset(preset_idx):
                # Preset was activated - activate its scenes
                self.scene_manager.deactivate_all_scenes()  # Clear existing scenes
                self.scene_manager.activate_scenes(preset.scene_indices)

                # Send MIDI for each scene
                for scene_idx in preset.scene_indices:
                    self._send_scene_midi(scene_idx, True)
            else:
                # Preset was deactivated - deactivate all scenes
                self.scene_manager.deactivate_all_scenes()
                # Send MIDI to turn off all scenes
                for scene_idx in range(40):
                    if self.scene_manager.is_scene_active(scene_idx):
                        self._send_scene_midi(scene_idx, False)

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
        active_preset = self.preset_manager.active_preset
        if active_preset is not None:
            logger.info(f"Deactivating preset: {active_preset}")
            self._stop_cycling()

            # Deactivate preset and all its scenes
            self.preset_manager.deactivate_current_preset()
            self.scene_manager.deactivate_all_scenes()

            # Send MIDI to turn off all scenes
            for scene_idx in range(40):
                self._send_scene_midi(scene_idx, False)

            # Turn off preset button
            if self.active_preset_button:
                self._light_preset_button(self.active_preset_button, False)

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

        # Light up preset button
        preset_index = self._get_preset_index(preset)
        if preset_index is not None:
            preset_note = self.launchpad.preset_midi_note_from_index(preset_index)
            if preset_note:
                self._light_preset_button(preset_note, True)

        # Start cycling if multiple scenes
        if len(preset.scenes) > 1:
            self._start_cycling(preset)

    def _toggle_scene(self, scene_name: str):
        """Toggle scene by name."""
        if scene_name in self.state.active_scenes:
            self._deactivate_scene(scene_name)
        else:
            self._activate_scene(scene_name)

    def _toggle_scene_by_note(self, note: int):
        """Toggle scene by MIDI note."""
        scene = self._find_scene_by_note(note)
        if scene:
            self._toggle_scene(scene.name)

    def _find_scene_by_note(self, note: int) -> Optional[Scene]:
        """Find scene by MIDI note (button position)."""
        scene_idx = self.launchpad.midi_note_to_scene_index(note)
        if scene_idx is not None:
            scene_names = list(self.config.scenes.keys())
            if scene_idx < len(scene_names):
                scene_name = scene_names[scene_idx]
                return self.config.scenes[scene_name]
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

    def _send_scene_midi(self, scene_idx: int, active: bool):
        """Send MIDI for scene activation to DasLight."""
        # Get the scene from our automatic scene manager
        scene = self.scene_manager.get_scene(scene_idx)
        if not scene:
            return

        # Send to DasLight via loopMIDI if available
        if self.midi_out:
            try:
                velocity = 127 if active else 0
                midi_note = self.launchpad.scene_midi_note_from_index(scene_idx)
                # pygame.midi uses write() method with timestamp
                timestamp = pygame.midi.time() if PYGAME_AVAILABLE and pygame else 0
                self.midi_out.write([[[0x90, midi_note, velocity], timestamp]])
                logger.debug(
                    f"Sent to DasLight: Scene {scene_idx}, Note {midi_note}, Vel {velocity}"
                )
            except Exception as e:
                logger.error(f"MIDI send error: {e}")

        # Light up the corresponding scene button on Launchpad
        self._update_scene_button_light(scene_idx, active)

    def _update_scene_button_light(self, scene_idx: int, active: bool):
        """Update scene button lighting on Launchpad."""
        if not self.launchpad or not self.launchpad.is_connected:
            return

        coords = self.launchpad.scene_coords_from_index(scene_idx)
        if coords:
            x, y = coords
            if active:
                self.launchpad.light_scene_button(x, y)
            else:
                self.launchpad.clear_scene_button(x, y)

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
        self.scene_manager.deactivate_all_scenes()
        self.preset_manager.deactivate_current_preset()
        # Send MIDI to turn off all scenes
        for scene_idx in range(40):
            self._send_scene_midi(scene_idx, False)

    def reset_blackout(self):
        """Reset blackout."""
        self.state.blackout = False
        logger.info("Blackout reset")

    def _light_launchpad_button(self, note: int, on: bool):
        """Light up button on Launchpad based on MIDI note."""
        logger.debug(f"Button light request: note {note}, on={on}")

        # Convert MIDI note to x,y coordinates for our abstraction
        x, y = self.launchpad._midi_note_to_xy(note)
        if x is not None and y is not None:
            # Determine if this is a scene or preset button
            if self.launchpad.is_scene_button(x, y):
                color = LaunchpadColor.GREEN_FULL if on else LaunchpadColor.OFF
                self.launchpad.light_scene_button(x, y, color)
                logger.debug(f"Scene button ({x}, {y}) -> {'ON' if on else 'OFF'}")
            elif self.launchpad.is_preset_button(x, y):
                preset_y = y - 5  # Convert to preset coordinate system
                color = LaunchpadColor.AMBER_FULL if on else LaunchpadColor.OFF
                self.launchpad.light_preset_button(x, preset_y, color)
                logger.debug(
                    f"Preset button ({x}, {preset_y}) -> {'ON' if on else 'OFF'}"
                )
        else:
            logger.warning(f"Could not map MIDI note {note} to grid coordinates")

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
        active_scenes = [
            idx for idx in range(40) if self.scene_manager.is_scene_active(idx)
        ]
        active_preset = self.preset_manager.active_preset

        return {
            "running": self.running,
            "active_scenes": active_scenes,
            "active_preset": active_preset,
            "cycling": self.state.cycling,
            "blackout": self.state.blackout,
            "active_preset_button": self.active_preset_button,
        }
