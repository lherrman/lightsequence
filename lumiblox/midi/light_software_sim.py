"""
LightSoftware Simulator for Testing  (mido + python-rtmidi)

Simulates LightSoftware behavior without needing the actual software running.
Maintains a 9x5 grid of scene states and provides MIDI feedback.
"""

import logging
import typing as t

import mido

from lumiblox.common.constants import ROWS_PER_PAGE
from lumiblox.midi.midi_manager import midi_manager

if t.TYPE_CHECKING:
    from lumiblox.common.config import ConfigManager

logger = logging.getLogger(__name__)


class LightSoftwareSim:
    """
    Simulates LightSoftware for testing without the actual software.
    Provides MIDI feedback and maintains scene state.
    """

    def __init__(self, config: t.Optional["ConfigManager"] = None):
        # Scene mapping: relative coordinates (x, y) to MIDI notes
        self._scene_to_note_map = self._build_scene_note_mapping()

        # Reverse mapping for feedback processing
        self._note_to_scene_map = {v: k for k, v in self._scene_to_note_map.items()}

        # Scene state storage: 9 columns x 10 rows (2 pages)
        self.scene_states: t.Dict[t.Tuple[int, int], bool] = {}
        for x in range(9):
            for y in range(10):
                self.scene_states[(x, y)] = False

        # MIDI connection variables (mido port objects)
        self.midi_out = None  # type: t.Any
        self.midi_in = None   # type: t.Any

        # Connection state flag
        self.connection_good = False

        # Feedback queue - messages to send back to controller
        self.feedback_queue: t.List[t.Tuple[int, int, int]] = []

        # MIDI output values
        if config:
            midi_output_config = config.data.get("midi_output", {})
            self.on_value = midi_output_config.get("on_value", 127)
            self.off_value = midi_output_config.get("off_value", 0)
        else:
            self.on_value = 127
            self.off_value = 0

    def _build_scene_note_mapping(self) -> t.Dict[t.Tuple[int, int], int]:
        """
        Build mapping from page-local scene coordinates to MIDI notes.

        Only covers one page (ROWS_PER_PAGE rows).  Different pages
        reuse the same notes but are distinguished by MIDI channel
        (channel = page index).
        """
        scene_map = {}
        base_notes = [81, 71, 61, 51, 41]

        for x in range(9):  # 9 columns
            for local_y in range(len(base_notes)):
                note = base_notes[local_y] + x
                if 0 <= note <= 127:
                    scene_map[(x, local_y)] = note

        return scene_map

    def _scene_to_note_and_channel(self, scene_index: t.Tuple[int, int]) -> t.Optional[t.Tuple[int, int]]:
        """Return (note, channel) for an absolute scene coordinate, or None."""
        x, y = scene_index
        page = y // ROWS_PER_PAGE
        local_y = y % ROWS_PER_PAGE
        note = self._scene_to_note_map.get((x, local_y))
        if note is None:
            return None
        return note, page

    def _close_ports(self) -> None:
        """Close existing MIDI port objects."""
        midi_manager.close_port(self.midi_out)
        midi_manager.close_port(self.midi_in)
        self.midi_out = None
        self.midi_in = None

    def connect_midi(self) -> bool:
        """
        Connect to loopMIDI ports for simulation.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Close any stale port handles before opening new ones
            self._close_ports()

            # Open output (to send feedback via loopMIDI "lightsoftware_out")
            self.midi_out = midi_manager.open_output_by_keyword("lightsoftware_out")
            if self.midi_out:
                logger.info("✅ [SIM] LightSoftware OUT: %s", self.midi_out.name)
            else:
                logger.error("❌ [SIM] No LightSoftware_out MIDI output found")

            # Open input (to receive commands via loopMIDI "lightsoftware_in")
            self.midi_in = midi_manager.open_input_by_keyword("lightsoftware_in")
            if self.midi_in:
                logger.info("✅ [SIM] LightSoftware IN: %s", self.midi_in.name)
            else:
                logger.error("❌ [SIM] No LightSoftware_in MIDI input found")

            # Update connection state
            if self.midi_out and self.midi_in:
                self.connection_good = True
                logger.info("✅ [SIM] Successfully connected to MIDI (simulation mode)")
                return True
            else:
                self.connection_good = False
                logger.error("❌ [SIM] Failed to connect to MIDI - missing MIDI ports")
                return False

        except Exception as e:
            logger.error("[SIM] MIDI connection failed: %s", e)
            self.connection_good = False
            return False

    def set_scene_state(self, scene_index: t.Tuple[int, int], active: bool) -> None:
        """Set an explicit scene state (used to mirror deterministic controller diffs)."""
        result = self._scene_to_note_and_channel(scene_index)
        if result is None:
            logger.warning(
                "[SIM] No MIDI note mapped for scene coordinates %s", scene_index
            )
            return

        scene_note, channel = result
        self.scene_states[scene_index] = active
        velocity = self.on_value if active else self.off_value
        self.feedback_queue.append((scene_note, velocity, channel))
        logger.debug(
            "[SIM] Scene %s set to %s (note %s, ch %s, velocity %s)",
            scene_index,
            "ON" if active else "OFF",
            scene_note,
            channel,
            velocity,
        )

    def get_scene_coordinates_for_note(
        self, note: int, channel: int = 0
    ) -> t.Optional[t.Tuple[int, int]]:
        """
        Get absolute scene coordinates for a MIDI note and channel.

        Args:
            note: MIDI note number
            channel: MIDI channel (used as page index)

        Returns:
            Tuple of (x, y) absolute coordinates or None if not found
        """
        local = self._note_to_scene_map.get(note)
        if local is None:
            return None
        x, local_y = local
        return (x, local_y + channel * ROWS_PER_PAGE)

    def process_feedback(self) -> t.Dict[t.Tuple[int, int], bool]:
        """
        Send queued MIDI feedback and process incoming commands.
        This is called by the controller to get feedback.

        Uses the MIDI channel to determine which page a note belongs to,
        then returns absolute scene coordinates as keys.

        Validates port liveness before every I/O operation.

        Returns:
            Dictionary of scene_coords -> state changes (True=on, False=off)
        """
        changes: t.Dict[t.Tuple[int, int], bool] = {}

        if not self.connection_good:
            return changes

        # First, send any queued feedback
        if self.feedback_queue and midi_manager.is_port_alive(self.midi_out):
            try:
                for note, velocity, channel in self.feedback_queue:
                    msg = mido.Message(
                        "note_on", note=note, velocity=velocity, channel=channel
                    )
                    ok = midi_manager.safe_send(self.midi_out, msg)
                    if ok:
                        logger.debug(
                            "[SIM] Sent feedback: note %s, ch %s, velocity %s", note, channel, velocity
                        )
                        scene = self.get_scene_coordinates_for_note(note, channel)
                        if scene is not None:
                            changes[scene] = velocity > 0
                    else:
                        logger.warning("[SIM] Feedback send failed – marking disconnected")
                        self.connection_good = False
                        return changes

                self.feedback_queue.clear()
            except Exception as e:
                logger.error("[SIM] MIDI feedback send error: %s", e)
                self.connection_good = False
                return changes

        # Process incoming commands from controller
        if midi_manager.is_port_alive(self.midi_in):
            try:
                for msg in self.midi_in.iter_pending():
                    if msg.type == "note_on":
                        note = msg.note
                        velocity = msg.velocity
                        channel = msg.channel
                        logger.debug(
                            "[SIM] Received command: note %s, ch %s, velocity %s",
                            note,
                            channel,
                            velocity,
                        )

                        # Handle scene command - toggle based on velocity
                        scene_coords = self.get_scene_coordinates_for_note(note, channel)
                        if scene_coords:
                            if velocity > 0:
                                current_state = self.scene_states.get(
                                    scene_coords, False
                                )
                                self.set_scene_state(scene_coords, not current_state)
                            else:
                                self.set_scene_state(scene_coords, False)
            except Exception as e:
                logger.error("[SIM] MIDI command processing error: %s", e)
                self.connection_good = False

        return changes

    def close(self) -> None:
        """
        Clean shutdown of MIDI connections.

        Only closes this component's ports.  The shared MIDI subsystem
        is shut down via ``midi_manager.shutdown()`` at application exit.
        Idempotent – safe to call multiple times.
        """
        try:
            self._close_ports()
            logger.info("✅ [SIM] MIDI ports closed")
        except Exception as e:
            logger.error("[SIM] Error closing MIDI: %s", e)
        finally:
            self.connection_good = False

    def get_scene_state(self, scene_index: t.Tuple[int, int]) -> bool:
        """
        Get the current state of a scene.

        Args:
            scene_index: Tuple of (x, y) coordinates

        Returns:
            True if scene is active, False otherwise
        """
        return self.scene_states.get(scene_index, False)

    def get_all_active_scenes(self) -> t.List[t.Tuple[int, int]]:
        """
        Get list of all currently active scenes.

        Returns:
            List of (x, y) coordinates for active scenes
        """
        return [coords for coords, state in self.scene_states.items() if state]
