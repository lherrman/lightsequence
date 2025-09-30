#!/usr/bin/env python3
"""
Launchpad MK2 Light Sequence - RGB Animation System

Clean, minimal Python program for creating beautiful RGB animations
on the Novation Launchpad MK2.

Features:
- Numpy-based RGB animations
- Clean separation of concerns
- Hardware abstraction
- Button controls
- Extensible animation system

Usage:
    python main.py
"""

import logging
import sys
import time
from typing import Optional

from launchpad_controller import LaunchpadController
from rgb_animation_engine import RGBAnimationEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LaunchpadApp:
    """
    Main application class for RGB animations on Launchpad MK2.

    Minimal interface coordinating hardware and animation engine.
    """

    def __init__(self):
        """Initialize the application."""
        self.controller: Optional[LaunchpadController] = None
        self.animation_engine: Optional[RGBAnimationEngine] = None
        self.running = False

        # Animation control
        self.current_animation_index = 0
        self.available_animations = []

    def initialize(self) -> bool:
        """
        Initialize the Launchpad controller and animation engine.

        Returns:
            True if initialization successful
        """
        try:
            # Initialize Launchpad controller
            self.controller = LaunchpadController()

            if not self.controller.connect():
                logger.error("Failed to connect to Launchpad MK2")
                return False

            # Initialize RGB animation engine
            self.animation_engine = RGBAnimationEngine(self.controller.set_grid_rgb)
            self.available_animations = self.animation_engine.get_available_animations()

            # Set up button callbacks
            self.controller.add_button_callback(self._handle_button_press)

            logger.info("Application initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            return False

    def _handle_button_press(self, x: int, y: int, pressed: bool) -> None:
        """Handle button press events for animation control."""
        if not pressed:  # Only handle button press, not release
            return

        logger.info(f"Button pressed: ({x}, {y})")

        # Top row buttons (y=8) control animations
        if y == 8 and 0 <= x < len(self.available_animations):
            animation_name = self.available_animations[x]
            self._start_animation(animation_name)
            logger.info(f"Started animation: {animation_name}")

        # Right column buttons (x=8) for special functions
        elif x == 8:
            if y == 0:  # Stop animation
                self._stop_animation()
                logger.info("Stopped animation")
            elif y == 1:  # Next animation
                self._next_animation()
            elif y == 2:  # Previous animation
                self._previous_animation()
            elif y == 7:  # Exit application
                logger.info("Exit button pressed")
                self.shutdown()

    def _start_animation(self, name: str) -> None:
        """Start an animation by name."""
        if self.animation_engine:
            self.animation_engine.start_animation(name)
            self.interactive_mode = (
                False  # Exit interactive mode when starting animation
            )

    def _stop_animation(self) -> None:
        """Stop current animation."""
        if self.animation_engine:
            self.animation_engine.stop_animation()

    def _next_animation(self) -> None:
        """Start next animation in the list."""
        if not self.available_animations:
            return

        self.current_animation_index = (self.current_animation_index + 1) % len(
            self.available_animations
        )
        animation_name = self.available_animations[self.current_animation_index]
        self._start_animation(animation_name)
        logger.info(f"Next animation: {animation_name}")

    def _previous_animation(self) -> None:
        """Start previous animation in the list."""
        if not self.available_animations:
            return

        self.current_animation_index = (self.current_animation_index - 1) % len(
            self.available_animations
        )
        animation_name = self.available_animations[self.current_animation_index]
        self._start_animation(animation_name)
        logger.info(f"Previous animation: {animation_name}")

    def run(self) -> None:
        """Run the main application loop."""
        if not self.initialize():
            logger.error("Failed to initialize application")
            return

        self.running = True

        try:
            # Start event loop for button handling
            if self.controller is not None:
                self.controller.start_event_loop()

            # Start with first animation
            if self.available_animations:
                self._start_animation(self.available_animations[0])

            logger.info("=== Launchpad MK2 RGB Animation System Started ===")
            logger.info("Controls:")
            logger.info("  Top row: Select animations")
            logger.info("  Right column:")
            logger.info("    Red (top): Stop animation")
            logger.info("    Green: Next animation")
            logger.info("    Orange: Previous animation")
            logger.info("    White (bottom): Exit")
            logger.info("Press Ctrl+C to exit")

            # Main loop - keep application running
            while self.running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Clean shutdown of the application."""
        logger.info("Shutting down application...")
        self.running = False

        if self.animation_engine:
            self.animation_engine.stop_animation()

        if self.controller:
            self.controller.disconnect()

        logger.info("Application shutdown complete")


def main():
    """Main entry point."""
    try:
        app = LaunchpadApp()
        app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
