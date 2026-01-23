"""
Unified Sequence Controller

Manages all sequences (including "presets" which are just 1-step sequences).
Handles playback, storage, and state management.
"""

import json
import logging
import threading
import time
import typing as t
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SequenceDurationUnit(str, Enum):
    """Units for a sequence step's duration."""

    SECONDS = "seconds"
    BARS = "bars"


@dataclass
class SequenceStep:
    """Represents a single step in a sequence."""

    scenes: t.List[t.Tuple[int, int]]  
    duration: float  
    name: str = ""  
    duration_unit: SequenceDurationUnit = SequenceDurationUnit.SECONDS


class PlaybackState(str, Enum):
    """Playback states."""

    PLAYING = "playing"
    PAUSED = "paused"


class SequenceController:
    """
    Unified controller for all sequences (presets are 1-step sequences).

    Handles:
    - Storage and retrieval
    - Playback management
    - Step transitions
    """

    _BEATS_PER_BAR = 4

    def __init__(self, storage_file: Path):
        """Initialize sequence controller."""
        self.storage_file = storage_file
        self.sequences: t.Dict[t.Tuple[int, int], t.List[SequenceStep]] = {}
        self.loop_settings: t.Dict[t.Tuple[int, int], bool] = {}

        # Playback state
        self.active_sequence: t.Optional[t.Tuple[int, int]] = None
        self.current_step_index: int = 0
        self.playback_state = PlaybackState.PLAYING
        self.playback_thread: t.Optional[threading.Thread] = None
        self._thread_lock = threading.Lock()
        self.stop_event = threading.Event()
        self._bar_condition = threading.Condition()
        self._beats_remaining: t.Optional[int] = None

        # Callbacks
        self.on_step_change: t.Optional[
            t.Callable[[t.List[t.Tuple[int, int]]], None]
        ] = None
        self.on_sequence_complete: t.Optional[t.Callable[[], None]] = None
        self.on_playback_state_change: t.Optional[t.Callable[[bool], None]] = None

        # Load sequences from storage
        self._load_from_storage()

    # ============================================================================
    # STORAGE METHODS
    # ============================================================================

    def _load_from_storage(self) -> None:
        """Load all sequences from storage file."""
        try:
            if not self.storage_file.exists():
                self._create_empty_storage()
                return

            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "sequences" not in data:
                logger.warning("Invalid storage format, creating new")
                self._create_empty_storage()
                return

            # Parse sequences
            for seq_data in data.get("sequences", []):
                index = tuple(seq_data["index"])
                loop = seq_data.get("loop", True)

                steps = []
                for step_data in seq_data.get("steps", []):
                    step = SequenceStep(
                        scenes=[tuple(s) for s in step_data["scenes"]],
                        duration=step_data.get("duration", 1.0),
                        name=step_data.get("name", ""),
                        duration_unit=self._parse_duration_unit(
                            step_data.get("duration_unit")
                        ),
                    )
                    steps.append(step)

                if steps:
                    self.sequences[index] = steps
                    self.loop_settings[index] = loop

            logger.info(f"Loaded {len(self.sequences)} sequences from storage")

        except Exception as e:
            logger.error(f"Error loading sequences: {e}")
            self._create_empty_storage()

    def _create_empty_storage(self) -> None:
        """Create empty storage file."""
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump({"sequences": []}, f, indent=2)
            logger.info("Created empty sequence storage")
        except Exception as e:
            logger.error(f"Error creating storage: {e}")

    def _save_to_storage(self) -> None:
        """Save all sequences to storage file."""
        try:
            sequences_data = []
            for index, steps in self.sequences.items():
                seq_data = {
                    "index": list(index),
                    "loop": self.loop_settings.get(index, True),
                    "steps": [
                        {
                            "scenes": [list(s) for s in step.scenes],
                            "duration": step.duration,
                            "name": step.name,
                            "duration_unit": step.duration_unit.value,
                        }
                        for step in steps
                    ],
                }
                sequences_data.append(seq_data)

            # Atomic write
            temp_file = self.storage_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump({"sequences": sequences_data}, f, indent=2)
            temp_file.replace(self.storage_file)

            logger.debug(f"Saved {len(sequences_data)} sequences")

        except Exception as e:
            logger.error(f"Error saving sequences: {e}")

    # ============================================================================
    # SEQUENCE MANAGEMENT
    # ============================================================================

    def save_sequence(
        self, index: t.Tuple[int, int], steps: t.List[SequenceStep], loop: bool = True
    ) -> None:
        """Save or update a sequence."""
        if not steps:
            logger.warning(f"Cannot save empty sequence at {index}")
            return

        self.sequences[index] = steps
        self.loop_settings[index] = loop
        self._save_to_storage()

        logger.info(f"Saved sequence {index} with {len(steps)} steps (loop={loop})")

    def get_sequence(
        self, index: t.Tuple[int, int]
    ) -> t.Optional[t.List[SequenceStep]]:
        """Get sequence steps."""
        return self.sequences.get(index)

    def delete_sequence(self, index: t.Tuple[int, int]) -> bool:
        """Delete a sequence."""
        if index in self.sequences:
            # Stop if currently playing
            if self.active_sequence == index:
                self.stop_playback()

            del self.sequences[index]
            self.loop_settings.pop(index, None)
            self._save_to_storage()
            logger.info(f"Deleted sequence {index}")
            return True
        return False

    def get_all_indices(self) -> t.Set[t.Tuple[int, int]]:
        """Get all sequence indices."""
        return set(self.sequences.keys())

    def is_multi_step(self, index: t.Tuple[int, int]) -> bool:
        """Check if sequence has multiple steps (not a simple preset)."""
        sequence = self.sequences.get(index)
        return sequence is not None and len(sequence) > 1

    def get_loop_setting(self, index: t.Tuple[int, int]) -> bool:
        """Get loop setting for a sequence."""
        return self.loop_settings.get(index, True)

    # ============================================================================
    # PLAYBACK CONTROL
    # ============================================================================

    def stop_playback(self) -> None:
        """Stop any active playback and reset state."""
        self.stop_event.set()
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
        self.playback_thread = None
        self.active_sequence = None
        self.current_step_index = 0
        self.playback_state = PlaybackState.PAUSED
        with self._bar_condition:
            self._beats_remaining = None
            self._bar_condition.notify_all()
        self.stop_event.clear()

    def activate_sequence(self, index: t.Tuple[int, int]) -> bool:
        """
        Activate a sequence (switch to it, maintain play/pause state).

        Args:
            index: The sequence to activate
        """
        if index not in self.sequences:
            logger.warning(f"Sequence {index} not found")
            return False

        # Stop any current playback thread
        self.stop_event.set()
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
        self.playback_thread = None

        # Switch to new sequence
        self.active_sequence = index
        self.current_step_index = 0
        self.stop_event.clear()
        with self._bar_condition:
            self._beats_remaining = None
            self._bar_condition.notify_all()

        # Trigger first step
        sequence = self.sequences[index]
        if self.on_step_change:
            self.on_step_change(sequence[0].scenes)

        # Start playback thread if appropriate
        self._start_playback_thread_if_needed()

        logger.debug(f"Activated sequence {index}")
        return True

    def play(self) -> None:
        """Start playing."""
        if self.playback_state == PlaybackState.PLAYING:
            return

        self.playback_state = PlaybackState.PLAYING

        # Notify state change
        if self.on_playback_state_change:
            self.on_playback_state_change(True)

        self._start_playback_thread_if_needed()

        logger.debug("Playback started")

    def pause(self) -> None:
        """Pause playback."""
        if self.playback_state == PlaybackState.PLAYING:
            self.playback_state = PlaybackState.PAUSED

            # Notify state change
            if self.on_playback_state_change:
                self.on_playback_state_change(False)

            logger.debug("Playback paused")

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        if self.playback_state == PlaybackState.PLAYING:
            self.pause()
        else:
            self.play()

    def clear(self) -> None:
        """Clear active sequence (keep play/pause state)."""
        self.stop_event.set()
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
        self.playback_thread = None
        self.stop_event.clear()

        self.active_sequence = None
        self.current_step_index = 0
        with self._bar_condition:
            self._beats_remaining = None
            self._bar_condition.notify_all()

        # Don't change playback state - it stays as is
        logger.debug("Cleared sequence")

    def next_step(self) -> bool:
        """Advance to next step manually."""
        if not self.active_sequence:
            return False

        sequence = self.sequences.get(self.active_sequence)
        if not sequence or len(sequence) <= 1:
            return False

        self.current_step_index = (self.current_step_index + 1) % len(sequence)

        if self.on_step_change:
            self.on_step_change(sequence[self.current_step_index].scenes)
        with self._bar_condition:
            self._beats_remaining = None

        logger.debug(f"Advanced to step {self.current_step_index + 1}/{len(sequence)}")
        return True

    def _start_playback_thread_if_needed(self) -> None:
        """Ensure a playback worker is running when required."""
        if self.playback_state != PlaybackState.PLAYING:
            return
        if not self.active_sequence:
            return

        sequence = self.sequences.get(self.active_sequence)
        if not sequence or len(sequence) <= 1:
            return

        with self._thread_lock:
            if self.playback_thread and self.playback_thread.is_alive():
                return

            self.stop_event.clear()
            self.playback_thread = threading.Thread(
                target=self._playback_loop, daemon=True
            )
            self.playback_thread.start()

    def _playback_loop(self) -> None:
        """Main playback loop (runs in thread)."""
        if not self.active_sequence:
            return

        sequence = self.sequences[self.active_sequence]
        should_loop = self.loop_settings.get(self.active_sequence, True)

        try:
            while not self.stop_event.is_set():
                if self.playback_state == PlaybackState.PAUSED:
                    time.sleep(0.1)
                    continue

                if not (0 <= self.current_step_index < len(sequence)):
                    break

                step = sequence[self.current_step_index]

                if self.on_step_change:
                    try:
                        self.on_step_change(step.scenes)
                    except Exception as e:
                        logger.error(f"Error in step change callback: {e}")

                if step.duration_unit == SequenceDurationUnit.BARS:
                    completed = self._wait_for_bars(step)
                else:
                    completed = self._wait_for_seconds(step)

                if self.stop_event.is_set() or not completed:
                    break

                self.current_step_index += 1

                if self.current_step_index >= len(sequence):
                    if should_loop:
                        self.current_step_index = 0
                    else:
                        if self.on_sequence_complete:
                            try:
                                self.on_sequence_complete()
                            except Exception as e:
                                logger.error(
                                    f"Error in complete callback: {e}"
                                )
                        break
        finally:
            with self._thread_lock:
                self.playback_thread = None
            logger.debug("Playback loop exited")

    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_playback()

    # ------------------------------------------------------------------
    # Duration helpers
    # ------------------------------------------------------------------

    def notify_bar_advanced(self) -> None:
        """Notify the controller that one full bar has elapsed."""
        self.notify_beat_advanced(self._BEATS_PER_BAR)

    def notify_beat_advanced(self, beats: int = 1) -> None:
        """Notify the controller that beats have elapsed for the current step."""
        if beats <= 0:
            return
        if self.playback_state != PlaybackState.PLAYING:
            return
        if not self.active_sequence:
            return

        with self._bar_condition:
            if self._beats_remaining is None or self._beats_remaining <= 0:
                return

            self._beats_remaining = max(0, self._beats_remaining - beats)
            logger.debug(
                "Beat advanced for sequence step; remaining_beats=%s",
                self._beats_remaining,
            )
            if self._beats_remaining <= 0:
                self._bar_condition.notify_all()

    def _wait_for_seconds(self, step: SequenceStep) -> bool:
        end_time = time.time() + step.duration
        while time.time() < end_time and not self.stop_event.is_set():
            if self.playback_state == PlaybackState.PAUSED:
                pause_start = time.time()
                while (
                    self.playback_state == PlaybackState.PAUSED
                    and not self.stop_event.is_set()
                ):
                    time.sleep(0.1)
                if not self.stop_event.is_set():
                    end_time += time.time() - pause_start
            time.sleep(0.1)
        return not self.stop_event.is_set()

    def _wait_for_bars(self, step: SequenceStep) -> bool:
        beats_to_wait = max(
            1, int(round(step.duration * self._BEATS_PER_BAR))
        )
        with self._bar_condition:
            self._beats_remaining = beats_to_wait
        logger.debug(
            "Waiting for %d beats (~%.2f bars) before advancing sequence step",
            beats_to_wait,
            beats_to_wait / self._BEATS_PER_BAR,
        )

        while not self.stop_event.is_set():
            with self._bar_condition:
                if self._beats_remaining is None or self._beats_remaining <= 0:
                    break
                if self.playback_state != PlaybackState.PLAYING:
                    self._bar_condition.wait(timeout=0.1)
                    continue
                self._bar_condition.wait(timeout=0.5)

        with self._bar_condition:
            self._beats_remaining = None

        return not self.stop_event.is_set()

    @staticmethod
    def _parse_duration_unit(raw_value: t.Optional[str]) -> SequenceDurationUnit:
        if not raw_value:
            return SequenceDurationUnit.SECONDS
        try:
            return SequenceDurationUnit(raw_value)
        except ValueError:
            logger.warning(
                "Unknown sequence duration unit '%s', defaulting to seconds",
                raw_value,
            )
            return SequenceDurationUnit.SECONDS
