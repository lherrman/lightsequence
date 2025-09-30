"""
Configuration management with dataclasses
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class Scene:
    """Lighting scene configuration."""

    name: str
    midi_note: int
    color: str = "#3498DB"
    description: str = ""


@dataclass
class Preset:
    """Preset configuration with scene playlist."""

    name: str
    scenes: List[str] = field(default_factory=list)
    cycle_interval: float = 2.0
    description: str = ""
    _button_index: Optional[int] = field(default=None, init=False)


@dataclass
class Config:
    """Main configuration."""

    scenes: Dict[str, Scene] = field(default_factory=dict)
    presets: Dict[str, Preset] = field(default_factory=dict)


def load_config(file_path: str = "config.yaml") -> Config:
    """Load configuration from YAML."""
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)

        config = Config()

        # Load scenes
        for name, scene_data in data.get("scenes", {}).items():
            config.scenes[name] = Scene(
                name=name,
                midi_note=scene_data["midi_note"],
                color=scene_data.get("color", "#3498DB"),
                description=scene_data.get("description", ""),
            )

        # Load presets
        for name, preset_data in data.get("presets", {}).items():
            config.presets[name] = Preset(
                name=name,
                scenes=preset_data.get("scenes", []),
                cycle_interval=preset_data.get("cycle_interval", 2.0),
                description=preset_data.get("description", ""),
            )

        logger.info(
            f"Loaded {len(config.scenes)} scenes, {len(config.presets)} presets"
        )
        return config

    except FileNotFoundError:
        logger.warning("Config file not found, creating default")
        return create_default_config(file_path)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return Config()


def save_config(config: Config, file_path: str = "config.yaml"):
    """Save configuration to YAML."""
    try:
        data = {
            "scenes": {
                name: {
                    "midi_note": scene.midi_note,
                    "color": scene.color,
                    "description": scene.description,
                }
                for name, scene in config.scenes.items()
            },
            "presets": {
                name: {
                    "scenes": preset.scenes,
                    "cycle_interval": preset.cycle_interval,
                    "description": preset.description,
                }
                for name, preset in config.presets.items()
            },
        }

        with open(file_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        logger.info(f"Saved config to {file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


def create_default_config(file_path: str = "config.yaml") -> Config:
    """Create default configuration."""
    config = Config()

    # Create sample scenes
    scenes_data = [
        ("Red", 11, "#FF0000"),
        ("Green", 12, "#00FF00"),
        ("Blue", 13, "#0000FF"),
        ("White", 14, "#FFFFFF"),
        ("Purple", 15, "#8A2BE2"),
    ]

    for name, note, color in scenes_data:
        config.scenes[name] = Scene(name, note, color, f"{name} lighting")

    # Create sample presets
    config.presets["Party"] = Preset(
        "Party", ["Red", "Green", "Blue"], 1.5, "Party cycling"
    )
    config.presets["Chill"] = Preset("Chill", ["Blue", "Purple"], 3.0, "Relaxed mood")

    save_config(config, file_path)
    return config
