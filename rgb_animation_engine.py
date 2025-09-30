"""
RGB Animation Engine for Novation Launchpad MK2

This module provides a numpy-based animation system where animations work
with RGB arrays and the controller handles color mapping and discretization.
"""

import time
import threading
import math
import numpy as np
from typing import Callable, Optional, List, Dict
from abc import ABC, abstractmethod
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AnimationState(Enum):
    """Animation states."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


class RGBAnimation(ABC):
    """
    Base class for RGB-based animations.

    Animations work with numpy arrays of RGB values and don't need to worry
    about color mapping or hardware-specific details.
    """

    def __init__(self, name: str, duration: Optional[float] = None):
        """
        Initialize animation.

        Args:
            name: Animation name
            duration: Animation duration in seconds (None for infinite)
        """
        self.name = name
        self.duration = duration
        self.start_time: Optional[float] = None
        self.state = AnimationState.STOPPED

    @abstractmethod
    def update(self, elapsed_time: float) -> np.ndarray:
        """
        Update animation frame.

        Args:
            elapsed_time: Time elapsed since animation start

        Returns:
            RGB array of shape (8, 8, 3) with values 0.0-1.0
        """
        pass

    def start(self) -> None:
        """Start the animation."""
        self.start_time = time.time()
        self.state = AnimationState.RUNNING

    def stop(self) -> None:
        """Stop the animation."""
        self.state = AnimationState.STOPPED
        self.start_time = None

    def pause(self) -> None:
        """Pause the animation."""
        if self.state == AnimationState.RUNNING:
            self.state = AnimationState.PAUSED

    def resume(self) -> None:
        """Resume the animation."""
        if self.state == AnimationState.PAUSED:
            self.state = AnimationState.RUNNING

    def is_finished(self, elapsed_time: float) -> bool:
        """Check if animation is finished based on duration."""
        if self.duration is None:
            return False
        return elapsed_time >= self.duration


class RainbowWaveAnimation(RGBAnimation):
    """Rainbow wave animation using HSV color space."""

    def __init__(
        self,
        duration: Optional[float] = None,
        speed: float = 1.0,
        wave_length: float = 4.0,
    ):
        super().__init__("RainbowWave", duration)
        self.speed = speed
        self.wave_length = wave_length

    def update(self, elapsed_time: float) -> np.ndarray:
        if self.is_finished(elapsed_time):
            return np.zeros((8, 8, 3))

        rgb_array = np.zeros((8, 8, 3))

        for y in range(8):
            for x in range(8):
                # Create wave pattern
                wave_pos = (x + y) / self.wave_length + elapsed_time * self.speed
                hue = (wave_pos % 1.0) * 360  # 0-360 degrees

                # Convert HSV to RGB (H=hue, S=1, V=1)
                h = hue / 60.0
                c = 1.0  # chroma
                x_val = c * (1 - abs((h % 2) - 1))

                if 0 <= h < 1:
                    r, g, b = c, x_val, 0
                elif 1 <= h < 2:
                    r, g, b = x_val, c, 0
                elif 2 <= h < 3:
                    r, g, b = 0, c, x_val
                elif 3 <= h < 4:
                    r, g, b = 0, x_val, c
                elif 4 <= h < 5:
                    r, g, b = x_val, 0, c
                else:  # 5 <= h < 6
                    r, g, b = c, 0, x_val

                rgb_array[y, x] = [r, g, b]

        return rgb_array


class PulseAnimation(RGBAnimation):
    """Pulsing animation with smooth RGB transitions."""

    def __init__(
        self,
        color: tuple = (1.0, 0.0, 0.0),
        duration: Optional[float] = None,
        speed: float = 2.0,
    ):
        super().__init__("Pulse_RGB", duration)
        self.color = np.array(color)  # RGB color as numpy array
        self.speed = speed

    def update(self, elapsed_time: float) -> np.ndarray:
        if self.is_finished(elapsed_time):
            return np.zeros((8, 8, 3))

        # Calculate pulse intensity using sine wave
        intensity = (math.sin(elapsed_time * self.speed) + 1) / 2

        # Create uniform color array with pulsing intensity
        rgb_array = np.zeros((8, 8, 3))
        rgb_array[:, :] = self.color * intensity

        return rgb_array


class WaveAnimation(RGBAnimation):
    """Wave animation spreading from center with smooth RGB falloff."""

    def __init__(
        self,
        color: tuple = (0.0, 1.0, 0.0),
        duration: Optional[float] = None,
        speed: float = 2.0,
    ):
        super().__init__("Wave_RGB", duration)
        self.color = np.array(color)
        self.speed = speed

    def update(self, elapsed_time: float) -> np.ndarray:
        if self.is_finished(elapsed_time):
            return np.zeros((8, 8, 3))

        rgb_array = np.zeros((8, 8, 3))
        center_x, center_y = 3.5, 3.5
        wave_radius = (elapsed_time * self.speed) % 8

        # Create coordinate meshgrid
        y_coords, x_coords = np.mgrid[0:8, 0:8]

        # Calculate distances from center
        distances = np.sqrt((x_coords - center_x) ** 2 + (y_coords - center_y) ** 2)

        # Create wave intensity based on distance from wave radius
        wave_width = 1.5
        intensity = np.maximum(0, 1.0 - np.abs(distances - wave_radius) / wave_width)

        # Apply color with intensity
        for i in range(3):  # R, G, B channels
            rgb_array[:, :, i] = self.color[i] * intensity

        return rgb_array


class SpinAnimation(RGBAnimation):
    """Spinning lines with smooth RGB rendering."""

    def __init__(
        self,
        color: tuple = (0.0, 0.0, 1.0),
        duration: Optional[float] = None,
        speed: float = 1.0,
    ):
        super().__init__("Spin_RGB", duration)
        self.color = np.array(color)
        self.speed = speed

    def update(self, elapsed_time: float) -> np.ndarray:
        if self.is_finished(elapsed_time):
            return np.zeros((8, 8, 3))

        rgb_array = np.zeros((8, 8, 3))
        center_x, center_y = 3.5, 3.5
        angle = elapsed_time * self.speed

        # Create multiple rotating lines
        for line_offset in np.linspace(0, 2 * np.pi, 4, endpoint=False):
            line_angle = angle + line_offset

            # Calculate line points
            for t in np.linspace(-3, 3, 20):
                x = center_x + t * np.cos(line_angle)
                y = center_y + t * np.sin(line_angle)

                # Round to nearest grid position
                grid_x = int(round(x))
                grid_y = int(round(y))

                if 0 <= grid_x < 8 and 0 <= grid_y < 8:
                    # Calculate intensity based on distance from exact position
                    distance = np.sqrt((x - grid_x) ** 2 + (y - grid_y) ** 2)
                    intensity = max(0, 1.0 - distance)

                    # Add to existing value (for overlapping lines)
                    current_intensity = np.linalg.norm(rgb_array[grid_y, grid_x])
                    new_intensity = min(1.0, current_intensity + intensity * 0.5)
                    rgb_array[grid_y, grid_x] = self.color * new_intensity

        return rgb_array


class SparkleAnimation(RGBAnimation):
    """Random sparkle animation with fading."""

    def __init__(
        self,
        duration: Optional[float] = None,
        sparkle_rate: float = 0.1,
        fade_rate: float = 0.95,
    ):
        super().__init__("Sparkle_RGB", duration)
        self.sparkle_rate = sparkle_rate
        self.fade_rate = fade_rate
        self.last_sparkle_time = 0
        self.sparkle_buffer = np.zeros((8, 8, 3))

    def update(self, elapsed_time: float) -> np.ndarray:
        if self.is_finished(elapsed_time):
            return np.zeros((8, 8, 3))

        # Fade existing sparkles
        self.sparkle_buffer *= self.fade_rate

        # Add new sparkles
        if elapsed_time - self.last_sparkle_time > self.sparkle_rate:
            # Add 1-3 new sparkles
            num_sparkles = np.random.randint(1, 4)

            for _ in range(num_sparkles):
                x = np.random.randint(0, 8)
                y = np.random.randint(0, 8)

                # Random bright color
                color = np.random.rand(3)
                color = color / np.linalg.norm(color)  # Normalize to unit length

                self.sparkle_buffer[y, x] = color

            self.last_sparkle_time = elapsed_time

        return self.sparkle_buffer.copy()


class PlasmaAnimation(RGBAnimation):
    """Plasma effect animation."""

    def __init__(self, duration: Optional[float] = None, speed: float = 1.0):
        super().__init__("Plasma", duration)
        self.speed = speed

    def update(self, elapsed_time: float) -> np.ndarray:
        if self.is_finished(elapsed_time):
            return np.zeros((8, 8, 3))

        rgb_array = np.zeros((8, 8, 3))
        t = elapsed_time * self.speed

        # Create coordinate grids
        y, x = np.mgrid[0:8, 0:8]

        # Plasma equations
        plasma1 = np.sin(x * 0.5 + t)
        plasma2 = np.sin(y * 0.7 + t * 1.3)
        plasma3 = np.sin((x + y) * 0.25 + t * 0.8)
        plasma4 = np.sin(np.sqrt(x**2 + y**2) * 0.3 + t * 1.7)

        # Combine plasma patterns
        plasma = (plasma1 + plasma2 + plasma3 + plasma4) / 4.0

        # Convert to RGB using different phase offsets
        rgb_array[:, :, 0] = (np.sin(plasma * 2 * np.pi) + 1) / 2  # Red
        rgb_array[:, :, 1] = (
            np.sin(plasma * 2 * np.pi + 2 * np.pi / 3) + 1
        ) / 2  # Green
        rgb_array[:, :, 2] = (
            np.sin(plasma * 2 * np.pi + 4 * np.pi / 3) + 1
        ) / 2  # Blue

        return rgb_array


class FireAnimation(RGBAnimation):
    """Fire effect animation."""

    def __init__(self, duration: Optional[float] = None, intensity: float = 1.0):
        super().__init__("Fire", duration)
        self.intensity = intensity
        self.noise_buffer = np.random.rand(8, 10)  # Extra rows for fire base

    def update(self, elapsed_time: float) -> np.ndarray:
        if self.is_finished(elapsed_time):
            return np.zeros((8, 8, 3))

        # Shift noise buffer up and add new bottom row
        self.noise_buffer[:-1] = self.noise_buffer[1:]
        self.noise_buffer[-1] = np.random.rand(8) * self.intensity

        # Apply fire algorithm (simplified)
        fire_buffer = np.zeros((8, 8))

        for y in range(8):
            for x in range(8):
                # Average surrounding pixels with bias toward bottom
                total = 0
                count = 0

                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        ny, nx = y + dy + 2, x + dx  # +2 for extra rows
                        if 0 <= ny < 10 and 0 <= nx < 8:
                            weight = 1.5 if dy > 0 else 1.0  # Bias toward bottom
                            total += self.noise_buffer[ny, nx] * weight
                            count += weight

                if count > 0:
                    fire_buffer[y, x] = total / count

                # Cool down as we go up
                fire_buffer[y, x] *= 1.0 - y * 0.1

        # Convert fire intensity to RGB
        rgb_array = np.zeros((8, 8, 3))

        # Fire color mapping: black -> red -> orange -> yellow -> white
        for y in range(8):
            for x in range(8):
                intensity = fire_buffer[y, x]

                if intensity < 0.25:
                    # Black to red
                    rgb_array[y, x] = [intensity * 4, 0, 0]
                elif intensity < 0.5:
                    # Red to orange
                    rgb_array[y, x] = [1.0, (intensity - 0.25) * 2, 0]
                elif intensity < 0.75:
                    # Orange to yellow
                    rgb_array[y, x] = [1.0, 1.0, (intensity - 0.5) * 4]
                else:
                    # Yellow to white
                    white_amount = (intensity - 0.75) * 4
                    rgb_array[y, x] = [1.0, 1.0, 1.0 * white_amount]

        return np.clip(rgb_array, 0, 1)


class RGBAnimationEngine:
    """
    RGB-based animation engine for the Launchpad MK2.

    Animations work with numpy RGB arrays and the engine handles
    hardware communication and color mapping.
    """

    def __init__(self, set_grid_rgb_callback: Callable[[np.ndarray], None]):
        """
        Initialize RGB animation engine.

        Args:
            set_grid_rgb_callback: Function to set entire grid RGB (takes numpy array)
        """
        self.set_grid_rgb_callback = set_grid_rgb_callback

        # Animation state
        self.current_animation: Optional[RGBAnimation] = None
        self.animation_thread: Optional[threading.Thread] = None
        self.running = False
        self.frame_rate = 30  # FPS

        # Built-in RGB animations
        self.animations: Dict[str, Callable] = {
            "rainbow_wave": RainbowWaveAnimation,
            "pulse_red": lambda: PulseAnimation((1.0, 0.0, 0.0)),
            "pulse_green": lambda: PulseAnimation((0.0, 1.0, 0.0)),
            "pulse_blue": lambda: PulseAnimation((0.0, 0.0, 1.0)),
            "pulse_purple": lambda: PulseAnimation((1.0, 0.0, 1.0)),
            "wave_green": lambda: WaveAnimation((0.0, 1.0, 0.0)),
            "wave_blue": lambda: WaveAnimation((0.0, 0.0, 1.0)),
            "wave_cyan": lambda: WaveAnimation((0.0, 1.0, 1.0)),
            "spin_blue": lambda: SpinAnimation((0.0, 0.0, 1.0)),
            "spin_red": lambda: SpinAnimation((1.0, 0.0, 0.0)),
            "spin_white": lambda: SpinAnimation((1.0, 1.0, 1.0)),
            "sparkle": SparkleAnimation,
            "plasma": PlasmaAnimation,
            "fire": FireAnimation,
        }

    def add_animation(self, name: str, animation_class: Callable) -> None:
        """Add a custom animation."""
        self.animations[name] = animation_class

    def get_available_animations(self) -> List[str]:
        """Get list of available animation names."""
        return list(self.animations.keys())

    def start_animation(
        self, name: str, duration: Optional[float] = None, **kwargs
    ) -> bool:
        """Start an animation."""
        if name not in self.animations:
            logger.error(f"Animation '{name}' not found")
            return False

        # Stop current animation
        self.stop_animation()

        try:
            # Create animation instance
            animation_factory = self.animations[name]
            animation = animation_factory(**kwargs)

            # Override duration if specified
            if duration is not None:
                animation.duration = duration

            self.current_animation = animation

            # Start animation thread
            self.running = True
            self.animation_thread = threading.Thread(
                target=self._animation_loop, daemon=True
            )
            self.animation_thread.start()

            logger.info(f"Started RGB animation: {name}")
            return True

        except Exception as e:
            logger.error(f"Error starting animation '{name}': {e}")
            return False

    def stop_animation(self) -> None:
        """Stop current animation."""
        self.running = False

        if self.animation_thread:
            self.animation_thread.join()
            self.animation_thread = None

        if self.current_animation:
            self.current_animation.stop()
            self.current_animation = None

        # Clear all LEDs
        self._clear_grid()
        logger.info("Stopped RGB animation")

    def pause_animation(self) -> None:
        """Pause current animation."""
        if self.current_animation:
            self.current_animation.pause()

    def resume_animation(self) -> None:
        """Resume current animation."""
        if self.current_animation:
            self.current_animation.resume()

    def is_running(self) -> bool:
        """Check if an animation is currently running."""
        return self.running and self.current_animation is not None

    def get_current_animation(self) -> Optional[RGBAnimation]:
        """Get current animation instance."""
        return self.current_animation

    def _clear_grid(self) -> None:
        """Clear the LED grid."""
        empty_grid = np.zeros((8, 8, 3))
        self.set_grid_rgb_callback(empty_grid)

    def _animation_loop(self) -> None:
        """Internal animation loop."""
        if not self.current_animation:
            return

        self.current_animation.start()
        frame_time = 1.0 / self.frame_rate

        while self.running and self.current_animation:
            frame_start = time.time()

            if self.current_animation.state == AnimationState.RUNNING:
                if self.current_animation.start_time is None:
                    continue
                elapsed_time = frame_start - self.current_animation.start_time

                try:
                    # Update animation and get RGB array
                    rgb_array = self.current_animation.update(elapsed_time)

                    # Send to hardware
                    self.set_grid_rgb_callback(rgb_array)

                    # Check if animation is finished
                    if self.current_animation.is_finished(elapsed_time):
                        logger.info(
                            f"RGB Animation '{self.current_animation.name}' finished"
                        )
                        break

                except Exception as e:
                    logger.error(f"Error in RGB animation update: {e}")
                    break

            # Maintain frame rate
            frame_duration = time.time() - frame_start
            sleep_time = max(0, frame_time - frame_duration)
            time.sleep(sleep_time)

        # Clean up
        self.running = False
        if self.current_animation:
            self.current_animation.stop()

    def create_custom_animation(
        self, name: str, update_func: Callable[[float], np.ndarray]
    ) -> None:
        """
        Create a custom animation from an update function.

        Args:
            name: Animation name
            update_func: Function that takes elapsed_time and returns RGB array (8, 8, 3)
        """

        class CustomRGBAnimation(RGBAnimation):
            def __init__(self, update_function):
                super().__init__(name)
                self.update_function = update_function

            def update(self, elapsed_time: float) -> np.ndarray:
                return self.update_function(elapsed_time)

        self.add_animation(name, lambda: CustomRGBAnimation(update_func))
