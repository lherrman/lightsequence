import logging
import time
import typing as t
from pathlib import Path
from enum import Enum

from daslight import Daslight
from launchpad import LaunchpadMK2, ButtonType
from preset_manager import PresetManager
from background_animator import BackgroundManager
from sequence_manager import SequenceManager, SequenceState
from config import get_config_manager, get_colors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Button configurations
SAVE_BUTTON = [0, 0]
SAVE_SHIFT_BUTTON = [1, 0]
BACKGROUND_BUTTON = [7, 0]
PLAYBACK_TOGGLE_BUTTON = [0, 5]
NEXT_STEP_BUTTON = [0, 6]
CONNECTION_STATUS_BUTTON = [0, 7]


class AppState(str, Enum):
    """Application states."""

    NORMAL = "normal"
    SAVE_MODE = "save_mode"
    SAVE_SHIFT_MODE = "save_shift_mode"


class LightController:
    """Main controller for light sequence management."""

    def __init__(self):
        # Hardware connections
        self.midi_software = Daslight()
        self.launchpad = LaunchpadMK2()

        # Managers
        preset_file = Path("presets.json")
        self.preset_manager = PresetManager(preset_file)
        self.background_manager = BackgroundManager()
        self.sequence_manager = SequenceManager()

        # State
        self.app_state = AppState.NORMAL
        self.active_preset: t.Optional[t.List[int]] = None
        self.active_scenes: t.Set[t.Tuple[int, int]] = set()
        self.playback_enabled = True  # Default to playback enabled

        # Config and colors
        self.config_manager = get_config_manager()
        self.colors = get_colors()

        # Callbacks
        self.sequence_manager.on_step_change = self._on_sequence_step_change
        self.sequence_manager.on_sequence_complete = self._on_sequence_complete
        self.on_preset_changed: t.Optional[
            t.Callable[[t.Optional[t.List[int]]], None]
        ] = None
        self.on_preset_saved: t.Optional[t.Callable[[], None]] = None

    def connect(self) -> bool:
        """Connect to devices."""
        midi_connected = self.midi_software.connect_midi()
        if midi_connected:
            # Process initial feedback to sync active scenes
            changes = self.midi_software.process_feedback()
            for note, state in changes.items():
                scene_coords = self.midi_software.get_scene_coordinates_for_note(note)
                if scene_coords and state:
                    self.active_scenes.add(scene_coords)

            logger.info("Successfully connected to DasLight")
            if self.active_scenes:
                logger.info(f"Found {len(self.active_scenes)} active scenes on startup")
        else:
            logger.error("Failed to connect to DasLight")

        return midi_connected and self.launchpad.is_connected

    def run(self) -> None:
        """Main control loop."""
        if not self.connect():
            logger.error("Failed to connect to devices")
            return

        logger.info("Light controller started. Press Ctrl+C to exit.")
        self.launchpad.set_button_led(
            ButtonType.TOP, SAVE_BUTTON, self.colors.SAVE_MODE_OFF
        )

        # Initialize playback control buttons
        self._update_playback_buttons()

        # Initialize connection status
        self._update_connection_status()

        try:
            while True:
                self._process_events()
                self._update_connection_status_from_daslight()
                time.sleep(0.02)
        except KeyboardInterrupt:
            logger.info("Shutting down light controller...")
        finally:
            self.cleanup()

    def _process_events(self) -> None:
        """Process all events in one method."""
        # Handle button events
        button_event = self.launchpad.get_button_events()
        if button_event:
            self._handle_button_event(button_event)

        # Process MIDI feedback
        self._process_midi_feedback()

        # Update background
        self.launchpad.draw_background(self.background_manager.get_current_background())

    def _process_button_event(self, event: t.Dict[str, t.Any]) -> None:
        """Process button events (public interface for GUI compatibility)."""
        self._handle_button_event(event)

    def _handle_button_event(self, event: t.Dict[str, t.Any]) -> None:
        """Route button events based on type."""
        handlers = {
            ButtonType.SCENE: self._handle_scene_button,
            ButtonType.RIGHT: self._handle_right_button,
            ButtonType.PRESET: self._handle_preset_button,
            ButtonType.TOP: self._handle_top_button,
        }

        handler = handlers.get(event["type"])
        if handler:
            handler(event["index"], event["active"])

    def _handle_scene_button(self, coords: t.List[int], active: bool) -> None:
        """Handle scene button press."""
        if active and len(coords) >= 2:
            coord_tuple = (coords[0], coords[1])
            logger.debug(f"Scene button {coords} pressed")
            self.midi_software.send_scene_command(coord_tuple)

    def _handle_preset_button(self, coords: t.List[int], active: bool) -> None:
        """Handle preset button with state-based logic."""
        if not active:
            return

        state_handlers = {
            AppState.NORMAL: self._handle_preset_normal,
            AppState.SAVE_MODE: self._handle_preset_save,
            AppState.SAVE_SHIFT_MODE: self._handle_preset_save_shift,
        }

        handler = state_handlers[self.app_state]
        handler(coords)

    def _handle_preset_normal(self, coords: t.List[int]) -> None:
        """Handle preset button in normal mode."""
        if self.active_preset == coords:
            self._deactivate_current_preset()
            logger.debug(f"Preset {coords} deactivated")
        else:
            self._activate_preset(coords)
            logger.debug(f"Preset {coords} activated")

    def _handle_preset_save(self, coords: t.List[int]) -> None:
        """Handle preset button in save mode."""
        active_scenes = [[s[0], s[1]] for s in self.active_scenes]
        self.preset_manager.save_preset(coords, active_scenes)

        logger.info(f"Saved {len(active_scenes)} scenes to preset {coords}")
        self._notify_preset_saved()
        self._exit_save_modes()
        self._activate_preset(coords)

    def _handle_preset_save_shift(self, coords: t.List[int]) -> None:
        """Handle preset button in save shift mode."""
        if not self.active_scenes:
            logger.warning("No active scenes to add as step")
            return

        active_scenes = [[s[0], s[1]] for s in self.active_scenes]
        self.preset_manager.add_step_to_preset(coords, active_scenes)

        self._flash_success(coords)
        self._notify_preset_saved()
        self._exit_save_modes()
        self._activate_preset(coords)

    def _handle_top_button(self, coords: t.List[int], active: bool) -> None:
        """Handle top row buttons."""
        if not active:
            return

        if coords == SAVE_BUTTON:
            self._toggle_save_mode()
        elif coords == SAVE_SHIFT_BUTTON:
            self._toggle_save_shift_mode()
        elif coords == BACKGROUND_BUTTON:
            self._cycle_background()

    def _handle_right_button(self, coords: t.List[int], active: bool) -> None:
        """Handle right bar buttons (playback controls and scenes)."""
        if not active:
            return

        if coords == PLAYBACK_TOGGLE_BUTTON:
            self._toggle_playback()
        elif coords == NEXT_STEP_BUTTON:
            self._next_step()
        else:
            # Treat other right buttons as scene buttons
            self._handle_scene_button(coords, active)

    def _toggle_save_mode(self) -> None:
        """Toggle save mode state."""
        if self.app_state == AppState.NORMAL:
            self._enter_save_mode()
        else:
            self._exit_save_modes()

    def _toggle_save_shift_mode(self) -> None:
        """Toggle save shift mode (only works when in save mode)."""
        if self.app_state not in [AppState.SAVE_MODE, AppState.SAVE_SHIFT_MODE]:
            logger.debug("SAVE_SHIFT only works when save mode is active")
            return

        if self.app_state == AppState.SAVE_MODE:
            self.app_state = AppState.SAVE_SHIFT_MODE
            self.launchpad.set_button_led(
                ButtonType.TOP, SAVE_SHIFT_BUTTON, self.colors.YELLOW_BRIGHT
            )
            logger.debug("Save shift mode ON - preset buttons will add steps")
        else:  # app_state == AppState.SAVE_SHIFT_MODE
            self.app_state = AppState.SAVE_MODE
            self.launchpad.set_button_led(
                ButtonType.TOP, SAVE_SHIFT_BUTTON, self.colors.OFF
            )
            logger.debug("Save shift mode OFF - preset buttons will save normally")

        self._update_preset_leds_for_save_mode()

    def _enter_save_mode(self) -> None:
        """Enter save mode."""
        self.app_state = AppState.SAVE_MODE

        if self.sequence_manager.sequence_state != SequenceState.STOPPED:
            self.sequence_manager.stop_sequence()
            logger.debug("Stopped sequence playback for save mode")

        self.launchpad.set_button_led(
            ButtonType.TOP, SAVE_BUTTON, self.colors.SAVE_MODE_ON
        )
        self._update_preset_leds_for_save_mode()
        logger.debug("Entered save mode")

    def _exit_save_modes(self) -> None:
        """Exit all save modes and return to normal."""
        self.app_state = AppState.NORMAL

        # Turn off save buttons
        self.launchpad.set_button_led(
            ButtonType.TOP, SAVE_BUTTON, self.colors.SAVE_MODE_OFF
        )
        self.launchpad.set_button_led(
            ButtonType.TOP, SAVE_SHIFT_BUTTON, self.colors.OFF
        )

        # Clear and restore preset LEDs
        self._clear_all_preset_leds()
        if self.active_preset:
            self.launchpad.set_button_led(
                ButtonType.PRESET, self.active_preset, self.colors.PRESET_ON
            )

        logger.debug("Exited save mode")

    def _cycle_background(self) -> None:
        """Cycle background animation."""
        self.background_manager.cycle_background()

    def _toggle_playback(self) -> None:
        """Toggle sequence playback (play/pause)."""
        if not self.active_preset:
            logger.debug("No active preset - playback toggle has no effect")
            return

        if not self.preset_manager.has_sequence(self.active_preset):
            logger.debug(
                "Active preset is not a sequence - playback toggle has no effect"
            )
            return

        current_state = self.sequence_manager.sequence_state

        if current_state == SequenceState.PLAYING:
            self.sequence_manager.pause_sequence()
            self.playback_enabled = False
            logger.debug("Sequence playback paused")
        elif current_state == SequenceState.PAUSED:
            self.sequence_manager.resume_sequence()
            self.playback_enabled = True
            logger.debug("Sequence playback resumed")
        else:
            logger.debug("No sequence currently playing to pause/resume")
            return

        self._update_playback_buttons()

    def _next_step(self) -> None:
        """Jump to next step in current sequence."""
        if not self.active_preset:
            logger.debug("No active preset - cannot advance step")
            return

        if not self.preset_manager.has_sequence(self.active_preset):
            logger.debug("Active preset is not a sequence - cannot advance step")
            return

        if self.sequence_manager.next_step():
            # Flash the next step button to indicate success
            self.launchpad.set_button_led(
                ButtonType.RIGHT, NEXT_STEP_BUTTON, self.colors.SUCCESS_FLASH
            )
            time.sleep(0.1)
            self._update_playback_buttons()

    def _update_playback_buttons(self) -> None:
        """Update the playback control button LEDs."""
        # Update playback toggle button based on current state
        if not self.active_preset or not self.preset_manager.has_sequence(
            self.active_preset
        ):
            # No sequence active - turn off playback buttons
            self.launchpad.set_button_led(
                ButtonType.RIGHT, PLAYBACK_TOGGLE_BUTTON, self.colors.OFF
            )
            self.launchpad.set_button_led(
                ButtonType.RIGHT, NEXT_STEP_BUTTON, self.colors.OFF
            )
            return

        current_state = self.sequence_manager.sequence_state

        if current_state == SequenceState.PLAYING:
            # Green for playing
            self.launchpad.set_button_led(
                ButtonType.RIGHT, PLAYBACK_TOGGLE_BUTTON, self.colors.PLAYBACK_PLAYING
            )
        elif current_state == SequenceState.PAUSED:
            # Orange for paused
            self.launchpad.set_button_led(
                ButtonType.RIGHT, PLAYBACK_TOGGLE_BUTTON, self.colors.PLAYBACK_PAUSED
            )
        else:
            # Off for stopped
            self.launchpad.set_button_led(
                ButtonType.RIGHT, PLAYBACK_TOGGLE_BUTTON, self.colors.OFF
            )

        # Next step button - blue when sequence is active (playing or paused)
        if current_state in [SequenceState.PLAYING, SequenceState.PAUSED]:
            self.launchpad.set_button_led(
                ButtonType.RIGHT, NEXT_STEP_BUTTON, self.colors.NEXT_STEP
            )
        else:
            self.launchpad.set_button_led(
                ButtonType.RIGHT, NEXT_STEP_BUTTON, self.colors.OFF
            )

    def _activate_preset(self, coords: t.List[int]) -> None:
        """Activate a preset (simple or sequence)."""
        # Stop any running sequence but don't clear scenes - let smart transition handle it
        if self.active_preset:
            self.sequence_manager.stop_sequence()
            self.launchpad.set_button_led(
                ButtonType.PRESET, self.active_preset, self.colors.OFF
            )

        self.active_preset = coords.copy()
        self.launchpad.set_button_led(ButtonType.PRESET, coords, self.colors.PRESET_ON)

        if self.on_preset_changed:
            self.on_preset_changed(coords.copy())

        # No blackout needed - smart scene transitions will handle it

        if self._handle_sequence_preset(coords):
            # Update playback buttons for sequence presets
            self._update_playback_buttons()
            return

        self._handle_simple_preset(coords)
        # Update playback buttons (will turn them off for simple presets)
        self._update_playback_buttons()

    def _handle_sequence_preset(self, coords: t.List[int]) -> bool:
        """Handle sequence preset activation. Returns True if sequence was started."""
        if not self.preset_manager.has_sequence(coords):
            return False

        sequence_steps = self.preset_manager.get_sequence(coords)
        if not sequence_steps:
            return False

        preset_tuple = (coords[0], coords[1])
        self.sequence_manager.add_sequence(preset_tuple, sequence_steps)

        loop_enabled = self.preset_manager.get_loop_setting(coords)
        self.sequence_manager.set_loop_enabled(loop_enabled)

        if self.sequence_manager.start_sequence(preset_tuple):
            logger.info(
                f"Started sequence preset {coords} with {len(sequence_steps)} steps (loop: {loop_enabled})"
            )
            return True
        else:
            logger.error(f"Failed to start sequence for preset {coords}")
            if sequence_steps[0].scenes:
                self._activate_scenes(sequence_steps[0].scenes)
            return False

    def _handle_simple_preset(self, coords: t.List[int]) -> None:
        """Handle simple preset activation."""
        preset = self.preset_manager.get_preset_by_index(coords)
        if preset and "scenes" in preset:
            self._activate_scenes(preset["scenes"])
            logger.debug(
                f"Activated simple preset {coords} with {len(preset['scenes'])} scenes"
            )
        else:
            # No preset saved - deactivate all running scenes
            self._activate_scenes([])
            logger.debug(f"No preset saved at {coords} - deactivated all scenes")

    def _deactivate_current_preset(self) -> None:
        """Deactivate current preset."""
        if not self.active_preset:
            return

        self.sequence_manager.stop_sequence()
        self.launchpad.set_button_led(
            ButtonType.PRESET, self.active_preset, self.colors.OFF
        )

        # Use smart transition to turn off all scenes
        self._transition_to_scenes(set())

        self.active_preset = None
        if self.on_preset_changed:
            self.on_preset_changed(None)

        # Update playback buttons (will turn them off)
        self._update_playback_buttons()

    def _activate_scenes(self, scenes: t.List[t.List[int]]) -> None:
        """Activate scenes with smart diffing to prevent flicker."""
        # Convert new scenes to set for efficient operations
        new_scenes = set()
        for scene_coords in scenes:
            if len(scene_coords) >= 2:
                new_scenes.add((scene_coords[0], scene_coords[1]))

        # Perform smart scene transition
        self._transition_to_scenes(new_scenes)

    def _transition_to_scenes(self, target_scenes: t.Set[t.Tuple[int, int]]) -> None:
        """Smart scene transition that only toggles scenes that need to change."""
        # Calculate which scenes need to be turned off
        scenes_to_deactivate = self.active_scenes - target_scenes

        # Calculate which scenes need to be turned on
        scenes_to_activate = target_scenes - self.active_scenes

        logger.debug(
            f"Scene transition: deactivating {len(scenes_to_deactivate)}, activating {len(scenes_to_activate)}, keeping {len(self.active_scenes & target_scenes)} unchanged"
        )

        # Deactivate scenes that should be off
        for scene_tuple in scenes_to_deactivate:
            self.midi_software.send_scene_command(scene_tuple)  # Toggle off
            coords_list = [scene_tuple[0], scene_tuple[1]]
            self.launchpad.set_button_led(
                ButtonType.SCENE, coords_list, self.colors.OFF
            )

        # Activate scenes that should be on
        for scene_tuple in scenes_to_activate:
            self.midi_software.send_scene_command(scene_tuple)  # Toggle on
            coords_list = [scene_tuple[0], scene_tuple[1]]
            self.launchpad.set_button_led(
                ButtonType.SCENE, coords_list, self.colors.SCENE_ON
            )

        # Update our tracking to the expected final state for next diffing calculation
        self.active_scenes = target_scenes.copy()

    def get_active_scenes_info(self) -> str:
        """Get information about currently active scenes (for debugging)."""
        if not self.active_scenes:
            return "No scenes currently active"

        scene_list = sorted(list(self.active_scenes))
        return f"Active scenes ({len(scene_list)}): {scene_list}"

    def _on_sequence_step_change(self, scenes: t.List[t.List[int]]) -> None:
        """Handle sequence step change with smart scene transitions."""
        if not self.active_preset:
            return

        # Use smart scene transition instead of blackout
        self._activate_scenes(scenes)

        logger.debug(f"Sequence step changed to {len(scenes)} scenes")

    def _on_sequence_complete(self) -> None:
        """Handle sequence completion."""
        logger.info("Sequence completed")

    def _process_midi_feedback(self) -> None:
        """Process MIDI feedback and update LEDs (public interface for GUI compatibility)."""
        changes = self.midi_software.process_feedback()

        for note, state in changes.items():
            # Skip ping responses (note 127) - handled by Daslight class
            if note == 127:
                continue

            scene_coords = self.midi_software.get_scene_coordinates_for_note(note)
            if scene_coords:
                if state:
                    self.active_scenes.add(scene_coords)
                else:
                    self.active_scenes.discard(scene_coords)

                color = self.colors.SCENE_ON if state else self.colors.OFF
                coords_list = [scene_coords[0], scene_coords[1]]
                self.launchpad.set_button_led(ButtonType.SCENE, coords_list, color)

    def _update_preset_leds_for_save_mode(self) -> None:
        """Update preset LEDs for save mode display."""
        if self.app_state == AppState.NORMAL:
            return

        preset_indices = self.preset_manager.get_all_preset_indices()
        color = (
            self.colors.PRESET_SAVE_SHIFT_MODE
            if self.app_state == AppState.SAVE_SHIFT_MODE
            else self.colors.PRESET_SAVE_MODE
        )

        for x in range(8):
            for y in range(3):
                coords = [x, y]
                led_color = (
                    color if tuple(coords) in preset_indices else self.colors.OFF
                )
                self.launchpad.set_button_led(ButtonType.PRESET, coords, led_color)

    def _clear_all_preset_leds(self) -> None:
        """Clear all preset LEDs."""
        for x in range(8):
            for y in range(3):
                self.launchpad.set_button_led(
                    ButtonType.PRESET, [x, y], self.colors.OFF
                )

    def _clear_scene_leds(self) -> None:
        """Clear all scene LEDs."""
        for x in range(8):
            for y in range(1, 6):
                self.launchpad.set_button_led(ButtonType.SCENE, [x, y], self.colors.OFF)

    def _clear_scene_leds_partial(self) -> None:
        """Clear scene LEDs for sequence changes (avoid preset row overlap)."""
        for x in range(8):
            for y in range(1, 5):  # Rows 1-4 only
                self.launchpad.set_button_led(ButtonType.SCENE, [x, y], self.colors.OFF)

    def _flash_success(self, coords: t.List[int]) -> None:
        """Flash button green briefly to indicate success."""
        self.launchpad.set_button_led(
            ButtonType.PRESET, coords, self.colors.SUCCESS_FLASH
        )
        time.sleep(0.2)
        color = (
            self.colors.PRESET_SAVE_SHIFT_MODE
            if self.app_state == AppState.SAVE_SHIFT_MODE
            else self.colors.PRESET_SAVE_MODE
        )
        self.launchpad.set_button_led(ButtonType.PRESET, coords, color)

    def _notify_preset_saved(self) -> None:
        """Notify external systems that preset was saved."""
        if self.on_preset_saved:
            self.on_preset_saved()

    def get_pressed_buttons_info(self) -> str:
        """Get info about currently pressed buttons."""
        pressed = self.launchpad.get_pressed_buttons()
        if not pressed:
            return "No buttons currently pressed"

        info_lines = [f"Currently pressed buttons ({len(pressed)}):"]
        for button in pressed:
            info_lines.append(f"  {button['type'].value}: {button['index']}")
        return "\n".join(info_lines)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.sequence_manager.cleanup()
        self.launchpad.close()
        logger.info("Light controller stopped")

    def _update_connection_status_from_daslight(self) -> None:
        """Update connection status from DasLight and update LED."""
        current_status = self.midi_software.check_connection_status()
        color = (
            self.colors.CONNECTION_GOOD
            if current_status
            else self.colors.CONNECTION_BAD
        )
        self.launchpad.set_button_led(ButtonType.RIGHT, CONNECTION_STATUS_BUTTON, color)

    def _update_connection_status(self) -> None:
        """Update the connection status LED using current DasLight status."""
        current_status = self.midi_software.connection_good
        color = (
            self.colors.CONNECTION_GOOD
            if current_status
            else self.colors.CONNECTION_BAD
        )
        self.launchpad.set_button_led(ButtonType.RIGHT, CONNECTION_STATUS_BUTTON, color)


def main():
    """Main entry point."""
    controller = LightController()
    controller.run()


if __name__ == "__main__":
    main()
