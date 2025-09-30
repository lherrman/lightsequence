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
from .daslight_midi import connect_daslight_midi, send_scene_command, process_daslight_feedback, close_daslight_midi
from .scene_manager import SceneManager
from .preset_manager import PresetManager

logger = logging.getLogger(__name__)


@dataclass
class ControllerState:
    """Current controller state."""

    def __init__(self):
        self.blackout: bool = False
        self.cycling: bool = False
        self.active_scenes: set[str] = set()
        self.active_preset: str | None = None


class LightController:
    """Main lighting controller."""

    def __init__(self, config: Config):
        self.config = config
        self.state = ControllerState()
        self.running = False

        # Hardware and MIDI
        self.launchpad = LaunchpadMK2()  # Hardware abstraction
        self.midi_out = None  # pygame MIDI for DasLight output
        self.midi_in = None  # pygame MIDI for DasLight feedback
        self.led_states = {}  # Track LED states for feedback
        
        # Record Arm state
        self.record_arm_pressed = False

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
            
    def _update_launchpad_led(self, note: int, active: bool):
        """Update Launchpad LED for a given MIDI note based on DasLight feedback."""
        try:
            # Convert MIDI note to x,y coordinates
            x, y = self.launchpad._midi_note_to_xy(note)
            if x is None or y is None:
                return
            
            # Check if it's a scene button (main grid area)
            scene_idx = self.launchpad.midi_note_to_scene_index(note)
            if scene_idx is not None:
                self._update_scene_button(x, y, active)
            else:
                # Could be a preset button or other control
                preset_idx = self.launchpad.midi_note_to_preset_index(note) if hasattr(self.launchpad, 'midi_note_to_preset_index') else None
                if preset_idx is not None:
                    self._update_preset_button(x, y, active)
        except Exception as e:
            logger.debug(f"Could not update LED for note {note}: {e}")

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

        # Connect to DasLight via loopMIDI using utility functions
        if PYGAME_AVAILABLE and pygame:
            try:
                self.midi_out, self.midi_in = connect_daslight_midi()
                if self.midi_out and self.midi_in:
                    logger.info("✅ Connected to DasLight via loopMIDI")
                    self._start_midi_feedback_polling()
                else:
                    logger.warning("❌ DasLight connection failed")
            except Exception as e:
                logger.warning(f"DasLight setup failed: {e}")
        else:
            logger.info("pygame not available - DasLight communication disabled")

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
        if not hasattr(self, "midi_feedback_thread"):
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
        if (
            hasattr(self, "midi_feedback_thread")
            and self.midi_feedback_thread
            and self.midi_feedback_thread.is_alive()
        ):
            self.midi_feedback_stop.set()
            self.midi_feedback_thread.join(timeout=1.0)
            logger.info("MIDI feedback polling stopped")

    def _midi_feedback_worker(self):
        """MIDI feedback polling worker thread using utility functions."""
        while not self.midi_feedback_stop.is_set():
            try:
                if self.midi_in:
                    # Use utility function to process feedback
                    led_changes = process_daslight_feedback(self.midi_in, self.led_states)
                    
                    # Update Launchpad LEDs based on changes
                    for note, active in led_changes.items():
                        self._update_launchpad_led(note, active)
                        
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
                logger.debug(
                    f"MIDI feedback: Scene {scene_idx} -> {'ON' if active else 'OFF'} (note={note}, vel={velocity})"
                )

                # Update scene manager state based on feedback
                self.scene_manager.handle_midi_feedback(scene_idx, active)
        except Exception as e:
            logger.error(f"Error handling MIDI feedback: {e}")

    def _simulate_midi_feedback(self, midi_note: int, velocity: int):
        """Simulate MIDI feedback from DasLight/simulator."""
        logger.debug(f"🎵 Simulated MIDI feedback: note={midi_note}, velocity={velocity}")
        
        # Process the feedback just like real MIDI feedback
        self._handle_midi_feedback(midi_note, velocity)

    def _handle_button_press_xy(self, x: int, y: int, pressed: bool):
        """Handle button press with x,y coordinates."""
        logger.info(f"🎯 Button event: ({x}, {y}) pressed={pressed}")
        
        # Debug: Show what type of button this is
        if self.launchpad.is_scene_button(x, y):
            scene_idx = self.launchpad.get_scene_index(x, y)
            logger.info(f"🔹 SCENE button detected: index={scene_idx}")
        elif self.launchpad.is_preset_button(x, y):
            preset_idx = self.launchpad.get_preset_index(x, y)
            logger.info(f"🔸 PRESET button detected: index={preset_idx}")
        elif self.launchpad.is_record_arm_button(x, y):
            logger.info(f"🎙️ RECORD ARM button detected")
        else:
            logger.info(f"❓ UNKNOWN button type at ({x}, {y})")

        # Handle Record Arm button
        if self.launchpad.is_record_arm_button(x, y):
            self.record_arm_pressed = pressed
            logger.info(f"🎙️ Record Arm button {'PRESSED' if pressed else 'RELEASED'}")
            
            if pressed:
                # Light up Record Arm button and show visual feedback
                self._show_record_mode_feedback()
            else:
                # Clear visual feedback and turn off Record Arm button
                self._clear_record_mode_feedback()
            return

        if not pressed:  # Only handle button presses, not releases (except Record Arm)
            logger.debug(f"Ignoring button release at ({x}, {y})")
            return

        if self.launchpad.is_scene_button(x, y):
            # Scene button pressed - send to simulator (which will send feedback)
            scene_idx = self.launchpad.get_scene_index(x, y)
            logger.info(f"🎯 Scene button PRESSED: idx={scene_idx} at ({x}, {y})")
            if scene_idx is not None:
                # Get MIDI note for this scene
                midi_note = self.launchpad.scene_midi_note_from_index(scene_idx)
                
                if midi_note is not None:
                    if self.midi_out:
                        # Send MIDI command to DasLight using utility function
                        scene = self.scene_manager.get_scene(scene_idx)
                        if scene:
                            # Toggle scene state
                            self._toggle_scene(scene.name)
                            logger.info(f"Toggled scene {scene.name} (index {scene_idx})")
                        else:
                            logger.warning(f"Scene not found for index {scene_idx}")
                    else:
                        logger.warning(f"No MIDI output connection available")
                else:
                    logger.warning(f"Could not get MIDI note for scene {scene_idx}")

        elif self.launchpad.is_preset_button(x, y):
            # Preset button pressed
            preset_idx = self.launchpad.get_preset_index(x, y)
            logger.info(f"Preset button pressed: idx={preset_idx}")
            if preset_idx is not None:
                if self.record_arm_pressed:
                    # Record mode: save current scene state to preset
                    self._record_preset(preset_idx)
                else:
                    # Normal mode: activate preset
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
        """Toggle scene by name - send MIDI command and let DasLight feedback control LEDs."""
        # Parse scene name to get index (format: "scene_X" where X is the index)
        try:
            if scene_name.startswith("scene_"):
                scene_idx = int(scene_name.split('_')[1])
                scene = self.scene_manager.get_scene(scene_idx)
                if scene and self.midi_out:
                    # Get MIDI note for this scene
                    midi_note = self.launchpad.scene_midi_note_from_index(scene_idx)
                    if midi_note is not None:
                        # Send toggle command to DasLight - let DasLight decide activate/deactivate
                        send_scene_command(self.midi_out, midi_note)
                        logger.info(f"Sent toggle command for scene: {scene_name} (note {midi_note})")
                    else:
                        logger.warning(f"No MIDI note for scene {scene_idx}")
                else:
                    logger.warning(f"Scene not found or no MIDI output: {scene_name}")
            else:
                logger.warning(f"Invalid scene name format: {scene_name}")
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing scene name {scene_name}: {e}")

    def _toggle_scene_by_note(self, note: int):
        """Toggle scene by MIDI note."""
        scene = self._find_scene_by_note(note)
        if scene:
            self._toggle_scene(scene.name)

    def _record_preset(self, preset_idx: int):
        """Record current scene state to a preset."""
        logger.info(f"🎙️ Recording preset {preset_idx}")
        
        # For now, we'll use a simple approach and record which scenes we think are active
        # In a more sophisticated implementation, we'd parse DasLight feedback to know exact states
        active_scene_indices = []
        
        # Check each scene to see if it might be active
        # This is a placeholder implementation - ideally we'd track state from DasLight feedback
        for scene_idx in range(40):  # We have 40 scenes (8x5)
            scene = self.scene_manager.get_scene(scene_idx)
            if scene:
                # Convert scene index to x,y coordinates (reverse of get_scene_index)
                y = scene_idx // 8
                x = scene_idx % 8
                
                # For this initial implementation, we'll just record empty for now
                # TODO: Implement proper active scene detection from DasLight LED feedback
                pass
        
        # Record the preset using the preset index (0-based)
        success = self.preset_manager.record_preset(preset_idx, active_scene_indices)
        
        if success:
            preset_name = f"User Preset {preset_idx + 1}"
            logger.info(f"✅ Preset '{preset_name}' recorded with {len(active_scene_indices)} active scenes")
        else:
            logger.error(f"❌ Failed to record preset {preset_idx}")

    def _show_record_mode_feedback(self):
        """Show visual feedback when Record Arm is pressed - light up programmed presets and Record Arm button."""
        logger.info("💡 Showing record mode feedback")
        
        # Light up Record Arm button
        self.launchpad.light_record_arm_button()
        logger.info("🔴 Record Arm button lit up")
        
        # Light up programmed presets
        programmed_indices = self.preset_manager.get_programmed_preset_indices()
        if programmed_indices:
            self.launchpad.light_programmed_presets(programmed_indices)
            logger.info(f"🟡 Lit up {len(programmed_indices)} programmed presets: {[i+1 for i in programmed_indices]}")
        else:
            logger.info("No programmed presets to show")

    def _clear_record_mode_feedback(self):
        """Clear visual feedback when Record Arm is released."""
        logger.info("💡 Clearing record mode feedback")
        
        # Clear Record Arm button
        self.launchpad.clear_record_arm_button()
        logger.info("Record Arm button cleared")
        
        # Clear preset buttons
        self.launchpad.clear_all_preset_buttons()
        logger.info("All preset buttons cleared")

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
        """Activate an automatic scene by name (for internal use only)."""
        # Parse scene name to get index (format: "scene_X" where X is the index)
        try:
            if scene_name.startswith("scene_"):
                scene_idx = int(scene_name.split('_')[1])
                scene = self.scene_manager.get_scene(scene_idx)
                if scene:
                    # Only send MIDI, don't update internal state - let DasLight feedback control state
                    self._send_scene_midi(scene_idx, True)
                    logger.info(f"Activated scene: {scene_name} (index {scene_idx})")
                else:
                    logger.warning(f"Scene not found: {scene_name}")
            else:
                logger.warning(f"Invalid scene name format: {scene_name}")
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing scene name {scene_name}: {e}")

    def _deactivate_scene(self, scene_name: str):
        """Deactivate an automatic scene by name (for internal use only)."""
        # Parse scene name to get index (format: "scene_X" where X is the index)
        try:
            if scene_name.startswith("scene_"):
                scene_idx = int(scene_name.split('_')[1])
                scene = self.scene_manager.get_scene(scene_idx)
                if scene:
                    # Only send MIDI, don't update internal state - let DasLight feedback control state
                    self._send_scene_midi(scene_idx, False)
                    logger.info(f"Deactivated scene: {scene_name} (index {scene_idx})")
                else:
                    logger.warning(f"Scene not found: {scene_name}")
            else:
                logger.warning(f"Invalid scene name format: {scene_name}")
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing scene name {scene_name}: {e}")

    def _deactivate_all_scenes(self):
        """Deactivate all scenes by checking DasLight state."""
        # Check all 40 scenes and deactivate active ones
        for scene_idx in range(40):
            if self.scene_manager.is_scene_active(scene_idx):
                scene = self.scene_manager.get_scene(scene_idx)
                if scene:
                    self._deactivate_scene(scene.name)

    def _send_scene_midi(self, scene_idx: int, active: bool):
        """Send MIDI for scene activation to DasLight using utility functions."""
        # Get the scene from our automatic scene manager
        scene = self.scene_manager.get_scene(scene_idx)
        if not scene:
            return

        # Send to DasLight via loopMIDI using utility function
        if self.midi_out and active:  # Only send activation commands
            try:
                # Get MIDI note for this scene
                midi_note = self.launchpad.scene_midi_note_from_index(scene_idx)
                if midi_note is not None:
                    # Use utility function for sending scene command
                    send_scene_command(self.midi_out, midi_note)
                    logger.debug(f"Sent to DasLight: Scene {scene_idx}, Note {midi_note}")
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
