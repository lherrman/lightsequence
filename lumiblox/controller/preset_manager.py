import json
import logging
import typing as t
from pathlib import Path
from lumiblox.controller.sequence import SequenceStep

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
                        self.create_empty_presets_file()
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
                logger.info("Presets file doesn't exist")
                self.create_empty_presets_file()
                return {"presets": []}
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading presets: {e}, using default structure")
            return {"presets": []}

    def create_empty_presets_file(self) -> None:
        """Create an empty presets file with default structure."""
        try:
            if not self.preset_file.exists():
                self.preset_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.preset_file, "w", encoding="utf-8") as f:
                    json.dump({"presets": []}, f, indent=4)
                logger.info(f"Created new presets file at {self.preset_file}")
            else:
                logger.info(f"Presets file already exists at {self.preset_file}")
                # If the file exists but is empty, write the default structure
                if self.preset_file.stat().st_size == 0:
                    with open(self.preset_file, "w", encoding="utf-8") as f:
                        json.dump({"presets": []}, f, indent=4)
                    logger.info(f"Initialized empty presets file at {self.preset_file}")
        except Exception as e:
            logger.error(f"Error creating presets file: {e}")

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
                    # Overwrite with simple preset - remove sequence data if it exists
                    preset["scenes"] = valid_scenes
                    if "sequence" in preset:
                        del preset["sequence"]
                        logger.info(
                            f"Converted sequence preset {index} to simple preset"
                        )
                    if "loop" in preset:
                        del preset["loop"]
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

    def save_sequence(
        self, index: t.List[int], steps: t.List[SequenceStep], loop: bool = True
    ) -> None:
        """Save or update a preset with sequence steps."""
        try:
            # Validate input parameters
            if not isinstance(index, list) or len(index) < 2:
                logger.error(f"Invalid index format: {index}")
                return

            if not isinstance(steps, list):
                logger.error(f"Invalid steps format: {steps}")
                return

            presets_data = self.load_presets()

            # Convert steps to serializable format
            sequence_data = []
            for step in steps:
                step_data = {
                    "scenes": [
                        [int(scene[0]), int(scene[1])]
                        for scene in step.scenes
                        if isinstance(scene, list) and len(scene) >= 2
                    ],
                    "duration": float(step.duration),
                    "name": str(step.name) if step.name else "",
                }
                sequence_data.append(step_data)

            # Find existing preset or create new one
            preset_found = False
            for preset in presets_data["presets"]:
                if preset["index"] == index:
                    preset["sequence"] = sequence_data
                    preset["loop"] = loop
                    # Keep scenes for backward compatibility (use first step's scenes)
                    if sequence_data:
                        preset["scenes"] = sequence_data[0]["scenes"]
                    preset_found = True
                    logger.info(f"Updated existing preset {index} with sequence")
                    break

            if not preset_found:
                new_preset = {
                    "index": [int(index[0]), int(index[1])],
                    "sequence": sequence_data,
                    "scenes": sequence_data[0]["scenes"] if sequence_data else [],
                    "loop": loop,
                }
                presets_data["presets"].append(new_preset)
                logger.info(f"Created new preset {index} with sequence")

            self.save_presets(presets_data)
            logger.info(
                f"Preset {index} saved with {len(sequence_data)} sequence steps"
            )
        except Exception as e:
            logger.error(f"Error in save_sequence: {e}")

    def get_sequence(self, index: t.List[int]) -> t.Optional[t.List[SequenceStep]]:
        """Get sequence steps for a preset."""
        preset = self.get_preset_by_index(index)
        if not preset:
            return None

        # Check if preset has sequence data
        if "sequence" in preset and isinstance(preset["sequence"], list):
            try:
                steps = []
                for step_data in preset["sequence"]:
                    if isinstance(step_data, dict):
                        step = SequenceStep(
                            scenes=step_data.get("scenes", []),
                            duration=float(step_data.get("duration", 1.0)),
                            name=step_data.get("name", ""),
                        )
                        steps.append(step)
                return steps
            except Exception as e:
                logger.error(f"Error parsing sequence for preset {index}: {e}")

        # Fallback to simple scenes format for backward compatibility
        if "scenes" in preset:
            return [SequenceStep(scenes=preset["scenes"], duration=1.0, name="Default")]

        return None

    def has_sequence(self, index: t.List[int]) -> bool:
        """Check if a preset has a multi-step sequence."""
        preset = self.get_preset_by_index(index)
        if not preset:
            return False

        # Check if it has sequence data with more than one step
        if "sequence" in preset and isinstance(preset["sequence"], list):
            return len(preset["sequence"]) > 1

        return False

    def remove_sequence(self, index: t.List[int]) -> bool:
        """Remove sequence data from a preset, keeping only the first step as simple scenes."""
        try:
            presets_data = self.load_presets()

            for preset in presets_data["presets"]:
                if preset["index"] == index:
                    if "sequence" in preset:
                        # Keep first step as simple scenes
                        if preset["sequence"] and len(preset["sequence"]) > 0:
                            preset["scenes"] = preset["sequence"][0].get("scenes", [])
                        del preset["sequence"]
                        self.save_presets(presets_data)
                        logger.info(f"Removed sequence from preset {index}")
                        return True

            logger.warning(f"Preset {index} not found")
            return False
        except Exception as e:
            logger.error(f"Error removing sequence from preset {index}: {e}")
            return False

    def get_loop_setting(self, index: t.List[int]) -> bool:
        """Get loop setting for a preset."""
        preset = self.get_preset_by_index(index)
        if preset:
            return preset.get(
                "loop", True
            )  # Default to True for backward compatibility
        return True

    def add_step_to_preset(
        self, index: t.List[int], scenes: t.List[t.List[int]]
    ) -> None:
        """Add a new step to an existing preset or create a sequence if it doesn't exist."""
        try:
            # Check if preset already has a sequence
            if self.has_sequence(index):
                # Add step to existing sequence
                sequence = self.get_sequence(index)
                if sequence is not None:
                    new_step = SequenceStep(
                        scenes=scenes,
                        duration=1.0,  # Default 1 second duration
                        name=f"Step {len(sequence) + 1}",
                    )
                    sequence.append(new_step)
                    self.save_sequence(index, sequence, loop=True)
                    logger.info(
                        f"Added step to existing sequence for preset {index} (now {len(sequence)} steps)"
                    )
                else:
                    logger.error("Failed to get existing sequence")
            else:
                # Create new sequence - first check if preset exists as simple preset
                existing_preset = self.get_preset_by_index(index)
                if existing_preset and "scenes" in existing_preset:
                    # Convert existing simple preset to sequence and add new step
                    step1 = SequenceStep(
                        scenes=existing_preset["scenes"], duration=1.0, name="Step 1"
                    )
                    step2 = SequenceStep(scenes=scenes, duration=1.0, name="Step 2")
                    self.save_sequence(index, [step1, step2], loop=True)
                    logger.info(
                        f"Converted preset {index} to sequence and added step (now 2 steps)"
                    )
                else:
                    # Create completely new sequence
                    new_step = SequenceStep(scenes=scenes, duration=1.0, name="Step 1")
                    self.save_sequence(index, [new_step], loop=True)
                    logger.info(f"Created new sequence for preset {index} with 1 step")
        except Exception as e:
            logger.error(f"Error adding step to preset {index}: {e}")
