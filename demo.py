#!/usr/bin/env python3
"""
Launchpad MK2 Animation Demo - Cycles through animations

This demo cycles through different RGB animations. If hardware is available,
use buttons to cycle. Otherwise, it auto-cycles for demonstration.
"""

import logging
import time
from typing import Optional

from launchpad_controller import LaunchpadController
from rgb_animation_engine import RGBAnimationEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AnimationDemo:
    """Demo application that cycles through animations."""

    def __init__(self):
        """Initialize the demo."""
        self.controller: Optional[LaunchpadController] = None
        self.animation_engine: Optional[RGBAnimationEngine] = None
        self.running = False

        # Animation control
        self.current_animation_index = 0
        self.available_animations = []
        self.has_hardware = False

    def initialize(self) -> bool:
        """Initialize the system."""
        try:
            # Try to initialize hardware
            self.controller = LaunchpadController()
            self.has_hardware = self.controller.connect()

            if self.has_hardware:
                logger.info("Hardware connected - use any button to cycle animations")
                # Initialize RGB animation engine with hardware
                self.animation_engine = RGBAnimationEngine(self.controller.set_grid_rgb)
                # Set up button callback for cycling
                self.controller.add_button_callback(self._on_button_press)
            else:
                logger.info("No hardware - running in demo mode with auto-cycling")
                # Initialize with mock function for demo
                self.animation_engine = RGBAnimationEngine(self._mock_set_grid_rgb)

            self.available_animations = self.animation_engine.get_available_animations()
            logger.info(f"Available animations: {self.available_animations}")

            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False

    def _mock_set_grid_rgb(self, rgb_array):
        """Mock function for demo mode."""
        avg_intensity = rgb_array.mean()
        max_intensity = rgb_array.max()
        print(f"Animation frame: avg={avg_intensity:.3f}, max={max_intensity:.3f}")

    def _on_button_press(self, x: int, y: int, pressed: bool) -> None:
        """Handle any button press to cycle animation."""
        if pressed:  # Only on button press, not release
            self._next_animation()
            logger.info(f"Button ({x}, {y}) pressed - cycling animation")

    def _next_animation(self) -> None:
        """Switch to next animation."""
        if not self.available_animations or not self.animation_engine:
            return

        # Cycle to next animation
        self.current_animation_index = (self.current_animation_index + 1) % len(
            self.available_animations
        )
        animation_name = self.available_animations[self.current_animation_index]

        logger.info(
            f"Starting animation {self.current_animation_index + 1}/{len(self.available_animations)}: {animation_name}"
        )
        self.animation_engine.start_animation(animation_name)

    def run_hardware_mode(self) -> None:
        """Run with hardware - wait for button presses."""
        if not self.controller or not self.animation_engine:
            return

        try:
            # Start event loop
            self.controller.start_event_loop()

            # Start first animation
            self._next_animation()

            logger.info("=== Hardware Mode Active ===")
            logger.info("Press any button on the Launchpad to cycle through animations")
            logger.info("Press Ctrl+C to exit")

            # Keep running until interrupted
            while self.running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            if self.animation_engine:
                self.animation_engine.stop_animation()
            if self.controller:
                self.controller.disconnect()

    def run_demo_mode(self) -> None:
        """Run demo mode with auto-cycling."""
        if not self.animation_engine:
            return

        try:
            logger.info("=== Demo Mode Active ===")
            logger.info("Auto-cycling through animations every 5 seconds")
            logger.info("Press Ctrl+C to exit")

            while self.running:
                # Start next animation
                self._next_animation()

                # Wait 5 seconds before cycling
                for _ in range(50):  # 50 * 0.1 = 5 seconds
                    if not self.running:
                        break
                    time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            if self.animation_engine:
                self.animation_engine.stop_animation()

    def run(self) -> None:
        """Run the demo."""
        if not self.initialize():
            logger.error("Failed to initialize demo")
            return

        self.running = True

        try:
            if self.has_hardware:
                self.run_hardware_mode()
            else:
                self.run_demo_mode()
        except Exception as e:
            logger.error(f"Demo error: {e}")
        finally:
            self.running = False
            logger.info("Demo finished")


def main():
    """Main entry point."""
    demo = AnimationDemo()
    try:
        demo.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    main()
