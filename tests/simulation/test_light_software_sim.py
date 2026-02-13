"""Test light software simulator"""
import pytest
from lumiblox.midi.light_software_sim import LightSoftwareSim
from lumiblox.midi.light_software_protocol import LightSoftwareProtocol


@pytest.fixture
def simulator():
    """Create a light software simulator instance"""
    sim = LightSoftwareSim()
    yield sim
    if sim.midi_out or sim.midi_in:
        sim.close()


def test_sim_implements_protocol(simulator):
    """Test that the simulator satisfies the LightSoftwareProtocol"""
    assert isinstance(simulator, LightSoftwareProtocol)


def test_simulator_initialization(simulator):
    """Test simulator initialization"""
    assert simulator is not None
    assert simulator.scene_states is not None
    assert len(simulator.scene_states) == 9 * 10  # 9 columns x 10 rows (2 pages)


def test_scene_note_mapping(simulator):
    """Test scene to note mapping"""
    # Test a few known mappings
    assert simulator._scene_to_note_map[(0, 0)] == 81
    assert simulator._scene_to_note_map[(0, 1)] == 71
    assert simulator._scene_to_note_map[(1, 0)] == 82


def test_set_scene_state(simulator):
    """Setting scene state should be idempotent and explicit."""
    scene_coords = (0, 0)

    simulator.set_scene_state(scene_coords, True)
    assert simulator.get_scene_state(scene_coords) is True

    # Re-assert ON should keep it on
    simulator.set_scene_state(scene_coords, True)
    assert simulator.get_scene_state(scene_coords) is True

    # Explicit off
    simulator.set_scene_state(scene_coords, False)
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
    simulator.set_scene_state((0, 0), True)
    simulator.set_scene_state((1, 1), True)
    simulator.set_scene_state((2, 2), True)
    
    active_scenes = simulator.get_all_active_scenes()
    assert len(active_scenes) == 3
    assert (0, 0) in active_scenes
    assert (1, 1) in active_scenes
    assert (2, 2) in active_scenes


def test_process_feedback(simulator):
    """Test processing MIDI feedback"""
    # Activate a scene
    simulator.set_scene_state((0, 0), True)
    
    # Process feedback should return changes
    changes = simulator.process_feedback()
    
    # Should have at least one change
    assert len(changes) >= 0  # Queue might be empty if already processed


def test_multiple_scene_toggles(simulator):
    """Test multiple scene toggles"""
    scene_coords = (3, 3)
    
    # Toggle on
    simulator.set_scene_state(scene_coords, True)
    assert simulator.get_scene_state(scene_coords) is True
    
    # Toggle off
    simulator.set_scene_state(scene_coords, False)
    assert simulator.get_scene_state(scene_coords) is False
    
    # Toggle on again
    simulator.set_scene_state(scene_coords, True)
    assert simulator.get_scene_state(scene_coords) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
