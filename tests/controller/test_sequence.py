"""Test sequence management functionality"""
import pytest
import time
from controller.controller.sequence import SequenceManager, SequenceStep, SequenceState


@pytest.fixture
def sequence_manager():
    """Create a sequence manager instance"""
    manager = SequenceManager()
    yield manager
    manager.cleanup()


@pytest.fixture
def sample_steps():
    """Create sample sequence steps"""
    return [
        SequenceStep(scenes=[[0, 0], [1, 1]], duration=0.2, name="Step 1"),
        SequenceStep(scenes=[[2, 2], [3, 3]], duration=0.2, name="Step 2"),
        SequenceStep(scenes=[[4, 4]], duration=0.2, name="Step 3"),
    ]


def test_add_sequence(sequence_manager, sample_steps):
    """Test adding a sequence"""
    preset_index = (0, 0)
    sequence_manager.add_sequence(preset_index, sample_steps)
    
    assert sequence_manager.has_sequence(preset_index)
    retrieved = sequence_manager.get_sequence(preset_index)
    assert len(retrieved) == 3
    assert retrieved[0].name == "Step 1"


def test_start_stop_sequence(sequence_manager, sample_steps):
    """Test starting and stopping a sequence"""
    preset_index = (0, 0)
    sequence_manager.add_sequence(preset_index, sample_steps)
    
    # Start sequence
    result = sequence_manager.start_sequence(preset_index)
    assert result is True
    assert sequence_manager.sequence_state == SequenceState.PLAYING
    assert sequence_manager.current_sequence == preset_index
    
    # Stop sequence
    sequence_manager.stop_sequence()
    assert sequence_manager.sequence_state == SequenceState.STOPPED
    assert sequence_manager.current_sequence is None


def test_pause_resume_sequence(sequence_manager, sample_steps):
    """Test pausing and resuming a sequence"""
    preset_index = (0, 0)
    sequence_manager.add_sequence(preset_index, sample_steps)
    sequence_manager.start_sequence(preset_index)
    
    # Pause
    sequence_manager.pause_sequence()
    assert sequence_manager.sequence_state == SequenceState.PAUSED
    
    # Resume
    sequence_manager.resume_sequence()
    assert sequence_manager.sequence_state == SequenceState.PLAYING
    
    sequence_manager.stop_sequence()


def test_next_step(sequence_manager, sample_steps):
    """Test manually advancing to next step"""
    preset_index = (0, 0)
    sequence_manager.add_sequence(preset_index, sample_steps)
    sequence_manager.start_sequence(preset_index)
    
    time.sleep(0.1)  # Let sequence start
    
    initial_step = sequence_manager.current_step_index
    result = sequence_manager.next_step()
    
    assert result is True
    assert sequence_manager.current_step_index == (initial_step + 1) % len(sample_steps)
    
    sequence_manager.stop_sequence()


def test_sequence_loop(sequence_manager):
    """Test sequence looping functionality"""
    preset_index = (0, 0)
    steps = [
        SequenceStep(scenes=[[0, 0]], duration=0.1, name="Step 1"),
        SequenceStep(scenes=[[1, 1]], duration=0.1, name="Step 2"),
    ]
    
    step_changes = []
    
    def on_step_change(scenes):
        step_changes.append(scenes)
    
    sequence_manager.on_step_change = on_step_change
    sequence_manager.add_sequence(preset_index, steps)
    sequence_manager.set_loop_enabled(True)
    sequence_manager.start_sequence(preset_index)
    
    # Wait for at least one full cycle
    time.sleep(0.5)
    
    # Should have looped
    assert len(step_changes) >= 2
    
    sequence_manager.stop_sequence()


def test_get_current_step_info(sequence_manager, sample_steps):
    """Test getting current step information"""
    preset_index = (0, 0)
    sequence_manager.add_sequence(preset_index, sample_steps)
    sequence_manager.start_sequence(preset_index)
    
    time.sleep(0.1)
    
    info = sequence_manager.get_current_step_info()
    assert info is not None
    assert info['preset_index'] == preset_index
    assert info['total_steps'] == 3
    assert 'step_name' in info
    assert 'remaining_time' in info
    
    sequence_manager.stop_sequence()


def test_remove_sequence(sequence_manager, sample_steps):
    """Test removing a sequence"""
    preset_index = (0, 0)
    sequence_manager.add_sequence(preset_index, sample_steps)
    
    assert sequence_manager.has_sequence(preset_index)
    
    result = sequence_manager.remove_sequence(preset_index)
    assert result is True
    assert not sequence_manager.has_sequence(preset_index)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
