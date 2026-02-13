"""App State Manager — handles save modes and pilot selection."""

import logging
import typing as t

from lumiblox.common.enums import AppState
from lumiblox.common.config import get_config
from lumiblox.controller.led_controller import LEDController
from lumiblox.controller.sequence_controller import SequenceController
from lumiblox.common.project_data_repository import ProjectDataRepository

if t.TYPE_CHECKING:
    from lumiblox.pilot.pilot_controller import PilotController

logger = logging.getLogger(__name__)


class AppStateManager:
    """Manages application modes: normal, save, save-shift, pilot-select."""

    def __init__(
        self,
        led_ctrl: LEDController,
        sequence_ctrl: SequenceController,
        project_repo: ProjectDataRepository,
        switch_pilot_fn: t.Callable[[int], bool],
        set_sequence_led_fn: t.Callable[[t.Tuple[int, int], bool], None],
    ):
        self.led_ctrl = led_ctrl
        self.sequence_ctrl = sequence_ctrl
        self.project_repo = project_repo
        self.config = get_config()
        self._switch_pilot = switch_pilot_fn
        self._set_sequence_led = set_sequence_led_fn

        self.state = AppState.NORMAL
        self.pilot_controller: t.Optional["PilotController"] = None

        # External callbacks
        self.on_pilot_selection_changed: t.Optional[t.Callable[[int], None]] = None

    # ------------------------------------------------------------------
    # Save modes
    # ------------------------------------------------------------------

    def toggle_save_mode(self) -> None:
        """Toggle save mode."""
        if self.state == AppState.SAVE_MODE:
            self.exit_save_mode()
        else:
            self.enter_save_mode()

    def toggle_save_shift_mode(self) -> None:
        """Toggle save shift mode."""
        if self.state == AppState.SAVE_SHIFT_MODE:
            self.exit_save_mode()
        else:
            self.enter_save_shift_mode()

    def enter_save_mode(self) -> None:
        """Enter save mode."""
        if self.state == AppState.PILOT_SELECT_MODE:
            self.exit_pilot_select_mode()
        self.state = AppState.SAVE_MODE
        self.sequence_ctrl.stop_playback()

        coords = tuple(self.config.data["key_bindings"]["save_button"]["coordinates"])
        self.led_ctrl.update_control_led(coords, "save_mode_on")

        indices = self.sequence_ctrl.get_all_indices()
        self.led_ctrl.update_sequence_leds_for_save_mode("normal", indices)

    def enter_save_shift_mode(self) -> None:
        """Enter save shift mode."""
        if self.state == AppState.PILOT_SELECT_MODE:
            self.exit_pilot_select_mode()
        self.state = AppState.SAVE_SHIFT_MODE
        self.sequence_ctrl.stop_playback()

        coords = tuple(self.config.data["key_bindings"]["save_shift_button"]["coordinates"])
        self.led_ctrl.update_control_led(coords, "save_mode_on")

        indices = self.sequence_ctrl.get_all_indices()
        self.led_ctrl.update_sequence_leds_for_save_mode("shift", indices)

    def exit_save_mode(self) -> None:
        """Exit all save modes."""
        self.state = AppState.NORMAL

        for key in ["save_button", "save_shift_button"]:
            coords = tuple(self.config.data["key_bindings"][key]["coordinates"])
            self.led_ctrl.update_control_led(coords, "off")

        self.led_ctrl.clear_sequence_leds()
        if self.sequence_ctrl.active_sequence:
            self._set_sequence_led(self.sequence_ctrl.active_sequence, True)

    # ------------------------------------------------------------------
    # Pilot select mode
    # ------------------------------------------------------------------

    def toggle_pilot_select_mode(self) -> None:
        """Toggle pilot selection mode."""
        if self.state == AppState.PILOT_SELECT_MODE:
            self.exit_pilot_select_mode()
            return

        if self.state in (AppState.SAVE_MODE, AppState.SAVE_SHIFT_MODE):
            self.exit_save_mode()
        self.enter_pilot_select_mode()

    def enter_pilot_select_mode(self) -> None:
        """Enter pilot selection mode and update LEDs."""
        self.refresh_pilot_presets()
        self.state = AppState.PILOT_SELECT_MODE

        coords = tuple(
            self.config.data["key_bindings"]["pilot_select_button"]["coordinates"]
        )
        self.led_ctrl.update_control_led(coords, "save_mode_on")
        self.render_pilot_selection_leds()

    def exit_pilot_select_mode(self) -> None:
        """Exit pilot selection mode and restore sequence LEDs."""
        if self.state != AppState.PILOT_SELECT_MODE:
            return

        self.state = AppState.NORMAL
        coords = tuple(
            self.config.data["key_bindings"]["pilot_select_button"]["coordinates"]
        )
        self.led_ctrl.update_control_led(coords, "off")

        self.led_ctrl.clear_sequence_leds()
        if self.sequence_ctrl.active_sequence:
            self._set_sequence_led(self.sequence_ctrl.active_sequence, True)

    def render_pilot_selection_leds(self) -> None:
        """Render pilot selection grid on sequence buttons."""
        pilot_count = len(self.project_repo.pilots)
        active_index = self.project_repo.get_active_pilot_index()
        self.led_ctrl.display_pilot_selection(pilot_count, active_index)

    def handle_pilot_selection_button(self, index: t.Tuple[int, int]) -> None:
        """Handle pilot selection via sequence pads."""
        self.refresh_pilot_presets()
        pilot_slot = self.sequence_index_to_linear(index)
        if pilot_slot is None:
            return

        if pilot_slot >= len(self.project_repo.pilots):
            return

        self.activate_pilot_by_index(pilot_slot)
        self.exit_pilot_select_mode()

    def activate_pilot_by_index(self, pilot_index: int) -> None:
        """Activate pilot preset by index and notify listeners."""
        if self._switch_pilot(pilot_index):
            if self.pilot_controller:
                self.project_repo.load()

            if self.on_pilot_selection_changed:
                try:
                    self.on_pilot_selection_changed(pilot_index)
                except Exception as exc:
                    logger.debug(f"Pilot selection callback failed: {exc}")

    def get_active_pilot_index(self) -> t.Optional[int]:
        """Return the currently enabled pilot preset index."""
        return self.project_repo.get_active_pilot_index()

    def sequence_index_to_linear(self, index: t.Tuple[int, int]) -> t.Optional[int]:
        """Convert (x, y) sequence coordinates to linear slot index."""
        x, y = index
        if not (0 <= x <= 7 and 0 <= y <= 2):
            return None
        return y * 8 + x

    def refresh_pilot_presets(self) -> None:
        """Reload pilot presets from disk if possible."""
        success = self.project_repo.load()
        if not success:
            logger.warning("Unable to reload pilot presets; using last known state")
