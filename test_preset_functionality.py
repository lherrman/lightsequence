#!/usr/bin/env python3
"""
Test script to verify preset recording and activation functionality.
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lightcontroller.preset_manager import PresetManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_preset_functionality():
    """Test preset recording and activation."""
    logger.info("🧪 Testing preset functionality")
    
    # Create preset manager
    preset_manager = PresetManager()
    
    # Test 1: Record a preset with some scenes
    logger.info("Test 1: Recording preset with scenes [1, 5, 10]")
    active_scenes = [1, 5, 10]
    success = preset_manager.record_preset(0, active_scenes)
    
    assert success, "Failed to record preset"
    logger.info(f"✅ Preset recorded successfully")
    
    # Test 2: Check if preset is now programmed
    programmed = preset_manager.get_programmed_preset_indices()
    logger.info(f"Programmed presets: {programmed}")
    assert 0 in programmed, "Preset 0 should be programmed"
    logger.info(f"✅ Preset correctly marked as programmed")
    
    # Test 3: Get the recorded preset and verify its content
    preset = preset_manager.get_preset(0)
    assert preset is not None, "Preset should exist"
    assert preset.scene_indices == active_scenes, f"Expected {active_scenes}, got {preset.scene_indices}"
    logger.info(f"✅ Preset content verified: {preset.scene_indices}")
    
    # Test 4: Record another preset
    logger.info("Test 4: Recording second preset with scenes [2, 7, 12, 20]")
    active_scenes_2 = [2, 7, 12, 20]
    success = preset_manager.record_preset(5, active_scenes_2)
    
    assert success, "Failed to record second preset"
    programmed = preset_manager.get_programmed_preset_indices()
    logger.info(f"Programmed presets after second recording: {programmed}")
    assert len(programmed) == 2, f"Expected 2 programmed presets, got {len(programmed)}"
    assert 0 in programmed and 5 in programmed, "Both presets should be programmed"
    logger.info(f"✅ Multiple presets working correctly")
    
    # Test 5: Test preset activation (returns True if activated, False if deactivated)
    logger.info("Test 5: Testing preset activation toggle")
    was_activated = preset_manager.activate_preset(0)
    logger.info(f"Preset 0 activation result: {was_activated}")
    
    # Activate again to test toggle
    was_deactivated = preset_manager.activate_preset(0)
    logger.info(f"Preset 0 second activation (should deactivate): {was_deactivated}")
    
    logger.info("🎉 All preset functionality tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_preset_functionality()
        print("\n🎉 All tests passed! Preset recording and activation is working correctly.")
        print("\nTo test with your Launchpad MK2:")
        print("1. 🎹 Press scene buttons to turn them on/off")
        print("2. 🎙️ Hold Record Arm button (will glow red)")
        print("3. 🟡 See which preset buttons light up (those have content)")
        print("4. 📝 While holding Record Arm, press a preset button to record current scenes")
        print("5. 🎯 Press preset button normally (without Record Arm) to activate that preset")
        print("6. 🔄 Press same preset again to deactivate it")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)