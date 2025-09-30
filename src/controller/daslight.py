"""
DasLight MIDI Communication Utilities

Clean utility functions for communicating with DasLight via loopMIDI.
Based on working patterns from test_minimal.py
"""

import logging
from typing import Optional, Dict, Any, Tuple
import pygame.midi

logger = logging.getLogger(__name__)


class Daslight:
    def __init__(self): ...

    def connect_midi(
        self,
    ) -> Tuple[Optional[pygame.midi.Output], Optional[pygame.midi.Input]]:
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

    def send_scene_command(self, scene_note: int) -> None:
        """
        Send scene activation command to DasLight.

        Args:
            midi_out: MIDI output device
            scene_note: MIDI note number for the scene
        """
        if self.midi_out:
            try:
                self.midi_out.write([[[0x90, scene_note, 127], pygame.midi.time()]])
                logger.debug(f"Sent to DasLight: Scene note {scene_note}")
            except Exception as e:
                logger.error(f"MIDI send error: {e}")

    def process_feedback(self) -> Dict[int, bool]:
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
