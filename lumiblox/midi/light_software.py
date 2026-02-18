"""
LightSoftware MIDI Communication Utilities  (mido + python-rtmidi)

Clean utility functions for communicating with LightSoftware via loopMIDI.
Only tested with DasLight 4.
"""

import logging
import typing as t

import mido

from lumiblox.common.device_state import DeviceManager, DeviceType
from lumiblox.midi.midi_manager import midi_manager

if t.TYPE_CHECKING:
    from lumiblox.common.config import ConfigManager

logger = logging.getLogger(__name__)


class LightSoftware:
    def __init__(
        self,
        device_manager: t.Optional[DeviceManager] = None,
        config: t.Optional["ConfigManager"] = None,
    ):
        # Scene mapping: relative coordinates (x, y) to MIDI notes
        self._scene_to_note_map = self._build_scene_note_mapping()

        # Reverse mapping for feedback processing
        self._note_to_scene_map = {v: k for k, v in self._scene_to_note_map.items()}
        
        # MIDI connection variables (mido port objects)
        self.midi_out = None  # type: t.Any
        self.midi_in = None   # type: t.Any
        
        # Connection state flag
        self.connection_good = False
        
        # Device state management
        self.device_manager = device_manager

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
        Connect to LightSoftware via loopMIDI ports.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.device_manager:
                self.device_manager.set_connecting(DeviceType.LIGHT_SOFTWARE)

            # Close any stale port handles before opening new ones
            self._close_ports()

            # Open input (feedback FROM LightSoftware via loopMIDI "lightsoftware_out")
            self.midi_in = midi_manager.open_input_by_keyword("lightsoftware_out")
            if self.midi_in:
                logger.info("✅ LightSoftware IN: %s", self.midi_in.name)
            else:
                logger.error("❌ No LightSoftware_out MIDI input found")

            # Open output (commands TO LightSoftware via loopMIDI "lightsoftware_in")
            self.midi_out = midi_manager.open_output_by_keyword("lightsoftware_in")
            if self.midi_out:
                logger.info("✅ LightSoftware OUT: %s", self.midi_out.name)
            else:
                logger.error("❌ No LightSoftware_in MIDI output found")

            # Update connection state
            if self.midi_out and self.midi_in:
                self.connection_good = True
                if self.device_manager:
                    self.device_manager.set_connected(DeviceType.LIGHT_SOFTWARE)
                logger.info("✅ Successfully connected to LightSoftware MIDI")
                return True
            else:
                self.connection_good = False
                if self.device_manager:
                    self.device_manager.set_disconnected(DeviceType.LIGHT_SOFTWARE)
                logger.error(
                    "❌ Failed to connect to LightSoftware - missing MIDI ports"
                )
                return False

        except Exception as e:
            logger.error("LightSoftware MIDI connection failed: %s", e)
            self.connection_good = False
            if self.device_manager:
                self.device_manager.set_error(DeviceType.LIGHT_SOFTWARE, str(e))
            return False

    def set_scene_state(self, scene_index: t.Tuple[int, int], active: bool) -> None:
        """Set scene state explicitly using a note-on message with velocity for on/off.

        Uses ``midi_manager.safe_send`` for automatic retry on transient
        I/O errors and marks the connection as bad when recovery fails so
        that ``DeviceMonitor`` can trigger a full reconnect.
        """
        if not self.connection_good:
            return

        if not midi_manager.is_port_alive(self.midi_out):
            logger.warning("LightSoftware output port is closed – marking disconnected")
            self._mark_disconnected("Output port closed")
            return

        scene_note = self._scene_to_note_map.get(scene_index)
        if scene_note is None:
            logger.warning("No MIDI note mapped for scene coordinates %s", scene_index)
            return

        velocity = self.on_value if active else self.off_value

        try:
            msg = mido.Message("note_on", note=scene_note, velocity=velocity, channel=0)
            ok = midi_manager.safe_send(self.midi_out, msg)
            if ok:
                logger.debug(
                    "Sent to LightSoftware: Scene %s -> note %s, velocity %s",
                    scene_index,
                    scene_note,
                    velocity,
                )
            else:
                self._mark_disconnected("safe_send failed")
        except Exception as e:
            logger.error("MIDI send error: %s", e)
            self._mark_disconnected(f"Send error: {e}")

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
        Process MIDI feedback from LightSoftware and return LED state changes.

        Validates port liveness before reading.  On failure the connection
        is marked bad so ``DeviceMonitor`` triggers reconnection.

        Returns:
            Dictionary of note -> state changes (True=on, False=off)
        """
        changes: t.Dict[int, bool] = {}

        if not self.connection_good:
            return changes

        if not midi_manager.is_port_alive(self.midi_in):
            self._mark_disconnected("Input port closed during feedback")
            return changes

        try:
            for msg in self.midi_in.iter_pending():
                if msg.type == "note_on":
                    changes[msg.note] = msg.velocity > 0

        except Exception as e:
            logger.error("MIDI feedback processing error: %s", e)
            self._mark_disconnected(f"Feedback error: {e}")

        return changes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mark_disconnected(self, reason: str) -> None:
        """Centralised helper to flag a broken connection."""
        if not self.connection_good:
            return  # already flagged – avoid log spam
        self.connection_good = False
        logger.warning("LightSoftware connection lost: %s", reason)
        if self.device_manager:
            self.device_manager.set_error(DeviceType.LIGHT_SOFTWARE, reason)

    def close(self) -> None:
        """
        Clean shutdown of LightSoftware MIDI connections.

        Only closes this component's ports.  The shared MIDI subsystem
        is shut down via ``midi_manager.shutdown()`` at application exit.
        Idempotent – safe to call multiple times.
        """
        try:
            self._close_ports()
            logger.info("✅  LightSoftware MIDI ports closed")
        except Exception as e:
            logger.error("Error closing LightSoftware MIDI: %s", e)
        finally:
            self.connection_good = False
            if self.device_manager:
                self.device_manager.set_disconnected(DeviceType.LIGHT_SOFTWARE)
