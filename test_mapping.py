#!/usr/bin/env python3
"""
Test script to verify Launchpad MK2 mapping consistency
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from lightcontroller.launchpad import LaunchpadMK2


def test_mapping():
    """Test that mapping is consistent between XY coordinates and MIDI notes."""
    lp = LaunchpadMK2()

    print("Testing MK2 MIDI note mapping...")
    print("=" * 50)

    # Test all positions in 8x8 grid
    for y in range(8):
        row_notes = []
        for x in range(8):
            note = lp._xy_to_midi_note(x, y)
            if note:
                # Test reverse mapping
                mapped_x, mapped_y = lp._midi_note_to_xy(note)
                if mapped_x != x or mapped_y != y:
                    print(f"ERROR: Mapping inconsistency at ({x}, {y})")
                    print(f"  XY->Note: {note}")
                    print(f"  Note->XY: ({mapped_x}, {mapped_y})")
                    return False
                row_notes.append(f"{note:2d}")
            else:
                row_notes.append("--")

        print(f"Row {y}: {' '.join(row_notes)}")

    print()
    print("Scene button mapping (first 40 positions):")
    print("-" * 40)

    for i in range(40):
        coords = lp.scene_coords_from_index(i)
        if coords:
            x, y = coords
            note = lp.scene_midi_note_from_index(i)
            reverse_idx = lp.midi_note_to_scene_index(note) if note else None

            if reverse_idx != i:
                print(f"ERROR: Scene index {i} -> note {note} -> index {reverse_idx}")
                return False

            if i % 8 == 0:
                print()
            print(f"S{i:2d}:({x},{y})={note:2d}", end="  ")

    print("\n")
    print("Preset button mapping (24 positions):")
    print("-" * 40)

    for i in range(24):
        coords = lp.preset_coords_from_index(i)
        if coords:
            x, y = coords
            note = lp.preset_midi_note_from_index(i)
            reverse_idx = lp.midi_note_to_preset_index(note) if note else None

            if reverse_idx != i:
                print(f"ERROR: Preset index {i} -> note {note} -> index {reverse_idx}")
                return False

            if i % 8 == 0:
                print()
            print(f"P{i:2d}:({x},{y})={note:2d}", end="  ")

    print("\n")
    print("✅ All mappings are consistent!")
    return True


def print_physical_layout():
    """Print the physical layout of the MK2."""
    lp = LaunchpadMK2()

    print("\nPhysical Launchpad MK2 Layout (MIDI notes):")
    print("=" * 50)
    print("Top row (scene launch buttons): 104 105 106 107 108 109 110 111")
    print()

    # Main 8x8 grid
    for y in range(8):
        row_notes = []
        for x in range(8):
            note = lp._xy_to_midi_note(x, y)
            row_notes.append(f"{note:3d}" if note else " --")

        # Right column button
        right_notes = [89, 79, 69, 59, 49, 39, 29, 19]
        right_note = right_notes[y] if y < len(right_notes) else "---"

        print(f"{' '.join(row_notes)}  {right_note}")

    print()
    print("Note: Y=0 is TOP row in our coordinate system")
    print("      Physical MK2 has Y=0 as BOTTOM row")


if __name__ == "__main__":
    print("🎹 Launchpad MK2 Mapping Test")
    print("=" * 50)

    if test_mapping():
        print_physical_layout()
    else:
        print("❌ Mapping test failed!")
        sys.exit(1)
