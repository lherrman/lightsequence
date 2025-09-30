"""
DasLight MIDI Communication Utilities

Clean utility functions for communicating with DasLight via loopMIDI.
Based on working patterns from test_minimal.py
"""

import logging
from typing import Optional, Dict, Any, Tuple
import pygame.midi

logger = logging.getLogger(__name__)


def connect_daslight_midi() -> Tuple[Optional[pygame.midi.Output], Optional[pygame.midi.Input]]:
    """
    Connect to DasLight via loopMIDI ports.
    
    Returns:
        Tuple of (midi_out, midi_in) for DasLight communication
        - midi_out: Send commands TO DasLight (via Daylight_in port)  
        - midi_in: Receive feedback FROM DasLight (via Daylight_out port)
    """
    try:
        pygame.midi.init()
        
        midi_out = None
        midi_in = None
        
        for i in range(pygame.midi.get_count()):
            info = pygame.midi.get_device_info(i)
            name = info[1].decode() if info[1] else ""
            
            # Connect output (to DasLight via Daylight_in)
            if "daylight_in" in name.lower() and info[3]:  # output device
                midi_out = pygame.midi.Output(i)
                logger.info(f"✅ DasLight OUT: {name}")
                
            # Connect input (from DasLight via Daylight_out)
            elif "daylight_out" in name.lower() and info[2]:  # input device
                midi_in = pygame.midi.Input(i)
                logger.info(f"✅ DasLight IN: {name}")
        
        if not midi_out:
            logger.error("❌ No Daylight_in MIDI output found")
        if not midi_in:
            logger.error("❌ No Daylight_out MIDI input found")
            
        return midi_out, midi_in
        
    except Exception as e:
        logger.error(f"DasLight MIDI connection failed: {e}")
        return None, None


def send_scene_command(midi_out: pygame.midi.Output, scene_note: int) -> None:
    """
    Send scene activation command to DasLight.
    
    Args:
        midi_out: MIDI output device
        scene_note: MIDI note number for the scene
    """
    if midi_out:
        try:
            midi_out.write([[[0x90, scene_note, 127], pygame.midi.time()]])
            logger.debug(f"📤 Sent to DasLight: Scene note {scene_note}")
        except Exception as e:
            logger.error(f"MIDI send error: {e}")


def process_daslight_feedback(midi_in: pygame.midi.Input, led_states: Dict[int, bool]) -> Dict[int, bool]:
    """
    Process MIDI feedback from DasLight and return LED state changes.
    
    Args:
        midi_in: MIDI input device
        led_states: Current LED states dictionary
        
    Returns:
        Dictionary of note -> state changes (True=on, False=off)
    """
    changes = {}
    
    if not midi_in or not midi_in.poll():
        return changes
        
    try:
        midi_events = midi_in.read(100)
        for event in midi_events:
            msg_data = event[0]
            if isinstance(msg_data, list) and len(msg_data) >= 3:
                status, note, velocity = msg_data[0], msg_data[1], msg_data[2]
                
                if status == 0x90:  # Note on message
                    # Only track changes, not repeated states
                    current_state = led_states.get(note, False)
                    new_state = velocity > 0
                    
                    if current_state != new_state:
                        led_states[note] = new_state
                        changes[note] = new_state
                        logger.debug(
                            f"📥 DasLight feedback: Scene {note} -> {'ON' if new_state else 'OFF'}"
                        )
                        
    except Exception as e:
        logger.error(f"MIDI feedback processing error: {e}")
        
    return changes


def close_daslight_midi(midi_out: Optional[pygame.midi.Output], midi_in: Optional[pygame.midi.Input]) -> None:
    """
    Clean shutdown of DasLight MIDI connections.
    
    Args:
        midi_out: MIDI output device to close
        midi_in: MIDI input device to close
    """
    try:
        if midi_out:
            midi_out.close()
            logger.info("✅ DasLight MIDI output closed")
        if midi_in:
            midi_in.close() 
            logger.info("✅ DasLight MIDI input closed")
        pygame.midi.quit()
    except Exception as e:
        logger.error(f"Error closing DasLight MIDI: {e}")