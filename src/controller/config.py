import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Colors:
    """LED color definitions."""

    OFF = [0.0, 0.0, 0.0]
    SAVE_MODE_ON = [1.0, 0.0, 0.5]
    SAVE_MODE_OFF = [0.0, 0.0, 0.0]
    BACKGROUND_CYCLE = [0.0, 1.0, 0.0]
    SUCCESS_FLASH = [0.0, 1.0, 0.0]
    YELLOW_BRIGHT = [1.0, 1.0, 0.0]
    PLAYBACK_PLAYING = [0.0, 1.0, 0.0]
    PLAYBACK_PAUSED = [1.0, 0.5, 0.0]
    NEXT_STEP = [0.0, 0.5, 1.0]
    CONNECTION_GOOD = [0.0, 0.3, 0.0]
    CONNECTION_BAD = [0.3, 0.0, 0.0]

    SCENE_ON: List[float]
    PRESET_ON: List[float]
    PRESET_SAVE_MODE: List[float]
    PRESET_SAVE_SHIFT_MODE: List[float]
    PRESETS_BACKGROUND_COLOR: List[float]
    COLUMN_COLORS: Dict[int, List[float]]

    def __init__(self, config_data: Dict[str, Any]):
        """Initialize colors from config data."""
        # Get colors from nested structure or fallback to root level (backward compatibility)
        colors_data = config_data.get("colors", config_data)

        self.SCENE_ON = self._hex_to_rgb(colors_data.get("scene_on_color", "#00ff00"))
        self.PRESET_ON = self._hex_to_rgb(colors_data.get("preset_on_color", "#ff0050"))
        self.PRESET_SAVE_MODE = self._hex_to_rgb(
            colors_data.get("preset_save_mode_color", "#ff0080")
        )
        self.PRESET_SAVE_SHIFT_MODE = self._hex_to_rgb(
            colors_data.get("preset_save_shift_mode_color", "#ffff00")
        )
        self.PRESETS_BACKGROUND_COLOR = self._hex_to_rgb(
            colors_data.get("presets_background_color", "#0a0a0a")
        )

        # Parse column colors
        self.COLUMN_COLORS = {}
        column_colors_config = colors_data.get("column_colors", {})
        for col_str, hex_color in column_colors_config.items():
            col_num = int(col_str)
            self.COLUMN_COLORS[col_num] = self._hex_to_rgb(hex_color)

    def _hex_to_rgb(self, hex_color: str) -> List[float]:
        """Convert hex color to RGB float list (0.0-1.0)."""
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]

        try:
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            return [r, g, b]
        except (ValueError, IndexError):
            logger.warning(f"Invalid hex color '{hex_color}', using black")
            return [0.0, 0.0, 0.0]


class ConfigManager:
    """Handles configuration loading and color management."""

    DEFAULT_CONFIG = {
        "brightness_foreground": 1.0,
        "brightness_background": 0.06,
        "brightness_background_effect": 1.0,
        "scene_on_color_from_column": True,
        "colors": {
            "column_colors": {
                "0": "#ff0000",
                "1": "#00ff00",
                "2": "#0000ff",
                "3": "#ffff00",
                "4": "#7500ff",
                "5": "#00ffff",
                "6": "#ffffff",
                "7": "#ff4800",
            },
            "preset_on_color": "#ff0080",
            "preset_save_mode_color": "#ff0080",
            "preset_save_shift_mode_color": "#ffff00",
            "presets_background_color": "#ff0080",
            "scene_on_color": "#00ff00",
            "save_mode_on": "#ff0080",
            "save_mode_off": "#000000",
            "background_cycle": "#00ff00",
            "success_flash": "#00ff00",
            "yellow_bright": "#ffff00",
            "playback_playing": "#00ff00",
            "playback_paused": "#ff8000",
            "next_step": "#0080ff",
            "connection_good": "#004d00",
            "connection_bad": "#4d0000",
            "off": "#000000",
        },
        "key_bindings": {
            "save_button": [0, 0],
            "save_shift_button": [1, 0],
            "background_button": [7, 0],
            "playback_toggle_button": [0, 5],
            "next_step_button": [0, 6],
            "connection_status_button": [0, 7],
        },
    }

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or Path("config.json")
        self.config_data = self._load_or_create_config()
        self.colors = Colors(self.config_data)

    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load config from file or create default if it doesn't exist."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    logger.info(f"Loaded config from {self.config_file}")

                    # Merge with defaults to ensure all keys exist
                    merged_config = self.DEFAULT_CONFIG.copy()
                    merged_config.update(config_data)

                    # Save back to file if new keys were added
                    if merged_config != config_data:
                        self._save_config(merged_config)
                        logger.info("Updated config file with missing default values")

                    return merged_config
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading config from {self.config_file}: {e}")
                logger.info("Creating new config file with defaults")

        # Create default config file
        self._save_config(self.DEFAULT_CONFIG)
        logger.info(f"Created default config file at {self.config_file}")
        return self.DEFAULT_CONFIG.copy()

    def _save_config(self, config_data: Dict[str, Any]) -> None:
        """Save config data to file."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, sort_keys=True)
        except IOError as e:
            logger.error(f"Error saving config to {self.config_file}: {e}")

    def get_brightness_foreground(self) -> float:
        """Get foreground brightness multiplier (0.0-1.0)."""
        return float(self.config_data.get("brightness_foreground", 1.0))

    def get_brightness_background(self) -> float:
        """Get background brightness multiplier (0.0-1.0)."""
        return float(self.config_data.get("brightness_background", 0.3))

    def get_brightness_background_effect(self) -> float:
        """Get background effect brightness multiplier (0.0-1.0)."""
        return float(self.config_data.get("brightness_background_effect", 1.0))

    def get_column_color(self, column: int) -> Optional[List[float]]:
        """Get color for a specific scene column."""
        return self.colors.COLUMN_COLORS.get(column)

    def get_presets_background_color(self) -> List[float]:
        """Get the background color for preset area."""
        return self.colors.PRESETS_BACKGROUND_COLOR

    def get_key_binding(self, key_name: str) -> Optional[List[int]]:
        """Get key binding coordinates for a specific button."""
        key_bindings = self.config_data.get("key_bindings", {})
        return key_bindings.get(key_name)

    def get_all_key_bindings(self) -> Dict[str, List[int]]:
        """Get all key bindings."""
        return self.config_data.get("key_bindings", {})

    def get_scene_on_color_from_column(self) -> bool:
        """Get whether active scenes should use column colors."""
        return bool(self.config_data.get("scene_on_color_from_column", True))

    def reload_config(self) -> None:
        """Reload configuration from file."""
        self.config_data = self._load_or_create_config()
        self.colors = Colors(self.config_data)
        logger.info("Configuration reloaded")


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_colors() -> Colors:
    """Get the colors instance from config manager."""
    return get_config_manager().colors
