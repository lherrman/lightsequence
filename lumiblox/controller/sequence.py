import logging
import threading
import time
import typing as t
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class SequenceStep:
    """Represents a single step in a sequence."""

    scenes: t.List[t.List[int]]  # List of scene coordinates
    duration: float  # Duration in seconds
    name: str = ""  # Optional name for the step


class SequenceState(str, Enum):
    """States for sequence playback."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class SequenceManager:
    """Manages sequence playback for presets with multiple timed steps."""

    def __init__(self):
        self.sequences: t.Dict[t.Tuple[int, int], t.List[SequenceStep]] = {}
        self.current_sequence: t.Optional[t.Tuple[int, int]] = None
        self.current_step_index: int = 0
        self.sequence_state = SequenceState.STOPPED
        self.step_start_time: float = 0
        self.sequence_thread: t.Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.should_loop: bool = True  # Default to loop sequences

        # Callbacks
        self.on_step_change: t.Optional[t.Callable[[t.List[t.List[int]]], None]] = None
        self.on_sequence_complete: t.Optional[t.Callable[[], None]] = None

    def add_sequence(
        self, preset_index: t.Tuple[int, int], steps: t.List[SequenceStep]
    ) -> None:
        """Add or update a sequence for a preset."""
        self.sequences[preset_index] = steps.copy()
        logger.debug(f"Added sequence for preset {preset_index} with {len(steps)} steps")

    def get_sequence(
        self, preset_index: t.Tuple[int, int]
    ) -> t.Optional[t.List[SequenceStep]]:
        """Get sequence for a preset."""
        return self.sequences.get(preset_index)

    def has_sequence(self, preset_index: t.Tuple[int, int]) -> bool:
        """Check if a preset has a sequence."""
        return preset_index in self.sequences and len(self.sequences[preset_index]) > 1

    def start_sequence(self, preset_index: t.Tuple[int, int]) -> bool:
        """Start playing a sequence."""
        if preset_index not in self.sequences:
            logger.warning(f"No sequence found for preset {preset_index}")
            return False

        if self.sequence_state == SequenceState.PLAYING:
            self.stop_sequence()

        self.current_sequence = preset_index
        self.current_step_index = 0
        self.sequence_state = SequenceState.PLAYING
        self.stop_event.clear()

        # Start the sequence thread
        self.sequence_thread = threading.Thread(target=self._sequence_loop, daemon=True)
        self.sequence_thread.start()

        logger.debug(f"Started sequence for preset {preset_index}")
        return True

    def stop_sequence(self) -> None:
        """Stop the current sequence."""
        if self.sequence_state != SequenceState.STOPPED:
            self.sequence_state = SequenceState.STOPPED
            self.stop_event.set()

            if self.sequence_thread and self.sequence_thread.is_alive():
                self.sequence_thread.join(timeout=1.0)

            self.current_sequence = None
            self.current_step_index = 0
            logger.debug("Sequence stopped")

    def pause_sequence(self) -> None:
        """Pause the current sequence."""
        if self.sequence_state == SequenceState.PLAYING:
            self.sequence_state = SequenceState.PAUSED
            logger.debug("Sequence paused")

    def resume_sequence(self) -> None:
        """Resume the paused sequence."""
        if self.sequence_state == SequenceState.PAUSED:
            self.sequence_state = SequenceState.PLAYING
            logger.debug("Sequence resumed")

    def next_step(self) -> bool:
        """Jump to the next step in the current sequence."""
        if not self.current_sequence or self.current_sequence not in self.sequences:
            logger.warning("No active sequence to advance")
            return False

        if self.sequence_state == SequenceState.STOPPED:
            logger.warning("Cannot advance stopped sequence")
            return False

        sequence = self.sequences[self.current_sequence]
        if len(sequence) <= 1:
            logger.debug("Sequence has only one step, cannot advance")
            return False

        # Advance to next step
        self.current_step_index = (self.current_step_index + 1) % len(sequence)
        self.step_start_time = time.time()

        # Trigger step change callback immediately
        if self.on_step_change:
            current_step = sequence[self.current_step_index]
            self.on_step_change(current_step.scenes)

        logger.debug(f"Advanced to step {self.current_step_index + 1}/{len(sequence)}")
        return True

    def get_current_step_info(self) -> t.Optional[t.Dict[str, t.Any]]:
        """Get information about the current step."""
        if not self.current_sequence or self.current_sequence not in self.sequences:
            return None

        sequence = self.sequences[self.current_sequence]
        if 0 <= self.current_step_index < len(sequence):
            step = sequence[self.current_step_index]
            elapsed_time = (
                time.time() - self.step_start_time if self.step_start_time > 0 else 0
            )
            remaining_time = max(0, step.duration - elapsed_time)

            return {
                "preset_index": self.current_sequence,
                "step_index": self.current_step_index,
                "total_steps": len(sequence),
                "step_name": step.name,
                "scenes": step.scenes,
                "duration": step.duration,
                "elapsed_time": elapsed_time,
                "remaining_time": remaining_time,
                "state": self.sequence_state.value,
            }

        return None

    def _sequence_loop(self) -> None:
        """Main sequence playback loop (runs in separate thread)."""
        if not self.current_sequence:
            return

        sequence = self.sequences[self.current_sequence]

        while (
            self.sequence_state != SequenceState.STOPPED
            and not self.stop_event.is_set()
        ):
            if self.sequence_state == SequenceState.PAUSED:
                time.sleep(0.1)
                continue

            if 0 <= self.current_step_index < len(sequence):
                step = sequence[self.current_step_index]

                # Trigger step change callback
                if self.on_step_change:
                    try:
                        self.on_step_change(step.scenes)
                    except Exception as e:
                        logger.error(f"Error in step change callback: {e}")

                # Record step start time
                self.step_start_time = time.time()

                logger.debug(
                    f"Playing step {self.current_step_index + 1}/{len(sequence)} "
                    f"for {step.duration}s with {len(step.scenes)} scenes"
                )

                # Wait for step duration (with checks for pause/stop)
                end_time = time.time() + step.duration
                while time.time() < end_time and not self.stop_event.is_set():
                    if self.sequence_state == SequenceState.PAUSED:
                        # Pause the timer
                        pause_start = time.time()
                        while (
                            self.sequence_state == SequenceState.PAUSED
                            and not self.stop_event.is_set()
                        ):
                            time.sleep(0.1)
                        # Adjust end time for pause duration
                        if not self.stop_event.is_set():
                            pause_duration = time.time() - pause_start
                            end_time += pause_duration
                    time.sleep(0.1)

                if self.stop_event.is_set():
                    break

                # Move to next step
                self.current_step_index += 1

                # Check if sequence is complete
                if self.current_step_index >= len(sequence):
                    # Check if sequence should loop (default behavior)
                    if self.should_loop:
                        logger.debug(
                            f"Looping sequence for preset {self.current_sequence}"
                        )
                        self.current_step_index = 0  # Reset to first step
                        continue
                    else:
                        logger.debug(
                            f"Sequence for preset {self.current_sequence} completed (no loop)"
                        )

                        # Trigger completion callback
                        if self.on_sequence_complete:
                            try:
                                self.on_sequence_complete()
                            except Exception as e:
                                logger.error(
                                    f"Error in sequence complete callback: {e}"
                                )

                        # Reset and stop
                        self.current_step_index = 0
                        self.sequence_state = SequenceState.STOPPED
                        break
            else:
                logger.error(f"Invalid step index: {self.current_step_index}")
                break

        logger.debug("Sequence loop ended")

    def remove_sequence(self, preset_index: t.Tuple[int, int]) -> bool:
        """Remove a sequence for a preset."""
        if preset_index in self.sequences:
            # Stop sequence if it's currently playing
            if self.current_sequence == preset_index:
                self.stop_sequence()

            del self.sequences[preset_index]
            logger.debug(f"Removed sequence for preset {preset_index}")
            return True
        return False

    def get_all_sequences(self) -> t.Dict[t.Tuple[int, int], t.List[SequenceStep]]:
        """Get all sequences."""
        return self.sequences.copy()

    def set_loop_enabled(self, enabled: bool) -> None:
        """Set whether sequences should loop."""
        self.should_loop = enabled
        logger.debug(f"Sequence looping {'enabled' if enabled else 'disabled'}")

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_sequence()
