"""
LED Controller

Manages all LED updates for Launchpad.
Centralizes LED logic and prevents duplication.
"""

import logging
import typing as t
from lumiblox.devices.launchpad import LaunchpadMK2, ButtonType as LaunchpadButtonType
from lumiblox.common.config import get_config

logger = logging.getLogger(__name__)


class LEDController:
    """
    Manages all LED displays on the Launchpad.
    
    Responsibilities:
    - Scene button LEDs
    - Sequence button LEDs
    - Control button LEDs
    - Background animations
    """
    
    def __init__(self, launchpad: LaunchpadMK2):
        """Initialize LED controller."""
        self.launchpad = launchpad
        self.config = get_config()
    
    def update_scene_led(self, scene: t.Tuple[int, int], active: bool) -> None:
        """Update LED for a scene button."""
        if not self.launchpad.is_connected:
            return
        
        color = self._get_scene_color(scene, active)
        self.launchpad.set_button_led(
            LaunchpadButtonType.SCENE,
            [scene[0], scene[1]],
            color
        )
    
    def update_sequence_led(self, index: t.Tuple[int, int], active: bool, is_multi_step: bool = False) -> None:
        """Update LED for a sequence button."""
        if not self.launchpad.is_connected:
            return
        
        if active:
            color = self.config.data["colors"]["preset_on"]
        else:
            color = self.config.data["colors"]["off"]
        
        self.launchpad.set_button_led(
            LaunchpadButtonType.PRESET,
            [index[0], index[1]],
            color
        )
    
    def update_control_led(self, coordinates: t.Tuple[int, int], color_key: str) -> None:
        """Update LED for a control button."""
        if not self.launchpad.is_connected:
            return
        
        # Determine button type from coordinates
        button_type = self._get_button_type_for_control(coordinates)
        color = self.config.data["colors"].get(color_key, [0, 0, 0])
        
        self.launchpad.set_button_led(
            button_type,
            [coordinates[0], coordinates[1]],
            color
        )
    
    def update_background(self, animation_type: str, app_state) -> None:
        """Update background animation."""
        if self.launchpad.is_connected:
            self.launchpad.draw_background(animation_type, app_state=app_state)
    
    def clear_sequence_leds(self) -> None:
        """Clear all sequence button LEDs."""
        if not self.launchpad.is_connected:
            return
        
        for x in range(8):
            for y in range(3):
                self.launchpad.set_button_led(
                    LaunchpadButtonType.PRESET,
                    [x, y],
                    self.config.data["colors"]["off"]
                )
    
    def update_sequence_leds_for_save_mode(self, save_mode_type: str, existing_indices: t.Set[t.Tuple[int, int]]) -> None:
        """Update all sequence LEDs for save mode."""
        if not self.launchpad.is_connected:
            return
        
        for x in range(8):
            for y in range(3):
                index = (x, y)
                has_sequence = index in existing_indices
                
                if has_sequence:
                    if save_mode_type == "shift":
                        color = self.config.data["colors"]["preset_save_shift_mode"]
                    else:
                        color = self.config.data["colors"]["preset_save_mode"]
                else:
                    if save_mode_type == "normal":
                        # Show empty slots in save mode
                        from lumiblox.common.utils import hex_to_rgb
                        base_color = hex_to_rgb(
                            self.config.data["colors"]["save_mode_preset_background"]
                        )
                        brightness = self.config.data["brightness_background"]
                        color = [c * brightness for c in base_color]
                    else:
                        color = self.config.data["colors"]["off"]
                
                self.launchpad.set_button_led(
                    LaunchpadButtonType.PRESET,
                    [x, y],
                    color
                )
    
    def flash_success(self, index: t.Tuple[int, int]) -> None:
        """Flash a button green to indicate success."""
        if not self.launchpad.is_connected:
            return
        
        import time
        self.launchpad.set_button_led(
            LaunchpadButtonType.PRESET,
            [index[0], index[1]],
            self.config.data["colors"]["success_flash"]
        )
        time.sleep(0.2)
    
    def _get_scene_color(self, scene: t.Tuple[int, int], active: bool) -> t.List[float]:
        """Get color for a scene LED."""
        if not active:
            return self.config.data["colors"]["off"]
        
        # Use column color if configured
        if self.config.data.get("scene_on_color_from_column", False):
            column_color = self.config.data["colors"]["column_colors"].get(
                str(scene[0])
            )
            if column_color:
                return column_color
        
        return self.config.data["colors"]["scene_on"]
    
    def _get_button_type_for_control(self, coordinates: t.Tuple[int, int]) -> LaunchpadButtonType:
        """Determine Launchpad button type from coordinates."""
        # Top row
        if coordinates[1] == 0:
            return LaunchpadButtonType.TOP
        # Right column
        elif coordinates[0] == 8:
            return LaunchpadButtonType.RIGHT
        # Default to scene
        return LaunchpadButtonType.SCENE
