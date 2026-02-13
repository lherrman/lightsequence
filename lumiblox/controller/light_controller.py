"""
Light Controller - Slim Orchestrator

Coordinates all subsystems:
- SequenceController: Manages sequences and playback
- SceneController: Handles scene activation
- InputHandler: Processes button events
- LEDController: Updates LEDs
- DeviceManager: Tracks device states
- DeviceMonitor: Auto-reconnects devices
"""

import logging
import time
import typing as t
from typing import TYPE_CHECKING

from lumiblox.controller.sequence_controller import (
    SequenceController,
    SequenceStep,
    PlaybackState,
)
from lumiblox.controller.scene_controller import SceneController
from lumiblox.controller.input_handler import InputHandler, ButtonEvent, ButtonType
from lumiblox.controller.led_controller import LEDController
from lumiblox.controller.device_monitor import DeviceMonitor
from lumiblox.controller.background_animator import BackgroundManager
from lumiblox.devices.launchpad import LaunchpadMK2
from lumiblox.midi.light_software import LightSoftware
from lumiblox.midi.light_software_sim import LightSoftwareSim
from lumiblox.common.device_state import DeviceManager, DeviceType
from lumiblox.common.config import get_config, ROWS_PER_PAGE, NUM_SCENE_PAGES, SCENE_COLUMNS
from lumiblox.common.enums import AppState
from lumiblox.pilot.project_data_repository import ProjectDataRepository
from lumiblox.midi.midi_manager import midi_manager

if TYPE_CHECKING:
    from lumiblox.pilot.pilot_controller import PilotController

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LightController:
    """
    Main orchestrator - coordinates all subsystems.
    
    """
    
    def __init__(self, simulation: bool = False):
        """Initialize the light controller."""
        # Device management
        self.device_manager = DeviceManager()
        self.device_monitor = DeviceMonitor(self.device_manager)
        
        # Initialize project data repository
        self.project_repo = ProjectDataRepository()
        
        # Core controllers
        self.sequence_ctrl = SequenceController(self.project_repo)
        self.scene_ctrl = SceneController()
        self.input_handler = InputHandler()
        
        # Hardware
        if simulation:
            logger.info("Using simulated lighting software")
            self.light_software = LightSoftwareSim()
        else:
            self.light_software = LightSoftware(device_manager=self.device_manager)
        
        self.launchpad = LaunchpadMK2(None, device_manager=self.device_manager)
        self.led_ctrl = LEDController(self.launchpad)
        self.background_mgr = BackgroundManager(None)  # Will update presets access
        
        # App state
        self.app_state = AppState.NORMAL
        self.active_sequence: t.Optional[t.Tuple[int, int]] = None
        self._last_sequence_scenes: t.Set[t.Tuple[int, int]] = set()
        self.active_page: int = 0
        self._blink_phase: bool = False
        self._last_blink_toggle: float = 0.0
        self._dual_active_positions: t.Set[t.Tuple[int, int]] = set()
        self._other_page_only_positions: t.Set[t.Tuple[int, int]] = set()
        self._BLINK_INTERVAL: float = 0.35  # seconds between color alternation
        self.config = get_config()
        self.pilot_controller: t.Optional["PilotController"] = None

        # Apply background animation from config (set once at startup)
        self.background_mgr.set_background(
            self.config.data.get("background_animation", "default")
        )

        
        # External callbacks (for GUI)
        self.on_sequence_changed: t.Optional[t.Callable[[t.Optional[t.Tuple[int, int]]], None]] = None
        self.on_sequence_saved: t.Optional[t.Callable[[], None]] = None
        self.on_pilot_selection_changed: t.Optional[t.Callable[[int], None]] = None
        
        # Wire up callbacks
        self._setup_callbacks()
    
    def _setup_callbacks(self) -> None:
        """Connect all the controllers together."""
        # Scene controller -> Light software & LED updates
        self.scene_ctrl.on_scene_activate = self._handle_scene_activate
        self.scene_ctrl.on_scene_deactivate = self._handle_scene_deactivate
        
        # Sequence controller -> Scene controller
        self.sequence_ctrl.on_step_change = self._handle_step_change
        self.sequence_ctrl.on_sequence_complete = self._handle_sequence_complete
        
        # Input handler -> Action handlers
        self.input_handler.on_scene_button = self._handle_scene_button
        self.input_handler.on_sequence_button = self._handle_sequence_button
        self.input_handler.on_control_button = self._handle_control_button
        
        # Register control buttons from config
        self._register_control_buttons()
        
        # Device monitor
        self.device_monitor.register_reconnect_callback(
            DeviceType.LAUNCHPAD, self.launchpad.connect
        )
        self.device_monitor.register_reconnect_callback(
            DeviceType.LIGHT_SOFTWARE, self.light_software.connect_midi
        )
        self.device_manager.register_state_change_callback(
            self._on_device_state_changed
        )
    
    def _register_control_buttons(self) -> None:
        """Register control buttons from configuration."""
        bindings = self.config.data.get("key_bindings", {})
        allowed_controls = {
            "save_button",
            "save_shift_button",
            "playback_toggle_button",
            "next_step_button",
            "clear_button",
            "pilot_select_button",
            "pilot_toggle_button",
            "page_1_button",
            "page_2_button",
        }
        for name, binding in bindings.items():
            if name not in allowed_controls:
                logger.debug("Skipping unsupported control binding: %s", name)
                continue
            coords = tuple(binding["coordinates"])
            self.input_handler.register_control_button(name, coords)
    
    # ============================================================================
    # LIFECYCLE
    # ============================================================================
    
    def initialize(self) -> bool:
        """Initialize hardware connections (non-blocking)."""
        # Try to connect light software
        if hasattr(self.light_software, 'connect_midi'):
            self.light_software.connect_midi()
        
        # Start device monitor
        self.device_monitor.start()
        
        # Sync initial state from light software
        self._sync_initial_scenes()
        
        # Show scene LEDs for the initial page
        self._refresh_scene_leds_for_page()
        
        logger.info("Light controller initialized")
        return True
    
    def run_main_loop(self) -> None:
        """Main control loop."""
        self.initialize()
        
        logger.info("Light controller running. Press Ctrl+C to exit.")
        
        try:
            while True:
                # Process inputs
                self._process_launchpad_input()
                self._process_midi_feedback()
                
                # Update outputs
                self._update_leds()
                
                time.sleep(0.02)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.device_monitor.stop()
        self.sequence_ctrl.cleanup()
        self.launchpad.close()
        if hasattr(self.light_software, 'close_midi'):
            self.light_software.close_midi()
        elif hasattr(self.light_software, 'close_light_software_midi'):
            self.light_software.close_light_software_midi()
        # Final MIDI shutdown — close all tracked ports at application exit
        midi_manager.shutdown()
        logger.info("Cleanup complete")
    
    def switch_pilot(self, pilot_index: int) -> bool:
        """
        Switch to a different pilot and reload its sequences.
        
        Args:
            pilot_index: Index of the pilot to switch to
            
        Returns:
            True if successful
        """
        if self.project_repo.set_active_pilot(pilot_index):
            # Stop any active sequence playback
            self.sequence_ctrl.stop_playback()
            
            # Reload sequences from the new active pilot
            self.sequence_ctrl.load_from_repository()
            
            logger.info(f"Switched to pilot at index {pilot_index}")
            return True
        return False
    
    # ============================================================================
    # INPUT PROCESSING
    # ============================================================================
    
    def _process_launchpad_input(self) -> None:
        """Process button events from launchpad."""
        if not self.launchpad.is_connected:
            return
        
        button_data = self.launchpad.get_button_events()
        if button_data:
            # Convert to generic ButtonEvent
            event = self._convert_launchpad_event(button_data)
            if event:
                self.input_handler.handle_button_event(event)
    
    def _convert_launchpad_event(self, data: t.Dict) -> t.Optional[ButtonEvent]:
        """Convert launchpad event to generic ButtonEvent."""
        from lumiblox.devices.launchpad import ButtonType as LPButtonType
        
        lp_type = data["type"]
        coords = tuple(data["index"])
        pressed = data["active"]
        
        # Map launchpad button type to generic type
        if lp_type == LPButtonType.SCENE:
            btn_type = ButtonType.SCENE
            # Apply page offset to get absolute scene coordinates
            coords = (coords[0], coords[1] + self.active_page * ROWS_PER_PAGE)
        elif lp_type == LPButtonType.PRESET:
            btn_type = ButtonType.SEQUENCE
        elif lp_type == LPButtonType.CONTROL:
            btn_type = ButtonType.CONTROL
        else:
            btn_type = ButtonType.UNKNOWN
        
        return ButtonEvent(btn_type, coords, pressed, source="launchpad")
    
    def _process_midi_feedback(self) -> None:
        """Process MIDI feedback from light software."""
        if not hasattr(self.light_software, 'process_feedback'):
            return
        if not getattr(self.light_software, 'connection_good', False):
            return
        
        changes = self.light_software.process_feedback()
        for note, is_active in changes.items():
            scene = self.light_software.get_scene_coordinates_for_note(note)
            if scene:
                guarded = self.scene_ctrl.get_sequence_guard_scenes()
                lp_scene = self._scene_to_launchpad_scene(scene)
                # For guarded scenes, controller is source of truth; only allow offs
                if scene in guarded:
                    if is_active:
                        continue
                    self.scene_ctrl.mark_scene_active(scene, False)
                    if lp_scene is not None:
                        self.led_ctrl.update_scene_led(lp_scene, False, page=self.active_page)
                    continue

                self.scene_ctrl.mark_scene_active(scene, is_active)
                if lp_scene is not None:
                    self.led_ctrl.update_scene_led(lp_scene, is_active, page=self.active_page)
    
    def _sync_initial_scenes(self) -> None:
        """Sync initial active scenes from light software."""
        if hasattr(self.light_software, 'process_feedback'):
            changes = self.light_software.process_feedback()
            for note, is_active in changes.items():
                if is_active:
                    scene = self.light_software.get_scene_coordinates_for_note(note)
                    if scene:
                        self.scene_ctrl.mark_scene_active(scene, True)
    
    # ============================================================================
    # EVENT HANDLERS
    # ============================================================================
    
    def _handle_scene_button(self, scene: t.Tuple[int, int], pressed: bool) -> None:
        """Handle scene button press."""
        if pressed:
            is_active = self.scene_ctrl.toggle_scene(scene)
            logger.debug(f"Scene {scene} toggled: {is_active}")
    
    def _handle_sequence_button(self, index: t.Tuple[int, int], pressed: bool) -> None:
        """Handle sequence button press (based on app state)."""
        if self.app_state == AppState.SAVE_MODE:
            self._save_sequence(index)
        elif self.app_state == AppState.SAVE_SHIFT_MODE:
            self._add_step_to_sequence(index)
        elif self.app_state == AppState.PILOT_SELECT_MODE:
            if pressed:
                self._handle_pilot_selection_button(index)
        else:
            self._activate_deactivate_sequence(index)
    
    def _handle_control_button(self, name: str, pressed: bool) -> None:
        """Handle control button press."""
        if not pressed:
            return
        
        handlers = {
            "save_button": self._toggle_save_mode,
            "save_shift_button": self._toggle_save_shift_mode,
            "playback_toggle_button": self._toggle_playback,
            "next_step_button": self._next_step,
            "clear_button": self._clear_all_scenes,
            "pilot_select_button": self._toggle_pilot_select_mode,
            "pilot_toggle_button": self._toggle_pilot_enabled,
            "page_1_button": lambda: self._switch_page(0),
            "page_2_button": lambda: self._switch_page(1),
        }
        
        handler = handlers.get(name)
        if handler:
            handler()
        else:
            # Unknown control - might be a scene button
            logger.debug(f"Unhandled control: {name}")
    
    # ============================================================================
    # SCENE CALLBACKS
    # ============================================================================
    
    def _handle_scene_activate(self, scene: t.Tuple[int, int]) -> None:
        """Handle scene activation."""
        logger.debug("scene_activate scene=%s", scene)
        # Use explicit state setting for deterministic control
        self.light_software.set_scene_state(scene, True)
        lp_scene = self._scene_to_launchpad_scene(scene)
        if lp_scene is not None:
            self.led_ctrl.update_scene_led(lp_scene, True, page=self.active_page)
    
    def _handle_scene_deactivate(self, scene: t.Tuple[int, int]) -> None:
        """Handle scene deactivation."""
        logger.debug("scene_deactivate scene=%s", scene)
        # Send explicit velocity 0 so offs are deterministic even if a toggle is missed.
        self.light_software.set_scene_state(scene, False)
        lp_scene = self._scene_to_launchpad_scene(scene)
        if lp_scene is not None:
            self.led_ctrl.update_scene_led(lp_scene, False, page=self.active_page)
    
    # ============================================================================
    # SEQUENCE CALLBACKS
    # ============================================================================
    
    def _handle_step_change(self, scenes: t.List[t.Tuple[int, int]]) -> None:
        """Handle sequence step change."""
        logger.debug(
            "step_change scenes=%s active_sequence=%s", scenes, self.sequence_ctrl.active_sequence
        )
        current_sequence = self.sequence_ctrl.active_sequence
        if current_sequence is None:
            logger.debug("Ignoring step change with no active sequence")
            return
        self._last_sequence_scenes = set(scenes)
        if current_sequence != self.active_sequence:
            if self.active_sequence:
                self._set_sequence_led_state(self.active_sequence, False)
            self.active_sequence = current_sequence
            if self.active_sequence:
                self._set_sequence_led_state(self.active_sequence, True)
            if self.on_sequence_changed:
                self.on_sequence_changed(self.active_sequence)
        self.scene_ctrl.activate_scenes(scenes, controlled=True)

    
    def _handle_sequence_complete(self) -> None:
        """Handle sequence completion."""
        logger.info("Sequence completed")
    
    # ============================================================================
    # SEQUENCE ACTIONS
    # ============================================================================
    
    def _activate_deactivate_sequence(self, index: t.Tuple[int, int]) -> None:
        """Activate or deactivate a sequence."""
        if self.active_sequence == index:
            # Deactivate
            last_scenes = self._last_sequence_scenes.copy()
            self.sequence_ctrl.clear()
            self.scene_ctrl.clear_controlled()
            if last_scenes:
                self.scene_ctrl.force_deactivate_scenes(last_scenes)
            self._last_sequence_scenes.clear()
            self.active_sequence = None
            self._set_sequence_led_state(index, False)
            if self.on_sequence_changed:
                self.on_sequence_changed(None)
        else:
            # Deactivate old sequence first
            if self.active_sequence:
                self._set_sequence_led_state(self.active_sequence, False)
                last_scenes = self._last_sequence_scenes.copy()
                next_sequence = self.sequence_ctrl.get_sequence(index)
                next_first_scenes = (
                    set(next_sequence[0].scenes) if next_sequence else set()
                )
                scenes_to_force_off = last_scenes - next_first_scenes
                if scenes_to_force_off:
                    self.scene_ctrl.force_deactivate_scenes(scenes_to_force_off)
            
            # Activate new sequence
            self.active_sequence = index
            self.sequence_ctrl.activate_sequence(index)
            self._set_sequence_led_state(index, True)
            if self.on_sequence_changed:
                self.on_sequence_changed(index)
    
    def _save_sequence(self, index: t.Tuple[int, int]) -> None:
        """Save current scenes as a sequence."""
        scenes = list(self.scene_ctrl.get_active_scenes())
        step = SequenceStep(scenes=scenes, duration=1.0, name="Step 1")
        self.sequence_ctrl.save_sequence(index, [step], loop=True)
        
        logger.info(f"Saved {len(scenes)} scenes to sequence {index}")
        if self.on_sequence_saved:
            self.on_sequence_saved()
        
        self._exit_save_mode()
        self._activate_deactivate_sequence(index)
    
    def _add_step_to_sequence(self, index: t.Tuple[int, int]) -> None:
        """Add current scenes as new step to sequence."""
        scenes = list(self.scene_ctrl.get_active_scenes())
        existing = self.sequence_ctrl.get_sequence(index)
        
        if existing:
            new_step = SequenceStep(scenes=scenes, duration=1.0, name=f"Step {len(existing)+1}")
            existing.append(new_step)
            self.sequence_ctrl.save_sequence(index, existing, loop=True)
        else:
            step = SequenceStep(scenes=scenes, duration=1.0, name="Step 1")
            self.sequence_ctrl.save_sequence(index, [step], loop=True)
        
        self.led_ctrl.flash_success(index)
        if self.on_sequence_saved:
            self.on_sequence_saved()
        
        self._exit_save_mode()
        self._activate_deactivate_sequence(index)
    
    # ============================================================================
    # APP STATE MANAGEMENT
    # ============================================================================
    
    def _toggle_save_mode(self) -> None:
        """Toggle save mode."""
        if self.app_state == AppState.SAVE_MODE:
            self._exit_save_mode()
        else:
            self._enter_save_mode()
    
    def _toggle_save_shift_mode(self) -> None:
        """Toggle save shift mode."""
        if self.app_state == AppState.SAVE_SHIFT_MODE:
            self._exit_save_mode()
        else:
            self._enter_save_shift_mode()
    
    def _enter_save_mode(self) -> None:
        """Enter save mode."""
        if self.app_state == AppState.PILOT_SELECT_MODE:
            self._exit_pilot_select_mode()
        self.app_state = AppState.SAVE_MODE
        self.sequence_ctrl.stop_playback()
        
        coords = tuple(self.config.data["key_bindings"]["save_button"]["coordinates"])
        self.led_ctrl.update_control_led(coords, "save_mode_on")
        
        indices = self.sequence_ctrl.get_all_indices()
        self.led_ctrl.update_sequence_leds_for_save_mode("normal", indices)
    
    def _enter_save_shift_mode(self) -> None:
        """Enter save shift mode."""
        if self.app_state == AppState.PILOT_SELECT_MODE:
            self._exit_pilot_select_mode()
        self.app_state = AppState.SAVE_SHIFT_MODE
        self.sequence_ctrl.stop_playback()
        
        coords = tuple(self.config.data["key_bindings"]["save_shift_button"]["coordinates"])
        self.led_ctrl.update_control_led(coords, "save_mode_on")
        
        indices = self.sequence_ctrl.get_all_indices()
        self.led_ctrl.update_sequence_leds_for_save_mode("shift", indices)
    
    def _exit_save_mode(self) -> None:
        """Exit all save modes."""
        self.app_state = AppState.NORMAL
        
        for key in ["save_button", "save_shift_button"]:
            coords = tuple(self.config.data["key_bindings"][key]["coordinates"])
            self.led_ctrl.update_control_led(coords, "off")
        
        self.led_ctrl.clear_sequence_leds()
        if self.active_sequence:
            self._set_sequence_led_state(self.active_sequence, True)

    def _toggle_pilot_select_mode(self) -> None:
        """Toggle pilot selection mode."""
        if self.app_state == AppState.PILOT_SELECT_MODE:
            self._exit_pilot_select_mode()
            return

        if self.app_state in (AppState.SAVE_MODE, AppState.SAVE_SHIFT_MODE):
            self._exit_save_mode()
        self._enter_pilot_select_mode()

    def _enter_pilot_select_mode(self) -> None:
        """Enter pilot selection mode and update LEDs."""
        self._refresh_pilot_presets()
        self.app_state = AppState.PILOT_SELECT_MODE

        coords = tuple(
            self.config.data["key_bindings"]["pilot_select_button"]["coordinates"]
        )
        self.led_ctrl.update_control_led(coords, "save_mode_on")
        self._render_pilot_selection_leds()

    def _exit_pilot_select_mode(self) -> None:
        """Exit pilot selection mode and restore sequence LEDs."""
        if self.app_state != AppState.PILOT_SELECT_MODE:
            return

        self.app_state = AppState.NORMAL
        coords = tuple(
            self.config.data["key_bindings"]["pilot_select_button"]["coordinates"]
        )
        self.led_ctrl.update_control_led(coords, "off")

        self.led_ctrl.clear_sequence_leds()
        if self.active_sequence:
            self._set_sequence_led_state(self.active_sequence, True)

    def _render_pilot_selection_leds(self) -> None:
        """Render pilot selection grid on sequence buttons."""
        pilot_count = len(self.project_repo.pilots)
        active_index = self.project_repo.get_active_pilot_index()
        self.led_ctrl.display_pilot_selection(pilot_count, active_index)

    def _handle_pilot_selection_button(self, index: t.Tuple[int, int]) -> None:
        """Handle pilot selection via sequence pads."""
        self._refresh_pilot_presets()
        pilot_slot = self._sequence_index_to_linear(index)
        if pilot_slot is None:
            return

        if pilot_slot >= len(self.project_repo.pilots):
            return

        self._activate_pilot_by_index(pilot_slot)
        self._exit_pilot_select_mode()

    def _activate_pilot_by_index(self, pilot_index: int) -> None:
        """Activate pilot preset by index and notify listeners."""
        # Switch to the pilot using the repository (reloads sequences automatically)
        if self.switch_pilot(pilot_index):
            # Reload pilot controller if active
            if self.pilot_controller:
                self.pilot_controller.preset_manager.load()

            # Notify listeners
            if self.on_pilot_selection_changed:
                try:
                    self.on_pilot_selection_changed(pilot_index)
                except Exception as exc:
                    logger.debug(f"Pilot selection callback failed: {exc}")

    def _get_active_pilot_index(self) -> t.Optional[int]:
        """Return the currently enabled pilot preset index."""
        return self.project_repo.get_active_pilot_index()

    def _sequence_index_to_linear(self, index: t.Tuple[int, int]) -> t.Optional[int]:
        """Convert (x, y) sequence coordinates to linear slot index."""
        x, y = index
        if not (0 <= x <= 7 and 0 <= y <= 2):
            return None
        return y * 8 + x

    def _refresh_pilot_presets(self) -> None:
        """Reload pilot presets from disk if possible."""
        success = self.project_repo.load()
        if not success:
            logger.warning("Unable to reload pilot presets; using last known state")

    def _set_sequence_led_state(self, index: t.Tuple[int, int], active: bool) -> None:
        """Update a sequence LED unless overridden by pilot mode."""
        if self.app_state == AppState.PILOT_SELECT_MODE:
            return
        self.led_ctrl.update_sequence_led(index, active)
    
    # ============================================================================
    # PAGE MANAGEMENT
    # ============================================================================
    
    def _scene_to_launchpad_scene(self, scene: t.Tuple[int, int]) -> t.Optional[t.Tuple[int, int]]:
        """Convert absolute scene coords to Launchpad scene coords.
        
        Returns None if the scene is not on the currently active page.
        """
        x, y = scene
        page_start = self.active_page * ROWS_PER_PAGE
        page_end = page_start + ROWS_PER_PAGE
        if page_start <= y < page_end:
            return (x, y - page_start)
        return None
    
    def _switch_page(self, page: int) -> None:
        """Switch to a different scene page on the Launchpad."""
        if page == self.active_page or page < 0 or page >= NUM_SCENE_PAGES:
            return
        
        logger.info("Switching scene page %d -> %d", self.active_page + 1, page + 1)
        self.active_page = page
        self._refresh_scene_leds_for_page()
    
    def _refresh_scene_leds_for_page(self) -> None:
        """Refresh all scene LEDs on the Launchpad for the current page."""
        active_scenes = self.scene_ctrl.get_active_scenes()
        other_page = 1 - self.active_page
        self._dual_active_positions = set()
        self._other_page_only_positions = set()
        for lp_y in range(ROWS_PER_PAGE):
            for lp_x in range(SCENE_COLUMNS):
                page0_scene = (lp_x, lp_y)
                page1_scene = (lp_x, lp_y + ROWS_PER_PAGE)
                p0_active = page0_scene in active_scenes
                p1_active = page1_scene in active_scenes
                current_active = (lp_x, lp_y + self.active_page * ROWS_PER_PAGE) in active_scenes
                other_active = (lp_x, lp_y + other_page * ROWS_PER_PAGE) in active_scenes
                if p0_active and p1_active:
                    # Both pages active — register for blink
                    self._dual_active_positions.add((lp_x, lp_y))
                    self.led_ctrl.update_scene_led((lp_x, lp_y), True, page=self.active_page)
                elif other_active and not current_active:
                    # Only the other page is active — show dim hint
                    self._other_page_only_positions.add((lp_x, lp_y))
                    self.led_ctrl.update_scene_led_other_page((lp_x, lp_y), other_page)
                else:
                    self.led_ctrl.update_scene_led((lp_x, lp_y), current_active, page=self.active_page)
    
    def _update_blinking_scene_leds(self) -> None:
        """Alternate colors for Launchpad positions active on both pages.
        
        Also maintains dim hints for positions only active on the other page.
        """
        active_scenes = self.scene_ctrl.get_active_scenes()
        other_page = 1 - self.active_page
        new_dual_active: t.Set[t.Tuple[int, int]] = set()
        new_other_only: t.Set[t.Tuple[int, int]] = set()

        for lp_y in range(ROWS_PER_PAGE):
            for lp_x in range(SCENE_COLUMNS):
                page0_scene = (lp_x, lp_y)
                page1_scene = (lp_x, lp_y + ROWS_PER_PAGE)
                p0_active = page0_scene in active_scenes
                p1_active = page1_scene in active_scenes
                current_active = (lp_x, lp_y + self.active_page * ROWS_PER_PAGE) in active_scenes
                other_active = (lp_x, lp_y + other_page * ROWS_PER_PAGE) in active_scenes

                if p0_active and p1_active:
                    new_dual_active.add((lp_x, lp_y))
                    show_page = 0 if self._blink_phase else 1
                    self.led_ctrl.update_scene_led((lp_x, lp_y), True, page=show_page)
                elif other_active and not current_active:
                    new_other_only.add((lp_x, lp_y))
                    # Only push dim color when position was not already tracked
                    if (lp_x, lp_y) not in self._other_page_only_positions:
                        self.led_ctrl.update_scene_led_other_page((lp_x, lp_y), other_page)

        # Positions that stopped being dual-active or other-only: restore
        changed = (self._dual_active_positions | self._other_page_only_positions) - (new_dual_active | new_other_only)
        for lp_x, lp_y in changed:
            current_scene = (lp_x, lp_y + self.active_page * ROWS_PER_PAGE)
            is_active = current_scene in active_scenes
            self.led_ctrl.update_scene_led(
                (lp_x, lp_y), is_active, page=self.active_page
            )

        self._dual_active_positions = new_dual_active
        self._other_page_only_positions = new_other_only

    # ============================================================================
    # OTHER CONTROLS
    # ============================================================================
    
    def _toggle_playback(self) -> None:
        """Toggle sequence playback."""
        if not self.active_sequence:
            return
        
        if self.sequence_ctrl.playback_state == PlaybackState.PLAYING:
            self.sequence_ctrl.pause()
        else:
            self.sequence_ctrl.play()
    
    def _next_step(self) -> None:
        """Advance to next step."""
        self.sequence_ctrl.next_step()
    
    def _clear_all_scenes(self) -> None:
        """Clear all active scenes."""
        if self.active_sequence:
            self.sequence_ctrl.stop_playback()
            self._set_sequence_led_state(self.active_sequence, False)
            self.active_sequence = None
        self._last_sequence_scenes.clear()
        
        self.scene_ctrl.clear_all()

    def _toggle_pilot_enabled(self) -> None:
        """Toggle pilot controller on/off and persist configuration."""
        pilot_running = False
        if self.pilot_controller:
            try:
                pilot_running = self.pilot_controller.is_running()
            except Exception as exc:
                logger.debug("Could not read pilot state: %s", exc)
        else:
            pilot_running = bool(self.config.data.get("pilot", {}).get("enabled", False))

        target_enabled = not pilot_running

        if target_enabled:
            if not self.pilot_controller:
                logger.warning("Pilot controller not attached; cannot enable pilot mode")
                return
            try:
                started = self.pilot_controller.start(enable_phrase_detection=False)
            except Exception as exc:
                logger.warning("Failed to start pilot controller: %s", exc)
                return
            if not started:
                logger.warning("Pilot controller did not start")
                return
            self.config.set_pilot_enabled(True)
        else:
            if self.pilot_controller and pilot_running:
                try:
                    self.pilot_controller.stop()
                except Exception as exc:
                    logger.warning("Failed to stop pilot controller: %s", exc)
                    return
            self.config.set_pilot_enabled(False)
    
    def _update_leds(self) -> None:
        """Update all LED displays."""
        if self.launchpad.is_connected:
            bg_type = self.background_mgr.get_current_background()
            self.led_ctrl.update_background(bg_type, self.app_state)

            # Blink dual-active scene LEDs (active on both pages)
            now = time.time()
            if now - self._last_blink_toggle >= self._BLINK_INTERVAL:
                self._blink_phase = not self._blink_phase
                self._last_blink_toggle = now
                self._update_blinking_scene_leds()

            # Playback toggle LED reflects play/pause state
            playback_coords = tuple(
                self.config.data["key_bindings"]["playback_toggle_button"][
                    "coordinates"
                ]
            )
            playback_color = (
                "playback_playing"
                if self.sequence_ctrl.playback_state == PlaybackState.PLAYING
                else "playback_paused"
            )
            self.led_ctrl.update_control_led(playback_coords, playback_color)

            # Next-step LED is shown when paused on a multi-step sequence
            next_step_coords = tuple(
                self.config.data["key_bindings"]["next_step_button"][
                    "coordinates"
                ]
            )
            active_index = self.sequence_ctrl.active_sequence
            active_sequence = (
                self.sequence_ctrl.get_sequence(active_index)
                if active_index
                else None
            )
            can_advance = (
                self.sequence_ctrl.playback_state == PlaybackState.PAUSED
                and active_sequence is not None
                and len(active_sequence) > 1
            )
            next_color = "next_step" if can_advance else "off"
            self.led_ctrl.update_control_led(next_step_coords, next_color)

            # Pilot toggle LED reflects pilot running state
            pilot_coords = tuple(
                self.config.data["key_bindings"]["pilot_toggle_button"][
                    "coordinates"
                ]
            )
            pilot_running = False
            if self.pilot_controller:
                try:
                    pilot_running = self.pilot_controller.is_running()
                except Exception as exc:
                    logger.debug("Could not read pilot state: %s", exc)
            else:
                pilot_running = bool(self.config.data.get("pilot", {}).get("enabled", False))

            pilot_color = "pilot_toggle_on" if pilot_running else "pilot_toggle_off"
            self.led_ctrl.update_control_led(pilot_coords, pilot_color)
            
            # Update clear button
            coords = tuple(self.config.data["key_bindings"]["clear_button"]["coordinates"])
            color_key = "success_flash" if self.scene_ctrl.has_active_scenes() else "off"
            self.led_ctrl.update_control_led(coords, color_key)

            # Update page button LEDs
            page_buttons = ["page_1_button", "page_2_button"]
            bindings = self.config.data.get("key_bindings", {})
            for page_idx, page_key in enumerate(page_buttons):
                if page_key in bindings:
                    page_coords = tuple(bindings[page_key]["coordinates"])
                    page_color = "page_active" if page_idx == self.active_page else "off"
                    self.led_ctrl.update_control_led(page_coords, page_color)
    
    def _on_device_state_changed(self, device_type, new_state) -> None:
        """Handle device state changes."""
        logger.debug(f"Device {device_type.value} -> {new_state.value}")
    
    # ============================================================================
    # EXTERNAL INTERFACE (for GUI)
    # ============================================================================
    
    def process_button_event_from_external(self, event: t.Dict) -> None:
        """Process button event from external source (GUI)."""
        # Convert dict to ButtonEvent if needed
        if isinstance(event, dict):
            evt = ButtonEvent(
                button_type=ButtonType(event.get("type", "unknown")),
                coordinates=tuple(event.get("index", (0, 0))),
                pressed=event.get("active", False),
                source="external"
            )
            self.input_handler.handle_button_event(evt)
    
    def process_midi_feedback_from_external(self) -> None:
        """Process MIDI feedback (for GUI compatibility)."""
        self._process_midi_feedback()

    def set_pilot_controller(self, pilot_controller: "PilotController") -> None:
        """Attach a pilot controller for preset synchronization."""
        self.pilot_controller = pilot_controller


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main(simulation: bool = False):
    """Main entry point."""
    controller = LightController(simulation=simulation)
    controller.run_main_loop()


if __name__ == "__main__":
    main()
