import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)


def get_button_type_enum(button_type_str: str):
    """Convert button type string to ButtonType enum.

    Args:
        button_type_str: String representation of button type ("TOP", "RIGHT", etc.)

    Returns:
        ButtonType enum value
    """
    # Import here to avoid circular imports
    from lumiblox.devices.launchpad import ButtonType

    button_type_map = {
        "TOP": ButtonType.TOP,
        "RIGHT": ButtonType.RIGHT,
        "SCENE": ButtonType.SCENE,
        "PRESET": ButtonType.PRESET,
    }

    return button_type_map.get(button_type_str.upper(), ButtonType.UNKNOWN)


class ColorConfig(TypedDict):
    """Type definition for color configuration."""

    column_colors: Dict[str, str]
    preset_on: str
    preset_save_mode: str
    preset_save_shift_mode: str
    presets_background: str
    save_mode_preset_background: str
    scene_on: str
    save_mode_on: str
    background_cycle: str
    success_flash: str
    yellow_bright: str
    playback_playing: str
    playback_paused: str
    next_step: str
    connection_good: str
    connection_bad: str
    off: str


class KeyBinding(TypedDict):
    """Type definition for a single key binding."""

    button_type: str  # "TOP", "RIGHT", "SCENE", "PRESET"
    coordinates: List[int]  # [x, y] relative coordinates


class KeyBindings(TypedDict):
    """Type definition for key bindings configuration."""

    save_button: KeyBinding
    save_shift_button: KeyBinding
    background_button: KeyBinding
    playback_toggle_button: KeyBinding
    next_step_button: KeyBinding
    clear_button: KeyBinding
    background_brightness_down: KeyBinding
    background_brightness_up: KeyBinding
    pilot_select_button: KeyBinding


class ConfigData(TypedDict):
    """Type definition for the complete configuration structure."""

    brightness_foreground: float
    brightness_background: float
    brightness_background_effect: float
    brightness_background_top_row: float
    scene_on_color_from_column: bool
    colors: ColorConfig
    key_bindings: KeyBindings
    pilot: Dict[str, Any]  # Pilot configuration (enabled, decks, etc.)


class ConfigManager:
    """Handles configuration loading and color management."""

    DEFAULT_CONFIG: ConfigData = {
        "brightness_foreground": 1.0,
        "brightness_background": 0.2,
        "brightness_background_effect": 1.0,
        "brightness_background_top_row": 0.5,
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
            "preset_on": "#ff0080",
            "preset_save_mode": "#ff0000",
            "preset_save_shift_mode": "#3cff00",
            "presets_background": "#ffffff",
            "save_mode_preset_background": "#ffffff",
            "scene_on": "#00ff00",
            "save_mode_on": "#ff0080",
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
            "save_button": {"button_type": "TOP", "coordinates": [0, 0]},
            "save_shift_button": {"button_type": "TOP", "coordinates": [1, 0]},
            "background_button": {"button_type": "TOP", "coordinates": [7, 0]},
            "playback_toggle_button": {"button_type": "RIGHT", "coordinates": [0, 5]},
            "next_step_button": {"button_type": "RIGHT", "coordinates": [0, 6]},
            "clear_button": {"button_type": "RIGHT", "coordinates": [8, 7]},
            "background_brightness_down": {"button_type": "TOP", "coordinates": [5, 0]},
            "background_brightness_up": {"button_type": "TOP", "coordinates": [6, 0]},
            "pilot_select_button": {"button_type": "TOP", "coordinates": [4, 0]},
        },
        "pilot": {
            "enabled": False,
            "midiclock_device": "midiclock",
            "zero_signal": {
                "enabled": False,
                "status": 144,
                "data1": 60,
                "data2": None,
            },
            "midi_actions": [
                # Example format:
                # {
                #     "name": "Phrase Sync",
                #     "action_type": "phrase_sync",
                #     "status": 144,  # 0x90 = Note On
                #     "data1": 60,    # Middle C
                #     "data2": None,  # Any velocity
                #     "parameters": {}
                # }
            ],
            "model_path": "pilot-tests/resources/traktor/classifier_traktor.pkl",
            "template_dir": "pilot-tests/resources/traktor",
            "decks": {
                "A": {
                    "master_button_region": None,
                    "timeline_region": None,
                },
                "B": {
                    "master_button_region": None,
                    "timeline_region": None,
                },
                "C": {
                    "master_button_region": None,
                    "timeline_region": None,
                },
                "D": {
                    "master_button_region": None,
                    "timeline_region": None,
                },
            },
        },
    }

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or Path("config.json")
        self.data = self._load_or_create_config()

    def _load_or_create_config(self) -> ConfigData:
        """Load config from file or create default if it doesn't exist."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    logger.info(f"Loaded config from {self.config_file}")

                    # Merge with defaults to ensure all keys exist
                    merged_config = self._deep_merge_config(
                        self.DEFAULT_CONFIG, config_data
                    )

                    # Migrate legacy connection status button to clear button
                    key_bindings = merged_config.get("key_bindings", {})
                    if (
                        "connection_status_button" in key_bindings
                        and "clear_button" not in key_bindings
                    ):
                        key_bindings["clear_button"] = key_bindings.pop(
                            "connection_status_button"
                        )

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

    def _save_config(self, config_data: ConfigData) -> None:
        """Save config data to file."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, sort_keys=True)
        except IOError as e:
            logger.error(f"Error saving config to {self.config_file}: {e}")

    def _deep_merge_config(self, default_config: Any, user_config: Any) -> Any:
        """Deep merge user config with defaults, ensuring all default keys exist."""
        merged = default_config.copy()

        for key, value in user_config.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                merged[key] = self._deep_merge_config(merged[key], value)
            else:
                # Use user value for non-dict values or new keys
                merged[key] = value
        return merged

    def reload_config(self) -> None:
        """Reload configuration from file."""
        self.data = self._load_or_create_config()

    def save(self) -> None:
        """Save current configuration to file."""
        self._save_config(self.data)
        logger.info(f"Saved configuration to {self.config_file}")

    def set_pilot_enabled(self, enabled: bool) -> None:
        """Set pilot enabled state and save to config."""
        if "pilot" not in self.data:
            self.data["pilot"] = self.DEFAULT_CONFIG.get("pilot", {}).copy()
        self.data["pilot"]["enabled"] = enabled
        self.save()
        logger.info(f"Pilot {'enabled' if enabled else 'disabled'} in configuration")

    def set_deck_region(
        self, deck: str, region_type: str, region_data: Dict[str, int]
    ) -> None:
        """Set a deck's capture region and save to config.

        Args:
            deck: Deck identifier (A, B, C, D)
            region_type: "master_button_region" or "timeline_region"
            region_data: Dictionary with keys x, y, width, height
        """
        if "pilot" not in self.data:
            self.data["pilot"] = self.DEFAULT_CONFIG.get("pilot", {}).copy()

        if "decks" not in self.data["pilot"]:
            self.data["pilot"]["decks"] = {
                "A": {"master_button_region": None, "timeline_region": None},
                "B": {"master_button_region": None, "timeline_region": None},
                "C": {"master_button_region": None, "timeline_region": None},
                "D": {"master_button_region": None, "timeline_region": None},
            }

        if deck not in self.data["pilot"]["decks"]:
            self.data["pilot"]["decks"][deck] = {
                "master_button_region": None,
                "timeline_region": None,
            }

        self.data["pilot"]["decks"][deck][region_type] = region_data  # type: ignore[index]
        self.save()
        logger.info(f"Saved {region_type} for deck {deck}: {region_data}")

    def get_deck_region(self, deck: str, region_type: str) -> Optional[Dict[str, int]]:
        """Get a deck's capture region from config.

        Args:
            deck: Deck identifier (A, B, C, D)
            region_type: "master_button_region" or "timeline_region"

        Returns:
            Dictionary with keys x, y, width, height or None if not set
        """
        pilot_config = self.data.get("pilot", {})
        decks = pilot_config.get("decks", {})
        deck_config = decks.get(deck, {})
        return deck_config.get(region_type)

    def clear_deck_regions(self, deck: str) -> None:
        """Clear stored capture regions for a deck and save."""
        if "pilot" not in self.data:
            return

        decks = self.data["pilot"].setdefault(
            "decks",
            {
                "A": {"master_button_region": None, "timeline_region": None},
                "B": {"master_button_region": None, "timeline_region": None},
                "C": {"master_button_region": None, "timeline_region": None},
                "D": {"master_button_region": None, "timeline_region": None},
            },
        )

        if deck not in decks:
            decks[deck] = {
                "master_button_region": None,
                "timeline_region": None,
            }
        else:
            decks[deck]["master_button_region"] = None
            decks[deck]["timeline_region"] = None

        self.save()
        logger.info(f"Cleared capture regions for deck {deck}")

    def get_midi_actions(self) -> List[Dict]:
        """Get all configured MIDI actions from config.

        Returns:
            List of MIDI action dictionaries
        """
        pilot_config = self.data.get("pilot", {})
        return pilot_config.get("midi_actions", [])

    def set_midi_actions(self, actions: List[Dict]) -> None:
        """Set MIDI actions in config and save.

        Args:
            actions: List of MIDI action dictionaries
        """
        if "pilot" not in self.data:
            self.data["pilot"] = self.DEFAULT_CONFIG.get("pilot", {}).copy()
        self.data["pilot"]["midi_actions"] = actions
        self.save()
        logger.info(f"Saved {len(actions)} MIDI actions to config")

    def add_midi_action(self, action: Dict) -> None:
        """Add a MIDI action to config and save.

        Args:
            action: MIDI action dictionary
        """
        actions = self.get_midi_actions()
        actions.append(action)
        self.set_midi_actions(actions)

    def remove_midi_action(self, name: str) -> bool:
        """Remove a MIDI action by name from config and save.

        Args:
            name: Name of the action to remove

        Returns:
            True if action was found and removed
        """
        actions = self.get_midi_actions()
        for i, action in enumerate(actions):
            if action.get("name") == name:
                actions.pop(i)
                self.set_midi_actions(actions)
                return True
        return False


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
