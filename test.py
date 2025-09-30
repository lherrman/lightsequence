#!/usr/bin/env python3
"""
Simple MIDI passthrough test for Launchpad <-> DasLight communication via loopMIDI

This test program:
1. Connects to Launchpad MK2 hardware
2. Connects to loopMIDI for DasLight communication
3. Forwards button presses from Launchpad to DasLight via loopMIDI
4. Forwards feedback from DasLight back to Launchpad LEDs

Usage: python test.py
"""

import logging
import threading
import time
from typing import Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import dependencies
try:
    import pygame
    import pygame.midi

    logger.info("pygame imported successfully")
except ImportError:
    logger.error("pygame not available - install with: pip install pygame")
    exit(1)

try:
    import launchpad_py as lp

    logger.info("launchpad_py imported successfully")
except ImportError:
    logger.error("launchpad_py not available - install with: pip install launchpad_py")
    exit(1)


class LaunchpadLoopMIDITest:
    """Simple passthrough test between Launchpad and loopMIDI."""

    def __init__(self):
        self.launchpad = None
        self.midi_out = None  # To DasLight
        self.midi_in = None  # From DasLight
        self.running = False
        self.led_states = {}  # Track LED states to prevent unnecessary updates
        self.button_states = {}  # Track button press/release states

        # Threading
        self.launchpad_thread = None
        self.midi_feedback_thread = None
        self.stop_event = threading.Event()

    def connect_launchpad(self) -> bool:
        """Connect to Launchpad MK2."""
        try:
            self.launchpad = lp.LaunchpadMk2()
            if self.launchpad.Open():
                self.launchpad.Reset()  # Clear all LEDs
                logger.info("✅ Connected to Launchpad MK2")
                return True
            else:
                logger.error("❌ Could not open Launchpad MK2")
                return False
        except Exception as e:
            logger.error(f"❌ Launchpad connection error: {e}")
            return False

    def connect_loopmidi(self) -> bool:
        """Connect to loopMIDI devices."""
        try:
            pygame.midi.init()
            device_count = pygame.midi.get_count()

            loopmidi_out_id = None
            loopmidi_in_id = None

            logger.info("🔍 Scanning for loopMIDI devices:")
            for i in range(device_count):
                info = pygame.midi.get_device_info(i)
                name = info[1].decode() if info[1] else "Unknown"
                is_input = info[2]
                is_output = info[3]

                logger.info(
                    f"  Device {i}: {name} (input={is_input}, output={is_output})"
                )

                # Look for specific Daylight loopMIDI ports
                # We send TO DasLight via Daylight_in (DasLight's input)
                # We receive FROM DasLight via Daylight_out (DasLight's output)
                if (
                    "daylight_in" in name.lower()
                    and is_output
                    and loopmidi_out_id is None
                ):
                    loopmidi_out_id = i
                    logger.info(f"  📤 Sending to DasLight via: {name}")
                elif (
                    "daylight_out" in name.lower()
                    and is_input
                    and loopmidi_in_id is None
                ):
                    loopmidi_in_id = i
                    logger.info(f"  📥 Receiving from DasLight via: {name}")

            # Connect output (to DasLight via Daylight_in)
            if loopmidi_out_id is not None:
                self.midi_out = pygame.midi.Output(loopmidi_out_id)
                logger.info(
                    "✅ Connected to send commands TO DasLight (via Daylight_in)"
                )
            else:
                logger.error("❌ No Daylight_in output device found")
                return False

            # Connect input (from DasLight via Daylight_out)
            if loopmidi_in_id is not None:
                self.midi_in = pygame.midi.Input(loopmidi_in_id)
                logger.info(
                    "✅ Connected to receive feedback FROM DasLight (via Daylight_out)"
                )
            else:
                logger.error("❌ No Daylight_out input device found")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ loopMIDI connection error: {e}")
            return False

    def start(self) -> bool:
        """Start the passthrough test."""
        logger.info("🚀 Starting Launchpad <-> loopMIDI passthrough test")

        # Connect hardware
        if not self.connect_launchpad():
            return False

        if not self.connect_loopmidi():
            return False

        # Start worker threads
        self.running = True
        self.stop_event.clear()

        # Thread to monitor Launchpad button presses
        self.launchpad_thread = threading.Thread(
            target=self._launchpad_worker, daemon=True
        )
        self.launchpad_thread.start()

        # Thread to monitor MIDI feedback from DasLight
        self.midi_feedback_thread = threading.Thread(
            target=self._midi_feedback_worker, daemon=True
        )
        self.midi_feedback_thread.start()

        logger.info("✅ Passthrough test started - press Launchpad buttons to test")
        logger.info("Press Ctrl+C to stop")

        return True

    def stop(self):
        """Stop the test."""
        logger.info("🛑 Stopping passthrough test...")

        self.running = False
        self.stop_event.set()

        # Wait for threads
        if self.launchpad_thread:
            self.launchpad_thread.join(timeout=1.0)
        if self.midi_feedback_thread:
            self.midi_feedback_thread.join(timeout=1.0)

        # Cleanup
        if self.launchpad:
            self.launchpad.Reset()
            self.launchpad.Close()

        if self.midi_out:
            self.midi_out.close()

        if self.midi_in:
            self.midi_in.close()

        pygame.midi.quit()
        logger.info("✅ Cleanup complete")

    def _launchpad_worker(self):
        """Worker thread to monitor Launchpad button presses."""
        logger.info("🎹 Launchpad monitoring started")

        while self.running and not self.stop_event.is_set():
            try:
                if self.launchpad:
                    buttons = self.launchpad.ButtonStateRaw()
                    if buttons:
                        for button in buttons:
                            self._handle_launchpad_button(button)

                time.sleep(0.01)  # 100Hz polling

            except Exception as e:
                logger.error(f"❌ Launchpad polling error: {e}")
                time.sleep(0.1)

    def _handle_launchpad_button(self, button):
        """Handle Launchpad button press/release - ONLY SEND ON PRESS."""
        try:
            note = None
            velocity = 0

            # Parse button event data
            if isinstance(button, (list, tuple)) and len(button) >= 2:
                # Format: [note, velocity] - standard format
                note, velocity = button[0], button[1]
                logger.info(f"🔍 ButtonStateRaw: Note {note}, Velocity {velocity}")
            elif isinstance(button, int):
                # Format: just note (should not happen with ButtonStateRaw)
                note = button
                velocity = 127
                logger.info(f"🔍 Integer format: Note {note} (assuming press)")
            else:
                logger.warning(f"⚠️  Unknown button format: {button}")
                return

            # CRITICAL FIX: According to launchpad.py docs:
            # ButtonStateRaw() returns [button, velocity] where:
            # - velocity > 0 = button pressed
            # - velocity = 0 = button released

            if velocity > 0:
                # Only send MIDI for button PRESSES
                if self.midi_out:
                    timestamp = pygame.midi.time()
                    self.midi_out.write([[[0x90, note, 127], timestamp]])
                    logger.info(
                        f"📤 ✅ SENT to DasLight: Note {note} PRESS (velocity {velocity})"
                    )
            else:
                # Completely ignore release events - NO MIDI SENT
                logger.info(
                    f"🔇 ❌ RELEASE IGNORED: Note {note} (velocity {velocity}) - NO MIDI SENT"
                )

        except Exception as e:
            logger.error(f"❌ Button handling error: {e}")

    def _midi_feedback_worker(self):
        """Worker thread to monitor MIDI feedback from DasLight."""
        logger.info("🎵 MIDI feedback monitoring started")

        while self.running and not self.stop_event.is_set():
            try:
                if self.midi_in and self.midi_in.poll():
                    midi_events = self.midi_in.read(100)
                    for event in midi_events:
                        self._handle_midi_feedback(event)

                time.sleep(0.01)  # 100Hz polling

            except Exception as e:
                logger.error(f"❌ MIDI feedback polling error: {e}")
                time.sleep(0.1)

    def _handle_midi_feedback(self, event):
        """Handle MIDI feedback from DasLight."""
        try:
            msg_data = event[0]
            if isinstance(msg_data, list) and len(msg_data) >= 3:
                status, note, velocity = msg_data[0], msg_data[1], msg_data[2]

                if status == 0x90:  # Note on message
                    logger.info(
                        f"📥 DasLight feedback: Note {note}, Velocity {velocity}"
                    )

                    # Only update LED if state actually changed
                    current_state = self.led_states.get(note, 0)
                    new_state = 1 if velocity > 0 else 0

                    if current_state != new_state:
                        self.led_states[note] = new_state

                        # Convert to Launchpad LED control
                        if self.launchpad:
                            if velocity > 0:
                                # Turn on LED (green for active)
                                self.launchpad.LedCtrlRaw(note, 0, 48)  # Green full
                                logger.info(f"💡 Launchpad LED ON: Note {note}")
                            else:
                                # Turn off LED
                                self.launchpad.LedCtrlRaw(note, 0, 0)  # Off
                                logger.info(f"💡 Launchpad LED OFF: Note {note}")
                    else:
                        logger.debug(f"🔄 LED state unchanged for Note {note}")

        except Exception as e:
            logger.error(f"❌ MIDI feedback handling error: {e}")


def main():
    """Main test function."""
    test = LaunchpadLoopMIDITest()

    try:
        if test.start():
            # Keep running until interrupted
            while test.running:
                time.sleep(0.1)
        else:
            logger.error("❌ Failed to start test")

    except KeyboardInterrupt:
        logger.info("🛑 Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
    finally:
        test.stop()


if __name__ == "__main__":
    main()
