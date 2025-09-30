import logging
import time
import typing as t

from controller.daslight import Daslight
from controller.launchpad import LaunchpadMK2, ButtonType

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
        """Handle preset button press with toggle functionality."""
        if not active:
            return

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
            logger.debug(f"Preset {coords} deactivated")
            return

        # Activate new preset
        self.active_preset = coords.copy()
        self.launchpad.set_button_led(ButtonType.PRESET, coords, self.COLOR_PRESET_ON)
        logger.debug(f"Preset {coords} activated")

    def _handle_top_button(self, coords: t.List[int], active: bool) -> None:
        """make pressed button stay lit"""
        if len(coords) >= 2 and active:
            logger.debug(f"Top button {coords} pressed")
            self.launchpad.set_button_led(
                ButtonType.TOP, coords, [0.0, 0.0, 1.0]
            )  # Blue

    def _process_button_event(self, button_event: t.Dict[str, t.Any]) -> None:
        """Process a button event based on its type."""
        button_type = button_event["type"]
        coords = button_event["index"]
        active = button_event["active"]

        if button_type == ButtonType.SCENE:
            self._handle_scene_button(coords, active)
        elif button_type == ButtonType.PRESET:
            self._handle_preset_button(coords, active)
        elif button_type == ButtonType.TOP:
            self._handle_top_button(coords, active)

    def _process_midi_feedback(self) -> None:
        """Process feedback from MIDI software and update Launchpad LEDs."""
        changes = self.midi_software.process_feedback()

        for note, state in changes.items():
            scene_coords = self.midi_software.get_scene_coordinates_for_note(note)
            if scene_coords:
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

        try:
            while True:
                # Handle button events
                button_event = self.launchpad.get_button_events()
                if button_event:
                    self._process_button_event(button_event)

                # Process MIDI feedback
                self._process_midi_feedback()

                time.sleep(0.01)  # Small delay to prevent excessive CPU usage

        except KeyboardInterrupt:
            logger.info("Shutting down light controller...")
        finally:
            self.cleanup()

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
