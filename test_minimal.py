#!/usr/bin/env python3
"""
Clean Launchpad MK2 <-> DasLight utility functions and test.

Provides clean utility functions for:
- Launchpad MK2 connection and button handling
- loopMIDI communication with DasLight
- Proper press/release filtering (no MIDI on release)
"""

import time
from typing import Optional, Dict, Any

try:
    import pygame.midi
    import launchpad_py as lp
except ImportError as e:
    print(f"Import error: {e}")
    exit(1)


# === UTILITY FUNCTIONS ===

def connect_launchpad_mk2() -> Optional[Any]:
    """Connect to Launchpad MK2 and reset it."""
    launchpad = lp.LaunchpadMk2()
    if launchpad.Open():
        launchpad.Reset()
        print("✅ Launchpad MK2 connected")
        return launchpad
    else:
        print("❌ No Launchpad MK2 found")
        return None

def connect_daslight_midi() -> tuple[Optional[Any], Optional[Any]]:
    """Connect to DasLight via loopMIDI (Daylight_in for sending, Daylight_out for receiving)."""
    pygame.midi.init()
    
    midi_out = None
    midi_in = None
    
    for i in range(pygame.midi.get_count()):
        info = pygame.midi.get_device_info(i)
        name = info[1].decode() if info[1] else ""
        
        # Connect output (to DasLight via Daylight_in)
        if "daylight_in" in name.lower() and info[3]:  # output device
            midi_out = pygame.midi.Output(i)
            print(f"✅ DasLight OUT: {name}")
            
        # Connect input (from DasLight via Daylight_out)
        elif "daylight_out" in name.lower() and info[2]:  # input device
            midi_in = pygame.midi.Input(i)
            print(f"✅ DasLight IN: {name}")
    
    if not midi_out:
        print("❌ No Daylight_in MIDI output found")
    if not midi_in:
        print("❌ No Daylight_out MIDI input found")
        
    return midi_out, midi_in

def send_scene_command(midi_out: Any, scene_note: int) -> None:
    """Send scene activation command to DasLight."""
    midi_out.write([[[0x90, scene_note, 127], pygame.midi.time()]])

def process_daslight_feedback(midi_in: Any, launchpad: Any, led_states: Dict[int, bool]) -> None:
    """Process MIDI feedback from DasLight and update Launchpad LEDs."""
    if not midi_in.poll():
        return
        
    midi_events = midi_in.read(100)
    for event in midi_events:
        msg_data = event[0]
        if isinstance(msg_data, list) and len(msg_data) >= 3:
            status, note, velocity = msg_data[0], msg_data[1], msg_data[2]
            
            if status == 0x90:  # Note on message
                # Only update LED if state actually changed
                current_state = led_states.get(note, False)
                new_state = velocity > 0
                
                if current_state != new_state:
                    led_states[note] = new_state
                    
                    if new_state:
                        # Scene active - turn LED green
                        launchpad.LedCtrlRaw(note, 0, 48)  # Green full
                        print(f"💡 Scene {note} LED ON")
                    else:
                        # Scene inactive - turn LED off
                        launchpad.LedCtrlRaw(note, 0, 0)  # Off
                        print(f"💡 Scene {note} LED OFF")

def update_launchpad_leds(launchpad: Any, led_states: Dict[int, bool]) -> None:
    """Update all Launchpad LEDs based on current states."""
    for note, state in led_states.items():
        if state:
            launchpad.LedCtrlRaw(note, 0, 48)  # Green
        else:
            launchpad.LedCtrlRaw(note, 0, 0)  # Off

def process_launchpad_buttons(launchpad: Any, button_states: Dict[int, bool], midi_out: Any) -> None:
    """Process Launchpad button events and send MIDI only on first press."""
    buttons = launchpad.ButtonStateRaw()
    if not buttons:
        return
        
    for button_data in buttons:
        if not isinstance(button_data, int):
            continue
            
        note = button_data
        
        # Filter based on MK2 event pattern:
        # Press: note -> 127, Release: note -> 0
        if note == 127:
            # Velocity confirmation event - ignore
            continue
        elif note == 0:
            # Release signal - clear all button states
            button_states.clear()
            continue
        elif 1 <= note <= 120:  # Valid button range
            if note not in button_states:
                # First press - send MIDI
                button_states[note] = True
                send_scene_command(midi_out, note)
                print(f"📤 Scene {note} activated")
            # Ignore subsequent events for same button
        # Ignore invalid notes

# === TEST CLASS ===

class MinimalTest:
    def __init__(self):
        self.running = False
        self.launchpad = None
        self.midi_out = None
        self.midi_in = None
        self.button_states = {}  # Track button press/release states
        self.led_states = {}     # Track LED states

    def setup(self):
        """Setup Launchpad and MIDI using utility functions."""
        self.launchpad = connect_launchpad_mk2()
        if not self.launchpad:
            return False
            
        self.midi_out, self.midi_in = connect_daslight_midi()
        if not self.midi_out or not self.midi_in:
            return False
            
        return True

    def run(self):
        """Main test loop using utility functions."""
        print("🎹 Press Launchpad buttons to activate DasLight scenes")
        print("Press Ctrl+C to stop")

        self.running = True
        try:
            while self.running:
                # Process Launchpad button presses
                process_launchpad_buttons(self.launchpad, self.button_states, self.midi_out)
                
                # Process DasLight feedback and update LEDs
                process_daslight_feedback(self.midi_in, self.launchpad, self.led_states)
                
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
        if self.midi_in:
            self.midi_in.close()
        pygame.midi.quit()
        print("✅ Cleanup complete")


# === MAIN TEST ===

def main():
    """Main test function using clean utility functions."""
    print("🚀 DasLight Scene Controller Test")
    print("=" * 40)
    
    test = MinimalTest()
    if test.setup():
        test.run()
    else:
        print("❌ Setup failed")

if __name__ == "__main__":
    main()
