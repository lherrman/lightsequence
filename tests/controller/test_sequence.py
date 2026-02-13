"""Tests for the modern SequenceController implementation."""

import time
from pathlib import Path

import pytest

from lumiblox.controller.sequence_controller import (
    PlaybackState,
    SequenceController,
    SequenceDurationUnit,
    SequenceStep,
)
from lumiblox.common.project_data_repository import ProjectDataRepository


@pytest.fixture()
def sequence_file(tmp_path: Path) -> Path:
    """Provide a temporary storage path for the repository."""
    return tmp_path / "pilots.json"


@pytest.fixture()
def repository(sequence_file: Path):
    """Create a test repository."""
    return ProjectDataRepository(sequence_file)


@pytest.fixture()
def controller(repository: ProjectDataRepository):
    """Create a controller backed by a test repository and ensure cleanup."""
    ctrl = SequenceController(repository)
    yield ctrl
    ctrl.cleanup()


def _sample_steps() -> list[SequenceStep]:
    return [
        SequenceStep(scenes=[(0, 0)], duration=0.05, name="Step 1"),
        SequenceStep(scenes=[(1, 1)], duration=0.05, name="Step 2"),
    ]


def test_save_and_reload_sequence(sequence_file: Path, repository: ProjectDataRepository):
    """Sequences should persist to disk and reload correctly."""
    index = (1, 2)
    steps = _sample_steps()

    controller = SequenceController(repository)
    controller.save_sequence(index, steps, loop=False)
    controller.cleanup()

    # Create new repository instance and controller to test persistence
    reloaded_repo = ProjectDataRepository(sequence_file)
    reloaded = SequenceController(reloaded_repo)
    loaded_steps = reloaded.get_sequence(index)
    assert loaded_steps is not None
    assert len(loaded_steps) == len(steps)
    assert reloaded.get_loop_setting(index) is False
    reloaded.cleanup()


def test_activate_sequence_triggers_callback(controller: SequenceController):
    """Activating a sequence should fire the step callback for the first step."""
    index = (0, 0)
    steps = _sample_steps()
    controller.save_sequence(index, steps)

    captured = []
    controller.on_step_change = lambda scenes: captured.append(tuple(scenes))

    assert controller.activate_sequence(index)
    assert captured  # ensured callback fired
    assert captured[0][0] == (0, 0)


def test_play_pause_reuses_single_thread(controller: SequenceController):
    """Toggling play/pause should not spawn duplicate worker threads."""
    index = (0, 1)
    steps = [
        SequenceStep(scenes=[(0, 0)], duration=0.5, name="Step 1"),
        SequenceStep(scenes=[(1, 1)], duration=0.5, name="Step 2"),
    ]
    controller.save_sequence(index, steps, loop=True)
    controller.activate_sequence(index)

    controller.play()

    for _ in range(50):  # wait up to ~0.5s
        if controller.playback_thread:
            break
        time.sleep(0.01)

    thread = controller.playback_thread
    assert thread is not None and thread.is_alive()
    assert controller.playback_state == PlaybackState.PLAYING

    controller.pause()
    assert controller.playback_state == PlaybackState.PAUSED

    controller.play()
    assert controller.playback_state == PlaybackState.PLAYING
    assert controller.playback_thread is thread

    controller.stop_playback()


def test_next_step_manual_advance(controller: SequenceController):
    """Manual step advancement should wrap around the sequence."""
    index = (2, 2)
    steps = _sample_steps()
    controller.save_sequence(index, steps)
    controller.activate_sequence(index)

    assert controller.current_step_index == 0
    assert controller.next_step() is True
    assert controller.current_step_index == 1
    assert controller.next_step() is True
    assert controller.current_step_index == 0


def test_bar_duration_advances_with_beats(controller: SequenceController):
    """Bar-based durations should advance once enough beats are reported."""
    index = (3, 3)
    steps = [
        SequenceStep(
            scenes=[(0, 0)],
            duration=1,
            name="Bars",
            duration_unit=SequenceDurationUnit.BARS,
        ),
        SequenceStep(scenes=[(1, 1)], duration=0.05, name="Seconds"),
    ]
    controller.save_sequence(index, steps, loop=False)
    controller.activate_sequence(index)
    controller.play()

    # Give the worker a moment to start waiting on beats
    time.sleep(0.05)
    controller.notify_bar_advanced()

    # Wait until it advances to the second step
    for _ in range(50):
        if controller.current_step_index == 1:
            break
        time.sleep(0.02)

    assert controller.current_step_index == 1
    controller.stop_playback()


def test_followup_sequences_persist(sequence_file: Path, repository: ProjectDataRepository):
    """Follow-up sequence lists should save to disk and reload."""
    primary_index = (4, 4)
    next_index = (5, 5)
    steps = _sample_steps()

    controller = SequenceController(repository)
    controller.save_sequence(primary_index, steps, loop=False, next_sequences=[next_index])
    controller.save_sequence(next_index, steps, loop=True)
    controller.cleanup()

    # Create new repository instance and controller to test persistence
    reloaded_repo = ProjectDataRepository(sequence_file)
    reloaded = SequenceController(reloaded_repo)
    assert reloaded.get_followup_sequences(primary_index) == [next_index]
    reloaded.cleanup()


def test_sequence_auto_chains_to_followup(controller: SequenceController):
    """Non-looping sequences should automatically jump to configured follow-ups."""
    first = (6, 6)
    follower = (7, 7)
    first_steps = [
        SequenceStep(scenes=[(0, 0)], duration=0.05, name="A1"),
        SequenceStep(scenes=[(0, 1)], duration=0.05, name="A2"),
    ]
    follower_steps = [
        SequenceStep(scenes=[(2, 2)], duration=0.05, name="B1"),
        SequenceStep(scenes=[(2, 3)], duration=0.05, name="B2"),
    ]

    controller.save_sequence(first, first_steps, loop=False, next_sequences=[follower])
    controller.save_sequence(follower, follower_steps, loop=True)

    controller.activate_sequence(first)
    controller.play()

    for _ in range(100):
        if controller.active_sequence == follower:
            break
        time.sleep(0.02)

    assert controller.active_sequence == follower
    controller.stop_playback()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
