"""Test that all modules can be imported correctly"""
import pytest


def test_import_common_modules():
    """Test importing common modules"""
    from lumiblox.common.config import get_config, ConfigManager
    from lumiblox.common.enums import AppState
    from lumiblox.common.utils import hex_to_rgb
    
    assert AppState.NORMAL is not None
    assert AppState.SAVE_MODE is not None
    assert AppState.SAVE_SHIFT_MODE is not None
    assert AppState.PILOT_SELECT_MODE is not None


def test_import_device_modules():
    """Test importing device modules"""
    from lumiblox.devices.launchpad import LaunchpadMK2
    from lumiblox.common.enums import ButtonType
    
    assert ButtonType.SCENE is not None
    assert ButtonType.SEQUENCE is not None


def test_import_midi_modules():
    """Test importing MIDI modules"""
    from lumiblox.midi.light_software import LightSoftware
    from lumiblox.midi.light_software_sim import LightSoftwareSim
    from lumiblox.midi.light_software_protocol import LightSoftwareProtocol
    
    assert LightSoftware is not None
    assert LightSoftwareSim is not None
    assert LightSoftwareProtocol is not None


def test_import_controller_modules():
    """Test importing controller modules"""
    from lumiblox.controller.light_controller import LightController
    from lumiblox.controller.sequence_controller import (
        SequenceController,
        SequenceStep,
        SequenceDurationUnit,
        PlaybackState,
    )
    from lumiblox.controller.background_animator import BackgroundManager, BackgroundAnimator
    from lumiblox.controller.app_state_manager import AppStateManager
    
    assert LightController is not None
    assert SequenceStep is not None
    assert SequenceController is not None
    assert SequenceDurationUnit is not None
    assert PlaybackState is not None
    assert BackgroundManager is not None
    assert AppStateManager is not None


def test_import_gui_module():
    """Test importing GUI module"""
    from lumiblox.gui.gui import LightSequenceGUI, main
    
    assert LightSequenceGUI is not None
    assert main is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
