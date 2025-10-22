"""
LightSoftware Simulator for Testing

Simulates LightSoftware behavior without needing the actual software running.
Maintains a 9x5 grid of scene states and provides MIDI feedback.
"""

import logging
import typing as t
import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame.midi

logger = logging.getLogger(__name__)


class LightSoftwareSim:
    """
    Simulates LightSoftware for testing without the actual software.
    Provides MIDI feedback and maintains scene state.
    """

    def __init__(self):
        # Scene mapping: relative coordinates (x, y) to MIDI notes
        self._scene_to_note_map = self._build_scene_note_mapping()

        # Reverse mapping for feedback processing
        self._note_to_scene_map = {v: k for k, v in self._scene_to_note_map.items()}

        # Scene state storage: 9 columns x 5 rows
        self.scene_states: t.Dict[t.Tuple[int, int], bool] = {}
        for x in range(9):
            for y in range(5):
                self.scene_states[(x, y)] = False

        # MIDI connection variables
        self.midi_out = None
        self.midi_in = None

        # Connection state flag
        self.connection_good = False

        # Feedback queue - messages to send back to controller
        self.feedback_queue: t.List[t.Tuple[int, int]] = []

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
        Connect to loopMIDI ports for simulation.

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

                # Connect output (to send feedback via LightSoftware_out)
                if "lightsoftware_out" in name.lower() and info[3]:  # output device
                    self.midi_out = pygame.midi.Output(i)
                    logger.info(f"✅ [SIM] LightSoftware OUT: {name}")

                # Connect input (to receive commands via LightSoftware_in)
                elif "lightsoftware_in" in name.lower() and info[2]:  # input device
                    self.midi_in = pygame.midi.Input(i)
                    logger.info(f"✅ [SIM] LightSoftware IN: {name}")

            if not self.midi_out:
                logger.error("❌ [SIM] No LightSoftware_out MIDI output found")
            if not self.midi_in:
                logger.error("❌ [SIM] No LightSoftware_in MIDI input found")

            # Update connection state if successful
            if self.midi_out and self.midi_in:
                self.connection_good = True
                logger.info("✅ [SIM] Successfully connected to MIDI (simulation mode)")
                return True
            else:
                self.connection_good = False
                logger.error("❌ [SIM] Failed to connect to MIDI - missing MIDI ports")
                return False

        except Exception as e:
            logger.error(f"[SIM] MIDI connection failed: {e}")
            self.connection_good = False
            return False

    def send_scene_command(self, scene_index: t.Tuple[int, int]) -> None:
        """
        Process scene activation command (simulates receiving from controller).
        This is called by the controller to activate scenes.

        Args:
            scene_index: Tuple of (x, y) coordinates relative to scene area
        """
        scene_note = self._scene_to_note_map.get(scene_index)
        if not scene_note:
            logger.warning(
                f"[SIM] No MIDI note mapped for scene coordinates {scene_index}"
            )
            return

        logger.debug(
            f"[SIM] Received scene command: {scene_index} -> note {scene_note}"
        )

        # Toggle scene state (this is what the real lighting software does)
        current_state = self.scene_states.get(scene_index, False)
        new_state = not current_state
        self.scene_states[scene_index] = new_state

        # Queue feedback with the new state
        velocity = 127 if new_state else 0
        self.feedback_queue.append((scene_note, velocity))

        logger.debug(
            f"[SIM] Scene {scene_index} toggled to {'ON' if new_state else 'OFF'}"
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

        Returns:
            Dictionary of note -> state changes (True=on, False=off)
        """
        changes = {}

        # First, send any queued feedback
        if self.midi_out and self.feedback_queue:
            try:
                for note, velocity in self.feedback_queue:
                    self.midi_out.write([[[0x90, note, velocity], pygame.midi.time()]])
                    logger.debug(
                        f"[SIM] Sent feedback: note {note}, velocity {velocity}"
                    )

                    changes[note] = velocity > 0

                self.feedback_queue.clear()
            except Exception as e:
                logger.error(f"[SIM] MIDI feedback send error: {e}")

        # Process incoming commands from controller
        if self.midi_in and self.midi_in.poll():
            try:
                midi_events = self.midi_in.read(100)
                for event in midi_events:
                    msg_data = event[0]
                    if isinstance(msg_data, list) and len(msg_data) >= 3:
                        status, note, velocity = msg_data[0], msg_data[1], msg_data[2]

                        if status == 0x90:  # Note on message
                            logger.debug(
                                f"[SIM] Received command: note {note}, velocity {velocity}"
                            )

                            # Handle scene command
                            scene_coords = self.get_scene_coordinates_for_note(note)
                            if scene_coords:
                                self.send_scene_command(scene_coords)

            except Exception as e:
                logger.error(f"[SIM] MIDI command processing error: {e}")

        return changes

    def close_light_software_midi(self) -> None:
        """
        Clean shutdown of MIDI connections.
        """
        try:
            if self.midi_out:
                self.midi_out.close()
                logger.info("✅ [SIM] MIDI output closed")
            if self.midi_in:
                self.midi_in.close()
                logger.info("✅ [SIM] MIDI input closed")
            pygame.midi.quit()
        except Exception as e:
            logger.error(f"[SIM] Error closing MIDI: {e}")
        self.midi_out = None
        self.midi_in = None

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
