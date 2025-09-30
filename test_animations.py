#!/usr/bin/env python3
"""
Simple test for the RGB Animation System

Quick test to verify the system works without needing hardware.
"""

import numpy as np
from rgb_animation_engine import RGBAnimationEngine


def mock_set_grid_rgb(rgb_array):
    """Mock function to simulate hardware control."""
    print(
        f"Grid update: shape={rgb_array.shape}, max={rgb_array.max():.2f}, min={rgb_array.min():.2f}"
    )


def test_animations():
    """Test the animation system."""
    print("Testing RGB Animation Engine...")

    # Create engine with mock hardware
    engine = RGBAnimationEngine(mock_set_grid_rgb)

    # List available animations
    print(f"Available animations: {engine.get_available_animations()}")

    # Test creating a simple custom animation
    def simple_pulse(elapsed_time):
        intensity = (np.sin(elapsed_time * 2) + 1) / 2
        rgb_array = np.zeros((8, 8, 3))
        rgb_array[:, :, 0] = intensity  # Red pulse
        return rgb_array

    engine.create_custom_animation("test_pulse", simple_pulse)
    print("Created custom animation")

    # Test starting an animation
    print("Starting rainbow wave animation...")
    success = engine.start_animation("rainbow_wave", duration=2.0)
    print(f"Animation started: {success}")

    if success:
        import time

        time.sleep(2.5)  # Let it run for a bit
        engine.stop_animation()
        print("Animation stopped")

    print("Test completed!")


if __name__ == "__main__":
    test_animations()
