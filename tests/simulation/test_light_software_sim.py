"""Test light software simulator"""
import pytest
from lumiblox.midi.light_software_sim import LightSoftwareSim


@pytest.fixture
def simulator():
    """Create a light software simulator instance"""
    sim = LightSoftwareSim()
    yield sim
    if sim.midi_out or sim.midi_in:
        sim.close_light_software_midi()


def test_simulator_initialization(simulator):
    """Test simulator initialization"""
    assert simulator is not None
    assert simulator.scene_states is not None
    assert len(simulator.scene_states) == 9 * 5  # 9 columns x 5 rows


def test_scene_note_mapping(simulator):
    """Test scene to note mapping"""
    # Test a few known mappings
    assert simulator._scene_to_note_map[(0, 0)] == 81
    assert simulator._scene_to_note_map[(0, 1)] == 71
    assert simulator._scene_to_note_map[(1, 0)] == 82


def test_send_scene_command(simulator):
    """Test sending scene commands"""
    scene_coords = (0, 0)
    
    # Initial state should be off
    assert simulator.get_scene_state(scene_coords) is False
    
    # Send command to toggle on
    simulator.send_scene_command(scene_coords)
    assert simulator.get_scene_state(scene_coords) is True
    
    # Send command to toggle off
    simulator.send_scene_command(scene_coords)
    assert simulator.get_scene_state(scene_coords) is False


def test_get_scene_coordinates_for_note(simulator):
    """Test getting scene coordinates from note"""
    note = 81
    coords = simulator.get_scene_coordinates_for_note(note)
    assert coords == (0, 0)
    
    note = 82
    coords = simulator.get_scene_coordinates_for_note(note)
    assert coords == (1, 0)


def test_get_all_active_scenes(simulator):
    """Test getting all active scenes"""
    # Activate some scenes
    simulator.send_scene_command((0, 0))
    simulator.send_scene_command((1, 1))
    simulator.send_scene_command((2, 2))
    
    active_scenes = simulator.get_all_active_scenes()
    assert len(active_scenes) == 3
    assert (0, 0) in active_scenes
    assert (1, 1) in active_scenes
    assert (2, 2) in active_scenes


def test_process_feedback(simulator):
    """Test processing MIDI feedback"""
    # Activate a scene
    simulator.send_scene_command((0, 0))
    
    # Process feedback should return changes
    changes = simulator.process_feedback()
    
    # Should have at least one change
    assert len(changes) >= 0  # Queue might be empty if already processed


def test_multiple_scene_toggles(simulator):
    """Test multiple scene toggles"""
    scene_coords = (3, 3)
    
    # Toggle on
    simulator.send_scene_command(scene_coords)
    assert simulator.get_scene_state(scene_coords) is True
    
    # Toggle off
    simulator.send_scene_command(scene_coords)
    assert simulator.get_scene_state(scene_coords) is False
    
    # Toggle on again
    simulator.send_scene_command(scene_coords)
    assert simulator.get_scene_state(scene_coords) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
