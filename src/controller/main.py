import logging
import time
import typing as t
from pathlib import Path

from daslight import Daslight
from launchpad import LaunchpadMK2, ButtonType
from preset_manager import PresetManager
from background_animator import BackgroundManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LightController:
    """Main controller class that handles communication between Launchpad and DasLight."""

    # Color definitions
    COLOR_SCENE_ON = [0.0, 1.0, 0.0]  # Green
    COLOR_SCENE_OFF = [0.0, 0.0, 0.0]  # Off
    COLOR_PRESET_ON = [1.0, 1.0, 0.0]  # Yellow
    COLOR_PRESET_OFF = [0.0, 0.0, 0.0]  # Off

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

    def _cycle_background(self) -> None:
        """Cycle to the next background animation."""
        self.background_manager.cycle_background()

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
                        ButtonType.PRESET, coords, [1.0, 0.0, 0.5]
                    )  # Magenta
                else:
                    # No preset - turn off
                    self.launchpad.set_button_led(
                        ButtonType.PRESET, coords, self.COLOR_PRESET_OFF
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
            SAVE_BUTTON = [0, 0]  # Example: top-left button as save button
            self.launchpad.set_button_led(ButtonType.TOP, SAVE_BUTTON, [0.0, 0.0, 0.0])

            # Clear all preset LEDs first
            for x in range(8):
                for y in range(3):
                    preset_coords = [x, y]
                    self.launchpad.set_button_led(
                        ButtonType.PRESET, preset_coords, self.COLOR_PRESET_OFF
                    )

            # Activate the newly saved preset
            self.active_preset = coords.copy()
            self.launchpad.set_button_led(
                ButtonType.PRESET, coords, self.COLOR_PRESET_ON
            )
            logger.info(f"Activated saved preset {coords}")
            return

        # Normal preset activation/deactivation logic
        # Clear previous preset LED
        if self.active_preset:
            self.launchpad.set_button_led(
                ButtonType.PRESET, self.active_preset, self.COLOR_PRESET_OFF
            )

        # Toggle preset if same button pressed again
        if self.active_preset == coords:
            self.active_preset = None
            self.launchpad.set_button_led(
                ButtonType.PRESET, coords, self.COLOR_PRESET_OFF
            )
            self.midi_software.send_scene_command((7, 0))
            logger.debug(f"Preset {coords} deactivated")
            return

        # Activate new preset
        self.active_preset = coords.copy()

        # send blackout (7,0)
        self.midi_software.send_scene_command((7, 0))
        self.launchpad.set_button_led(ButtonType.PRESET, coords, self.COLOR_PRESET_ON)

        # Load and activate scenes from the preset
        preset = self.preset_manager.get_preset_by_index(coords)
        if preset and "scenes" in preset:
            for scene_coords in preset["scenes"]:
                if len(scene_coords) >= 2:
                    scene_tuple = (scene_coords[0], scene_coords[1])
                    self.midi_software.send_scene_command(scene_tuple)
                    self.active_scenes.add(scene_tuple)
                    # Use abstracted LED control with relative coordinates
                    color = self.COLOR_SCENE_ON
                    coords_list = [scene_coords[0], scene_coords[1]]
                    self.launchpad.set_button_led(ButtonType.SCENE, coords_list, color)
            logger.info(
                f"Activated preset {coords} with {len(preset['scenes'])} scenes"
            )

        logger.debug(f"Preset {coords} activated")

    def _handle_top_button(self, coords: t.List[int], is_pressed: bool) -> None:
        """Handle top button press - light up when pressed, turn off when released."""

        SAVE_BUTTON = [0, 0]  # Top-left button as save button
        BACKGROUND_BUTTON = [1, 0]  # Second button from left as background cycle button

        if (
            coords == SAVE_BUTTON and is_pressed
        ):  # Only handle press events, not release
            self.save_button_state = not self.save_button_state

            if self.save_button_state:
                # Entering save mode - turn save button red and show preset buttons with presets in blue
                self.launchpad.set_button_led(
                    ButtonType.TOP, coords, [1.0, 0.0, 0.0]
                )  # Red
                self._update_preset_leds_for_save_mode()
                logger.info("Entered save mode")
            else:
                # Exiting save mode - turn save button off and restore normal preset display
                self.launchpad.set_button_led(
                    ButtonType.TOP, coords, [0.0, 0.0, 0.0]
                )  # Off

                # Clear all preset LEDs first
                for x in range(8):
                    for y in range(3):
                        preset_coords = [x, y]
                        self.launchpad.set_button_led(
                            ButtonType.PRESET, preset_coords, self.COLOR_PRESET_OFF
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
                    ButtonType.TOP, coords, [0.0, 1.0, 1.0]
                )  # Cyan
            else:
                self.launchpad.set_button_led(
                    ButtonType.TOP, coords, [0.0, 0.0, 0.0]
                )  # Off

    def _process_button_event(self, button_event: t.Dict[str, t.Any]) -> None:
        """Process a button event based on its type."""
        button_type = button_event["type"]
        coords = button_event["index"]
        is_pressed = button_event["active"]

        if button_type == ButtonType.SCENE:
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
                color = self.COLOR_SCENE_ON if state else self.COLOR_SCENE_OFF
                coords_list = [scene_coords[0], scene_coords[1]]
                self.launchpad.set_button_led(ButtonType.SCENE, coords_list, color)

    def run(self) -> None:
        """Main control loop."""
        if not self.connect():
            logger.error("Failed to connect to devices")
            return

        logger.info("Light controller started. Press Ctrl+C to exit.")
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
        self.launchpad.close()
        logger.info("Light controller stopped")


def main():
    """Main entry point."""
    controller = LightController()
    controller.run()


if __name__ == "__main__":
    main()
