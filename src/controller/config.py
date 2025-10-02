import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Colors:
    """Color definitions for LED states with configurable values."""
    
    # Static colors that don't change with config
    OFF = [0.0, 0.0, 0.0]
    SAVE_MODE_ON = [1.0, 0.0, 0.5]
    SAVE_MODE_OFF = [0.0, 0.0, 0.0]
    BACKGROUND_CYCLE = [0.0, 1.0, 0.0]
    SUCCESS_FLASH = [0.0, 1.0, 0.0]
    YELLOW_BRIGHT = [1.0, 1.0, 0.0]
    PLAYBACK_PLAYING = [0.0, 1.0, 0.0]  # Green for playing
    PLAYBACK_PAUSED = [1.0, 0.5, 0.0]  # Orange for paused
    NEXT_STEP = [0.0, 0.5, 1.0]  # Blue for next step button
    CONNECTION_GOOD = [0.0, 0.3, 0.0]  # Dark green for good connection
    CONNECTION_BAD = [0.3, 0.0, 0.0]  # Dark red for bad connection
    
    # Configurable colors (will be set from config)
    SCENE_ON: List[float]
    PRESET_ON: List[float]
    PRESET_SAVE_MODE: List[float]
    PRESET_SAVE_SHIFT_MODE: List[float]
    PRESETS_BACKGROUND_COLOR: List[float]
    COLUMN_COLORS: Dict[int, List[float]]

    def __init__(self, config_data: Dict[str, Any]):
        """Initialize colors from config data."""
        self.SCENE_ON = self._hex_to_rgb(config_data.get("scene_on_color", "#00ff00"))
        self.PRESET_ON = self._hex_to_rgb(config_data.get("preset_on_color", "#ff0050"))
        self.PRESET_SAVE_MODE = self._hex_to_rgb(config_data.get("preset_save_mode_color", "#ff0080"))
        self.PRESET_SAVE_SHIFT_MODE = self._hex_to_rgb(config_data.get("preset_save_shift_mode_color", "#ffff00"))
        self.PRESETS_BACKGROUND_COLOR = self._hex_to_rgb(config_data.get("presets_background_color", "#0a0a0a"))
        
        # Parse column colors
        self.COLUMN_COLORS = {}
        column_colors_config = config_data.get("column_colors", {})
        for col_str, hex_color in column_colors_config.items():
            col_num = int(col_str)
            self.COLUMN_COLORS[col_num] = self._hex_to_rgb(hex_color)

    def _hex_to_rgb(self, hex_color: str) -> List[float]:
        """Convert hex color to RGB float list (0.0-1.0)."""
        if hex_color.startswith('#'):
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
    """Manages application configuration from config.json file."""
    
    DEFAULT_CONFIG = {
        "brightness_foreground": 1.0,
        "brightness_background": 0.3,
        "column_colors": {
            "0": "#1a0a0a",  # Dark red
            "1": "#0a1a0a",  # Dark green  
            "2": "#0a0a1a",  # Dark blue
            "3": "#1a1a0a",  # Dark yellow
            "4": "#1a0a1a",  # Dark magenta
            "5": "#0a1a1a",  # Dark cyan
            "6": "#1a1a1a",  # Dark white/gray
            "7": "#1a0f0a",  # Dark orange
        },
        "presets_background_color": "#0a050a",  # Very dark purple
        "preset_on_color": "#ff0050",  # Bright magenta
        "scene_on_color": "#00ff00",  # Bright green
        "preset_save_mode_color": "#ff0080",  # Pink
        "preset_save_shift_mode_color": "#ffff00",  # Yellow
    }
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize config manager with optional config file path."""
        if config_file is None:
            config_file = Path("config.json")
        
        self.config_file = config_file
        self.config_data = self._load_or_create_config()
        self.colors = Colors(self.config_data)
    
    def _load_or_create_config(self) -> Dict[str, Any]:
        """Load config from file or create default if it doesn't exist."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
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
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, sort_keys=True)
        except IOError as e:
            logger.error(f"Error saving config to {self.config_file}: {e}")
    
    def get_brightness_foreground(self) -> float:
        """Get foreground brightness multiplier (0.0-1.0)."""
        return float(self.config_data.get("brightness_foreground", 1.0))
    
    def get_brightness_background(self) -> float:
        """Get background brightness multiplier (0.0-1.0)."""
        return float(self.config_data.get("brightness_background", 0.3))
    
    def get_column_color(self, column: int) -> Optional[List[float]]:
        """Get color for a specific scene column."""
        return self.colors.COLUMN_COLORS.get(column)
    
    def get_presets_background_color(self) -> List[float]:
        """Get the background color for preset area."""
        return self.colors.PRESETS_BACKGROUND_COLOR
    
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