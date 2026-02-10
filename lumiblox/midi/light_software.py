"""
LightSoftware MIDI Communication Utilities

Clean utility functions for communicating with LightSoftware via loopMIDI.
Only tested with DasLight 4

"""

import os
import logging
import typing as t

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame.midi

from lumiblox.common.device_state import DeviceManager, DeviceType
from lumiblox.midi.midi_manager import midi_manager

logger = logging.getLogger(__name__)


class LightSoftware:
    def __init__(self, device_manager: t.Optional[DeviceManager] = None):
        # Scene mapping: relative coordinates (x, y) to MIDI notes
        self._scene_to_note_map = self._build_scene_note_mapping()

        # Reverse mapping for feedback processing
        self._note_to_scene_map = {v: k for k, v in self._scene_to_note_map.items()}
        
        # MIDI connection variables
        self.midi_out = None
        self.midi_in = None
        
        # Connection state flag
        self.connection_good = False
        
        # Device state management
        self.device_manager = device_manager

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
        """Close existing MIDI port objects without touching the global subsystem."""
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

            midi_manager.acquire()

            with midi_manager.lock:
                for i in range(pygame.midi.get_count()):
                    info = pygame.midi.get_device_info(i)
                    interface, name, is_input, is_output, opened = info
                    name = name.decode() if name else ""

                    # Connect input (from LightSoftware via LightSoftware_out)
                    if "lightsoftware_out" in name.lower() and is_input:
                        self.midi_in = pygame.midi.Input(i)
                        logger.info(f"✅ LightSoftware IN: {name}")

                    # Connect output (to LightSoftware via LightSoftware_in)
                    elif "lightsoftware_in" in name.lower() and is_output:
                        self.midi_out = pygame.midi.Output(i)
                        logger.info(f"✅ LightSoftware OUT: {name}")

            if not self.midi_out:
                logger.error("❌ No LightSoftware_in MIDI output found")
            if not self.midi_in:
                logger.error("❌ No LightSoftware_out MIDI input found")

            # Update connection state if successful
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
            logger.error(f"LightSoftware MIDI connection failed: {e}")
            self.connection_good = False
            
            if self.device_manager:
                self.device_manager.set_error(DeviceType.LIGHT_SOFTWARE, str(e))
            
            return False

    def set_scene_state(self, scene_index: t.Tuple[int, int], active: bool) -> None:
        """Set scene state explicitly using a note-on message with velocity for on/off."""
        if not self.midi_out:
            logger.debug("MIDI output not connected - skipping scene command")
            return

        scene_note = self._scene_to_note_map.get(scene_index)
        if scene_note is None:
            logger.warning("No MIDI note mapped for scene coordinates %s", scene_index)
            return

        velocity = 127 if active else 0

        try:
            with midi_manager.lock:
                self.midi_out.write([[[0x90, scene_note, velocity], pygame.midi.time()]])
            logger.debug(
                "Sent to LightSoftware: Scene %s -> note %s, velocity %s",
                scene_index,
                scene_note,
                velocity,
            )
        except Exception as e:
            logger.error("MIDI send error: %s", e)
            self.connection_good = False
            if self.device_manager:
                self.device_manager.set_error(
                    DeviceType.LIGHT_SOFTWARE, f"Send error: {e}"
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
        Process MIDI feedback from LightSoftware and return LED state changes.

        Returns:
            Dictionary of note -> state changes (True=on, False=off)
        """
        changes = {}

        try:
            if not self.midi_in:
                return changes
            with midi_manager.lock:
                if not self.midi_in.poll():
                    return changes
                midi_events = self.midi_in.read(100)
            for event in midi_events:
                msg_data = event[0]
                if isinstance(msg_data, list) and len(msg_data) >= 3:
                    status, note, velocity = msg_data[0], msg_data[1], msg_data[2]

                    if status == 0x90:  # Note on message
                        # Only track changes, not repeated states
                        changes[note] = velocity > 0

        except Exception as e:
            logger.error(f"MIDI feedback processing error: {e}")
            # Mark as disconnected on error
            self.connection_good = False
            if self.device_manager:
                self.device_manager.set_error(DeviceType.LIGHT_SOFTWARE, f"Feedback error: {e}")

        return changes

    def close_midi(self) -> None:
        """
        Clean shutdown of LightSoftware MIDI connections.

        Only closes this component's ports.  The shared pygame.midi
        subsystem is shut down via ``midi_manager.shutdown()`` at
        application exit.
        """
        try:
            self._close_ports()
            midi_manager.release()
            logger.info("✅  LightSoftware MIDI ports closed")
            
            self.connection_good = False
            if self.device_manager:
                self.device_manager.set_disconnected(DeviceType.LIGHT_SOFTWARE)
                
        except Exception as e:
            logger.error(f"Error closing LightSoftware MIDI: {e}")
