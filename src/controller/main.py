import logging
import time
import typing as t
from pathlib import Path

from light_software import LightSoftware
from light_software_sim import LightSoftwareSim
from launchpad import LaunchpadMK2, ButtonType
from preset_manager import PresetManager
from background_animator import BackgroundManager
from sequence_manager import SequenceManager, SequenceState
from config import get_config
from enums import AppState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LightController:
    """Main controller for light sequence management."""

    def __init__(self, simulation: bool = False):
        """Initialize the light controller with all managers and hardware connections.

        Args:
            simulation: If True, use simulated lighting software instead of real one
        """
        # Managers - create these first
        preset_file = Path("presets.json")
        self.preset_manager = PresetManager(preset_file)
        self.background_manager = BackgroundManager(self.preset_manager)
        self.sequence_manager = SequenceManager()

        # Hardware connections
        if simulation:
            logger.info("🔧 Using simulated lighting software")
            self.light_software = LightSoftwareSim()
        else:
            self.light_software = LightSoftware()
        self.launchpad_controller = LaunchpadMK2(self.preset_manager)

        # Application state
        self.current_app_state = AppState.NORMAL
        self.currently_active_preset: t.Optional[t.List[int]] = None
        self.currently_active_scenes: t.Set[t.Tuple[int, int]] = set()
        self.preset_controlled_scenes: t.Set[t.Tuple[int, int]] = set()
        self.is_playback_enabled = True  # Default to playback enabled

        # Configuration
        self.app_config = get_config()

        # Setup callbacks
        self._setup_sequence_callbacks()

        # External callbacks (for GUI integration)
        self.on_preset_changed: t.Optional[
            t.Callable[[t.Optional[t.List[int]]], None]
        ] = None
        self.on_preset_saved: t.Optional[t.Callable[[], None]] = None

    def _setup_sequence_callbacks(self) -> None:
        """Setup callbacks for sequence manager events."""
        self.sequence_manager.on_step_change = self._handle_sequence_step_changed
        self.sequence_manager.on_sequence_complete = self._handle_sequence_completed

    def initialize_hardware_connections(self) -> bool:
        """Connect to all hardware devices and sync initial state."""
        midi_connection_successful = self.light_software.connect_midi()

        if midi_connection_successful:
            # Process initial feedback to sync active scenes
            initial_changes = self.light_software.process_feedback()
            for note, is_active in initial_changes.items():
                scene_coordinates = self.light_software.get_scene_coordinates_for_note(
                    note
                )
                if scene_coordinates and is_active:
                    self.currently_active_scenes.add(scene_coordinates)

            logger.info("Successfully connected to DasLight")
            if self.currently_active_scenes:
                logger.info(
                    f"Found {len(self.currently_active_scenes)} active scenes on startup"
                )
        else:
            logger.error("Failed to connect to DasLight")

        # Update clear button status immediately after connection attempt
        self._update_clear_button_display()

        return midi_connection_successful and self.launchpad_controller.is_connected

    def run_main_loop(self) -> None:
        """Main control loop - clearly separated input processing and output updates."""
        if not self.initialize_hardware_connections():
            logger.error("Failed to connect to devices")
            return

        logger.info("Light controller started. Press Ctrl+C to exit.")

        # Initialize clear button display
        self._update_clear_button_display()

        try:
            while True:
                # INPUT PROCESSING PHASE
                self._process_all_inputs()

                # OUTPUT UPDATES PHASE
                self._update_all_outputs()

                # Brief pause to prevent excessive CPU usage
                time.sleep(0.02)
        except KeyboardInterrupt:
            logger.info("Shutting down light controller...")
        finally:
            self.cleanup_resources()

    def cleanup_resources(self) -> None:
        """Clean up all resources and connections."""
        self.sequence_manager.cleanup()
        self.launchpad_controller.close()
        logger.info("Light controller stopped")

    # ============================================================================
    # INPUT PROCESSING METHODS
    # ============================================================================

    def _process_all_inputs(self) -> None:
        """Process all input sources in one consolidated method."""
        # Process physical button presses from launchpad
        self._process_launchpad_button_inputs()

        # Process MIDI feedback from lighting software
        self._process_midi_feedback_inputs()

    def _process_launchpad_button_inputs(self) -> None:
        """Handle button press events from the launchpad controller."""
        button_event = self.launchpad_controller.get_button_events()
        if button_event:
            self._route_button_event_to_handler(button_event)

    def _process_midi_feedback_inputs(self) -> None:
        """Process MIDI feedback from lighting software and update scene tracking."""
        midi_changes = self.light_software.process_feedback()

        for note, is_active in midi_changes.items():
            # Skip ping responses (note 127) - handled by Daslight class
            if note == 127:
                continue

            scene_coordinates = self.light_software.get_scene_coordinates_for_note(note)
            if scene_coordinates:
                if is_active:
                    self.currently_active_scenes.add(scene_coordinates)
                else:
                    self.currently_active_scenes.discard(scene_coordinates)
                    self.preset_controlled_scenes.discard(scene_coordinates)

                # Update the corresponding LED on the launchpad
                scene_color = self._determine_scene_led_color(
                    scene_coordinates, is_active
                )
                coordinates_list = [scene_coordinates[0], scene_coordinates[1]]
                self.launchpad_controller.set_button_led(
                    ButtonType.SCENE, coordinates_list, scene_color
                )

    # ============================================================================
    # OUTPUT UPDATE METHODS
    # ============================================================================

    def _update_all_outputs(self) -> None:
        """Update all output displays in one consolidated method."""
        # Update background animation
        self._update_background_display()

        # Update clear button indicator
        self._update_clear_button_display()

    def _update_background_display(self) -> None:
        """Update the background animation display on the launchpad."""
        current_background = self.background_manager.get_current_background()
        self.launchpad_controller.draw_background(
            current_background, app_state=self.current_app_state
        )

    def _update_clear_button_display(self) -> None:
        """Reflect whether there are active scenes on the clear button LED."""
        binding = self.app_config.data["key_bindings"]["clear_button"]
        from config import get_button_type_enum

        button_type = get_button_type_enum(binding["button_type"])
        color_key = "success_flash" if self.currently_active_scenes else "off"
        self.launchpad_controller.set_button_led(
            button_type,
            binding["coordinates"],
            self.app_config.data["colors"][color_key],
        )

    def _matches_key_binding(self, coordinates: list[int], key_name: str) -> bool:
        """Check if coordinates match a specific key binding."""
        binding = self.app_config.data["key_bindings"][key_name]
        return coordinates == binding["coordinates"]

    # ============================================================================
    # BUTTON EVENT ROUTING AND HANDLING
    # ============================================================================

    def _route_button_event_to_handler(self, button_event: t.Dict[str, t.Any]) -> None:
        """Route button events to appropriate handlers based on button type."""
        button_type_handlers = {
            ButtonType.SCENE: self._handle_scene_button_press,
            ButtonType.RIGHT: self._handle_right_column_button_press,
            ButtonType.PRESET: self._handle_preset_button_press,
            ButtonType.TOP: self._handle_top_row_button_press,
        }

        event_handler = button_type_handlers.get(button_event["type"])
        if event_handler:
            event_handler(button_event["index"], button_event["active"])

    def _handle_scene_button_press(
        self, coordinates: t.List[int], is_pressed: bool
    ) -> None:
        """Handle scene button press events."""
        if is_pressed and len(coordinates) >= 2:
            coordinate_tuple = (coordinates[0], coordinates[1])
            logger.debug(f"Scene button {coordinates} pressed")
            self.light_software.send_scene_command(coordinate_tuple)

    def _handle_preset_button_press(
        self, coordinates: t.List[int], is_pressed: bool
    ) -> None:
        """Handle preset button press with state-based routing."""
        if not is_pressed:
            return

        state_based_handlers = {
            AppState.NORMAL: self._handle_preset_button_normal_mode,
            AppState.SAVE_MODE: self._handle_preset_button_save_mode,
            AppState.SAVE_SHIFT_MODE: self._handle_preset_button_save_shift_mode,
        }

        handler = state_based_handlers[self.current_app_state]
        handler(coordinates)

    def _handle_top_row_button_press(
        self, coordinates: t.List[int], is_pressed: bool
    ) -> None:
        """Handle top row button presses (save, background, brightness controls)."""
        if not is_pressed:
            return

        if self._matches_key_binding(coordinates, "save_button"):
            self._toggle_save_mode_state()
        elif self._matches_key_binding(coordinates, "save_shift_button"):
            self._toggle_save_shift_mode_state()
        elif self._matches_key_binding(coordinates, "background_button"):
            self._cycle_background_animation()
        elif self._matches_key_binding(coordinates, "background_brightness_down"):
            self._decrease_background_brightness()
        elif self._matches_key_binding(coordinates, "background_brightness_up"):
            self._increase_background_brightness()

    def _handle_right_column_button_press(
        self, coordinates: t.List[int], is_pressed: bool
    ) -> None:
        """Handle right column button presses (playback controls and additional scenes)."""
        if not is_pressed:
            return

        if self._matches_key_binding(coordinates, "playback_toggle_button"):
            self._toggle_sequence_playback()
        elif self._matches_key_binding(coordinates, "next_step_button"):
            self._advance_to_next_sequence_step()
        elif self._matches_key_binding(coordinates, "clear_button"):
            self._clear_all_active_scenes()
        else:
            # Treat other right column buttons as scene buttons
            self._handle_scene_button_press(coordinates, is_pressed)

    # ============================================================================
    # PRESET HANDLING BY MODE
    # ============================================================================

    def _handle_preset_button_normal_mode(self, coordinates: t.List[int]) -> None:
        """Handle preset button press in normal operating mode."""
        if self.currently_active_preset == coordinates:
            self._deactivate_current_preset()
            logger.debug(f"Preset {coordinates} deactivated")
        else:
            self._activate_preset(coordinates)
            logger.debug(f"Preset {coordinates} activated")

    def _handle_preset_button_save_mode(self, coordinates: t.List[int]) -> None:
        """Handle preset button press in save mode."""
        currently_active_scenes = [
            [scene[0], scene[1]] for scene in self.currently_active_scenes
        ]
        self.preset_manager.save_preset(coordinates, currently_active_scenes)

        logger.info(
            f"Saved {len(currently_active_scenes)} scenes to preset {coordinates}"
        )
        self._notify_external_preset_saved()
        self._exit_all_save_modes()
        self._activate_preset(coordinates)

    def _handle_preset_button_save_shift_mode(self, coordinates: t.List[int]) -> None:
        """Handle preset button press in save shift mode (adds step to sequence)."""
        if not self.currently_active_scenes:
            logger.warning("No active scenes to add as step")
            return

        currently_active_scenes = [
            [scene[0], scene[1]] for scene in self.currently_active_scenes
        ]
        self.preset_manager.add_step_to_preset(coordinates, currently_active_scenes)

        self._display_success_flash(coordinates)
        self._notify_external_preset_saved()
        self._exit_all_save_modes()
        self._activate_preset(coordinates)

    # ============================================================================
    # SAVE MODE STATE MANAGEMENT
    # ============================================================================

    def _toggle_save_mode_state(self) -> None:
        """Toggle between normal mode and save mode."""
        if self.current_app_state == AppState.SAVE_MODE:
            self._exit_all_save_modes()
        else:
            # Exit save shift mode if active, then enter save mode
            if self.current_app_state == AppState.SAVE_SHIFT_MODE:
                self._exit_all_save_modes()
            self._enter_save_mode()

    def _toggle_save_shift_mode_state(self) -> None:
        """Toggle save shift mode independently."""
        if self.current_app_state == AppState.SAVE_SHIFT_MODE:
            self._exit_all_save_modes()
        else:
            # Exit save mode if active, then enter save shift mode
            if self.current_app_state == AppState.SAVE_MODE:
                self._exit_all_save_modes()
            self._enter_save_shift_mode()

    def _enter_save_mode(self) -> None:
        """Enter save mode state."""
        self.current_app_state = AppState.SAVE_MODE

        if self.sequence_manager.sequence_state != SequenceState.STOPPED:
            self.sequence_manager.stop_sequence()
            logger.debug("Stopped sequence playback for save mode")

        # Light up save button
        self._set_save_button_led("save_button", True)
        self._update_preset_leds_for_current_save_mode()
        logger.debug("Entered save mode")

    def _enter_save_shift_mode(self) -> None:
        """Enter save shift mode state."""
        self.current_app_state = AppState.SAVE_SHIFT_MODE

        if self.sequence_manager.sequence_state != SequenceState.STOPPED:
            self.sequence_manager.stop_sequence()
            logger.debug("Stopped sequence playback for save shift mode")

        # Light up save shift button
        self._set_save_button_led("save_shift_button", True)
        self._update_preset_leds_for_current_save_mode()
        logger.debug("Entered save shift mode")

    def _exit_all_save_modes(self) -> None:
        """Exit all save modes and return to normal operation."""
        self.current_app_state = AppState.NORMAL

        # Turn off save mode indicator buttons
        self._set_save_button_led("save_button", False)
        self._set_save_button_led("save_shift_button", False)

        # Clear and restore preset LEDs to normal state
        self._clear_all_preset_button_leds()
        if self.currently_active_preset:
            self.launchpad_controller.set_button_led(
                ButtonType.PRESET,
                self.currently_active_preset,
                self.app_config.data["colors"]["preset_on"],
            )

        logger.debug("Exited save mode")

    def _set_save_button_led(self, button_key: str, is_on: bool) -> None:
        """Set LED state for save buttons using configuration."""
        binding = self.app_config.data["key_bindings"][button_key]
        from config import get_button_type_enum

        button_type = get_button_type_enum(binding["button_type"])
        color = (
            self.app_config.data["colors"]["save_mode_on"]
            if is_on
            else self.app_config.data["colors"]["off"]
        )
        self.launchpad_controller.set_button_led(
            button_type, binding["coordinates"], color
        )

    # ============================================================================
    # BACKGROUND ANIMATION CONTROLS
    # ============================================================================

    def _cycle_background_animation(self) -> None:
        """Cycle to the next background animation."""
        self.background_manager.cycle_background()

    def _decrease_background_brightness(self) -> None:
        """Decrease background brightness by 0.03, minimum 0.0."""
        current_brightness_level = self.app_config.data["brightness_background"]
        new_brightness_level = max(0.0, current_brightness_level - 0.03)
        self._set_background_brightness_level(new_brightness_level)
        logger.debug(f"Background brightness decreased to {new_brightness_level:.2f}")

    def _increase_background_brightness(self) -> None:
        """Increase background brightness by 0.03, maximum 1.0."""
        current_brightness_level = self.app_config.data["brightness_background"]
        new_brightness_level = min(1.0, current_brightness_level + 0.03)
        self._set_background_brightness_level(new_brightness_level)
        logger.debug(f"Background brightness increased to {new_brightness_level:.2f}")

    def _set_background_brightness_level(self, brightness_level: float) -> None:
        """Set background brightness and persist the setting."""
        # Update the config data directly
        self.app_config.data["brightness_background"] = brightness_level
        # Save to file
        self.app_config._save_config(self.app_config.data)

        # Redraw the background immediately with force_update=True to show the change
        self.launchpad_controller.draw_background(
            self.background_manager.get_current_background(), force_update=True
        )
        # Update brightness button LEDs
        self.launchpad_controller.draw_background()

    # ============================================================================
    # SEQUENCE PLAYBACK CONTROLS
    # ============================================================================

    def _toggle_sequence_playback(self) -> None:
        """Toggle sequence playback between play and pause states."""
        if not self.currently_active_preset:
            logger.debug("No active preset - playback toggle has no effect")
            return

        if not self.preset_manager.has_sequence(self.currently_active_preset):
            logger.debug(
                "Active preset is not a sequence - playback toggle has no effect"
            )
            return

        current_sequence_state = self.sequence_manager.sequence_state

        if current_sequence_state == SequenceState.PLAYING:
            self.sequence_manager.pause_sequence()
            self.is_playback_enabled = False
            logger.debug("Sequence playback paused")
        elif current_sequence_state == SequenceState.PAUSED:
            self.sequence_manager.resume_sequence()
            self.is_playback_enabled = True
            logger.debug("Sequence playback resumed")
        else:
            logger.debug("No sequence currently playing to pause/resume")
            return

        self._update_playback_control_button_displays()

    def _advance_to_next_sequence_step(self) -> None:
        """Manually advance to the next step in the current sequence."""
        if not self.currently_active_preset:
            logger.debug("No active preset - cannot advance step")
            return

        if not self.preset_manager.has_sequence(self.currently_active_preset):
            logger.debug("Active preset is not a sequence - cannot advance step")
            return

        if self.sequence_manager.next_step():
            # Flash the next step button to indicate successful advancement
            self._set_playback_button_led("next_step_button", "next_step")
            time.sleep(0.1)
            self._update_playback_control_button_displays()

    def _update_playback_control_button_displays(self) -> None:
        """Update the LED displays for all playback control buttons."""
        # Update playback toggle button based on current state
        if not self.currently_active_preset or not self.preset_manager.has_sequence(
            self.currently_active_preset
        ):
            # No sequence active - turn off playback control buttons
            self._set_playback_button_led("playback_toggle_button", "off")
            self._set_playback_button_led("next_step_button", "off")
            return

        current_sequence_state = self.sequence_manager.sequence_state

        if current_sequence_state == SequenceState.PLAYING:
            # Green indicator for actively playing
            self._set_playback_button_led("playback_toggle_button", "playback_playing")
        elif current_sequence_state == SequenceState.PAUSED:
            # Orange indicator for paused state
            self._set_playback_button_led("playback_toggle_button", "playback_paused")
        else:
            # Off indicator for stopped state
            self._set_playback_button_led("playback_toggle_button", "off")

        # Next step button - blue when sequence is active (playing or paused)
        if current_sequence_state in [SequenceState.PLAYING, SequenceState.PAUSED]:
            self._set_playback_button_led("next_step_button", "next_step")
        else:
            self._set_playback_button_led("next_step_button", "off")

    def _set_playback_button_led(self, button_key: str, color_key: str) -> None:
        """Set LED for playback buttons using configuration."""
        binding = self.app_config.data["key_bindings"][button_key]
        from config import get_button_type_enum

        button_type = get_button_type_enum(binding["button_type"])
        color = self.app_config.data["colors"][color_key]
        self.launchpad_controller.set_button_led(
            button_type, binding["coordinates"], color
        )

    # ============================================================================
    # PRESET ACTIVATION AND MANAGEMENT
    # ============================================================================

    def _activate_preset(self, coordinates: t.List[int]) -> None:
        """Activate a preset (either simple scenes or sequence)."""
        # Stop any running sequence but don't clear scenes - let smart transition handle it
        if self.currently_active_preset:
            self.sequence_manager.stop_sequence()
            self.launchpad_controller.set_button_led(
                ButtonType.PRESET,
                self.currently_active_preset,
                self.app_config.data["colors"]["off"],
            )

        self.currently_active_preset = coordinates.copy()
        self.launchpad_controller.set_button_led(
            ButtonType.PRESET, coordinates, self.app_config.data["colors"]["preset_on"]
        )

        if self.on_preset_changed:
            self.on_preset_changed(coordinates.copy())

        # No blackout needed - smart scene transitions will handle it
        if self._try_activate_sequence_preset(coordinates):
            # Update playback buttons for sequence presets
            self._update_playback_control_button_displays()
            return

        self._activate_simple_preset(coordinates)
        # Update playback buttons (will turn them off for simple presets)
        self._update_playback_control_button_displays()

    def _try_activate_sequence_preset(self, coordinates: t.List[int]) -> bool:
        """Attempt to activate a sequence preset. Returns True if successful."""
        if not self.preset_manager.has_sequence(coordinates):
            return False

        sequence_steps = self.preset_manager.get_sequence(coordinates)
        if not sequence_steps:
            return False

        preset_tuple = (coordinates[0], coordinates[1])
        self.sequence_manager.add_sequence(preset_tuple, sequence_steps)

        is_loop_enabled = self.preset_manager.get_loop_setting(coordinates)
        self.sequence_manager.set_loop_enabled(is_loop_enabled)

        if self.sequence_manager.start_sequence(preset_tuple):
            logger.debug(
                f"Started sequence preset {coordinates} with {len(sequence_steps)} steps (loop: {is_loop_enabled})"
            )
            return True
        else:
            logger.error(f"Failed to start sequence for preset {coordinates}")
            if sequence_steps[0].scenes:
                self._activate_scene_list(sequence_steps[0].scenes)
            return False

    def _activate_simple_preset(self, coordinates: t.List[int]) -> None:
        """Activate a simple preset (non-sequence)."""
        preset_data = self.preset_manager.get_preset_by_index(coordinates)
        if preset_data and "scenes" in preset_data:
            self._activate_scene_list(preset_data["scenes"])
            logger.debug(
                f"Activated simple preset {coordinates} with {len(preset_data['scenes'])} scenes"
            )
        else:
            # No preset saved - deactivate all running scenes
            self._activate_scene_list([])
            logger.debug(f"No preset saved at {coordinates} - deactivated all scenes")

    def _deactivate_current_preset(self) -> None:
        """Deactivate the currently active preset."""
        if not self.currently_active_preset:
            return

        self.sequence_manager.stop_sequence()
        self.launchpad_controller.set_button_led(
            ButtonType.PRESET,
            self.currently_active_preset,
            self.app_config.data["colors"]["off"],
        )

        # Use smart transition to turn off all scenes
        self._transition_to_target_scenes(set())

        self.currently_active_preset = None
        if self.on_preset_changed:
            self.on_preset_changed(None)

        # Update playback buttons (will turn them off)
        self._update_playback_control_button_displays()

    # ============================================================================
    # SCENE ACTIVATION AND SMART TRANSITIONS
    # ============================================================================

    def _activate_scene_list(self, scene_list: t.List[t.List[int]]) -> None:
        """Activate a list of scenes using smart diffing to prevent flicker."""
        # Convert scene list to set of tuples for efficient operations
        target_scene_set = set()
        for scene_coordinates in scene_list:
            if len(scene_coordinates) >= 2:
                target_scene_set.add((scene_coordinates[0], scene_coordinates[1]))

        # Perform smart scene transition
        self._transition_to_target_scenes(target_scene_set)

    def _transition_to_target_scenes(
        self, target_scene_set: t.Set[t.Tuple[int, int]]
    ) -> None:
        """Smart scene transition that only toggles scenes that need to change."""
        # Determine preset-controlled scenes that should be deactivated
        scenes_to_deactivate = self.preset_controlled_scenes - target_scene_set

        # Determine scenes that need activation (and aren't already active)
        scenes_to_activate = target_scene_set - self.currently_active_scenes

        logger.debug(
            f"Scene transition: deactivating {len(scenes_to_deactivate)}, activating {len(scenes_to_activate)}, keeping {len(self.currently_active_scenes & target_scene_set)} unchanged"
        )

        # Deactivate scenes that should be turned off
        for scene_tuple in scenes_to_deactivate:
            self.light_software.send_scene_command(scene_tuple)  # Toggle off
            coordinates_list = [scene_tuple[0], scene_tuple[1]]
            self.launchpad_controller.set_button_led(
                ButtonType.SCENE,
                coordinates_list,
                self.app_config.data["colors"]["off"],
            )

            self.currently_active_scenes.discard(scene_tuple)
            self.preset_controlled_scenes.discard(scene_tuple)

        # Activate scenes that should be turned on
        for scene_tuple in scenes_to_activate:
            self.light_software.send_scene_command(scene_tuple)  # Toggle on
            coordinates_list = [scene_tuple[0], scene_tuple[1]]

            # Determine appropriate color for the activated scene
            scene_led_color = self._determine_scene_led_color(scene_tuple, True)
            self.launchpad_controller.set_button_led(
                ButtonType.SCENE, coordinates_list, scene_led_color
            )

            self.currently_active_scenes.add(scene_tuple)
            self.preset_controlled_scenes.add(scene_tuple)

        self._update_clear_button_display()

    def _clear_all_active_scenes(self) -> None:
        """Turn off every active scene regardless of origin."""
        if self.currently_active_preset:
            self._deactivate_current_preset()

        if not self.currently_active_scenes:
            logger.debug("Clear button pressed but no scenes are active")
            return

        active_scenes_snapshot = list(self.currently_active_scenes)
        for scene_tuple in active_scenes_snapshot:
            self.light_software.send_scene_command(scene_tuple)
            self.launchpad_controller.set_button_led(
                ButtonType.SCENE,
                [scene_tuple[0], scene_tuple[1]],
                self.app_config.data["colors"]["off"],
            )

        self.currently_active_scenes.clear()
        self.preset_controlled_scenes.clear()
        self._update_clear_button_display()

    def _determine_scene_led_color(
        self, scene_coordinates: t.Tuple[int, int], is_active: bool
    ) -> t.Union[t.List[float], str]:
        """Determine the appropriate LED color for a scene based on configuration."""
        if not is_active:
            return self.app_config.data["colors"]["off"]

        # Choose color based on config setting
        if self.app_config.data["scene_on_color_from_column"]:
            column_specific_color = self.app_config.data["colors"]["column_colors"].get(
                str(scene_coordinates[0])
            )
            return (
                column_specific_color
                if column_specific_color
                else self.app_config.data["colors"]["scene_on"]
            )
        else:
            return self.app_config.data["colors"]["scene_on"]

    # ============================================================================
    # SEQUENCE EVENT HANDLERS
    # ============================================================================

    def _handle_sequence_step_changed(
        self, new_scene_list: t.List[t.List[int]]
    ) -> None:
        """Handle sequence step change events with smart scene transitions."""
        if not self.currently_active_preset:
            return

        # Use smart scene transition instead of blackout
        self._activate_scene_list(new_scene_list)
        logger.debug(f"Sequence step changed to {len(new_scene_list)} scenes")

    def _handle_sequence_completed(self) -> None:
        """Handle sequence completion events."""
        logger.info("Sequence completed")

    # ============================================================================
    # LED DISPLAY MANAGEMENT
    # ============================================================================

    def _update_preset_leds_for_current_save_mode(self) -> None:
        """Update preset LEDs to reflect the current save mode state."""
        if self.current_app_state == AppState.NORMAL:
            return

        existing_preset_indices = self.preset_manager.get_all_preset_indices()

        for column in range(8):
            for row in range(3):
                coordinates = [column, row]
                has_preset = tuple(coordinates) in existing_preset_indices

                if has_preset:
                    # Button has a preset - use appropriate save mode color
                    if self.current_app_state == AppState.SAVE_SHIFT_MODE:
                        button_led_color = self.app_config.data["colors"][
                            "preset_save_shift_mode"
                        ]
                    else:  # AppState.SAVE_MODE
                        button_led_color = self.app_config.data["colors"][
                            "preset_save_mode"
                        ]
                else:
                    # Button has no preset
                    if self.current_app_state == AppState.SAVE_MODE:
                        # In save mode: reduced brightness white
                        from utils import hex_to_rgb

                        base_color = hex_to_rgb(
                            self.app_config.data["colors"][
                                "save_mode_preset_background"
                            ]
                        )
                        brightness = self.app_config.data["brightness_background"]
                        button_led_color = [c * brightness for c in base_color]
                    else:  # AppState.SAVE_SHIFT_MODE
                        # In save shift mode: turn off empty buttons
                        button_led_color = self.app_config.data["colors"]["off"]

                self.launchpad_controller.set_button_led(
                    ButtonType.PRESET, coordinates, button_led_color
                )

    def _clear_all_preset_button_leds(self) -> None:
        """Turn off all preset button LEDs."""
        for column in range(8):
            for row in range(3):
                self.launchpad_controller.set_button_led(
                    ButtonType.PRESET,
                    [column, row],
                    self.app_config.data["colors"]["off"],
                )

    def _clear_all_scene_button_leds(self) -> None:
        """Turn off all scene button LEDs."""
        for column in range(8):
            for row in range(1, 6):
                self.launchpad_controller.set_button_led(
                    ButtonType.SCENE,
                    [column, row],
                    self.app_config.data["colors"]["off"],
                )

    def _clear_scene_leds_partial_range(self) -> None:
        """Turn off scene LEDs for sequence changes (avoid preset row overlap)."""
        for column in range(8):
            for row in range(1, 5):  # Rows 1-4 only
                self.launchpad_controller.set_button_led(
                    ButtonType.SCENE,
                    [column, row],
                    self.app_config.data["colors"]["off"],
                )

    def _display_success_flash(self, coordinates: t.List[int]) -> None:
        """Flash a button green briefly to indicate successful operation."""
        self.launchpad_controller.set_button_led(
            ButtonType.PRESET,
            coordinates,
            self.app_config.data["colors"]["success_flash"],
        )
        time.sleep(0.2)
        flash_color = (
            self.app_config.data["colors"]["preset_save_shift_mode"]
            if self.current_app_state == AppState.SAVE_SHIFT_MODE
            else self.app_config.data["colors"]["preset_save_mode"]
        )
        self.launchpad_controller.set_button_led(
            ButtonType.PRESET, coordinates, flash_color
        )

    # ============================================================================
    # EXTERNAL INTERFACE AND CALLBACKS
    # ============================================================================

    def _notify_external_preset_saved(self) -> None:
        """Notify external systems that a preset was saved."""
        if self.on_preset_saved:
            self.on_preset_saved()

    def process_button_event_from_external(self, event: t.Dict[str, t.Any]) -> None:
        """Process button events from external sources (GUI compatibility interface)."""
        self._route_button_event_to_handler(event)

    def process_midi_feedback_from_external(self) -> None:
        """Process MIDI feedback from external sources (GUI compatibility interface)."""
        self._process_midi_feedback_inputs()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main(simulation: bool = False):
    """Main application entry point.

    Args:
        simulation: If True, use simulated lighting software instead of real one
    """
    light_controller = LightController(simulation=simulation)
    light_controller.run_main_loop()


if __name__ == "__main__":
    main()
