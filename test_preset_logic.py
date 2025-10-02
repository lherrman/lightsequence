#!/usr/bin/env python3
"""
Test script to verify preset background color logic.
"""

import sys
import os

sys.path.append("src/controller")

from preset_manager import PresetManager
from background_animator import BackgroundAnimator
from pathlib import Path


def test_preset_background_logic():
    """Test the preset background color logic."""

    # Create preset manager
    preset_manager = PresetManager(Path("presets.json"))

    # Create background animator with preset manager
    animator = BackgroundAnimator(preset_manager)

    # Get preset indices
    preset_indices = preset_manager.get_all_preset_indices()
    print(f"Found presets at indices: {preset_indices}")

    # Test coordinate conversion
    print("\nTesting coordinate conversion:")
    for y in range(6, 9):  # Launchpad preset area (y=6,7,8)
        for x in range(8):
            preset_coords = (x, y - 6)  # Convert to preset coordinate system
            has_preset = preset_coords in preset_indices
            print(
                f"Launchpad ({x}, {y}) -> Preset {preset_coords}: {'HAS PRESET' if has_preset else 'empty'}"
            )

    # Test that only buttons with presets get background color
    print(f"\nPreset at (0,0) should glow: {(0, 0) in preset_indices}")
    print(f"Preset at (1,0) should be dark: {(1, 0) in preset_indices}")
    print(f"Preset at (0,1) should be dark: {(0, 1) in preset_indices}")


if __name__ == "__main__":
    test_preset_background_logic()
