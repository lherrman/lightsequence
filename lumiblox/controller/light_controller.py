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
from pathlib import Path

from lumiblox.controller.sequence_controller import SequenceController, SequenceStep
from lumiblox.controller.scene_controller import SceneController
from lumiblox.controller.input_handler import InputHandler, ButtonEvent, ButtonType
from lumiblox.controller.led_controller import LEDController
from lumiblox.controller.device_monitor import DeviceMonitor
from lumiblox.controller.background_animator import BackgroundManager
from lumiblox.devices.launchpad import LaunchpadMK2
from lumiblox.midi.light_software import LightSoftware
from lumiblox.midi.light_software_sim import LightSoftwareSim
from lumiblox.common.device_state import DeviceManager, DeviceType
from lumiblox.common.config import get_config
from lumiblox.common.enums import AppState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LightController:
    """
    Main orchestrator - coordinates all subsystems.
    
    Much slimmer than before - delegates to specialized controllers.
    """
    
    def __init__(self, simulation: bool = False):
        """Initialize the light controller."""
        # Device management
        self.device_manager = DeviceManager()
        self.device_monitor = DeviceMonitor(self.device_manager)
        
        # Core controllers
        self.sequence_ctrl = SequenceController(Path("sequences.json"))
        self.scene_ctrl = SceneController()
        self.input_handler = InputHandler()
        
        # Hardware
        if simulation:
            logger.info("🔧 Using simulated lighting software")
            self.light_software = LightSoftwareSim()
        else:
            self.light_software = LightSoftware(device_manager=self.device_manager)
        
        self.launchpad = LaunchpadMK2(None, device_manager=self.device_manager)
        self.led_ctrl = LEDController(self.launchpad)
        self.background_mgr = BackgroundManager(None)  # Will update presets access
        
        # App state
        self.app_state = AppState.NORMAL
        self.active_sequence: t.Optional[t.Tuple[int, int]] = None
        self.config = get_config()
        
        # External callbacks (for GUI)
        self.on_sequence_changed: t.Optional[t.Callable[[t.Optional[t.Tuple[int, int]]], None]] = None
        self.on_sequence_saved: t.Optional[t.Callable[[], None]] = None
        
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
        for name, binding in bindings.items():
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
        
        logger.info("✅ Light controller initialized")
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
        logger.info("Cleanup complete")
    
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
        elif lp_type == LPButtonType.PRESET:
            btn_type = ButtonType.SEQUENCE
        elif lp_type in [LPButtonType.TOP, LPButtonType.RIGHT]:
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
                self.scene_ctrl.mark_scene_active(scene, is_active)
                self.led_ctrl.update_scene_led(scene, is_active)
    
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
            self.light_software.send_scene_command(scene)
            logger.debug(f"Scene {scene} toggled: {is_active}")
    
    def _handle_sequence_button(self, index: t.Tuple[int, int], pressed: bool) -> None:
        """Handle sequence button press (based on app state)."""
        if self.app_state == AppState.SAVE_MODE:
            self._save_sequence(index)
        elif self.app_state == AppState.SAVE_SHIFT_MODE:
            self._add_step_to_sequence(index)
        else:
            self._activate_deactivate_sequence(index)
    
    def _handle_control_button(self, name: str, pressed: bool) -> None:
        """Handle control button press."""
        if not pressed:
            return
        
        handlers = {
            "save_button": self._toggle_save_mode,
            "save_shift_button": self._toggle_save_shift_mode,
            "background_button": self._cycle_background,
            "background_brightness_up": self._increase_bg_brightness,
            "background_brightness_down": self._decrease_bg_brightness,
            "playback_toggle_button": self._toggle_playback,
            "next_step_button": self._next_step,
            "clear_button": self._clear_all_scenes,
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
        self.light_software.send_scene_command(scene)
        self.led_ctrl.update_scene_led(scene, True)
    
    def _handle_scene_deactivate(self, scene: t.Tuple[int, int]) -> None:
        """Handle scene deactivation."""
        self.light_software.send_scene_command(scene)
        self.led_ctrl.update_scene_led(scene, False)
    
    # ============================================================================
    # SEQUENCE CALLBACKS
    # ============================================================================
    
    def _handle_step_change(self, scenes: t.List[t.Tuple[int, int]]) -> None:
        """Handle sequence step change."""
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
            self.sequence_ctrl.clear()
            self.scene_ctrl.clear_controlled()
            self.active_sequence = None
            self.led_ctrl.update_sequence_led(index, False)
            if self.on_sequence_changed:
                self.on_sequence_changed(None)
        else:
            # Deactivate old sequence first
            if self.active_sequence:
                self.led_ctrl.update_sequence_led(self.active_sequence, False)
            
            # Activate new sequence
            self.active_sequence = index
            self.sequence_ctrl.activate_sequence(index)
            self.led_ctrl.update_sequence_led(index, True)
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
        self.app_state = AppState.SAVE_MODE
        self.sequence_ctrl.stop_playback()
        
        coords = tuple(self.config.data["key_bindings"]["save_button"]["coordinates"])
        self.led_ctrl.update_control_led(coords, "save_mode_on")
        
        indices = self.sequence_ctrl.get_all_indices()
        self.led_ctrl.update_sequence_leds_for_save_mode("normal", indices)
    
    def _enter_save_shift_mode(self) -> None:
        """Enter save shift mode."""
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
            self.led_ctrl.update_sequence_led(self.active_sequence, True)
    
    # ============================================================================
    # OTHER CONTROLS
    # ============================================================================
    
    def _toggle_playback(self) -> None:
        """Toggle sequence playback."""
        if not self.active_sequence:
            return
        
        if self.sequence_ctrl.playback_state.value == "playing":
            self.sequence_ctrl.pause_playback()
        elif self.sequence_ctrl.playback_state.value == "paused":
            self.sequence_ctrl.resume_playback()
    
    def _next_step(self) -> None:
        """Advance to next step."""
        self.sequence_ctrl.next_step()
    
    def _clear_all_scenes(self) -> None:
        """Clear all active scenes."""
        if self.active_sequence:
            self.sequence_ctrl.stop_playback()
            self.led_ctrl.update_sequence_led(self.active_sequence, False)
            self.active_sequence = None
        
        self.scene_ctrl.clear_all()
    
    def _cycle_background(self) -> None:
        """Cycle background animation."""
        self.background_mgr.cycle_background()
    
    def _increase_bg_brightness(self) -> None:
        """Increase background brightness."""
        current = self.config.data["brightness_background"]
        new_value = min(1.0, current + 0.03)
        self.config.data["brightness_background"] = new_value
        self.config._save_config(self.config.data)
    
    def _decrease_bg_brightness(self) -> None:
        """Decrease background brightness."""
        current = self.config.data["brightness_background"]
        new_value = max(0.0, current - 0.03)
        self.config.data["brightness_background"] = new_value
        self.config._save_config(self.config.data)
    
    def _update_leds(self) -> None:
        """Update all LED displays."""
        if self.launchpad.is_connected:
            bg_type = self.background_mgr.get_current_background()
            self.led_ctrl.update_background(bg_type, self.app_state)
            
            # Update clear button
            coords = tuple(self.config.data["key_bindings"]["clear_button"]["coordinates"])
            color_key = "success_flash" if self.scene_ctrl.has_active_scenes() else "off"
            self.led_ctrl.update_control_led(coords, color_key)
    
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


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main(simulation: bool = False):
    """Main entry point."""
    controller = LightController(simulation=simulation)
    controller.run_main_loop()


if __name__ == "__main__":
    main()
