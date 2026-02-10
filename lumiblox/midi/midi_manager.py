"""
Centralized MIDI Subsystem Manager

Provides reference-counted init/quit for pygame.midi and a shared lock
so that multiple components (LightSoftware, ClockSync, etc.) can safely
share the same underlying PortMidi backend without stepping on each other.

Usage::

    from lumiblox.midi.midi_manager import midi_manager

    midi_manager.acquire()        # ref-counted init
    # ... open ports, do work ...
    midi_manager.release()        # ref-counted; only calls quit() when last user releases

    with midi_manager.lock:       # serialize access to pygame.midi from different threads
        port = pygame.midi.Output(device_id)
"""

import logging
import threading
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame.midi

logger = logging.getLogger(__name__)


class MidiManager:
    """Thread-safe, reference-counted wrapper around ``pygame.midi.init/quit``."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._ref_count = 0
        self._ref_lock = threading.Lock()  # protects _ref_count

    # ------------------------------------------------------------------
    # Reference-counted init / quit
    # ------------------------------------------------------------------

    def acquire(self) -> None:
        """Increment reference count and initialise pygame.midi if needed."""
        with self._ref_lock:
            if self._ref_count == 0:
                with self.lock:
                    if not pygame.midi.get_init():
                        pygame.midi.init()
                        logger.info("pygame.midi initialised (first acquire)")
            self._ref_count += 1
            logger.debug("MidiManager acquired (ref_count=%d)", self._ref_count)

    def release(self) -> None:
        """Decrement reference count.  Does **not** call ``pygame.midi.quit()``
        automatically – that is reserved for :meth:`shutdown` at application exit
        to avoid pulling the rug from under other components."""
        with self._ref_lock:
            if self._ref_count > 0:
                self._ref_count -= 1
            logger.debug("MidiManager released (ref_count=%d)", self._ref_count)

    def ensure_init(self) -> None:
        """Make sure pygame.midi is initialised (idempotent, no ref-count change).

        Useful inside reconnect paths where you just want to be sure the
        subsystem is alive but don't want to bump the ref count again.
        """
        with self.lock:
            if not pygame.midi.get_init():
                pygame.midi.init()
                logger.info("pygame.midi re-initialised (ensure_init)")

    def shutdown(self) -> None:
        """Final application-level shutdown.  Always quits pygame.midi."""
        with self._ref_lock:
            self._ref_count = 0
        with self.lock:
            try:
                if pygame.midi.get_init():
                    pygame.midi.quit()
                    logger.info("pygame.midi shut down")
            except Exception as exc:
                logger.error("Error during pygame.midi shutdown: %s", exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def close_port(self, port) -> None:
        """Safely close a single pygame.midi Input or Output port."""
        if port is None:
            return
        with self.lock:
            try:
                port.close()
            except Exception as exc:
                logger.debug("Error closing MIDI port: %s", exc)


# Module-level singleton
midi_manager = MidiManager()
