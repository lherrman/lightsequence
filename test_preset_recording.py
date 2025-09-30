#!/usr/bin/env python3
"""
Test script for preset recording functionality.
This script helps verify that the preset recording system is working correctly.
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lightcontroller.preset_manager import PresetManager
from lightcontroller.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_preset_recording():
    """Test the preset recording functionality."""
    logger.info("🧪 Testing preset recording functionality")
    
    # Load config
    config = Config()
    config.load_config()
    
    # Create preset manager
    preset_manager = PresetManager(config)
    
    # Test 1: Check initial state - all presets should be empty
    logger.info("Test 1: Checking initial preset state")
    programmed = preset_manager.get_programmed_preset_indices()
    logger.info(f"Initially programmed presets: {programmed}")
    assert len(programmed) == 0, f"Expected 0 programmed presets, got {len(programmed)}"
    logger.info("✅ Test 1 passed: All presets initially empty")
    
    # Test 2: Record a preset with some scenes
    logger.info("Test 2: Recording a preset with scenes")
    test_scenes = [0, 5, 10, 15]  # Some test scene indices
    success = preset_manager.record_preset(0, test_scenes)  # Record to preset 0
    assert success, "Failed to record preset"
    
    # Check if preset is now programmed
    programmed = preset_manager.get_programmed_preset_indices()
    logger.info(f"After recording preset 0: {programmed}")
    assert 0 in programmed, "Preset 0 should be programmed"
    assert len(programmed) == 1, f"Expected 1 programmed preset, got {len(programmed)}"
    logger.info("✅ Test 2 passed: Preset recorded successfully")
    
    # Test 3: Record another preset
    logger.info("Test 3: Recording another preset")
    test_scenes_2 = [2, 7, 12]
    success = preset_manager.record_preset(5, test_scenes_2)  # Record to preset 5
    assert success, "Failed to record second preset"
    
    programmed = preset_manager.get_programmed_preset_indices()
    logger.info(f"After recording preset 5: {programmed}")
    assert 0 in programmed and 5 in programmed, "Both presets should be programmed"
    assert len(programmed) == 2, f"Expected 2 programmed presets, got {len(programmed)}"
    logger.info("✅ Test 3 passed: Multiple presets work correctly")
    
    # Test 4: Record empty preset (should still be considered programmed but empty)
    logger.info("Test 4: Recording empty preset")
    success = preset_manager.record_preset(10, [])  # Record empty preset
    assert success, "Failed to record empty preset"
    
    programmed = preset_manager.get_programmed_preset_indices()
    logger.info(f"After recording empty preset 10: {programmed}")
    # Empty presets should NOT be considered programmed
    assert 10 not in programmed, "Empty preset should not be considered programmed"
    logger.info("✅ Test 4 passed: Empty presets handled correctly")
    
    # Test 5: Overwrite existing preset
    logger.info("Test 5: Overwriting existing preset")
    new_scenes = [1, 3, 8, 20]
    success = preset_manager.record_preset(0, new_scenes)  # Overwrite preset 0
    assert success, "Failed to overwrite preset"
    
    programmed = preset_manager.get_programmed_preset_indices()
    logger.info(f"After overwriting preset 0: {programmed}")
    assert 0 in programmed, "Preset 0 should still be programmed"
    assert len(programmed) == 2, f"Expected 2 programmed presets, got {len(programmed)}"
    logger.info("✅ Test 5 passed: Preset overwriting works")
    
    logger.info("🎉 All tests passed! Preset recording functionality is working correctly.")
    return True

if __name__ == "__main__":
    try:
        test_preset_recording()
        print("\n🎉 All tests passed! The preset recording system is working correctly.")
        print("\nYou can now test with your Launchpad MK2:")
        print("1. Press scene buttons to activate/deactivate lights")
        print("2. Hold Record Arm button (button 104) - programmed presets will light up")
        print("3. While holding Record Arm, press a preset button to record current state")
        print("4. Release Record Arm - visual feedback will clear")
        print("5. Press preset button normally to activate that preset")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)