"""
Centralized MIDI Subsystem Manager  (mido + python-rtmidi)

Provides thread-safe port management with automatic reconnection for the
mido/rtmidi backend.  Replaces the old pygame.midi-based MidiManager.

All port open/close operations go through this manager so that error
handling, reconnection logic, and logging are consistent across the
application (LightSoftware, ClockSync, etc.).

Usage::

    from lumiblox.midi.midi_manager import midi_manager

    # Open a port by keyword (substring match, case-insensitive)
    port = midi_manager.open_input_by_keyword("lightsoftware_out")
    port = midi_manager.open_output_by_keyword("lightsoftware_in")

    # Close a single port safely
    midi_manager.close_port(port)

    # Application-level shutdown
    midi_manager.shutdown()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional, List

import mido
import mido.ports

# Force the rtmidi backend (best latency / stability on Windows)
mido.set_backend("mido.backends.rtmidi")

logger = logging.getLogger(__name__)


class MidiManager:
    """Thread-safe MIDI port manager built on *mido* + *python-rtmidi*."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._open_ports: List = []
        self._ports_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Port discovery helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_input_names() -> List[str]:
        """Return available MIDI input port names."""
        try:
            return mido.get_input_names()
        except Exception as exc:
            logger.error("Failed to list MIDI input ports: %s", exc)
            return []

    @staticmethod
    def get_output_names() -> List[str]:
        """Return available MIDI output port names."""
        try:
            return mido.get_output_names()
        except Exception as exc:
            logger.error("Failed to list MIDI output ports: %s", exc)
            return []

    @staticmethod
    def find_port_name(keyword: str, names: List[str]) -> Optional[str]:
        """Find first port name containing *keyword* (case-insensitive).

        Args:
            keyword: Substring to match against available port names.
            names:   List of port names (from ``get_input_names`` etc.).

        Returns:
            The full port name, or ``None`` if no match.
        """
        keyword_lower = keyword.lower()
        for name in names:
            if keyword_lower in name.lower():
                return name
        return None

    # ------------------------------------------------------------------
    # Port open helpers
    # ------------------------------------------------------------------

    def open_input_by_keyword(self, keyword: str) -> Optional[mido.ports.BaseInput]:
        """Open a MIDI input port whose name contains *keyword*.

        Returns:
            An open ``mido`` input port, or ``None`` on failure.
        """
        with self.lock:
            name = self.find_port_name(keyword, self.get_input_names())
            if name is None:
                logger.warning("No MIDI input port matching '%s'", keyword)
                return None
            try:
                port = mido.open_input(name)
                self._track_port(port)
                logger.info("Opened MIDI input: %s", name)
                return port
            except (IOError, OSError) as exc:
                logger.error("Failed to open MIDI input '%s': %s", name, exc)
                return None

    def open_output_by_keyword(self, keyword: str) -> Optional[mido.ports.BaseOutput]:
        """Open a MIDI output port whose name contains *keyword*.

        Returns:
            An open ``mido`` output port, or ``None`` on failure.
        """
        with self.lock:
            name = self.find_port_name(keyword, self.get_output_names())
            if name is None:
                logger.warning("No MIDI output port matching '%s'", keyword)
                return None
            try:
                port = mido.open_output(name)
                self._track_port(port)
                logger.info("Opened MIDI output: %s", name)
                return port
            except (IOError, OSError) as exc:
                logger.error("Failed to open MIDI output '%s': %s", name, exc)
                return None

    def open_input(self, name: str) -> Optional[mido.ports.BaseInput]:
        """Open a MIDI input port by exact *name*."""
        with self.lock:
            try:
                port = mido.open_input(name)
                self._track_port(port)
                logger.info("Opened MIDI input: %s", name)
                return port
            except (IOError, OSError) as exc:
                logger.error("Failed to open MIDI input '%s': %s", name, exc)
                return None

    def open_output(self, name: str) -> Optional[mido.ports.BaseOutput]:
        """Open a MIDI output port by exact *name*."""
        with self.lock:
            try:
                port = mido.open_output(name)
                self._track_port(port)
                logger.info("Opened MIDI output: %s", name)
                return port
            except (IOError, OSError) as exc:
                logger.error("Failed to open MIDI output '%s': %s", name, exc)
                return None

    # ------------------------------------------------------------------
    # Port close / shutdown
    # ------------------------------------------------------------------

    def close_port(self, port) -> None:
        """Safely close a single mido port (input or output).

        Sends an all-notes-off panic on output ports before closing to
        avoid stuck notes.
        """
        if port is None:
            return
        try:
            if not getattr(port, "closed", True):
                # If it's an output port, silence all channels first
                if hasattr(port, "send"):
                    try:
                        port.panic()
                    except Exception:
                        pass
                port.close()
                logger.debug("Closed MIDI port: %s", getattr(port, "name", "?"))
        except Exception as exc:
            logger.debug("Error closing MIDI port: %s", exc)
        finally:
            self._untrack_port(port)

    def shutdown(self) -> None:
        """Final application-level shutdown – close all tracked ports.

        Output ports receive an all-notes-off panic before close to prevent
        stuck notes.  A brief sleep gives USB drivers time to flush.
        """
        with self._ports_lock:
            ports_to_close = list(self._open_ports)
            self._open_ports.clear()
        for port in ports_to_close:
            try:
                if not getattr(port, "closed", True):
                    if hasattr(port, "send"):
                        try:
                            port.panic()
                        except Exception:
                            pass
                    port.close()
            except Exception as exc:
                logger.debug("Error during shutdown port close: %s", exc)
        # Brief pause so USB/loopMIDI driver buffers can flush
        time.sleep(0.05)
        logger.info("MIDI manager shut down (all ports closed)")

    # ------------------------------------------------------------------
    # Port health / reconnect utilities
    # ------------------------------------------------------------------

    @staticmethod
    def is_port_alive(port) -> bool:
        """Return ``True`` if the port is open and usable."""
        if port is None:
            return False
        return not getattr(port, "closed", True)

    def reconnect_input(
        self, keyword: str, old_port, *, max_attempts: int = 3, delay: float = 0.5
    ) -> Optional[mido.ports.BaseInput]:
        """Attempt to reconnect an input port with retries.

        Closes the *old_port* first, then tries to re-open by keyword.

        Returns:
            A new open port, or ``None`` after all retries fail.
        """
        self.close_port(old_port)
        for attempt in range(1, max_attempts + 1):
            port = self.open_input_by_keyword(keyword)
            if port is not None:
                logger.info("Reconnected MIDI input '%s' (attempt %d)", keyword, attempt)
                return port
            logger.debug(
                "Reconnect attempt %d/%d for input '%s' failed",
                attempt, max_attempts, keyword,
            )
            time.sleep(delay)
        return None

    def reconnect_output(
        self, keyword: str, old_port, *, max_attempts: int = 3, delay: float = 0.5
    ) -> Optional[mido.ports.BaseOutput]:
        """Attempt to reconnect an output port with retries."""
        self.close_port(old_port)
        for attempt in range(1, max_attempts + 1):
            port = self.open_output_by_keyword(keyword)
            if port is not None:
                logger.info("Reconnected MIDI output '%s' (attempt %d)", keyword, attempt)
                return port
            logger.debug(
                "Reconnect attempt %d/%d for output '%s' failed",
                attempt, max_attempts, keyword,
            )
            time.sleep(delay)
        return None

    # ------------------------------------------------------------------
    # Reliable send helper
    # ------------------------------------------------------------------

    def safe_send(
        self,
        port,
        msg: "mido.Message",
        *,
        retries: int = 2,
        retry_delay: float = 0.005,
    ) -> bool:
        """Send a MIDI message with automatic retry on transient errors.

        Args:
            port:  An open ``mido`` output port.
            msg:   The ``mido.Message`` to send.
            retries: Number of retry attempts after the first failure.
            retry_delay: Seconds to wait between retries.

        Returns:
            ``True`` if the message was sent successfully, ``False`` otherwise.
        """
        if port is None or getattr(port, "closed", True):
            logger.warning("safe_send: port is None or closed – message dropped")
            return False

        last_exc: Optional[Exception] = None
        for attempt in range(1 + retries):
            try:
                port.send(msg)
                return True
            except (IOError, OSError) as exc:
                last_exc = exc
                if attempt < retries:
                    logger.debug(
                        "safe_send retry %d/%d after %s", attempt + 1, retries, exc
                    )
                    time.sleep(retry_delay)

        logger.error("safe_send failed after %d attempts: %s", 1 + retries, last_exc)
        return False

    # ------------------------------------------------------------------
    # Internal bookkeeping
    # ------------------------------------------------------------------

    def _track_port(self, port) -> None:
        with self._ports_lock:
            self._open_ports.append(port)

    def _untrack_port(self, port) -> None:
        with self._ports_lock:
            try:
                self._open_ports.remove(port)
            except ValueError:
                pass


# Module-level singleton
midi_manager = MidiManager()
