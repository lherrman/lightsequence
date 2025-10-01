import logging
import time
import typing as t
from pathlib import Path

from daslight import Daslight
from launchpad import LaunchpadMK2, ButtonType
from preset_manager import PresetManager
from background_animator import BackgroundManager
from sequence_manager import SequenceManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAVE_BUTTON = [0, 0]
BACKGROUND_BUTTON = [7, 0]


class LightController:
    """Main controller class that handles communication between Launchpad and DasLight."""

    # Color definitions
    COLOR_SCENE_ON = [0.0, 1.0, 0.0]
    COLOR_OFF = [0.0, 0.0, 0.0]
    COLOR_PRESET_ON = [1.0, 0.0, 5.0]
    COLOR_PRESET_SAVE_MODE = [1.0, 0.0, 0.5]
    COLOR_SAVE_MODE_ON = [1.0, 0.0, 0.5]
    COLOR_SAVE_MODE_OFF = [0.0, 1.0, 0.0]
    COLOR_BACKGROUND_CYCLE = [0.0, 1.0, 0.0]

    def __init__(self):
        """Initialize the light controller with DasLight and Launchpad connections."""
        self.midi_software = Daslight()
        self.launchpad = LaunchpadMK2()
        self.active_preset: t.Optional[t.List[int]] = None
        self.active_scenes: t.Set[t.Tuple[int, int]] = (
            set()
        )  # Track active scene coordinates

        self.save_button_state = False  # Track save button state

        # Initialize managers
        preset_file = Path(__file__).parent / "presets.json"
        self.preset_manager = PresetManager(preset_file)
        self.background_manager = BackgroundManager()
        self.sequence_manager = SequenceManager()

        # Set up sequence manager callbacks
        self.sequence_manager.on_step_change = self._on_sequence_step_change
        self.sequence_manager.on_sequence_complete = self._on_sequence_complete

    def _cycle_background(self) -> None:
        """Cycle to the next background animation."""
        self.background_manager.cycle_background()

    def _on_sequence_step_change(self, scenes: t.List[t.List[int]]) -> None:
        """Called when sequence changes to a new step."""
        # Only process if we have an active preset (sequence should be running)
        if not self.active_preset:
            return

        # Clear all scene LEDs first
        for x in range(8):
            for y in range(1, 6):  # Scene rows 1-5
                self.launchpad.set_button_led(ButtonType.SCENE, [x, y], self.COLOR_OFF)

        # Clear active scenes tracking
        self.active_scenes.clear()

        # Send blackout first
        self.midi_software.send_scene_command((8, 0))

        # Activate new scenes using helper method
        self._activate_scenes(scenes)

        # Ensure active preset LED stays on (might get cleared by some operations)
        if self.active_preset:
            self.launchpad.set_button_led(
                ButtonType.PRESET, self.active_preset, self.COLOR_PRESET_ON
            )

        logger.debug(f"Sequence step changed to {len(scenes)} scenes")

    def _on_sequence_complete(self) -> None:
        """Called when sequence completes (non-looping sequences only)."""
        logger.info("Sequence completed")
        # For non-looping sequences, keep the last step active
        # The preset remains active until manually toggled off

    def _deactivate_current_preset(self) -> None:
        """Deactivate the currently active preset (both simple and sequence)."""
        if not self.active_preset:
            return

        # Stop any running sequence
        self.sequence_manager.stop_sequence()

        # Turn off preset LED
        self.launchpad.set_button_led(
            ButtonType.PRESET, self.active_preset, self.COLOR_OFF
        )

        # Send blackout
        self.midi_software.send_scene_command((8, 0))

        # Clear active scenes tracking
        self.active_scenes.clear()

        # Clear scene LEDs
        for x in range(8):
            for y in range(1, 6):  # Scene rows 1-5
                self.launchpad.set_button_led(ButtonType.SCENE, [x, y], self.COLOR_OFF)

        # Clear active preset
        self.active_preset = None

    def _activate_preset(self, coords: t.List[int]) -> None:
        """Activate a preset (handles both simple and sequence presets uniformly)."""
        # Deactivate any current preset first
        if self.active_preset:
            self._deactivate_current_preset()

        # Set as active preset
        self.active_preset = coords.copy()

        # Light up preset button
        self.launchpad.set_button_led(ButtonType.PRESET, coords, self.COLOR_PRESET_ON)

        # Send blackout first
        self.midi_software.send_scene_command((8, 0))

        # Check if this preset has a sequence
        preset_tuple = (coords[0], coords[1])
        if self.preset_manager.has_sequence(coords):
            # Handle sequence preset
            sequence_steps = self.preset_manager.get_sequence(coords)
            if sequence_steps:
                # Add sequence to sequence manager
                self.sequence_manager.add_sequence(preset_tuple, sequence_steps)

                # Set loop setting
                loop_enabled = self.preset_manager.get_loop_setting(coords)
                self.sequence_manager.set_loop_enabled(loop_enabled)

                # Start sequence playback
                if self.sequence_manager.start_sequence(preset_tuple):
                    logger.info(
                        f"Activated sequence preset {coords} with {len(sequence_steps)} steps (loop: {loop_enabled})"
                    )
                else:
                    logger.error(f"Failed to start sequence for preset {coords}")
                    # Fallback to first step if sequence fails
                    if sequence_steps[0].scenes:
                        self._activate_scenes(sequence_steps[0].scenes)
        else:
            # Handle simple preset
            preset = self.preset_manager.get_preset_by_index(coords)
            if preset and "scenes" in preset:
                self._activate_scenes(preset["scenes"])
                logger.info(
                    f"Activated simple preset {coords} with {len(preset['scenes'])} scenes"
                )

    def _activate_scenes(self, scenes: t.List[t.List[int]]) -> None:
        """Activate a list of scenes (helper method)."""
        for scene_coords in scenes:
            if len(scene_coords) >= 2:
                scene_tuple = (scene_coords[0], scene_coords[1])
                self.midi_software.send_scene_command(scene_tuple)
                self.active_scenes.add(scene_tuple)
                # Update LED
                self.launchpad.set_button_led(
                    ButtonType.SCENE, scene_coords, self.COLOR_SCENE_ON
                )

    def _update_preset_leds_for_save_mode(self) -> None:
        """Update preset button LEDs when in save mode to show which have presets."""
        if not self.save_button_state:
            return

        preset_indices = self.preset_manager.get_all_preset_indices()

        # Light up all preset buttons that have presets saved
        for x in range(8):
            for y in range(3):
                coords = [x, y]
                if tuple(coords) in preset_indices:
                    # Preset exists - make it glow
                    self.launchpad.set_button_led(
                        ButtonType.PRESET, coords, self.COLOR_PRESET_SAVE_MODE
                    )
                else:
                    # No preset - turn off
                    self.launchpad.set_button_led(
                        ButtonType.PRESET, coords, self.COLOR_OFF
                    )

    def connect(self) -> bool:
        """Connect to both MIDI and Launchpad devices."""
        midi_connected = self.midi_software.connect_midi()
        if midi_connected:
            # Process initial feedback to get current state
            self.midi_software.process_feedback()
            logger.info("Successfully connected to DasLight")
        else:
            logger.error("Failed to connect to DasLight")

        return midi_connected and self.launchpad.is_connected

    def _handle_scene_button(self, coords: t.List[int], active: bool) -> None:
        """Handle scene button press."""
        if len(coords) >= 2 and active:
            coord_tuple = (coords[0], coords[1])
            logger.debug(f"Scene button {coords} pressed")
            self.midi_software.send_scene_command(coord_tuple)

    def _handle_preset_button(self, coords: t.List[int], active: bool) -> None:
        """Handle preset button press with toggle functionality and save mode."""
        if not active:
            return

        # If in save mode, save current active scenes to this preset
        if self.save_button_state:
            active_scene_list = [[scene[0], scene[1]] for scene in self.active_scenes]
            self.preset_manager.save_preset(coords, active_scene_list)
            logger.info(f"Saved {len(active_scene_list)} scenes to preset {coords}")

            # Exit save mode
            self.save_button_state = False

            self.launchpad.set_button_led(
                ButtonType.TOP, SAVE_BUTTON, self.COLOR_SAVE_MODE_OFF
            )

            # Clear all preset LEDs first
            for x in range(8):
                for y in range(3):
                    preset_coords = [x, y]
                    self.launchpad.set_button_led(
                        ButtonType.PRESET, preset_coords, self.COLOR_OFF
                    )

            # Activate the newly saved preset
            self._activate_preset(coords)
            logger.info(f"Activated saved preset {coords}")
            return

        # Normal preset activation/deactivation logic
        # Toggle preset if same button pressed again
        if self.active_preset == coords:
            self._deactivate_current_preset()
            logger.debug(f"Preset {coords} deactivated")
            return

        # Activate new preset
        self._activate_preset(coords)

        logger.debug(f"Preset {coords} activated")

    def _handle_top_button(self, coords: t.List[int], is_pressed: bool) -> None:
        """Handle top button press - light up when pressed, turn off when released."""

        if (
            coords == SAVE_BUTTON and is_pressed
        ):  # Only handle press events, not release
            self.save_button_state = not self.save_button_state

            if self.save_button_state:
                # Entering save mode - turn save button red and show preset buttons with presets in blue
                self.launchpad.set_button_led(
                    ButtonType.TOP, coords, self.COLOR_SAVE_MODE_ON
                )  # Red
                self._update_preset_leds_for_save_mode()
                logger.info("Entered save mode")
            else:
                # Exiting save mode - turn save button off and restore normal preset display
                self.launchpad.set_button_led(
                    ButtonType.TOP, coords, self.COLOR_SAVE_MODE_OFF
                )  # Off

                # Clear all preset LEDs first
                for x in range(8):
                    for y in range(3):
                        preset_coords = [x, y]
                        self.launchpad.set_button_led(
                            ButtonType.PRESET, preset_coords, self.COLOR_OFF
                        )

                # Show only the active preset if there is one
                if self.active_preset:
                    self.launchpad.set_button_led(
                        ButtonType.PRESET, self.active_preset, self.COLOR_PRESET_ON
                    )
                logger.info("Exited save mode")

        elif coords == BACKGROUND_BUTTON:  # Background cycling button
            if is_pressed:
                self._cycle_background()
                self.launchpad.set_button_led(
                    ButtonType.TOP, coords, self.COLOR_BACKGROUND_CYCLE
                )  # Cyan
            else:
                self.launchpad.set_button_led(
                    ButtonType.TOP, coords, self.COLOR_OFF
                )  # Off

    def _process_button_event(self, button_event: t.Dict[str, t.Any]) -> None:
        """Process a button event based on its type."""
        button_type = button_event["type"]
        coords = button_event["index"]
        is_pressed = button_event["active"]

        if button_type == ButtonType.SCENE:
            self._handle_scene_button(coords, is_pressed)
        if button_type == ButtonType.RIGHT:
            self._handle_scene_button(coords, is_pressed)

        elif button_type == ButtonType.PRESET:
            self._handle_preset_button(coords, is_pressed)
        elif button_type == ButtonType.TOP:
            self._handle_top_button(coords, is_pressed)

    def _process_midi_feedback(self) -> None:
        """Process feedback from MIDI software and update Launchpad LEDs."""
        changes = self.midi_software.process_feedback()

        for note, state in changes.items():
            scene_coords = self.midi_software.get_scene_coordinates_for_note(note)
            if scene_coords:
                # Update active scenes tracking
                if state:
                    self.active_scenes.add(scene_coords)
                else:
                    self.active_scenes.discard(scene_coords)

                # Use abstracted LED control with relative coordinates
                color = self.COLOR_SCENE_ON if state else self.COLOR_OFF
                coords_list = [scene_coords[0], scene_coords[1]]
                self.launchpad.set_button_led(ButtonType.SCENE, coords_list, color)

    def run(self) -> None:
        """Main control loop."""
        if not self.connect():
            logger.error("Failed to connect to devices")
            return

        logger.info("Light controller started. Press Ctrl+C to exit.")

        # turn on save button LED to indicate ready state
        self.launchpad.set_button_led(
            ButtonType.TOP, SAVE_BUTTON, self.COLOR_SAVE_MODE_OFF
        )

        i = 0
        try:
            while True:
                # Handle button events
                button_event = self.launchpad.get_button_events()
                if button_event:
                    self._process_button_event(button_event)

                # Process MIDI feedback
                self._process_midi_feedback()

                self.launchpad.draw_background(
                    self.background_manager.get_current_background()
                )

                time.sleep(0.02)  # Small delay to prevent excessive CPU usage
                i += 1
        except KeyboardInterrupt:
            logger.info("Shutting down light controller...")
        finally:
            self.cleanup()

    def get_pressed_buttons_info(self) -> str:
        """Get information about all currently pressed buttons."""
        pressed = self.launchpad.get_pressed_buttons()
        if not pressed:
            return "No buttons currently pressed"

        info_lines = [f"Currently pressed buttons ({len(pressed)}):"]
        for button in pressed:
            button_type = button["type"]
            coords = button["index"]
            info_lines.append(f"  {button_type.value}: {coords}")

        return "\n".join(info_lines)

    def cleanup(self) -> None:
        """Clean up resources."""
        self.sequence_manager.cleanup()
        self.launchpad.close()
        logger.info("Light controller stopped")


def main():
    """Main entry point."""
    controller = LightController()
    controller.run()


if __name__ == "__main__":
    main()
