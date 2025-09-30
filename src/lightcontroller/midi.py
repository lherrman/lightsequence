"""
Minimal MIDI mapping for Novation Launchpad MK2
"""

from typing import Optional

# MIDI note mapping for 8x8 grid (verified with hardware)
GRID_NOTES = {
    # Row 0 (bottom): 11-18
    (0, 0): 11,
    (1, 0): 12,
    (2, 0): 13,
    (3, 0): 14,
    (4, 0): 15,
    (5, 0): 16,
    (6, 0): 17,
    (7, 0): 18,
    # Row 1: 21-28
    (0, 1): 21,
    (1, 1): 22,
    (2, 1): 23,
    (3, 1): 24,
    (4, 1): 25,
    (5, 1): 26,
    (6, 1): 27,
    (7, 1): 28,
    # Row 2: 31-38
    (0, 2): 31,
    (1, 2): 32,
    (2, 2): 33,
    (3, 2): 34,
    (4, 2): 35,
    (5, 2): 36,
    (6, 2): 37,
    (7, 2): 38,
    # Row 3: 41-48
    (0, 3): 41,
    (1, 3): 42,
    (2, 3): 43,
    (3, 3): 44,
    (4, 3): 45,
    (5, 3): 46,
    (6, 3): 47,
    (7, 3): 48,
    # Row 4: 51-58
    (0, 4): 51,
    (1, 4): 52,
    (2, 4): 53,
    (3, 4): 54,
    (4, 4): 55,
    (5, 4): 56,
    (6, 4): 57,
    (7, 4): 58,
    # Row 5: 61-68
    (0, 5): 61,
    (1, 5): 62,
    (2, 5): 63,
    (3, 5): 64,
    (4, 5): 65,
    (5, 5): 66,
    (6, 5): 67,
    (7, 5): 68,
    # Row 6: 71-78
    (0, 6): 71,
    (1, 6): 72,
    (2, 6): 73,
    (3, 6): 74,
    (4, 6): 75,
    (5, 6): 76,
    (6, 6): 77,
    (7, 6): 78,
    # Row 7 (top): 81-88
    (0, 7): 81,
    (1, 7): 82,
    (2, 7): 83,
    (3, 7): 84,
    (4, 7): 85,
    (5, 7): 86,
    (6, 7): 87,
    (7, 7): 88,
}

# Preset buttons (right column): 89-96
PRESET_NOTES = {i: 89 + i for i in range(8)}

# Reverse mappings
NOTE_TO_COORD = {v: k for k, v in GRID_NOTES.items()}
NOTE_TO_PRESET = {v: k for k, v in PRESET_NOTES.items()}


def coord_to_note(x: int, y: int) -> Optional[int]:
    """Convert coordinate to MIDI note."""
    return GRID_NOTES.get((x, y))


def note_to_coord(note: int) -> Optional[tuple[int, int]]:
    """Convert MIDI note to coordinate."""
    return NOTE_TO_COORD.get(note)


def is_preset_note(note: int) -> bool:
    """Check if note is a preset button."""
    return note in NOTE_TO_PRESET


def get_preset_index(note: int) -> Optional[int]:
    """Get preset index from note."""
    return NOTE_TO_PRESET.get(note)
