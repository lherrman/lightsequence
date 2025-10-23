"""
Pilot Controller

Main coordinator for MIDI clock sync and phrase detection.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Callable
from enum import Enum

from lumiblox.pilot.clock_sync import ClockSync
from lumiblox.pilot.phrase_detector import PhraseDetector, CaptureRegion

logger = logging.getLogger(__name__)


class PilotState(Enum):
    """Pilot operational state."""

    STOPPED = "stopped"
    SYNCING = "syncing"  # Clock sync active, no phrase detection
    FULL = "full"  # Both sync and phrase detection active


class PilotController:
    """Coordinate MIDI clock synchronization and phrase detection."""

    def __init__(
        self,
        midiclock_device: str = "midiclock",
        on_beat: Optional[Callable[[int, int, int], None]] = None,
        on_bar: Optional[Callable[[int], None]] = None,
        on_phrase: Optional[Callable[[int], None]] = None,
        on_phrase_type_change: Optional[Callable[[str], None]] = None,
        on_bpm_change: Optional[Callable[[float], None]] = None,
    ):
        """
        Initialize pilot controller.

        Args:
            midiclock_device: MIDI device keyword for clock sync
            on_beat: Callback for beat events
            on_bar: Callback for bar start events
            on_phrase: Callback for phrase start events
            on_phrase_type_change: Callback when phrase type changes
            on_bpm_change: Callback for BPM updates
        """
        self.state = PilotState.STOPPED

        # Create clock sync
        self.clock_sync = ClockSync(
            device_keyword=midiclock_device,
            on_beat=self._on_beat,
            on_bar=self._on_bar,
            on_phrase=self._on_phrase,
            on_bpm_change=on_bpm_change,
        )

        # Create phrase detector
        self.phrase_detector = PhraseDetector(
            on_phrase_change=on_phrase_type_change,
        )

        # Store callbacks
        self.on_beat_callback = on_beat
        self.on_bar_callback = on_bar
        self.on_phrase_callback = on_phrase

        # Phrase detection state
        self.phrase_detection_enabled = False
        self.detection_bar = 6  # Detect at 7th bar (0-indexed)
        self.last_detection_phrase = -1

    # Lifecycle -------------------------------------------------------------
    def start(self, enable_phrase_detection: bool = False) -> bool:
        """
        Start the pilot system.

        Args:
            enable_phrase_detection: Whether to enable phrase detection

        Returns:
            True if successful, False otherwise
        """
        # Start clock sync
        if not self.clock_sync.open():
            logger.error("Failed to open MIDI clock sync")
            return False

        self.state = PilotState.SYNCING

        # Start phrase detection if requested
        if enable_phrase_detection:
            if not self.enable_phrase_detection():
                logger.warning(
                    "Failed to enable phrase detection, continuing with sync only"
                )

        logger.info(f"Pilot started (state: {self.state.value})")
        return True

    def stop(self) -> None:
        """Stop the pilot system."""
        self.clock_sync.close()
        self.phrase_detector.close()
        self.state = PilotState.STOPPED
        self.phrase_detection_enabled = False
        logger.info("Pilot stopped")

    def enable_phrase_detection(self) -> bool:
        """
        Enable phrase detection.

        Returns:
            True if successful, False otherwise
        """
        if not self.phrase_detector.open():
            logger.error("Failed to open phrase detector")
            return False

        if not self.phrase_detector.is_ready():
            logger.error(
                "Phrase detector not ready (model/templates/regions not configured)"
            )
            return False

        self.phrase_detection_enabled = True
        if self.state == PilotState.SYNCING:
            self.state = PilotState.FULL
        logger.info("Phrase detection enabled")
        return True

    def disable_phrase_detection(self) -> None:
        """Disable phrase detection."""
        self.phrase_detection_enabled = False
        self.phrase_detector.close()
        if self.state == PilotState.FULL:
            self.state = PilotState.SYNCING
        logger.info("Phrase detection disabled")

    # Configuration ---------------------------------------------------------
    def configure_zero_signal(
        self,
        status: Optional[int] = None,
        data1: Optional[int] = None,
        data2: Optional[int] = None,
    ) -> None:
        """Configure MIDI signal for auto-alignment."""
        self.clock_sync.set_zero_signal(status, data1, data2)

    def load_classifier_model(self, model_path: str) -> bool:
        """Load the SVM classifier model."""
        return self.phrase_detector.load_model(model_path)

    def load_deck_templates(self, template_dir: str) -> bool:
        """Load deck button state templates."""
        return self.phrase_detector.load_templates(template_dir)

    def configure_deck(
        self,
        deck_name: str,
        master_button_region: Optional[CaptureRegion] = None,
        timeline_region: Optional[CaptureRegion] = None,
    ) -> None:
        """Configure capture regions for a deck."""
        self.phrase_detector.configure_deck(
            deck_name, master_button_region, timeline_region
        )

    # Control ---------------------------------------------------------------
    def align_to_beat(self) -> None:
        """Manually align to the current beat."""
        self.clock_sync.align_to_tap()

    def poll(self) -> None:
        """
        Poll for MIDI messages and update state.
        Must be called frequently (e.g., every 1ms).
        """
        if self.state == PilotState.STOPPED:
            return

        self.clock_sync.poll()

    # Internal callbacks ----------------------------------------------------
    def _on_beat(self, beat_in_bar: int, bar_index: int, phrase_index: int) -> None:
        """Internal beat callback - triggers phrase detection."""
        # Forward to user callback
        if self.on_beat_callback:
            self.on_beat_callback(beat_in_bar, bar_index, phrase_index)

    def _on_bar(self, bar_index: int) -> None:
        """Internal bar callback - triggers phrase detection."""
        # Check if we should detect phrase type (at 7th bar of phrase)
        if self.phrase_detection_enabled and self.state == PilotState.FULL:
            bar_in_phrase = bar_index % 8
            phrase_index = bar_index // 8

            # Detect at 7th bar (index 6) of each new phrase
            if (
                bar_in_phrase == self.detection_bar
                and phrase_index != self.last_detection_phrase
            ):
                self.last_detection_phrase = phrase_index
                self.phrase_detector.update_phrase_detection()

        # Forward to user callback
        if self.on_bar_callback:
            self.on_bar_callback(bar_index)

    def _on_phrase(self, phrase_index: int) -> None:
        """Internal phrase callback - commits phrase changes."""
        # Commit phrase change at phrase boundary
        if self.phrase_detection_enabled and self.state == PilotState.FULL:
            self.phrase_detector.commit_phrase_change()

        # Forward to user callback
        if self.on_phrase_callback:
            self.on_phrase_callback(phrase_index)

    # Status ----------------------------------------------------------------
    def is_running(self) -> bool:
        """Check if pilot is running."""
        return self.state != PilotState.STOPPED

    def is_aligned(self) -> bool:
        """Check if clock sync is aligned."""
        return self.clock_sync.is_aligned()

    def get_state(self) -> PilotState:
        """Get current pilot state."""
        return self.state

    def get_current_position(self) -> tuple[int, int, int, int]:
        """Get current position (beat_in_bar, bar_in_phrase, bar_index, phrase_index)."""
        return self.clock_sync.get_current_position()

    def get_phrase_progress(self) -> float:
        """Get progress through current phrase (0.0 to 1.0)."""
        return self.clock_sync.get_phrase_progress()

    def get_bpm(self) -> Optional[float]:
        """Get current BPM."""
        return self.clock_sync.get_bpm()

    def get_current_phrase_type(self) -> Optional[str]:
        """Get current phrase type (body/breakdown)."""
        return self.phrase_detector.get_current_phrase_type()

    def get_detected_phrase_type(self) -> Optional[str]:
        """Get detected next phrase type."""
        return self.phrase_detector.get_detected_phrase_type()

    def is_phrase_detection_ready(self) -> bool:
        """Check if phrase detection is ready to use."""
        return self.phrase_detector.is_ready()
