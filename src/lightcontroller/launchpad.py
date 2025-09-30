"""
Launchpad MK2 abstraction layer
Provides clean interface for lighting control and button handling
"""

import logging
from typing import Optional, Callable, Tuple, List
from enum import IntEnum

try:
    import launchpad_py as lp

    LAUNCHPAD_AVAILABLE = True
except ImportError:
    LAUNCHPAD_AVAILABLE = False
    lp = None
    logging.warning("launchpad_py not available - hardware control disabled")

logger = logging.getLogger(__name__)


class LaunchpadColor(IntEnum):
    """Launchpad color values."""

    OFF = 0
    RED_LOW = 1
    RED_MID = 2
    RED_FULL = 3
    GREEN_LOW = 16
    GREEN_MID = 32
    GREEN_FULL = 48
    AMBER_LOW = 17
    AMBER_MID = 34
    AMBER_FULL = 51
    YELLOW_LOW = 33
    YELLOW_MID = 50
    YELLOW_FULL = 67


class LaunchpadMK2:
    """
    Abstraction layer for Novation Launchpad MK2

    Layout:
    - 8x5 Scene buttons (rows 0-4, y=1 to y=5 in launchpad coordinates)
    - 8x3 Preset buttons (rows 5-7, y=6 to y=8 in launchpad coordinates)
    """

    def __init__(self):
        self.device = None
        self.button_callback: Optional[Callable[[int, int, bool], None]] = None
        self.is_connected = False
        self.button_states = {}  # Track current button states to prevent duplicate events

    def connect(self) -> bool:
        """Connect to Launchpad MK2 hardware."""
        if not LAUNCHPAD_AVAILABLE:
            logger.warning("launchpad_py not available")
            return False

        try:
            self.device = lp.LaunchpadMk2()
            if self.device.Open():
                self.device.Reset()  # Clear all LEDs
                self.is_connected = True
                logger.info("Connected to Launchpad MK2")
                return True
            else:
                logger.warning("Could not open Launchpad MK2")
                return False
        except Exception as e:
            logger.error(f"Launchpad connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from Launchpad."""
        if self.device:
            try:
                self.device.Reset()  # Clear all LEDs
                self.device.Close()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self.device = None
                self.is_connected = False
                logger.info("Disconnected from Launchpad")

    def set_button_callback(self, callback: Callable[[int, int, bool], None]):
        """
        Set callback for button presses.

        Args:
            callback: Function(x, y, pressed) where:
                - x, y: Button coordinates (0-7)
                - pressed: True if pressed, False if released
        """
        self.button_callback = callback

    def poll_buttons(self):
        """
        Poll for button presses using MK2-specific pattern.
        
        MK2 ButtonStateRaw() returns integers with this pattern:
        - Button press: note -> 127 (velocity confirmation)
        - Button release: note -> 0 (release signal)
        
        We only send events for actual button presses, ignore releases.
        """
        if not self.device or not self.is_connected or not self.button_callback:
            return

        try:
            buttons = self.device.ButtonStateRaw()
            if not buttons:
                return
                
            for button_data in buttons:
                if not isinstance(button_data, int):
                    continue
                    
                note = button_data
                logger.info(f"🎹 Raw MIDI event: {note}")
                
                # Filter based on MK2 event pattern from test_minimal.py:
                # Press: note -> 127, Release: note -> 0
                if note == 127:
                    # Velocity confirmation event - ignore
                    logger.debug("Ignoring velocity confirmation (127)")
                    continue
                elif note == 0:
                    # Release signal - send release events for all pressed buttons
                    logger.info("🔄 Button release signal (0) - sending release events")
                    if self.button_callback:
                        for (x, y) in list(self.button_states.keys()):
                            logger.info(f"🔻 Button RELEASE: ({x}, {y})")
                            self.button_callback(x, y, False)
                    self.button_states.clear()
                    continue
                elif 1 <= note <= 120:  # Valid button range (includes Record Arm button 104)
                    # Convert MIDI note to grid coordinates
                    x, y = self._midi_note_to_xy(note)
                    logger.info(f"🎯 MIDI note {note} -> coordinates ({x}, {y})")
                    # Special handling for Record Arm button which maps to (-1, -1)
                    if x is not None and y is not None:
                        button_key = (x, y)
                        if button_key not in self.button_states:
                            # First press - send event
                            self.button_states[button_key] = True
                            logger.info(f"✅ Button PRESS confirmed: note {note} -> ({x}, {y})")
                            self.button_callback(x, y, True)  # Always True for press
                        # Ignore subsequent events for same button until release
                # Ignore invalid notes

        except Exception as e:
            logger.error(f"Error polling buttons: {e}")

    def _midi_note_to_xy(self, note: int) -> Tuple[Optional[int], Optional[int]]:
        """
        Convert MIDI note to grid coordinates based on MK2 layout.

        MK2 Layout (RAW mode):
        - Main 8x8 grid: rows 11-18, 21-28, 31-38, 41-48, 51-58, 61-68, 71-78, 81-88
        - Y coordinate 0 = bottom row (11-18), Y coordinate 7 = top row (81-88)
        """
        # Main 8x8 grid
        if 11 <= note <= 18:  # Bottom row (y=7 in our 0-7 system, flipped)
            return note - 11, 7
        elif 21 <= note <= 28:  # Second from bottom (y=6)
            return note - 21, 6
        elif 31 <= note <= 38:  # Third from bottom (y=5)
            return note - 31, 5
        elif 41 <= note <= 48:  # Middle row (y=4)
            return note - 41, 4
        elif 51 <= note <= 58:  # Fifth row (y=3)
            return note - 51, 3
        elif 61 <= note <= 68:  # Sixth row (y=2)
            return note - 61, 2
        elif 71 <= note <= 78:  # Seventh row (y=1)
            return note - 71, 1
        elif 81 <= note <= 88:  # Top row (y=0)
            return note - 81, 0

        # Top row control buttons
        elif note == 104:  # Record Arm button
            return -1, -1  # Special coordinates for Record Arm
        elif note in [105, 106, 107, 108, 109, 110, 111]:
            # Map to top area outside main grid - we'll ignore these for now
            return None, None

        # Right column control buttons (track control)
        elif note in [89, 79, 69, 59, 49, 39, 29, 19]:
            # Map to right area outside main grid - we'll ignore these for now
            return None, None

        return None, None

    def _xy_to_midi_note(self, x: int, y: int) -> Optional[int]:
        """
        Convert grid coordinates to MIDI note based on MK2 layout.

        Args:
            x: Column (0-7)
            y: Row (0-7, where 0=top, 7=bottom in visual representation)
        """
        if not (0 <= x <= 7 and 0 <= y <= 7):
            return None

        # Map our visual coordinates to MIDI notes
        # y=0 (top visual) = note 81+x (top physical row)
        # y=7 (bottom visual) = note 11+x (bottom physical row)
        if y == 0:  # Top row
            return 81 + x
        elif y == 1:
            return 71 + x
        elif y == 2:
            return 61 + x
        elif y == 3:
            return 51 + x
        elif y == 4:
            return 41 + x
        elif y == 5:
            return 31 + x
        elif y == 6:
            return 21 + x
        elif y == 7:  # Bottom row
            return 11 + x

        return None

    def light_scene_button(
        self, x: int, y: int, color: LaunchpadColor = LaunchpadColor.GREEN_FULL
    ):
        """
        Light up a scene button (rows 0-4).

        Args:
            x: Column (0-7)
            y: Row (0-4 for scenes)
            color: Color to display
        """
        if not (0 <= x <= 7 and 0 <= y <= 4):
            logger.warning(f"Invalid scene button coordinates: ({x}, {y})")
            return

        self._set_led(x, y, color)

    def light_preset_button(
        self, x: int, y: int, color: LaunchpadColor = LaunchpadColor.AMBER_FULL
    ):
        """
        Light up a preset button (rows 5-7).

        Args:
            x: Column (0-7)
            y: Row (5-7 for presets, but pass 0-2 here)
            color: Color to display
        """
        if not (0 <= x <= 7 and 0 <= y <= 2):
            logger.warning(f"Invalid preset button coordinates: ({x}, {y})")
            return

        # Map to actual preset rows (5-7)
        actual_y = y + 5
        self._set_led(x, actual_y, color)

    def clear_scene_button(self, x: int, y: int):
        """Clear a scene button."""
        self.light_scene_button(x, y, LaunchpadColor.OFF)

    def clear_preset_button(self, x: int, y: int):
        """Clear a preset button."""
        self.light_preset_button(x, y, LaunchpadColor.OFF)

    def clear_all(self):
        """Clear all buttons."""
        if self.device and self.is_connected:
            try:
                self.device.Reset()
            except Exception as e:
                logger.error(f"Error clearing display: {e}")

    def light_programmed_presets(self, programmed_indices: List[int], color: LaunchpadColor = LaunchpadColor.YELLOW_FULL):
        """Light up all programmed preset buttons."""
        for preset_idx in programmed_indices:
            if 0 <= preset_idx <= 23:  # 24 presets total (0-23)
                # Convert preset index to x,y coordinates
                x = preset_idx % 8
                y = preset_idx // 8  # This gives 0-2 for the three preset rows
                self.light_preset_button(x, y, color)
                logger.debug(f"Lit preset button {preset_idx+1} at ({x}, {y})")

    def clear_all_preset_buttons(self):
        """Clear all preset buttons."""
        for preset_idx in range(24):  # 24 presets total
            x = preset_idx % 8
            y = preset_idx // 8
            self.clear_preset_button(x, y)

    def light_record_arm_button(self, color: LaunchpadColor = LaunchpadColor.RED_FULL):
        """Light up the Record Arm button."""
        if self.device and self.is_connected:
            try:
                # Record Arm button is MIDI note 104
                self.device.LedCtrlRaw(104, color.value, color.value)
                logger.debug(f"Lit Record Arm button with color {color}")
            except Exception as e:
                logger.error(f"Error lighting Record Arm button: {e}")

    def clear_record_arm_button(self):
        """Clear the Record Arm button."""
        self.light_record_arm_button(LaunchpadColor.OFF)

    def _set_led(self, x: int, y: int, color: LaunchpadColor):
        """Set LED at grid position."""
        if not self.device or not self.is_connected:
            return

        try:
            # Convert grid coordinates to MIDI note using proper mapping
            note = self._xy_to_midi_note(x, y)
            if note is None:
                logger.warning(f"Invalid coordinates for LED: ({x}, {y})")
                return

            # Use RGB LED control for MK2 (more accurate colors)
            # Convert LaunchpadColor to RGB values
            r, g, b = self._color_to_rgb(color)
            self.device.LedCtrlRaw(note, r, g, b)
        except Exception as e:
            logger.error(f"Error setting LED at ({x}, {y}): {e}")

    def _color_to_rgb(self, color: LaunchpadColor) -> Tuple[int, int, int]:
        """Convert LaunchpadColor to RGB values (0-63 range for MK2)."""
        if color == LaunchpadColor.OFF:
            return 0, 0, 0
        elif color == LaunchpadColor.RED_LOW:
            return 15, 0, 0
        elif color == LaunchpadColor.RED_MID:
            return 31, 0, 0
        elif color == LaunchpadColor.RED_FULL:
            return 63, 0, 0
        elif color == LaunchpadColor.GREEN_LOW:
            return 0, 15, 0
        elif color == LaunchpadColor.GREEN_MID:
            return 0, 31, 0
        elif color == LaunchpadColor.GREEN_FULL:
            return 0, 63, 0
        elif color == LaunchpadColor.AMBER_LOW:
            return 15, 7, 0
        elif color == LaunchpadColor.AMBER_MID:
            return 31, 15, 0
        elif color == LaunchpadColor.AMBER_FULL:
            return 63, 31, 0
        elif color == LaunchpadColor.YELLOW_LOW:
            return 15, 15, 0
        elif color == LaunchpadColor.YELLOW_MID:
            return 31, 31, 0
        elif color == LaunchpadColor.YELLOW_FULL:
            return 63, 63, 0
        else:
            return 31, 31, 31  # Default to dim white

    def set_grid_rgb(self, grid: List[List[Tuple[int, int, int]]]):
        """
        Set entire 8x8 grid with RGB colors.

        Args:
            grid: 8x8 list of (r, g, b) tuples, values 0-255
        """
        if not self.device or not self.is_connected:
            return

        try:
            # Set each LED using direct RGB values
            for y in range(8):
                for x in range(8):
                    if y < len(grid) and x < len(grid[y]):
                        r, g, b = grid[y][x]
                        # Convert 0-255 RGB to 0-63 range for MK2
                        r_scaled = int(r * 63 / 255)
                        g_scaled = int(g * 63 / 255)
                        b_scaled = int(b * 63 / 255)

                        note = self._xy_to_midi_note(x, y)
                        if note is not None:
                            self.device.LedCtrlRaw(note, r_scaled, g_scaled, b_scaled)
        except Exception as e:
            logger.error(f"Error setting RGB grid: {e}")

    def scene_midi_note_from_index(self, index: int) -> Optional[int]:
        """Get MIDI note for scene index."""
        coords = self.scene_coords_from_index(index)
        if coords:
            return self._xy_to_midi_note(coords[0], coords[1])
        return None

    def preset_midi_note_from_index(self, index: int) -> Optional[int]:
        """Get MIDI note for preset index."""
        coords = self.preset_coords_from_index(index)
        if coords:
            return self._xy_to_midi_note(coords[0], coords[1])
        return None

    def midi_note_to_scene_index(self, note: int) -> Optional[int]:
        """Convert MIDI note to scene index."""
        x, y = self._midi_note_to_xy(note)
        if x is not None and y is not None and self.is_scene_button(x, y):
            return self.get_scene_index(x, y)
        return None

    def midi_note_to_preset_index(self, note: int) -> Optional[int]:
        """Convert MIDI note to preset index."""
        x, y = self._midi_note_to_xy(note)
        if x is not None and y is not None and self.is_preset_button(x, y):
            return self.get_preset_index(x, y)
        return None

    def is_scene_button(self, x: int, y: int) -> bool:
        """Check if coordinates are for a scene button."""
        return 0 <= x <= 7 and 0 <= y <= 4

    def is_preset_button(self, x: int, y: int) -> bool:
        """Check if coordinates are for a preset button."""
        return 0 <= x <= 7 and 5 <= y <= 7
        
    def is_record_arm_button(self, x: int, y: int) -> bool:
        """Check if coordinates are for the Record Arm button."""
        return x == -1 and y == -1

    def get_scene_index(self, x: int, y: int) -> Optional[int]:
        """Get linear scene index from coordinates."""
        if self.is_scene_button(x, y):
            return y * 8 + x
        return None

    def get_preset_index(self, x: int, y: int) -> Optional[int]:
        """Get linear preset index from coordinates."""
        if self.is_preset_button(x, y):
            return (y - 5) * 8 + x
        return None

    def scene_coords_from_index(self, index: int) -> Optional[Tuple[int, int]]:
        """Get scene coordinates from linear index."""
        if 0 <= index < 40:  # 8x5 = 40 scene buttons
            y = index // 8
            x = index % 8
            return (x, y)
        return None

    def preset_coords_from_index(self, index: int) -> Optional[Tuple[int, int]]:
        """Get preset coordinates from linear index."""
        if 0 <= index < 24:  # 8x3 = 24 preset buttons
            y = index // 8 + 5  # Preset rows start at y=5
            x = index % 8
            return (x, y)
        return None

    def play_rgb_effect(self, effect_name: str = "wave", duration: float = 2.0):
        """
        Play RGB effects on the Launchpad.

        Args:
            effect_name: Name of effect ("wave", "pulse", "rainbow", "chase")
            duration: Duration in seconds
        """
        if not self.is_connected:
            return

        import time
        import math

        steps = int(duration * 20)  # 20 FPS

        for step in range(steps):
            grid = []

            for y in range(8):
                row = []
                for x in range(8):
                    if effect_name == "wave":
                        # Sine wave across the grid
                        phase = (x + y + step * 0.5) * 0.5
                        r = int(127 + 127 * math.sin(phase))
                        g = int(127 + 127 * math.sin(phase + 2))
                        b = int(127 + 127 * math.sin(phase + 4))
                    elif effect_name == "pulse":
                        # Pulsing from center
                        center_x, center_y = 3.5, 3.5
                        dist = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                        phase = dist - step * 0.3
                        intensity = int(127 + 127 * math.sin(phase))
                        r = intensity if step % 60 < 20 else 0
                        g = intensity if 20 <= step % 60 < 40 else 0
                        b = intensity if step % 60 >= 40 else 0
                    elif effect_name == "rainbow":
                        # Rainbow effect
                        hue = (x * 40 + y * 20 + step * 10) % 360
                        if hue < 60:
                            r, g, b = 255, int(255 * hue / 60), 0
                        elif hue < 120:
                            r, g, b = int(255 * (120 - hue) / 60), 255, 0
                        elif hue < 180:
                            r, g, b = 0, 255, int(255 * (hue - 120) / 60)
                        elif hue < 240:
                            r, g, b = 0, int(255 * (240 - hue) / 60), 255
                        elif hue < 300:
                            r, g, b = int(255 * (hue - 240) / 60), 0, 255
                        else:
                            r, g, b = 255, 0, int(255 * (360 - hue) / 60)
                    elif effect_name == "chase":
                        # Chasing light
                        chase_pos = (step // 3) % 64
                        linear_pos = y * 8 + x
                        if linear_pos == chase_pos:
                            r, g, b = 255, 255, 255
                        elif abs(linear_pos - chase_pos) == 1:
                            r, g, b = 100, 100, 100
                        else:
                            r, g, b = 0, 0, 0
                    else:
                        r, g, b = 0, 0, 0

                    row.append((r, g, b))
                grid.append(row)

            self.set_grid_rgb(grid)
            time.sleep(0.05)  # 20 FPS

        # Clear at the end
        self.clear_all()
