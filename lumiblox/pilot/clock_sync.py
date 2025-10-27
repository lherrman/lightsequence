"""
MIDI Clock Synchronization

Listens to MIDI clock pulses and tracks beats, bars, and phrases.
Supports manual tap alignment and MIDI signal-based alignment.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Deque, Optional, Tuple, Callable
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame.midi

from lumiblox.pilot.midi_actions import MidiActionHandler

logger = logging.getLogger(__name__)

# MIDI Constants
MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_CONTINUE = 0xFB
MIDI_STOP = 0xFC
PULSES_PER_QUARTER = 24
BEATS_PER_BAR = 4
BARS_PER_PHRASE = 4  # Changed from 8 to 4 bars per phrase


class ClockSync:
    """Synchronize to MIDI clock and announce bar/phrase boundaries."""

    def __init__(
        self,
        device_keyword: str,
        on_beat: Optional[Callable[[int, int, int], None]] = None,
        on_bar: Optional[Callable[[int], None]] = None,
        on_phrase: Optional[Callable[[int], None]] = None,
        on_bpm_change: Optional[Callable[[float], None]] = None,
        on_aligned: Optional[Callable[[], None]] = None,
        on_midi_message: Optional[Callable[[list], None]] = None,
    ):
        """
        Initialize clock sync.

        Args:
            device_keyword: Substring to match MIDI input device name (case-insensitive)
            on_beat: Callback for beat events: (beat_in_bar, bar_index, phrase_index)
            on_bar: Callback for bar start events: (bar_index)
            on_phrase: Callback for phrase start events: (phrase_index)
            on_bpm_change: Callback for BPM updates: (bpm)
            on_aligned: Callback when alignment happens (manual or automatic)
        """
        if pygame is None:
            raise RuntimeError("pygame.midi is required for MIDI clock monitoring")

        self.device_keyword = device_keyword.lower()
        self.device_id: Optional[int] = None
        self.device_name: Optional[str] = None
        self.midi_in: Optional[pygame.midi.Input] = None  # type: ignore
        self.is_open = False
        self.is_active = False  # Whether to process clock messages

        # Callbacks
        self.on_beat = on_beat
        self.on_bar = on_bar
        self.on_phrase = on_phrase
        self.on_bpm_change = on_bpm_change
        self.on_aligned = on_aligned
        self.on_midi_message = on_midi_message

        # State tracking
        self.total_pulses = 0
        self.pulses: Deque[Tuple[int, float]] = deque(maxlen=256)
        self.zero_pulse: Optional[int] = None
        self.last_bar: Optional[int] = None
        self.last_phrase: Optional[int] = None
        self.last_beat_time: Optional[float] = None
        self.beat_intervals: Deque[float] = deque(maxlen=16)
        self.current_bpm: Optional[float] = None

        # MIDI action handler for configurable MIDI message actions
        self.midi_action_handler = MidiActionHandler()

        # Register default MIDI action callback
        from lumiblox.pilot.midi_actions import MidiActionType

        self.midi_action_handler.register_callback(
            MidiActionType.PHRASE_SYNC, lambda _: self.align_to_tap()
        )

        # Legacy zero signal configuration (for backward compatibility)
        self.zero_signal_status: Optional[int] = None
        self.zero_signal_data1: Optional[int] = None
        self.zero_signal_data2: Optional[int] = None

    # Setup -----------------------------------------------------------------
    def open(self) -> bool:
        """
        Open the MIDI device connection.

        Returns:
            True if successful, False otherwise
        """
        try:
            # If already open, just resume
            if self.is_open and self.midi_in:
                self.is_active = True
                logger.info("MIDI clock resumed")
                return True

            # Only init if not already initialized (shared subsystem)
            if not pygame.midi.get_init():
                pygame.midi.init()

            self.device_id, self.device_name = self._find_device()
            if self.device_id is None:
                logger.error(f"No MIDI input matching '{self.device_keyword}' found")
                return False
            self.midi_in = pygame.midi.Input(self.device_id)
            self.is_open = True
            self.is_active = True
            logger.info(
                f"Listening for MIDI clock on '{self.device_name}' (device {self.device_id})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to open MIDI device: {e}")
            return False

    def stop(self) -> None:
        """Pause processing MIDI clock (keep device open)."""
        self.is_active = False
        self._reset_alignment()
        logger.info("MIDI clock paused")

    def close(self) -> None:
        """Close the MIDI device connection (only called on shutdown)."""
        self.is_active = False
        if self.midi_in:
            try:
                self.midi_in.close()
            except AttributeError as e:
                # Handle pygame threading issues during shutdown
                logger.debug(
                    f"AttributeError closing MIDI input (likely threading): {e}"
                )
            except Exception as e:
                logger.error(f"Error closing MIDI input: {e}")
            self.midi_in = None

        self.is_open = False
        self.device_id = None
        logger.info("MIDI clock connection closed")

    def _find_device(self) -> Tuple[Optional[int], Optional[str]]:
        """Find MIDI input device matching the keyword."""
        for idx in range(pygame.midi.get_count()):
            info = pygame.midi.get_device_info(idx)
            if not info:
                continue
            _interface, name, is_input, _is_output, _opened = info
            if not is_input:
                continue
            decoded = name.decode() if isinstance(name, bytes) else str(name)
            if self.device_keyword in decoded.lower():
                return idx, decoded
        return None, None

    # Configuration ---------------------------------------------------------
    def set_zero_signal(
        self,
        status: Optional[int] = None,
        data1: Optional[int] = None,
        data2: Optional[int] = None,
    ) -> None:
        """
        Configure MIDI signal that triggers alignment.

        Args:
            status: MIDI status byte (e.g., 0x90 for note on)
            data1: MIDI data byte 1 (e.g., note number)
            data2: MIDI data byte 2 (e.g., velocity), None to ignore
        """
        self.zero_signal_status = status
        self.zero_signal_data1 = data1
        self.zero_signal_data2 = data2
        logger.info(
            f"Zero signal configured: status={status:02X}, data1={data1}, data2={data2}"
        )

    # MIDI Processing -------------------------------------------------------
    def poll(self) -> None:
        """Poll for MIDI messages. Call this frequently (e.g., every 1ms)."""
        if not self.midi_in or not self.is_open or not self.is_active:
            return

        while self.midi_in.poll():
            for data, _timestamp in self.midi_in.read(128):
                if not data or isinstance(data, int):
                    continue
                status = data[0]
                if status == MIDI_CLOCK:
                    self._on_clock()
                elif status in {MIDI_START, MIDI_CONTINUE, MIDI_STOP}:
                    self._reset_alignment()
                    if self.on_midi_message:
                        self.on_midi_message(data)
                else:
                    if self.on_midi_message:
                        self.on_midi_message(data)
                    # Check for MIDI actions (including legacy zero signal)
                    if self._is_zero_signal(data):
                        self.align_to_tap()
                    # Process through action handler
                    self.midi_action_handler.process_midi_message(data)

    def _is_zero_signal(self, data: list) -> bool:
        """Check if MIDI message matches configured zero signal."""
        if self.zero_signal_status is None:
            return False
        if data[0] != self.zero_signal_status:
            return False
        if self.zero_signal_data1 is not None and len(data) > 1:
            if data[1] != self.zero_signal_data1:
                return False
        if self.zero_signal_data2 is not None and len(data) > 2:
            if data[2] != self.zero_signal_data2:
                return False
        return True

    def _on_clock(self) -> None:
        """Handle MIDI clock pulse."""
        now = time.perf_counter()
        self.total_pulses += 1
        self.pulses.append((self.total_pulses, now))

        if self.zero_pulse is None:
            return

        relative = self.total_pulses - self.zero_pulse
        if relative >= 0 and relative % PULSES_PER_QUARTER == 0:
            self._on_beat_internal(now)
            beat_index = relative // PULSES_PER_QUARTER
            self._announce_beat(beat_index)

    # Alignment -------------------------------------------------------------
    def align_to_tap(self) -> None:
        """Align to the current time (snap to nearest beat)."""
        if not self.pulses:
            logger.warning("No MIDI clock pulses yet, cannot align")
            return

        now = time.perf_counter()
        nearest_index, nearest_time = min(
            self.pulses, key=lambda item: abs(item[1] - now)
        )
        offset = nearest_index % PULSES_PER_QUARTER
        self.zero_pulse = nearest_index - offset
        self.last_bar = None
        self.last_phrase = None
        self.last_beat_time = None
        self.beat_intervals.clear()
        self.current_bpm = None

        logger.info("Aligned to MIDI beat; bar/phrase counting active")

        # Notify alignment callback
        if self.on_aligned:
            self.on_aligned()

        self._announce_beat(0)

        if abs(nearest_time - now) > 0.05:
            logger.debug("Tap was between beats; snapped to closest beat")

    def _reset_alignment(self) -> None:
        """Reset alignment (triggered by MIDI start/continue/stop)."""
        self.zero_pulse = None
        self.last_bar = None
        self.last_phrase = None
        self.last_beat_time = None
        self.beat_intervals.clear()
        self.current_bpm = None
        logger.info("Alignment cleared")

    # Beat / Phrase ---------------------------------------------------------
    def _on_beat_internal(self, timestamp: float) -> None:
        """Track beat timing for BPM calculation."""
        if self.last_beat_time is not None:
            interval = timestamp - self.last_beat_time
            if interval > 0:
                self.beat_intervals.append(interval)
                avg_interval = sum(self.beat_intervals) / len(self.beat_intervals)
                bpm = 60.0 / avg_interval
                if self.current_bpm is None or abs(bpm - self.current_bpm) >= 0.5:
                    self.current_bpm = bpm
                    if self.on_bpm_change:
                        self.on_bpm_change(bpm)
                    logger.debug(f"BPM: {bpm:.2f}")
        self.last_beat_time = timestamp

    def _announce_beat(self, beat_index: int) -> None:
        """Announce beat, bar, and phrase events."""
        bar_index = beat_index // BEATS_PER_BAR
        beat_in_bar = beat_index % BEATS_PER_BAR
        phrase_index = bar_index // BARS_PER_PHRASE

        # Fire beat callback
        if self.on_beat:
            self.on_beat(beat_in_bar, bar_index, phrase_index)

        # Check for bar boundary
        if beat_in_bar == 0 and bar_index != self.last_bar:
            self.last_bar = bar_index
            if self.on_bar:
                self.on_bar(bar_index)
            logger.debug(f"Bar {bar_index + 1} start")

            # Check for phrase boundary
            if bar_index % BARS_PER_PHRASE == 0:
                if phrase_index != self.last_phrase:
                    self.last_phrase = phrase_index
                    if self.on_phrase:
                        self.on_phrase(phrase_index)
                    logger.debug(f"Phrase {phrase_index + 1} start")

    # Status ----------------------------------------------------------------
    def is_aligned(self) -> bool:
        """Check if sync is aligned."""
        return self.zero_pulse is not None

    def get_current_position(self) -> Tuple[int, int, int, int]:
        """
        Get current position in the music.

        Returns:
            Tuple of (beat_in_bar, bar_in_phrase, bar_index, phrase_index)
            Returns (0, 0, 0, 0) if not aligned
        """
        if self.zero_pulse is None or not self.pulses:
            return 0, 0, 0, 0

        relative = self.total_pulses - self.zero_pulse
        beat_index = relative // PULSES_PER_QUARTER
        bar_index = beat_index // BEATS_PER_BAR
        phrase_index = bar_index // BARS_PER_PHRASE
        beat_in_bar = beat_index % BEATS_PER_BAR
        bar_in_phrase = bar_index % BARS_PER_PHRASE

        return beat_in_bar, bar_in_phrase, bar_index, phrase_index

    def get_phrase_progress(self) -> float:
        """
        Get progress through current phrase (0.0 to 1.0).

        Returns:
            Progress as a fraction (0.0 at phrase start, 1.0 at end)
        """
        if self.zero_pulse is None:
            return 0.0

        relative = self.total_pulses - self.zero_pulse
        beat_index = relative // PULSES_PER_QUARTER
        bar_in_phrase = (beat_index // BEATS_PER_BAR) % BARS_PER_PHRASE
        beat_in_bar = beat_index % BEATS_PER_BAR

        total_beats_in_phrase = BARS_PER_PHRASE * BEATS_PER_BAR
        current_beat_in_phrase = bar_in_phrase * BEATS_PER_BAR + beat_in_bar

        return current_beat_in_phrase / total_beats_in_phrase

    def get_bpm(self) -> Optional[float]:
        """Get current BPM."""
        return self.current_bpm
