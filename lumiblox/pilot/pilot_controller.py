"""
Pilot Controller

Main coordinator for MIDI clock sync and phrase detection.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable
from enum import Enum

from lumiblox.pilot.clock_sync import ClockSync
from lumiblox.pilot.phrase_detector import PhraseDetector, CaptureRegion
from lumiblox.pilot.pilot_preset import PilotPresetManager
from lumiblox.pilot.rule_engine import RuleEngine

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
            on_aligned=self._on_aligned,
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
        self.detection_bar = 3  # Detect at 4th bar (0-indexed), start of new phrase
        self.last_detection_phrase = -1
        self.force_next_detection = False  # Flag to force detection on next bar

        # Phrase duration tracking
        self.current_phrase_type: Optional[str] = None
        self.phrase_start_bar: int = 0  # Bar when current phrase started
        self.phrase_bars_elapsed: int = 0  # Bars in current phrase

        # Automation system
        self.preset_manager = PilotPresetManager()
        self.rule_engine: Optional[RuleEngine] = (
            None  # Created when automation is enabled
        )

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
        """Stop the pilot system (keeps MIDI device open for quick restart)."""
        try:
            self.clock_sync.stop()  # Stop processing but keep device open
        except Exception as e:
            logger.error(f"Error stopping clock sync: {e}")

        try:
            self.phrase_detector.close()
        except Exception as e:
            logger.error(f"Error closing phrase detector: {e}")

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

        # Force detection on the very next bar (in controller thread)
        self.force_next_detection = True

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

    def enable_automation(
        self,
        on_sequence_switch: Optional[Callable[[str], None]] = None,
        on_rule_fired: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Enable automation rule engine.

        Args:
            on_sequence_switch: Callback when activating a sequence (string format "x.y")
            on_rule_fired: Callback when a rule fires (receives rule name)
        """
        self.rule_engine = RuleEngine(
            on_sequence_switch=on_sequence_switch,
            on_rule_fired=on_rule_fired,
        )
        logger.info("Automation enabled")

    def disable_automation(self) -> None:
        """Disable automation rule engine."""
        self.rule_engine = None
        logger.info("Automation disabled")

    # Control ---------------------------------------------------------------
    def align_to_beat(self) -> None:
        """Manually align to the current beat."""
        self.clock_sync.align_to_tap()
        # Reset rule cooldowns when re-aligning (bar indices reset)
        if self.rule_engine:
            self.rule_engine.reset_cooldowns()

    def poll(self) -> None:
        """
        Poll for MIDI messages and update state.
        Must be called frequently (e.g., every 1ms).
        """
        if self.state == PilotState.STOPPED:
            return

        self.clock_sync.poll()

    # Internal callbacks ----------------------------------------------------
    def _on_aligned(self) -> None:
        """Internal alignment callback - reset rule cooldowns."""
        if self.rule_engine:
            self.rule_engine.reset_cooldowns()
            logger.debug("Rule cooldowns reset after alignment")

    def _on_beat(self, beat_in_bar: int, bar_index: int, phrase_index: int) -> None:
        """Internal beat callback - triggers phrase detection."""
        # Forward to user callback
        if self.on_beat_callback:
            self.on_beat_callback(beat_in_bar, bar_index, phrase_index)

    def _on_bar(self, bar_index: int) -> None:
        """Internal bar callback - triggers phrase detection."""
        # Update phrase duration tracking
        if self.current_phrase_type:
            self.phrase_bars_elapsed = bar_index - self.phrase_start_bar

        # Update rule engine state
        if self.rule_engine and self.current_phrase_type:
            bars, _ = self.get_phrase_duration()
            self.rule_engine.update_state(self.current_phrase_type, bars, bar_index)

            # Evaluate rules
            active_preset = self.preset_manager.get_active_preset()
            if active_preset:
                self.rule_engine.evaluate_preset(active_preset)

        # Check if we should detect phrase type (at 4th bar / start of new phrase)
        if self.phrase_detection_enabled and self.state == PilotState.FULL:
            bar_in_phrase = bar_index % 4
            phrase_index = bar_index // 4

            # Detect immediately if forced, or at 4th bar (index 3) of each phrase
            should_detect = self.force_next_detection or (
                bar_in_phrase == self.detection_bar
                and phrase_index != self.last_detection_phrase
            )

            if should_detect:
                self.last_detection_phrase = phrase_index
                self.force_next_detection = False
                self.phrase_detector.update_phrase_detection()

        # Forward to user callback
        if self.on_bar_callback:
            self.on_bar_callback(bar_index)

    def _on_phrase(self, phrase_index: int) -> None:
        """Internal phrase callback - commits phrase changes."""
        # Commit phrase change at phrase boundary
        if self.phrase_detection_enabled and self.state == PilotState.FULL:
            old_type = self.current_phrase_type
            self.phrase_detector.commit_phrase_change()
            new_type = self.phrase_detector.get_current_phrase_type()

            # Reset duration tracking if phrase type changed
            if new_type != old_type:
                previous_phrase_bars = self.phrase_bars_elapsed
                self.current_phrase_type = new_type
                current_bar = (
                    self.clock_sync.get_current_position()[2]
                    if self.clock_sync.is_aligned()
                    else 0
                )
                self.phrase_start_bar = current_bar
                self.phrase_bars_elapsed = 0
                logger.info(
                    f"Phrase changed: {old_type} → {new_type}, reset duration tracking"
                )

                if self.rule_engine:
                    self.rule_engine.notify_phrase_change(
                        new_phrase_type=new_type,
                        previous_phrase_type=old_type,
                        previous_phrase_bars=previous_phrase_bars,
                        change_bar=current_bar,
                    )
                    active_preset = self.preset_manager.get_active_preset()
                    if active_preset:
                        self.rule_engine.evaluate_preset(active_preset)

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

    def get_phrase_duration(self) -> tuple[int, int]:
        """
        Get duration of current phrase type.

        Returns:
            Tuple of (bars_elapsed, phrases_elapsed) in current phrase type
        """
        bars = self.phrase_bars_elapsed
        phrases = bars // 4  # Changed from 8 to 4 bars per phrase
        return (bars, phrases)

    def get_detected_phrase_type(self) -> Optional[str]:
        """Get detected next phrase type."""
        return self.phrase_detector.get_detected_phrase_type()

    def get_active_deck(self) -> Optional[str]:
        """Get the currently active deck (if detection is running)."""
        if not self.phrase_detection_enabled:
            return None
        return self.phrase_detector.last_active_deck

    def is_phrase_detection_ready(self) -> bool:
        """Check if phrase detection is ready to use."""
        return self.phrase_detector.is_ready()

    def cleanup(self) -> None:
        """Clean up resources (called on application shutdown)."""
        try:
            self.clock_sync.close()
        except Exception as e:
            logger.error(f"Error closing clock sync: {e}")

        try:
            self.phrase_detector.close()
        except Exception as e:
            logger.error(f"Error closing phrase detector: {e}")

        logger.info("Pilot controller cleaned up")
