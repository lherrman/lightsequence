"""
Pilot Module

Handles MIDI clock synchronization and phrase detection for automatic light control.
"""

from lumiblox.pilot.clock_sync import ClockSync
from lumiblox.pilot.phrase_detector import PhraseDetector
from lumiblox.pilot.pilot_controller import PilotController

__all__ = ["ClockSync", "PhraseDetector", "PilotController"]
