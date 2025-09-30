#!/usr/bin/env python3
"""
Minimal Launchpad MK2 <-> loopMIDI test based on official documentation.

Key findings from https://github.com/FMMT666/launchpad.py:
- ButtonStateRaw() returns: [ <button>, <value> ] where value 0 = released, >0 = pressed
- Only send MIDI on button PRESS (value > 0), completely ignore RELEASE (value = 0)
"""

import time

try:
    import pygame.midi
    import launchpad_py as lp
except ImportError as e:
    print(f"Import error: {e}")
    exit(1)


class MinimalTest:
    def __init__(self):
        self.running = False
        self.launchpad = None
        self.midi_out = None
        self.button_states = {}  # Track button press/release states

    def setup(self):
        """Setup Launchpad and MIDI output."""
        # Connect Launchpad MK2
        self.launchpad = lp.LaunchpadMk2()
        if not self.launchpad.Open():
            print("❌ No Launchpad MK2 found")
            return False
        self.launchpad.Reset()
        print("✅ Launchpad MK2 connected")

        # Connect loopMIDI output (to DasLight)
        pygame.midi.init()
        for i in range(pygame.midi.get_count()):
            info = pygame.midi.get_device_info(i)
            name = info[1].decode() if info[1] else ""
            if "daylight_in" in name.lower() and info[3]:  # output device
                self.midi_out = pygame.midi.Output(i)
                print(f"✅ MIDI output: {name}")
                break

        if not self.midi_out:
            print("❌ No Daylight_in MIDI output found")
            return False

        return True

    def run(self):
        """Main loop - poll buttons and send MIDI only on PRESS."""
        print("🎹 Press Launchpad buttons (only PRESS sends MIDI, RELEASE ignored)")
        print("Press Ctrl+C to stop")

        self.running = True
        try:
            while self.running:
                # Poll button events
                buttons = self.launchpad.ButtonStateRaw()
                if buttons:
                    for button_data in buttons:
                        if not isinstance(button_data, int):
                            continue
                            
                        note = button_data
                        
                        # Detect press/release pattern:
                        # Press: note -> 127, Release: note -> 0
                        if note == 127:
                            # This confirms a button press - ignore this velocity event
                            continue
                        elif note == 0:
                            # This signals button release - clear all pressed states
                            self.button_states.clear()
                            print("� Button RELEASED → all states cleared")
                            continue
                        elif 1 <= note <= 120:  # Valid button range
                            # Check if this button was already pressed
                            if note not in self.button_states:
                                # First time seeing this button - it's a PRESS
                                self.button_states[note] = True
                                self.midi_out.write([[[0x90, note, 127], pygame.midi.time()]])
                                print(f"📤 Button {note} PRESSED → MIDI sent")
                            else:
                                # Already seen - this is the release event, ignore
                                print(f"🔇 Button {note} already processed → ignored")
                        else:
                            print(f"🔇 Invalid note {note} → ignored")

                time.sleep(0.01)  # 100Hz polling

        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean shutdown."""
        self.running = False
        if self.launchpad:
            self.launchpad.Reset()
            self.launchpad.Close()
        if self.midi_out:
            self.midi_out.close()
        pygame.midi.quit()
        print("✅ Cleanup complete")


if __name__ == "__main__":
    test = MinimalTest()
    if test.setup():
        test.run()
