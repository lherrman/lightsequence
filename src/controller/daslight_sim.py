"""
DasLight MIDI Communication Utilities

Clean utility functions for communicating with DasLight via loopMIDI.
Based on working patterns from test_minimal.py
"""

import logging
import typing as t
import pygame.midi
import numpy as np

logger = logging.getLogger(__name__)


class DaslightSim:
    def __init__(self):
        # Scene mapping: relative coordinates (x, y) to MIDI notes
        self._scene_to_note_map = self._build_scene_note_mapping()

        # Preset mapping: relative coordinates (x, y) to MIDI notes
        self._preset_to_note_map = self._build_preset_note_mapping()

        # Reverse mapping for feedback processing
        self._note_to_scene_map = {v: k for k, v in self._scene_to_note_map.items()}

        # MIDI connection variables
        self.midi_out = None
        self.midi_in = None

    def _build_scene_note_mapping(self) -> t.Dict[t.Tuple[int, int], int]:
        """Build mapping from scene button coordinates to MIDI notes."""
        scene_map = {}
        base_notes = [81, 71, 61, 51, 41]  # Column base notes (y=0 to y=4)

        for x in range(8):  # 8 columns
            for y in range(5):  # 5 rows (y=0 to y=4 relative to scene area)
                note = base_notes[y] + x
                scene_map[(x, y)] = note

        return scene_map

    def _build_preset_note_mapping(self) -> t.Dict[t.Tuple[int, int], int]:
        """Build mapping from preset button coordinates to MIDI notes."""
        preset_map = {}
        base_notes = [31, 21, 11]  # Row base notes (y=0 to y=2)

        for x in range(8):  # 8 columns
            for y in range(3):  # 3 rows (y=0 to y=2 relative to preset area)
                note = base_notes[y] + x
                preset_map[(x, y)] = note

        return preset_map

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
                if "daylight_out" in name.lower() and info[3]:  # output device
                    self.midi_out = pygame.midi.Output(i)
                    logger.info(f"✅ Sim OUT: {name}")

                # Connect input (from Sim via Daylight_out)
                elif "daylight_in" in name.lower() and info[2]:  # input device
                    self.midi_in = pygame.midi.Input(i)
                    logger.info(f"✅ Sim IN: {name}")

            if not self.midi_out:
                logger.error("❌ No Sim OUT MIDI output found")
            if not self.midi_in:
                logger.error("❌ No Sim IN MIDI input found")

            return self.midi_out, self.midi_in

        except Exception as e:
            logger.error(f"DasLight MIDI connection failed: {e}")
            return None, None

    def process(self) -> None:
        """
        Listen to midi_in for incoming notes (only the scene notes), and convert them to scene coordinates.
        toggle the state of the button in the internal state and send the new state to midi_out as a note
        """
        # if self.midi_in and self.midi_in.poll():
        #     midi_events = self.midi_in.read(10)  # Read up to 10 events at once
        #     for event in midi_events:
        #         data, timestamp = event
        #         status, note, velocity, _ = data

        #         if status in [144, 128]:  # Note On or Note Off
        #             is_pressed = status == 144 and velocity > 0

        #             if note in self._note_to_scene_map:
        #                 x, y = self._note_to_scene_map[note]
        #                 logger.info(
        #                     f"Sim Button {'Pressed' if is_pressed else 'Released'}: Scene ({x}, {y})"
        #                 )

        #                 # Echo back the note to simulate feedback
        #                 if self.midi_out:
        #                     self.midi_out.write_short(
        #                         144 if is_pressed else 128, note, velocity if is_pressed else 0
        #                     )
        #             else:
        #                 logger.debug(f"Received unmapped note: {note}")
