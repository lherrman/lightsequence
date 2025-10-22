"""Test that all modules can be imported correctly"""
import pytest


def test_import_common_modules():
    """Test importing common modules"""
    from controller.common.config import get_config, ConfigManager
    from controller.common.enums import AppState
    from controller.common.utils import hex_to_rgb
    
    assert AppState.NORMAL is not None
    assert AppState.SAVE_MODE is not None
    assert AppState.SAVE_SHIFT_MODE is not None


def test_import_device_modules():
    """Test importing device modules"""
    from controller.devices.launchpad import LaunchpadMK2, ButtonType
    
    assert ButtonType.SCENE is not None
    assert ButtonType.PRESET is not None
    assert ButtonType.TOP is not None
    assert ButtonType.RIGHT is not None


def test_import_midi_modules():
    """Test importing MIDI modules"""
    from controller.midi.light_software import LightSoftware
    from controller.midi.light_software_sim import LightSoftwareSim
    
    assert LightSoftware is not None
    assert LightSoftwareSim is not None


def test_import_controller_modules():
    """Test importing controller modules"""
    from controller.controller.main import LightController
    from controller.controller.sequence import SequenceManager, SequenceStep, SequenceState
    from controller.controller.preset_manager import PresetManager
    from controller.controller.background_animator import BackgroundManager, BackgroundAnimator
    
    assert LightController is not None
    assert SequenceManager is not None
    assert SequenceStep is not None
    assert PresetManager is not None
    assert BackgroundManager is not None


def test_import_gui_module():
    """Test importing GUI module"""
    from controller.gui.gui import LightSequenceGUI, main
    
    assert LightSequenceGUI is not None
    assert main is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
