"""
Controller Thread

Manages the LightController in a separate thread to prevent GUI blocking.
Also manages the PilotController for MIDI clock sync and phrase detection.
"""

import logging
import time
import typing as t
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from lumiblox.controller.light_controller import LightController
from lumiblox.pilot.pilot_controller import PilotController
from lumiblox.common.config import get_config

logger = logging.getLogger(__name__)


class ControllerThread(QThread):
    """Thread to run the LightController without blocking the GUI."""

    controller_ready = Signal()
    controller_error = Signal(str)

    def __init__(self, simulation: bool = False):
        super().__init__()
        self.controller: t.Optional[LightController] = None
        self.pilot_controller: t.Optional[PilotController] = None
        self.should_stop = False
        self.simulation = simulation
        self.pilot_update_callback: t.Optional[t.Callable[[], None]] = None

    def run(self):
        """Run the controller in a separate thread."""
        try:
            self.controller = LightController(simulation=self.simulation)
            # Initialize hardware connections (non-blocking)
            self.controller.initialize()

            # Initialize pilot controller
            self._initialize_pilot()

            # Always emit ready signal - app works without hardware
            self.controller_ready.emit()

            # Modified run loop to work with threading
            logger.info("Light controller started in thread.")

            while not self.should_stop:
                try:
                    # Process inputs
                    self.controller._process_launchpad_input()
                    self.controller._process_midi_feedback()

                    # Update outputs
                    self.controller._update_leds()

                    # Poll pilot controller for MIDI clock
                    if self.pilot_controller:
                        self.pilot_controller.poll()
                        # Trigger GUI update if callback is set
                        if self.pilot_update_callback:
                            self.pilot_update_callback()

                    time.sleep(0.001)  # 1ms for MIDI clock polling
                except Exception as e:
                    logger.error(f"Error in controller loop: {e}")
                    # Continue running instead of breaking to prevent crashes
                    time.sleep(0.1)  # Wait a bit longer on error

        except Exception as e:
            self.controller_error.emit(f"Controller error: {e}")
        finally:
            if self.pilot_controller:
                try:
                    self.pilot_controller.stop()
                except Exception as e:
                    logger.error(f"Error stopping pilot: {e}")
            if self.controller:
                self.controller.cleanup()

    def _initialize_pilot(self) -> None:
        """Initialize the pilot controller with configuration."""
        try:
            config_manager = get_config()
            pilot_config = config_manager.data.get("pilot", {})

            # Always create pilot controller (so GUI can interact with it)
            # but it won't auto-start if disabled in config
            midiclock_device = pilot_config.get("midiclock_device", "midiclock")
            self.pilot_controller = PilotController(
                midiclock_device=midiclock_device,
                on_bpm_change=lambda bpm: logger.info(f"BPM: {bpm:.2f}"),
                on_phrase_type_change=lambda phrase_type: logger.info(
                    f"Phrase type: {phrase_type}"
                ),
            )

            # Configure zero signal if enabled
            zero_signal = pilot_config.get("zero_signal", {})
            if zero_signal.get("enabled", False):
                self.pilot_controller.configure_zero_signal(
                    status=zero_signal.get("status"),
                    data1=zero_signal.get("data1"),
                    data2=zero_signal.get("data2"),
                )

            # Load model and templates
            model_path = pilot_config.get("model_path")
            template_dir = pilot_config.get("template_dir")

            if model_path and Path(model_path).exists():
                self.pilot_controller.load_classifier_model(model_path)
            else:
                logger.warning(f"Model file not found: {model_path}")

            if template_dir and Path(template_dir).exists():
                self.pilot_controller.load_deck_templates(template_dir)
            else:
                logger.warning(f"Template directory not found: {template_dir}")

            # Load deck regions from config
            decks = pilot_config.get("decks", {})
            for deck_name, deck_config in decks.items():
                button_region = deck_config.get("master_button_region")
                timeline_region = deck_config.get("timeline_region")

                if button_region and timeline_region:
                    from lumiblox.pilot.phrase_detector import CaptureRegion

                    button_capture_region = CaptureRegion(
                        x=button_region["x"],
                        y=button_region["y"],
                        width=button_region["width"],
                        height=button_region["height"],
                    )
                    timeline_capture_region = CaptureRegion(
                        x=timeline_region["x"],
                        y=timeline_region["y"],
                        width=timeline_region["width"],
                        height=timeline_region["height"],
                    )

                    self.pilot_controller.configure_deck(
                        deck_name, button_capture_region, timeline_capture_region
                    )
                    logger.info(f"Loaded deck {deck_name} regions from config")

            if pilot_config.get("enabled", False):
                logger.info("Pilot controller initialized (enabled in config)")
            else:
                logger.info(
                    "Pilot controller initialized (disabled in config - enable in GUI to use)"
                )

        except Exception as e:
            logger.error(f"Failed to initialize pilot: {e}")
            self.pilot_controller = None

    def stop(self):
        """Stop the controller thread."""
        self.should_stop = True
        if self.controller:
            try:
                # Clear any callbacks to prevent cross-thread calls during shutdown
                self.controller.on_sequence_changed = None
                self.controller.on_sequence_saved = None
                # Don't call cleanup here - it's called in the thread's run() finally block
            except Exception as e:
                logger.error(f"Error clearing callbacks: {e}")
        self.wait(3000)  # Wait up to 3 seconds for thread to finish
