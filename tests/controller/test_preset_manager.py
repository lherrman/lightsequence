"""Test preset management functionality"""
import pytest
import tempfile
from pathlib import Path
from lumiblox.controller.preset_manager import PresetManager
from lumiblox.controller.sequence import SequenceStep


@pytest.fixture
def temp_preset_file():
    """Create a temporary preset file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        preset_file = Path(f.name)
    yield preset_file
    # Cleanup
    if preset_file.exists():
        preset_file.unlink()


@pytest.fixture
def preset_manager(temp_preset_file):
    """Create a preset manager instance"""
    return PresetManager(temp_preset_file)


def test_create_empty_presets_file(preset_manager, temp_preset_file):
    """Test creating an empty presets file"""
    preset_manager.create_empty_presets_file()
    assert temp_preset_file.exists()


def test_save_and_load_preset(preset_manager):
    """Test saving and loading a preset"""
    preset_coords = [0, 0]
    scenes = [[1, 1], [2, 2], [3, 3]]
    
    preset_manager.save_preset(preset_coords, scenes)
    
    loaded_preset = preset_manager.get_preset_by_index(preset_coords)
    assert loaded_preset is not None
    assert loaded_preset['scenes'] == scenes


def test_get_all_preset_indices(preset_manager):
    """Test getting all preset indices"""
    preset_manager.save_preset([0, 0], [[1, 1]])
    preset_manager.save_preset([1, 1], [[2, 2]])
    preset_manager.save_preset([2, 0], [[3, 3]])
    
    indices = preset_manager.get_all_preset_indices()
    assert len(indices) == 3
    assert (0, 0) in indices
    assert (1, 1) in indices
    assert (2, 0) in indices


def test_remove_preset(preset_manager):
    """Test removing a preset by saving empty scenes"""
    preset_coords = [0, 0]
    preset_manager.save_preset(preset_coords, [[1, 1]])
    
    assert preset_manager.get_preset_by_index(preset_coords) is not None
    
    # Remove by saving empty preset (or use remove_sequence if it's a sequence)
    presets_data = preset_manager.load_presets()
    presets_data["presets"] = [p for p in presets_data["presets"] if p["index"] != preset_coords]
    preset_manager.save_presets(presets_data)
    
    assert preset_manager.get_preset_by_index(preset_coords) is None


def test_save_sequence(preset_manager):
    """Test saving a sequence"""
    preset_coords = [0, 0]
    steps = [
        SequenceStep(scenes=[[0, 0]], duration=1.0, name="Step 1"),
        SequenceStep(scenes=[[1, 1]], duration=2.0, name="Step 2"),
    ]
    
    preset_manager.save_sequence(preset_coords, steps, loop=True)
    
    assert preset_manager.has_sequence(preset_coords)
    loaded_steps = preset_manager.get_sequence(preset_coords)
    assert len(loaded_steps) == 2
    assert loaded_steps[0].name == "Step 1"
    assert loaded_steps[0].duration == 1.0


def test_add_step_to_preset(preset_manager):
    """Test adding a step to an existing preset"""
    preset_coords = [0, 0]
    initial_scenes = [[0, 0]]
    additional_scenes = [[1, 1]]
    
    # Save initial preset
    preset_manager.save_preset(preset_coords, initial_scenes)
    
    # Add a step
    preset_manager.add_step_to_preset(preset_coords, additional_scenes)
    
    # Should now be a sequence
    assert preset_manager.has_sequence(preset_coords)
    steps = preset_manager.get_sequence(preset_coords)
    assert len(steps) == 2


def test_loop_setting(preset_manager):
    """Test loop setting for sequences"""
    preset_coords = [0, 0]
    steps = [
        SequenceStep(scenes=[[0, 0]], duration=1.0, name="Step 1"),
        SequenceStep(scenes=[[1, 1]], duration=1.0, name="Step 2"),
    ]
    
    # Save with loop enabled
    preset_manager.save_sequence(preset_coords, steps, loop=True)
    assert preset_manager.get_loop_setting(preset_coords) is True
    
    # Save with loop disabled
    preset_manager.save_sequence(preset_coords, steps, loop=False)
    assert preset_manager.get_loop_setting(preset_coords) is False


def test_clear_all_presets(preset_manager):
    """Test clearing all presets"""
    preset_manager.save_preset([0, 0], [[1, 1]])
    preset_manager.save_preset([1, 1], [[2, 2]])
    
    indices = preset_manager.get_all_preset_indices()
    assert len(indices) == 2
    
    # Clear by saving empty presets data
    preset_manager.save_presets({"presets": []})
    
    indices = preset_manager.get_all_preset_indices()
    assert len(indices) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
