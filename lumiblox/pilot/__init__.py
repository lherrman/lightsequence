"""
Pilot Module

Handles MIDI clock synchronization and phrase detection for automatic light control.
"""

from lumiblox.pilot.clock_sync import ClockSync
from lumiblox.pilot.phrase_detector import PhraseDetector

__all__ = ["ClockSync", "PhraseDetector"]
