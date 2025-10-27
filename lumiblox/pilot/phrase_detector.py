"""
Phrase Detection

Captures screen regions from DJ software to detect deck state and classify
musical phrases as "body" (bass) or "breakdown".
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

import numpy as np
import mss
import cv2 as cv
from PIL import Image
import joblib

logger = logging.getLogger(__name__)

# Constants from training
ANALYZE_WIDTH = 220
ANALYZE_HEIGHT = 88
TRAIN_IMAGE_SIZE = (64, 32)
DECK_BUTTON_SIZE = (32, 32)


@dataclass
class CaptureRegion:
    """Screen capture region definition."""

    x: int
    y: int
    width: int
    height: int

    def to_bbox(self) -> dict:
        """Convert to mss bbox format."""
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class DeckState:
    """Deck state (A, B, C, D)."""

    name: str  # e.g., "A", "B", "C", "D"
    is_master: bool  # Is this deck currently playing (master)?
    master_button_region: Optional[CaptureRegion] = None
    timeline_region: Optional[CaptureRegion] = None


class PhraseDetector:
    """Detect musical phrase type (body/breakdown) from DJ software screen."""

    def __init__(
        self,
        on_phrase_change: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize phrase detector.

        Args:
            on_phrase_change: Callback when phrase type changes: ("body" or "breakdown")
        """
        if mss is None:
            raise RuntimeError("mss library is required for screen capture")
        if cv is None or Image is None:
            raise RuntimeError(
                "opencv-python and Pillow are required for image processing"
            )
        if joblib is None:
            raise RuntimeError("joblib is required for loading SVM model")

        self.on_phrase_change = on_phrase_change
        self.grabber: Optional[mss.mss] = None  # type: ignore
        self.model = None
        self.model_loaded = False

        # Deck configurations
        self.decks = {
            "A": DeckState("A", False),
            "B": DeckState("B", False),
            "C": DeckState("C", False),
            "D": DeckState("D", False),
        }

        # Template images for deck button state detection
        self.template_on: Optional[np.ndarray] = None
        self.template_off: Optional[np.ndarray] = None

        # Current state
        self.current_phrase_type: Optional[str] = None  # "body" or "breakdown"
        self.detected_phrase_type: Optional[str] = None  # Next phrase type to switch to
        self.last_active_deck: Optional[str] = None  # Last detected active deck
        self.last_capture_time = 0.0

    # Setup -----------------------------------------------------------------
    def open(self) -> bool:
        """
        Open screen capture resources.
        Note: mss grabber is created lazily per-thread to avoid threading issues.

        Returns:
            True if successful, False otherwise
        """
        # Don't create grabber here - it will be created on first use
        # This avoids threading issues with mss's thread-local storage
        logger.info("Screen capture initialized (grabber will be created on first use)")
        return True

    def close(self) -> None:
        """Close screen capture resources."""
        if self.grabber:
            try:
                self.grabber.close()
            except Exception as e:
                logger.debug(f"Error closing grabber (may be thread-local): {e}")
            self.grabber = None
        logger.info("Screen capture closed")

    def _ensure_grabber(self) -> bool:
        """
        Ensure grabber is created in the current thread.
        mss uses thread-local storage, so we need to create it in each thread that uses it.

        Returns:
            True if grabber is available, False otherwise
        """
        if self.grabber is None:
            try:
                self.grabber = mss.mss()
                logger.debug("Created mss grabber in current thread")
            except Exception as e:
                logger.error(f"Failed to create screen grabber: {e}")
                return False
        return True

    def load_model(self, model_path: str) -> bool:
        """
        Load the trained SVM classifier model.

        Args:
            model_path: Path to the joblib-serialized model file

        Returns:
            True if successful, False otherwise
        """
        try:
            model_file = Path(model_path)
            if not model_file.exists():
                logger.error(f"Model file not found: {model_path}")
                return False
            self.model = joblib.load(model_path)
            self.model_loaded = True
            logger.info(f"Classifier model loaded from {model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def load_templates(self, template_dir: str) -> bool:
        """
        Load deck button state templates (on.png and off.png).

        Args:
            template_dir: Directory containing on.png and off.png

        Returns:
            True if successful, False otherwise
        """
        try:
            template_path = Path(template_dir)
            on_path = template_path / "on.png"
            off_path = template_path / "off.png"

            if not on_path.exists() or not off_path.exists():
                logger.error(f"Template files not found in {template_dir}")
                return False

            # Load and resize to 32x32
            img_on = cv.imread(str(on_path))
            img_off = cv.imread(str(off_path))

            self.template_on = cv.resize(img_on, DECK_BUTTON_SIZE)
            self.template_off = cv.resize(img_off, DECK_BUTTON_SIZE)

            logger.info(f"Templates loaded from {template_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            return False

    # Configuration ---------------------------------------------------------
    def configure_deck(
        self,
        deck_name: str,
        master_button_region: Optional[CaptureRegion] = None,
        timeline_region: Optional[CaptureRegion] = None,
    ) -> None:
        """
        Configure capture regions for a deck.

        Args:
            deck_name: Deck identifier ("A", "B", "C", "D")
            master_button_region: Screen region for the deck's master button
            timeline_region: Screen region for the deck's timeline
        """
        if deck_name not in self.decks:
            logger.error(f"Invalid deck name: {deck_name}")
            return

        deck = self.decks[deck_name]
        if master_button_region:
            deck.master_button_region = master_button_region
        if timeline_region:
            deck.timeline_region = timeline_region

        logger.info(
            f"Deck {deck_name} configured: "
            f"button={master_button_region is not None}, "
            f"timeline={timeline_region is not None}"
        )

    def clear_deck(self, deck_name: str) -> None:
        """Clear stored capture regions for a deck."""
        if deck_name not in self.decks:
            logger.error(f"Invalid deck name: {deck_name}")
            return

        deck = self.decks[deck_name]
        deck.master_button_region = None
        deck.timeline_region = None
        deck.is_master = False
        logger.info(f"Cleared capture regions for deck {deck_name}")

    # Detection -------------------------------------------------------------
    def detect_active_deck(self) -> Optional[str]:
        """
        Detect which deck is currently the master (playing).
        Captures all decks and selects the one with smallest distance to "on" template.

        Returns:
            Deck name ("A", "B", "C", "D") or None if none detected
        """
        if (
            not self._ensure_grabber()
            or self.template_on is None
            or self.template_off is None
        ):
            return None

        # Capture all decks and calculate distances
        deck_distances = {}

        for deck_name, deck in self.decks.items():
            if deck.master_button_region is None:
                continue

            try:
                # Capture button region
                bbox = deck.master_button_region.to_bbox()
                shot = self.grabber.grab(bbox)  # type: ignore[union-attr]
                img = np.array(shot)

                # Convert BGRA to BGR
                if img.shape[2] == 4:
                    img = cv.cvtColor(img, cv.COLOR_BGRA2BGR)

                # Resize to 32x32 for comparison
                img_resized = cv.resize(img, DECK_BUTTON_SIZE)

                # Calculate distance to "on" template
                dist_on = np.linalg.norm(img_resized - self.template_on)
                deck_distances[deck_name] = dist_on

                # Update deck state (for debugging/info)
                dist_off = np.linalg.norm(img_resized - self.template_off)
                deck.is_master = bool(dist_on < dist_off)

                logger.debug(
                    f"Deck {deck_name}: dist_on={dist_on:.1f}, dist_off={dist_off:.1f}"
                )

            except Exception as e:
                logger.error(f"Error detecting deck {deck_name}: {e}")
                continue

        # Select deck with smallest distance to "on" template
        if not deck_distances:
            logger.warning("No decks could be captured")
            return None

        active_deck = min(deck_distances, key=deck_distances.get)  # type: ignore
        logger.info(
            f"Active deck: {active_deck} (distance: {deck_distances[active_deck]:.1f})"
        )

        # Mark the active deck
        self.decks[active_deck].is_master = True
        for deck_name in deck_distances:
            if deck_name != active_deck:
                self.decks[deck_name].is_master = False

        return active_deck

    def classify_phrase(self, deck_name: Optional[str] = None) -> Optional[str]:
        """
        Classify the current phrase type for the given deck.

        Args:
            deck_name: Deck to analyze, or None to auto-detect

        Returns:
            "body" or "breakdown", or None if classification failed
        """
        if not self.model_loaded or not self._ensure_grabber():
            logger.warning("Model or grabber not initialized")
            return None

        # Auto-detect active deck if not specified
        if deck_name is None:
            deck_name = self.detect_active_deck()
            if deck_name is None:
                logger.warning("No active deck detected")
                return None
            logger.info(f"Detected active deck: {deck_name}")

        # Store the active deck
        self.last_active_deck = deck_name

        deck = self.decks.get(deck_name)
        if deck is None or deck.timeline_region is None:
            logger.warning(f"Deck {deck_name} not configured")
            return None

        try:
            start = time.perf_counter()

            # Capture timeline region
            bbox = deck.timeline_region.to_bbox()
            shot = self.grabber.grab(bbox)  # type: ignore[union-attr]
            img = np.array(shot)

            # Convert BGRA to BGR
            if img.shape[2] == 4:
                img = cv.cvtColor(img, cv.COLOR_BGRA2BGR)

            # Convert to RGB
            img_rgb = cv.cvtColor(img, cv.COLOR_BGR2RGB)

            # Resize to training size
            img_pil = Image.fromarray(img_rgb).resize(TRAIN_IMAGE_SIZE)

            # Convert to feature vector (same format as training)
            features = np.asarray(img_pil, dtype=np.float32).reshape(-1) / 255.0

            # Predict
            prediction = self.model.predict(features.reshape(1, -1))[0]  # type: ignore[union-attr]
            result = "breakdown" if prediction == 1 else "body"

            elapsed = time.perf_counter() - start
            self.last_capture_time = elapsed

            logger.info(
                f"Deck {deck_name} → {result.upper()} (took {elapsed * 1000:.1f}ms)"
            )
            return result

        except Exception as e:
            logger.error(f"Error classifying phrase for deck {deck_name}: {e}")
            return None

    def update_phrase_detection(self) -> Optional[str]:
        """
        Detect and update the phrase type.
        Should be called at the 8th bar (start of new phrase).

        Returns:
            The detected phrase type, or None if detection failed
        """
        logger.info("Running phrase detection...")
        result = self.classify_phrase()
        if result:
            self.detected_phrase_type = result
            logger.info(f"✓ Phrase detected as: {result.upper()}")
        else:
            logger.warning("⚠ Phrase detection failed - no result")
        return result

    def commit_phrase_change(self) -> None:
        """
        Commit the detected phrase change (call at phrase boundary).
        Triggers the on_phrase_change callback if the phrase type changed.
        """
        if (
            self.detected_phrase_type
            and self.detected_phrase_type != self.current_phrase_type
        ):
            self.current_phrase_type = self.detected_phrase_type
            logger.info(f"Phrase changed to: {self.current_phrase_type}")
            if self.on_phrase_change:
                self.on_phrase_change(self.current_phrase_type)

    # Status ----------------------------------------------------------------
    def get_current_phrase_type(self) -> Optional[str]:
        """Get the current phrase type."""
        return self.current_phrase_type

    def get_detected_phrase_type(self) -> Optional[str]:
        """Get the detected next phrase type."""
        return self.detected_phrase_type

    def is_configured(self) -> bool:
        """Check if at least one deck is fully configured."""
        return any(
            deck.master_button_region is not None and deck.timeline_region is not None
            for deck in self.decks.values()
        )

    def is_ready(self) -> bool:
        """Check if detector is ready to use."""
        # Note: grabber is created lazily, so we don't check for it here
        return (
            self.model_loaded
            and self.template_on is not None
            and self.template_off is not None
            and self.is_configured()
        )
