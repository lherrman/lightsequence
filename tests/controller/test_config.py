"""Test configuration management"""
import pytest
import tempfile
from pathlib import Path
from lumiblox.common.config import ConfigManager, get_config
from lumiblox.common.enums import AppState


@pytest.fixture
def temp_config_file():
    """Create a temporary config file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_file = Path(f.name)
    yield config_file
    # Cleanup
    if config_file.exists():
        config_file.unlink()


@pytest.fixture
def config_manager(temp_config_file):
    """Create a config manager instance"""
    return ConfigManager(temp_config_file)


def test_create_default_config(config_manager, temp_config_file):
    """Test creating default configuration"""
    assert temp_config_file.exists()
    assert config_manager.data is not None
    assert 'brightness_foreground' in config_manager.data
    assert 'colors' in config_manager.data
    assert 'key_bindings' in config_manager.data


def test_brightness_values(config_manager):
    """Test brightness configuration values"""
    assert 'brightness_foreground' in config_manager.data
    assert 'brightness_background' in config_manager.data
    assert 'brightness_background_effect' in config_manager.data
    assert 'brightness_background_top_row' in config_manager.data
    
    # Check that values are in valid range
    assert 0.0 <= config_manager.data['brightness_foreground'] <= 1.0
    assert 0.0 <= config_manager.data['brightness_background'] <= 1.0


def test_color_configuration(config_manager):
    """Test color configuration"""
    colors = config_manager.data['colors']
    
    # Check essential colors exist
    assert 'column_colors' in colors
    assert 'preset_on' in colors
    assert 'scene_on' in colors
    assert 'off' in colors
    
    # Check column colors
    column_colors = colors['column_colors']
    assert len(column_colors) == 8
    for i in range(8):
        assert str(i) in column_colors


def test_key_bindings(config_manager):
    """Test key bindings configuration"""
    bindings = config_manager.data['key_bindings']
    
    # Check essential bindings exist
    assert 'save_button' in bindings
    assert 'background_button' in bindings
    assert 'playback_toggle_button' in bindings
    assert 'clear_button' in bindings
    
    # Check binding structure
    save_button = bindings['save_button']
    assert 'button_type' in save_button
    assert 'coordinates' in save_button
    assert isinstance(save_button['coordinates'], list)
    assert len(save_button['coordinates']) == 2


def test_reload_config(config_manager, temp_config_file):
    """Test reloading configuration"""
    # Modify config
    original_brightness = config_manager.data['brightness_foreground']
    config_manager.data['brightness_foreground'] = 0.5
    
    # Reload should restore from file
    config_manager.reload_config()
    
    # Should be back to original or default
    assert config_manager.data['brightness_foreground'] == original_brightness


def test_get_button_type_enum():
    """Test button type enum conversion"""
    from lumiblox.common.config import get_button_type_enum
    from lumiblox.devices.launchpad import ButtonType
    
    assert get_button_type_enum("TOP") == ButtonType.TOP
    assert get_button_type_enum("RIGHT") == ButtonType.RIGHT
    assert get_button_type_enum("SCENE") == ButtonType.SCENE
    assert get_button_type_enum("PRESET") == ButtonType.PRESET
    assert get_button_type_enum("invalid") == ButtonType.UNKNOWN


def test_global_config_manager():
    """Test global config manager singleton"""
    config1 = get_config()
    config2 = get_config()
    
    # Should be the same instance
    assert config1 is config2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
