"""
LightSoftware Simulator for Testing  (mido + python-rtmidi)

Simulates LightSoftware behavior without needing the actual software running.
Maintains a 9x5 grid of scene states and provides MIDI feedback.
"""

import logging
import typing as t

import mido

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
        self.feedback_queue: t.List[t.Tuple[int, int]] = []

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
        Build mapping from scene button coordinates to MIDI notes.
        Page 1 (y=0-4): Original Launchpad MK2 note layout.
        Page 2 (y=5-9): Extended mapping using remaining MIDI note ranges.
        """
        scene_map = {}
        base_notes = [81, 71, 61, 51, 41, 31, 21, 11, 1, 91]

        for x in range(9):  # 9 columns
            for y in range(len(base_notes)):
                note = base_notes[y] + x
                if 0 <= note <= 127:
                    scene_map[(x, y)] = note

        return scene_map

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
        scene_note = self._scene_to_note_map.get(scene_index)
        if scene_note is None:
            logger.warning(
                "[SIM] No MIDI note mapped for scene coordinates %s", scene_index
            )
            return

        self.scene_states[scene_index] = active
        velocity = self.on_value if active else self.off_value
        self.feedback_queue.append((scene_note, velocity))
        logger.debug(
            "[SIM] Scene %s set to %s (note %s, velocity %s)",
            scene_index,
            "ON" if active else "OFF",
            scene_note,
            velocity,
        )

    def get_scene_coordinates_for_note(
        self, note: int
    ) -> t.Optional[t.Tuple[int, int]]:
        """
        Get scene coordinates for a given MIDI note.

        Args:
            note: MIDI note number

        Returns:
            Tuple of (x, y) coordinates or None if not found
        """
        return self._note_to_scene_map.get(note)

    def process_feedback(self) -> t.Dict[int, bool]:
        """
        Send queued MIDI feedback and process incoming commands.
        This is called by the controller to get feedback.

        Validates port liveness before every I/O operation.

        Returns:
            Dictionary of note -> state changes (True=on, False=off)
        """
        changes: t.Dict[int, bool] = {}

        if not self.connection_good:
            return changes

        # First, send any queued feedback
        if self.feedback_queue and midi_manager.is_port_alive(self.midi_out):
            try:
                for note, velocity in self.feedback_queue:
                    msg = mido.Message(
                        "note_on", note=note, velocity=velocity, channel=0
                    )
                    ok = midi_manager.safe_send(self.midi_out, msg)
                    if ok:
                        logger.debug(
                            "[SIM] Sent feedback: note %s, velocity %s", note, velocity
                        )
                        changes[note] = velocity > 0
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
                        logger.debug(
                            "[SIM] Received command: note %s, velocity %s",
                            note,
                            velocity,
                        )

                        # Handle scene command - toggle based on velocity
                        scene_coords = self.get_scene_coordinates_for_note(note)
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
