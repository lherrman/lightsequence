"""Count bars and 8-bar phrases from a MIDI clock with a manual tap align."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import time
from collections import deque
from typing import Deque, Optional, Tuple

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import pygame.midi
except ImportError as exc:  # pragma: no cover - environment dependent
    raise RuntimeError("pygame.midi is required for MIDI clock monitoring") from exc


MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_CONTINUE = 0xFB
MIDI_STOP = 0xFC
PULSES_PER_QUARTER = 24
BEATS_PER_BAR = 4
BARS_PER_PHRASE = 8


class ClockCounter:
    """Align to a MIDI clock and announce bar / phrase boundaries."""

    def __init__(self, device_keyword: str) -> None:
        self.device_keyword = device_keyword.lower()
        self.device_id: Optional[int] = None
        self.device_name: Optional[str] = None
        self.midi_in: Optional[pygame.midi.Input] = None

        self.total_pulses = 0
        self.pulses: Deque[Tuple[int, float]] = deque(maxlen=256)
        self.zero_pulse: Optional[int] = None
        self.last_bar: Optional[int] = None
        self.last_phrase: Optional[int] = None
        self.last_beat_time: Optional[float] = None
        self.beat_intervals: Deque[float] = deque(maxlen=16)
        self.last_bpm: Optional[float] = None

    # Setup -----------------------------------------------------------------
    def open(self) -> None:
        pygame.midi.init()
        self.device_id, self.device_name = self._find_device()
        if self.device_id is None:
            raise RuntimeError(f"No MIDI input matching '{self.device_keyword}' found")
        self.midi_in = pygame.midi.Input(self.device_id)
        print(
            f"Listening for MIDI clock on '{self.device_name}' (device {self.device_id})"
        )

    def close(self) -> None:
        if self.midi_in:
            self.midi_in.close()
        pygame.midi.quit()

    def _find_device(self) -> Tuple[Optional[int], Optional[str]]:
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

    # MIDI ------------------------------------------------------------------
    def poll(self) -> None:
        if not self.midi_in:
            return
        while self.midi_in.poll():
            for data, _timestamp in self.midi_in.read(128):
                if not data:
                    continue
                status = data[0]
                if status == MIDI_CLOCK:
                    self._on_clock()
                elif status in {MIDI_START, MIDI_CONTINUE, MIDI_STOP}:
                    self._reset_alignment()

    def _on_clock(self) -> None:
        now = time.perf_counter()
        self.total_pulses += 1
        self.pulses.append((self.total_pulses, now))

        if self.zero_pulse is None:
            return

        relative = self.total_pulses - self.zero_pulse
        if relative >= 0 and relative % PULSES_PER_QUARTER == 0:
            self._on_beat(now)
            beat_index = relative // PULSES_PER_QUARTER
            self._announce_beat(beat_index)

    # Alignment --------------------------------------------------------------
    def align_to_tap(self) -> None:
        if not self.pulses:
            print("No MIDI clock pulses yet")
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
        self.last_bpm = None
        print("Aligned to MIDI beat; bar/phrase counting active")
        self._announce_beat(0)
        if abs(nearest_time - now) > 0.05:
            print("(tap was between beats; snapped to closest beat)")

    def _reset_alignment(self) -> None:
        self.zero_pulse = None
        self.last_bar = None
        self.last_phrase = None
        self.last_beat_time = None
        self.beat_intervals.clear()
        self.last_bpm = None
        print("Alignment cleared")

    # Beat / phrase ---------------------------------------------------------
    def _on_beat(self, timestamp: float) -> None:
        if self.last_beat_time is not None:
            interval = timestamp - self.last_beat_time
            if interval > 0:
                self.beat_intervals.append(interval)
                avg_interval = sum(self.beat_intervals) / len(self.beat_intervals)
                bpm = 60.0 / avg_interval
                if self.last_bpm is None or abs(bpm - self.last_bpm) >= 0.5:
                    self.last_bpm = bpm
                    print(f"BPM: {bpm:.2f}")
        self.last_beat_time = timestamp

    def _announce_beat(self, beat_index: int) -> None:
        bar_index = beat_index // BEATS_PER_BAR
        beat_in_bar = beat_index % BEATS_PER_BAR

        if beat_in_bar == 0 and bar_index != self.last_bar:
            self.last_bar = bar_index
            print(f"Bar {bar_index + 1} start")
            if bar_index % BARS_PER_PHRASE == 0:
                phrase_index = bar_index // BARS_PER_PHRASE
                if phrase_index != self.last_phrase:
                    self.last_phrase = phrase_index
                    print(f"Phrase {phrase_index + 1} start")
        elif beat_in_bar != 0:
            print(f"  Beat {beat_in_bar + 1} of bar {bar_index + 1}")

    # Run loop --------------------------------------------------------------
    async def run(self) -> None:
        self.open()
        tap_task: Optional[asyncio.Task[None]] = None
        try:
            tap_task = asyncio.create_task(self._listen_for_taps())
            print("Press Enter on the downbeat to align.")
            while True:
                self.poll()
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:  # pragma: no cover - manual shutdown
            raise
        finally:
            if tap_task is not None:
                tap_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tap_task
            self.close()

    async def _listen_for_taps(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.to_thread(input)
            loop.call_soon(self.align_to_tap)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count bars from a MIDI clock")
    parser.add_argument(
        "--device",
        default="midiclock",
        help="Substring of the MIDI input device name (case-insensitive)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counter = ClockCounter(args.device)
    try:
        asyncio.run(counter.run())
    except KeyboardInterrupt:
        print("Stopped by user")


if __name__ == "__main__":
    main()
    # Run loop -----------------------------------------------------------
