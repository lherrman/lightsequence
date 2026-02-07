"""
Unified Sequence Controller

Manages all sequences (including "presets" which are just 1-step sequences).
Handles playback and state management.
Persists sequences through ProjectDataRepository.
"""

import logging
import random
import threading
import time
import typing as t
from dataclasses import dataclass
from enum import Enum

if t.TYPE_CHECKING:
    from lumiblox.pilot.project_data_repository import ProjectDataRepository

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

    def __init__(self, repository: "ProjectDataRepository"):
        """Initialize sequence controller.
        
        Args:
            repository: ProjectDataRepository for loading/saving sequences
        """
        self.repository = repository
        self.sequences: t.Dict[t.Tuple[int, int], t.List[SequenceStep]] = {}
        self.loop_settings: t.Dict[t.Tuple[int, int], bool] = {}
        self.loop_counts: t.Dict[t.Tuple[int, int], int] = {}
        self.followup_sequences: t.Dict[
            t.Tuple[int, int], t.List[t.Tuple[int, int]]
        ] = {}

        # Playback state
        self.active_sequence: t.Optional[t.Tuple[int, int]] = None
        self.current_step_index: int = 0
        self.playback_state = PlaybackState.PLAYING
        self.playback_thread: t.Optional[threading.Thread] = None
        self._thread_lock = threading.Lock()
        self.stop_event = threading.Event()
        self._bar_condition = threading.Condition()
        self._beats_remaining: t.Optional[int] = None
        self._active_loop_iteration: int = 0

        # Callbacks
        self.on_step_change: t.Optional[
            t.Callable[[t.List[t.Tuple[int, int]]], None]
        ] = None
        self.on_sequence_complete: t.Optional[t.Callable[[], None]] = None
        self.on_playback_state_change: t.Optional[t.Callable[[bool], None]] = None

        # Load sequences from repository
        self.load_from_repository()

    # ============================================================================
    # REPOSITORY PERSISTENCE METHODS
    # ============================================================================

    def load_from_repository(self) -> None:
        """Load all sequences from repository."""
        try:
            data = self.repository.get_sequences()

            if not isinstance(data, dict) or "sequences" not in data:
                logger.warning("Invalid sequences format in repository")
                return

            # Clear existing sequences
            self.sequences.clear()
            self.loop_settings.clear()
            self.loop_counts.clear()
            self.followup_sequences.clear()

            # Parse sequences
            for seq_data in data.get("sequences", []):
                index = tuple(seq_data["index"])
                loop = seq_data.get("loop", True)
                loop_count_raw = seq_data.get("loop_count", 1)
                try:
                    loop_count = max(1, int(loop_count_raw))
                except (TypeError, ValueError):
                    loop_count = 1
                next_sequences = [
                    tuple(candidate)
                    for candidate in seq_data.get("next_sequences", [])
                    if isinstance(candidate, list) and len(candidate) == 2
                ]

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
                    self.loop_counts[index] = loop_count
                    if next_sequences:
                        self.followup_sequences[index] = next_sequences

            logger.info(f"Loaded {len(self.sequences)} sequences from repository")

        except Exception as e:
            logger.error(f"Error loading sequences from repository: {e}")

    def _save_to_repository(self) -> None:
        """Save all sequences to repository."""
        try:
            sequences_data = []
            for index, steps in self.sequences.items():
                index_payload = [int(index[0]), int(index[1])]
                seq_data = {
                    "index": index_payload,
                    "loop": self.loop_settings.get(index, True),
                    "loop_count": int(self.loop_counts.get(index, 1)),
                    "next_sequences": [
                        [int(candidate[0]), int(candidate[1])]
                        for candidate in self.followup_sequences.get(index, [])
                    ],
                    "steps": [
                        {
                            "scenes": [
                                [int(scene[0]), int(scene[1])]
                                for scene in step.scenes
                                if len(scene) >= 2
                            ],
                            "duration": float(step.duration),
                            "name": str(step.name),
                            "duration_unit": step.duration_unit.value,
                        }
                        for step in steps
                    ],
                }
                sequences_data.append(seq_data)

            self.repository.save_sequences({"sequences": sequences_data})
            logger.debug(f"Saved {len(sequences_data)} sequences to repository")

        except Exception as e:
            logger.error(f"Error saving sequences to repository: {e}")

    # ============================================================================
    # SEQUENCE MANAGEMENT
    # ============================================================================

    def save_sequence(
        self,
        index: t.Tuple[int, int],
        steps: t.List[SequenceStep],
        loop: bool = True,
        loop_count: t.Optional[int] = None,
        next_sequences: t.Optional[t.Sequence[t.Tuple[int, int]]] = None,
    ) -> None:
        """Save or update a sequence."""
        if not steps:
            logger.warning(f"Cannot save empty sequence at {index}")
            return

        self.sequences[index] = steps
        self.loop_settings[index] = loop
        if loop_count is not None:
            self.loop_counts[index] = max(1, int(loop_count))
        elif index not in self.loop_counts:
            self.loop_counts[index] = 1
        if next_sequences is not None:
            normalized = self._normalize_followups(next_sequences)
            if normalized:
                self.followup_sequences[index] = normalized
            else:
                self.followup_sequences.pop(index, None)
        self._save_to_repository()

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
            self.loop_counts.pop(index, None)
            self.followup_sequences.pop(index, None)
            self._prune_followup_references(index)
            self._save_to_repository()
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

    def get_loop_count(self, index: t.Tuple[int, int]) -> int:
        """Get loop count for a sequence when not always looping."""
        return max(1, int(self.loop_counts.get(index, 1)))

    def get_followup_sequences(
        self, index: t.Tuple[int, int]
    ) -> t.List[t.Tuple[int, int]]:
        """Get configured follow-up sequences for the given index."""
        return list(self.followup_sequences.get(index, []))

    # ============================================================================
    # PLAYBACK CONTROL
    # ============================================================================

    def stop_playback(self) -> None:
        """Stop any active playback and reset state."""
        self.stop_event.set()
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
        if self.playback_thread and self.playback_thread.is_alive():
            logger.warning("Playback thread did not stop within timeout")
        else:
            self.playback_thread = None
        self.active_sequence = None
        self.current_step_index = 0
        self._active_loop_iteration = 0
        self.playback_state = PlaybackState.PAUSED
        with self._bar_condition:
            self._beats_remaining = None
            self._bar_condition.notify_all()
        if not (self.playback_thread and self.playback_thread.is_alive()):
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
        self._active_loop_iteration = 0
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
        if self.playback_thread and self.playback_thread.is_alive():
            logger.warning("Playback thread did not stop within timeout")
        else:
            self.playback_thread = None
            self.stop_event.clear()

        self.active_sequence = None
        self.current_step_index = 0
        self._active_loop_iteration = 0
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
        queued_sequence: t.Optional[t.Tuple[int, int]] = None
        try:
            while not self.stop_event.is_set():
                if self.playback_state == PlaybackState.PAUSED:
                    time.sleep(0.1)
                    continue

                active_index = self.active_sequence
                if not active_index:
                    break

                sequence = self.sequences.get(active_index)
                if not sequence or len(sequence) <= 0:
                    break

                should_loop = self.loop_settings.get(active_index, True)
                loop_limit = max(1, int(self.loop_counts.get(active_index, 1)))

                if not (0 <= self.current_step_index < len(sequence)):
                    self.current_step_index = 0

                step = sequence[self.current_step_index]

                if self.stop_event.is_set() or self.active_sequence != active_index:
                    break

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
                        continue

                    self._active_loop_iteration += 1
                    if self._active_loop_iteration < loop_limit:
                        self.current_step_index = 0
                        continue

                    if self.on_sequence_complete:
                        try:
                            self.on_sequence_complete()
                        except Exception as e:
                            logger.error(f"Error in complete callback: {e}")

                    queued_sequence = self._select_followup_sequence(active_index)
                    break
        finally:
            with self._thread_lock:
                self.playback_thread = None
            if queued_sequence and not self.stop_event.is_set():
                self._activate_followup_sequence(queued_sequence)
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

    def _normalize_followups(
        self, candidates: t.Sequence[t.Tuple[int, int]]
    ) -> t.List[t.Tuple[int, int]]:
        normalized: t.List[t.Tuple[int, int]] = []
        for candidate in candidates:
            if (
                isinstance(candidate, tuple)
                and len(candidate) == 2
                and all(isinstance(coord, int) for coord in candidate)
            ):
                normalized.append(candidate)
            elif (
                isinstance(candidate, list)
                and len(candidate) == 2
                and all(isinstance(coord, int) for coord in candidate)
            ):
                normalized.append((candidate[0], candidate[1]))
        return normalized

    def _select_followup_sequence(
        self, index: t.Tuple[int, int]
    ) -> t.Optional[t.Tuple[int, int]]:
        candidates = [
            seq
            for seq in self.followup_sequences.get(index, [])
            if seq in self.sequences
        ]
        if not candidates:
            return None
        return random.choice(candidates)

    def _activate_followup_sequence(self, index: t.Tuple[int, int]) -> None:
        sequence = self.sequences.get(index)
        if not sequence:
            logger.debug(
                "Skipping follow-up activation for %s (sequence missing)", index
            )
            return

        logger.info("Automatically activating follow-up sequence %s", index)
        self.active_sequence = index
        self.current_step_index = 0
        self._active_loop_iteration = 0
        self.stop_event.clear()
        with self._bar_condition:
            self._beats_remaining = None
            self._bar_condition.notify_all()

        if self.on_step_change and sequence:
            try:
                self.on_step_change(sequence[0].scenes)
            except Exception as e:
                logger.error(f"Error in step change callback during follow-up: {e}")

        if self.playback_state == PlaybackState.PLAYING:
            self._start_playback_thread_if_needed()

    def _prune_followup_references(self, target: t.Tuple[int, int]) -> None:
        updated: t.Dict[t.Tuple[int, int], t.List[t.Tuple[int, int]]] = {}
        for owner, candidates in self.followup_sequences.items():
            filtered = [seq for seq in candidates if seq != target]
            if filtered:
                updated[owner] = filtered
        self.followup_sequences = updated
        self._save_to_repository()
