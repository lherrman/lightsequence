"""
DasLight MIDI Communication Utilities

Clean utility functions for communicating with DasLight via loopMIDI.
Based on working patterns from test_minimal.py
"""

import logging
import typing as t
import pygame.midi

logger = logging.getLogger(__name__)


class Daslight:
    def __init__(self):
        # Scene mapping: relative coordinates (x, y) to MIDI notes
        self._scene_to_note_map = self._build_scene_note_mapping()

        # Reverse mapping for feedback processing
        self._note_to_scene_map = {v: k for k, v in self._scene_to_note_map.items()}
        # MIDI connection variables
        self.midi_out = None
        self.midi_in = None

    def _build_scene_note_mapping(self) -> t.Dict[t.Tuple[int, int], int]:
        """Build mapping from scene button coordinates to MIDI notes."""
        scene_map = {}
        base_notes = [81, 71, 61, 51, 41]  # y=0 to y=5

        for x in range(9):  # 9 columns
            for y in range(5):  # 5 rows (y=0 to y=4 relative to scene area)
                note = base_notes[y] + x
                scene_map[(x, y)] = note

        return scene_map

    def connect_midi(
        self,
    ) -> t.Tuple[t.Optional[pygame.midi.Output], t.Optional[pygame.midi.Input]]:
        """
        Connect to DasLight via loopMIDI ports.

        Returns:
            Tuple of (midi_out, midi_in) for DasLight communication
            - midi_out: Send commands TO DasLight (via Daylight_in port)
            - midi_in: Receive feedback FROM DasLight (via Daylight_out port)
        """
        try:
            pygame.midi.init()

            self.midi_out = None
            self.midi_in = None

            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                name = info[1].decode() if info[1] else ""

                # Connect output (to DasLight via Daylight_in)
                if "daylight_in" in name.lower() and info[3]:  # output device
                    self.midi_out = pygame.midi.Output(i)
                    logger.info(f"✅ DasLight OUT: {name}")

                # Connect input (from DasLight via Daylight_out)
                elif "daylight_out" in name.lower() and info[2]:  # input device
                    self.midi_in = pygame.midi.Input(i)
                    logger.info(f"✅ DasLight IN: {name}")

            if not self.midi_out:
                logger.error("❌ No Daylight_in MIDI output found")
            if not self.midi_in:
                logger.error("❌ No Daylight_out MIDI input found")

            return self.midi_out, self.midi_in

        except Exception as e:
            logger.error(f"DasLight MIDI connection failed: {e}")
            return None, None

    def send_scene_command(self, scene_index: t.Tuple[int, int]) -> None:
        """
        Send scene activation command to DasLight.

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
            logger.debug(f"Sent to DasLight: Scene {scene_index} -> note {scene_note}")
        except Exception as e:
            logger.error(f"MIDI send error: {e}")

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
        Process MIDI feedback from DasLight and return LED state changes.

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
                        # Only track changes, not repeated states
                        changes[note] = velocity > 0

        except Exception as e:
            logger.error(f"MIDI feedback processing error: {e}")

        return changes

    def close_daslight_midi(self) -> None:
        """
        Clean shutdown of DasLight MIDI connections.
        """
        try:
            if self.midi_out:
                self.midi_out.close()
                logger.info("✅ DasLight MIDI output closed")
            if self.midi_in:
                self.midi_in.close()
                logger.info("✅ DasLight MIDI input closed")
            pygame.midi.quit()
        except Exception as e:
            logger.error(f"Error closing DasLight MIDI: {e}")
        self.midi_out = None
        self.midi_in = None
