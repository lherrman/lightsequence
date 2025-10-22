"""
Controller Thread

Manages the LightController in a separate thread to prevent GUI blocking.
"""

import logging
import time
import typing as t

from PySide6.QtCore import QThread, Signal

from lumiblox.controller.light_controller import LightController

logger = logging.getLogger(__name__)


class ControllerThread(QThread):
    """Thread to run the LightController without blocking the GUI."""

    controller_ready = Signal()
    controller_error = Signal(str)

    def __init__(self, simulation: bool = False):
        super().__init__()
        self.controller: t.Optional[LightController] = None
        self.should_stop = False
        self.simulation = simulation

    def run(self):
        """Run the controller in a separate thread."""
        try:
            self.controller = LightController(simulation=self.simulation)
            # Initialize hardware connections (non-blocking)
            self.controller.initialize()
            
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

                    time.sleep(0.02)  # Small delay to prevent excessive CPU usage
                except Exception as e:
                    logger.error(f"Error in controller loop: {e}")
                    # Continue running instead of breaking to prevent crashes
                    time.sleep(0.1)  # Wait a bit longer on error

        except Exception as e:
            self.controller_error.emit(f"Controller error: {e}")
        finally:
            if self.controller:
                self.controller.cleanup()

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
