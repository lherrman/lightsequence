"""
LightSoftware MIDI Communication Utilities

Clean utility functions for communicating with LightSoftware via loopMIDI.
Only tested with DasLight 4

"""

import os
import logging
import time
import typing as t

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame.midi

logger = logging.getLogger(__name__)


class LightSoftware:
    def __init__(self):
        # Scene mapping: relative coordinates (x, y) to MIDI notes
        self._scene_to_note_map = self._build_scene_note_mapping()

        # Reverse mapping for feedback processing
        self._note_to_scene_map = {v: k for k, v in self._scene_to_note_map.items()}
        # MIDI connection variables
        self.midi_out = None
        self.midi_in = None

        # Connection monitoring - start as False until connected
        self.connection_good = False
        self.last_ping_time = 0.0
        self.last_ping_response_time = 0.0
        self.ping_interval = 2.5  # seconds
        self.ping_timeout = 5.0  # seconds without response = bad connection

    def _build_scene_note_mapping(self) -> t.Dict[t.Tuple[int, int], int]:
        """
        Build mapping from scene button coordinates to MIDI notes.
        Corresponds to the default notes from Launchpad MK2
        """
        scene_map = {}
        base_notes = [81, 71, 61, 51, 41]  # y=0 to y=5

        for x in range(9):  # 9 columns
            for y in range(5):  # 5 rows (y=0 to y=4 relative to scene area)
                note = base_notes[y] + x
                scene_map[(x, y)] = note

        return scene_map

    def connect_midi(self) -> bool:
        """
        Connect to LightSoftware via loopMIDI ports.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            pygame.midi.init()

            self.midi_out = None
            self.midi_in = None

            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                name = info[1].decode() if info[1] else ""

                # Connect output (to LightSoftware via LightSoftware_in)
                if "lightsoftware_in" in name.lower() and info[3]:  # output device
                    self.midi_out = pygame.midi.Output(i)
                    logger.info(f"✅ LightSoftware OUT: {name}")

                # Connect input (from LightSoftware via LightSoftware_out)
                elif "lightsoftware_out" in name.lower() and info[2]:  # input device
                    self.midi_in = pygame.midi.Input(i)
                    logger.info(f"✅ LightSoftware IN: {name}")

            if not self.midi_out:
                logger.error("❌ No LightSoftware_in MIDI output found")
            if not self.midi_in:
                logger.error("❌ No LightSoftware_out MIDI input found")

            # Initialize connection monitoring if successful
            if self.midi_out and self.midi_in:
                self.connection_good = True
                self.last_ping_response_time = time.time()
                logger.info("✅ Successfully connected to LightSoftware MIDI")
                return True
            else:
                self.connection_good = False
                logger.error(
                    "❌ Failed to connect to LightSoftware - missing MIDI ports"
                )
                return False

        except Exception as e:
            logger.error(f"LightSoftware MIDI connection failed: {e}")
            self.connection_good = False
            return False

    def send_scene_command(self, scene_index: t.Tuple[int, int]) -> None:
        """
        Send scene activation command to LightSoftware.

        Args:
            scene_index: Tuple of (x, y) coordinates relative to scene area
        """
        if not self.midi_out:
            logger.warning("MIDI output not connected")
            return

        scene_note = self._scene_to_note_map.get(scene_index)
        if not scene_note:
            logger.warning(f"No MIDI note mapped for scene coordinates {scene_index}")
            return

        try:
            self.midi_out.write([[[0x90, scene_note, 127], pygame.midi.time()]])
            logger.debug(
                f"Sent to LightSoftware: Scene {scene_index} -> note {scene_note}"
            )
        except Exception as e:
            logger.error(f"MIDI send error: {e}")

    def send_ping(self) -> bool:
        """
        Send a ping to LightSoftware on note 127 to check connection status.

        Returns:
            True if ping was sent successfully, False otherwise
        """
        if not self.midi_out:
            return False

        try:
            self.midi_out.write([[[0x90, 127, 127], pygame.midi.time()]])
            logger.debug("Sent ping to LightSoftware on note 127")
            return True
        except Exception as e:
            logger.error(f"MIDI ping error: {e}")
            return False

    def check_connection_status(self) -> bool:
        """
        Check connection status and send pings as needed.

        Returns:
            True if connection is good, False otherwise
        """

        current_time = time.time()

        # Check if it's time to send a ping
        if current_time - self.last_ping_time >= self.ping_interval:
            if self.send_ping():
                self.last_ping_time = current_time
            else:
                # Failed to send ping - try to reconnect
                logger.warning("Failed to send ping - attempting reconnection")
                self.attempt_reconnection()

        # Check if we've lost connection (no response to ping)
        if current_time - self.last_ping_response_time > self.ping_timeout:
            if self.connection_good:
                self.connection_good = False
                logger.warning("LightSoftware connection lost")

        return self.connection_good

    def attempt_reconnection(self) -> bool:
        """
        Attempt to reconnect to LightSoftware.

        Returns:
            True if reconnection successful, False otherwise
        """
        logger.info("Attempting to reconnect to LightSoftware...")
        return self.connect_midi()

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

        if not self.midi_in or not self.midi_in.poll():
            return changes

        try:
            midi_events = self.midi_in.read(100)
            for event in midi_events:
                msg_data = event[0]
                if isinstance(msg_data, list) and len(msg_data) >= 3:
                    status, note, velocity = msg_data[0], msg_data[1], msg_data[2]

                    if status == 0x90:  # Note on message
                        # Check if this is a ping response (note 127)
                        if note == 127 and velocity > 0:
                            import time

                            self.last_ping_response_time = time.time()
                            if not self.connection_good:
                                self.connection_good = True
                                logger.info("LightSoftware connection restored")

                        # Only track changes, not repeated states
                        changes[note] = velocity > 0

        except Exception as e:
            logger.error(f"MIDI feedback processing error: {e}")

        return changes

    def close_light_software_midi(self) -> None:
        """
        Clean shutdown of LightSoftware MIDI connections.
        """
        try:
            if self.midi_out:
                self.midi_out.close()
                logger.info("✅  MIDI output closed")
            if self.midi_in:
                self.midi_in.close()
                logger.info("✅  MIDI input closed")
            pygame.midi.quit()
        except Exception as e:
            logger.error(f"Error closing  MIDI: {e}")
        self.midi_out = None
        self.midi_in = None
