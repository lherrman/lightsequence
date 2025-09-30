import json
import logging
import os
import time
import typing as t
from pathlib import Path

from daslight import Daslight
from launchpad import LaunchpadMK2, ButtonType

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
        self.preset_file = Path(__file__).parent / "presets.json"

    def _load_presets(self) -> t.Dict[str, t.Any]:
        """Load presets from JSON file."""
        try:
            if self.preset_file.exists():
                with open(self.preset_file, "r") as f:
                    content = f.read().strip()
                    if not content:
                        # File exists but is empty
                        logger.info("Presets file is empty, creating default structure")
                        return {"presets": []}
                    data = json.loads(content)
                    # Ensure the data has the expected structure
                    if not isinstance(data, dict) or "presets" not in data:
                        logger.warning(
                            "Invalid presets file format, creating default structure"
                        )
                        return {"presets": []}
                    return data
            else:
                # File doesn't exist, create default structure
                logger.info("Presets file doesn't exist, will create it when saving")
                return {"presets": []}
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading presets: {e}, using default structure")
            return {"presets": []}

    def _save_presets(self, presets_data: t.Dict[str, t.Any]) -> None:
        """Save presets to JSON file."""
        try:
            # Ensure the directory exists
            preset_dir = self.preset_file.parent
            if preset_dir and not preset_dir.exists():
                preset_dir.mkdir(parents=True, exist_ok=True)

            # Ensure the data has the correct structure
            if not isinstance(presets_data, dict):
                presets_data = {"presets": []}
            if "presets" not in presets_data:
                presets_data["presets"] = []

            # Validate the presets data structure before saving
            for i, preset in enumerate(presets_data["presets"]):
                if not isinstance(preset, dict):
                    logger.error(f"Invalid preset at index {i}: not a dictionary")
                    continue
                if "index" not in preset or "scenes" not in preset:
                    logger.error(
                        f"Invalid preset at index {i}: missing required fields"
                    )
                    continue
                if not isinstance(preset["index"], list) or not isinstance(
                    preset["scenes"], list
                ):
                    logger.error(
                        f"Invalid preset at index {i}: index or scenes not a list"
                    )
                    continue

            # Write to a temporary file first, then rename to avoid corruption
            temp_file = self.preset_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(presets_data, f, indent=4, ensure_ascii=False)

            # Atomic rename to replace the original file
            temp_file.replace(self.preset_file)
            logger.info("Presets saved successfully")
        except Exception as e:
            logger.error(f"Error saving presets: {e}")
            # Clean up temporary file if it exists
            temp_file = self.preset_file.with_suffix(".tmp")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def _get_preset_by_index(
        self, index: t.List[int]
    ) -> t.Optional[t.Dict[str, t.Any]]:
        """Get preset by index coordinates."""
        presets_data = self._load_presets()
        for preset in presets_data.get("presets", []):
            if preset.get("index") == index:
                return preset
        return None

    def _save_preset(self, index: t.List[int], scenes: t.List[t.List[int]]) -> None:
        """Save or update a preset with given scenes."""
        try:
            # Validate input parameters
            if not isinstance(index, list) or len(index) < 2:
                logger.error(f"Invalid index format: {index}")
                return

            if not isinstance(scenes, list):
                logger.error(f"Invalid scenes format: {scenes}")
                return

            # Validate scene coordinates
            valid_scenes = []
            for scene in scenes:
                if isinstance(scene, list) and len(scene) >= 2:
                    valid_scenes.append([int(scene[0]), int(scene[1])])
                else:
                    logger.warning(f"Skipping invalid scene format: {scene}")

            presets_data = self._load_presets()

            # Find existing preset or create new one
            preset_found = False
            for preset in presets_data["presets"]:
                if preset["index"] == index:
                    preset["scenes"] = valid_scenes
                    preset_found = True
                    logger.info(f"Updated existing preset {index}")
                    break

            if not preset_found:
                new_preset = {
                    "index": [int(index[0]), int(index[1])],
                    "scenes": valid_scenes,
                }
                presets_data["presets"].append(new_preset)
                logger.info(f"Created new preset {index}")

            self._save_presets(presets_data)
            logger.info(f"Preset {index} saved with {len(valid_scenes)} scenes")
        except Exception as e:
            logger.error(f"Error in _save_preset: {e}")

    def _update_preset_leds_for_save_mode(self) -> None:
        """Update preset button LEDs when in save mode to show which have presets."""
        if not self.save_button_state:
            return

        presets_data = self._load_presets()
        preset_indices = {
            tuple(preset["index"]): True for preset in presets_data.get("presets", [])
        }

        # Light up all preset buttons that have presets saved
        for x in range(8):
            for y in range(3):
                coords = [x, y]
                if tuple(coords) in preset_indices:
                    # Preset exists - make it glow
                    self.launchpad.set_button_led(
                        ButtonType.PRESET, coords, [0.0, 0.0, 1.0]
                    )  # Blue
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
            self._save_preset(coords, active_scene_list)
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
        preset = self._get_preset_by_index(coords)
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

        SAVE_BUTTON = [0, 0]  # Example: top-left button as save button
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
