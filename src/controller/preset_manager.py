import json
import logging
import typing as t
from pathlib import Path

logger = logging.getLogger(__name__)


class PresetManager:
    """Manages saving and loading of presets to/from JSON file."""

    def __init__(self, preset_file_path: Path):
        """Initialize the preset manager with a file path."""
        self.preset_file = preset_file_path

    def load_presets(self) -> t.Dict[str, t.Any]:
        """Load presets from JSON file."""
        try:
            if self.preset_file.exists():
                with open(self.preset_file, "r") as f:
                    content = f.read().strip()
                    if not content:
                        # File exists but is empty
                        logger.info("Presets file is empty, creating default structure")
                        return {"presets": []}
                    data = json.loads(content)
                    # Ensure the data has the expected structure
                    if not isinstance(data, dict) or "presets" not in data:
                        logger.warning(
                            "Invalid presets file format, creating default structure"
                        )
                        return {"presets": []}
                    return data
            else:
                # File doesn't exist, create default structure
                logger.info("Presets file doesn't exist, will create it when saving")
                return {"presets": []}
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading presets: {e}, using default structure")
            return {"presets": []}

    def save_presets(self, presets_data: t.Dict[str, t.Any]) -> None:
        """Save presets to JSON file."""
        try:
            # Ensure the directory exists
            preset_dir = self.preset_file.parent
            if preset_dir and not preset_dir.exists():
                preset_dir.mkdir(parents=True, exist_ok=True)

            # Ensure the data has the correct structure
            if not isinstance(presets_data, dict):
                presets_data = {"presets": []}
            if "presets" not in presets_data:
                presets_data["presets"] = []

            # Validate the presets data structure before saving
            for i, preset in enumerate(presets_data["presets"]):
                if not isinstance(preset, dict):
                    logger.error(f"Invalid preset at index {i}: not a dictionary")
                    continue
                if "index" not in preset or "scenes" not in preset:
                    logger.error(
                        f"Invalid preset at index {i}: missing required fields"
                    )
                    continue
                if not isinstance(preset["index"], list) or not isinstance(
                    preset["scenes"], list
                ):
                    logger.error(
                        f"Invalid preset at index {i}: index or scenes not a list"
                    )
                    continue

            # Write to a temporary file first, then rename to avoid corruption
            temp_file = self.preset_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(presets_data, f, indent=4, ensure_ascii=False)

            # Atomic rename to replace the original file
            temp_file.replace(self.preset_file)
            logger.info("Presets saved successfully")
        except Exception as e:
            logger.error(f"Error saving presets: {e}")
            # Clean up temporary file if it exists
            temp_file = self.preset_file.with_suffix(".tmp")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def get_preset_by_index(self, index: t.List[int]) -> t.Optional[t.Dict[str, t.Any]]:
        """Get preset by index coordinates."""
        presets_data = self.load_presets()
        for preset in presets_data.get("presets", []):
            if preset.get("index") == index:
                return preset
        return None

    def save_preset(self, index: t.List[int], scenes: t.List[t.List[int]]) -> None:
        """Save or update a preset with given scenes."""
        try:
            # Validate input parameters
            if not isinstance(index, list) or len(index) < 2:
                logger.error(f"Invalid index format: {index}")
                return

            if not isinstance(scenes, list):
                logger.error(f"Invalid scenes format: {scenes}")
                return

            # Validate scene coordinates
            valid_scenes = []
            for scene in scenes:
                if isinstance(scene, list) and len(scene) >= 2:
                    valid_scenes.append([int(scene[0]), int(scene[1])])
                else:
                    logger.warning(f"Skipping invalid scene format: {scene}")

            presets_data = self.load_presets()

            # Find existing preset or create new one
            preset_found = False
            for preset in presets_data["presets"]:
                if preset["index"] == index:
                    preset["scenes"] = valid_scenes
                    preset_found = True
                    logger.info(f"Updated existing preset {index}")
                    break

            if not preset_found:
                new_preset = {
                    "index": [int(index[0]), int(index[1])],
                    "scenes": valid_scenes,
                }
                presets_data["presets"].append(new_preset)
                logger.info(f"Created new preset {index}")

            self.save_presets(presets_data)
            logger.info(f"Preset {index} saved with {len(valid_scenes)} scenes")
        except Exception as e:
            logger.error(f"Error in save_preset: {e}")

    def get_all_preset_indices(self) -> t.Dict[t.Tuple[int, int], bool]:
        """Get all preset indices as a dictionary mapping tuples to True."""
        presets_data = self.load_presets()
        return {
            tuple(preset["index"]): True for preset in presets_data.get("presets", [])
        }
