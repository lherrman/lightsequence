"""
Pilot Presets

Automation rules for sequence switching based on phrase detection.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    """Convert a few common non-JSON types to primitives."""
    if isinstance(obj, Enum):
        return obj.value
    try:  # Avoid hard dependency on numpy
        import numpy as np

        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ConditionType(Enum):
    """Rule condition type."""

    AFTER_PHRASE_TYPE = "after_phrase_type"  # Every X bars while in this phrase type
    ON_PHRASE_CHANGE = "on_phrase_change"  # When switching to this phrase type (if previous was long enough)


class ActionType(Enum):
    """Rule action type."""

    ACTIVATE_SEQUENCE = "activate_sequence"  # Activate a specific sequence


@dataclass
class SequenceChoice:
    """Weighted sequence choice, optionally representing a no-op."""

    sequence_index: Optional[str]  # Format: "x.y", "x", or None when doing nothing
    weight: float  # 0.0 to 1.0, weights should sum to 1.0
    do_nothing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"weight": self.weight}
        data["sequence_index"] = self.sequence_index
        if self.do_nothing:
            data["do_nothing"] = True
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SequenceChoice:
        sequence_index = data.get("sequence_index")
        if sequence_index is not None:
            sequence_index = str(sequence_index)
        return cls(
            sequence_index=sequence_index,
            weight=data["weight"],
            do_nothing=bool(data.get("do_nothing", False)),
        )

    def get_index_tuple(self) -> tuple[int, int]:
        """Convert string index to (x, y) tuple."""
        if self.sequence_index is None:
            raise ValueError("Do-nothing choices do not map to a sequence index")

        if "." in self.sequence_index:
            parts = self.sequence_index.split(".")
            return (int(parts[0]), int(parts[1]))
        # Single number: assume it's an old linear index, convert to grid
        idx = int(self.sequence_index)
        return (idx % 8, idx // 8)

    def is_noop(self) -> bool:
        """Return True when this choice represents doing nothing."""
        return self.do_nothing or self.sequence_index is None


@dataclass
class RuleCondition:
    """Rule condition."""

    condition_type: ConditionType
    phrase_type: Optional[str] = None  # "body", "breakdown", or None for any
    duration_bars: Optional[int] = (
        None  # For AFTER: interval to repeat; For ON_CHANGE: min duration of previous phrase
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_type": self.condition_type.value,
            "phrase_type": self.phrase_type,
            "duration_bars": self.duration_bars,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuleCondition:
        return cls(
            condition_type=ConditionType(data["condition_type"]),
            phrase_type=data.get("phrase_type"),
            duration_bars=data.get("duration_bars"),
        )

    def evaluate(
        self,
        current_phrase_type: str,
        previous_phrase_type: Optional[str],
        bars_elapsed: int,
        previous_phrase_bars: int,
    ) -> bool:
        """
        Evaluate if this condition is met.

        Args:
            current_phrase_type: Current phrase type ("body" or "breakdown")
            previous_phrase_type: Previous phrase type (for change detection)
            bars_elapsed: Bars in current phrase type
            previous_phrase_bars: Duration of previous phrase in bars

        Returns:
            True if condition is met
        """
        if self.condition_type == ConditionType.AFTER_PHRASE_TYPE:
            # Check phrase type matches (if specified)
            if self.phrase_type and current_phrase_type != self.phrase_type:
                return False

            # Execute every duration_bars interval
            if self.duration_bars is not None:
                # Don't fire immediately at phrase start (bars_elapsed==0)
                if bars_elapsed == 0:
                    return False
                if bars_elapsed % self.duration_bars != 0:
                    return False

            return True

        elif self.condition_type == ConditionType.ON_PHRASE_CHANGE:
            # Check if phrase type just changed
            if previous_phrase_type is None:
                return False
            if previous_phrase_type == current_phrase_type:
                return False

            # Check if it changed TO the specified type (if specified)
            if self.phrase_type and current_phrase_type != self.phrase_type:
                return False

            # Check if previous phrase was long enough
            if self.duration_bars is not None:
                if previous_phrase_bars < self.duration_bars:
                    return False

            return True

        return False


@dataclass
class RuleAction:
    """Rule action."""

    action_type: ActionType
    sequences: Optional[List[SequenceChoice]] = None  # Weighted sequence choices

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "sequences": [s.to_dict() for s in self.sequences]
            if self.sequences
            else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RuleAction:
        sequences = None
        if data.get("sequences"):
            sequences = [SequenceChoice.from_dict(s) for s in data["sequences"]]

        return cls(
            action_type=ActionType(data["action_type"]),
            sequences=sequences,
        )


@dataclass
class AutomationRule:
    """Complete automation rule."""

    name: str
    enabled: bool
    condition: RuleCondition
    action: RuleAction
    cooldown_bars: int = 0  # Minimum bars between rule executions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "condition": self.condition.to_dict(),
            "action": self.action.to_dict(),
            "cooldown_bars": self.cooldown_bars,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AutomationRule:
        return cls(
            name=data["name"],
            enabled=data["enabled"],
            condition=RuleCondition.from_dict(data["condition"]),
            action=RuleAction.from_dict(data["action"]),
            cooldown_bars=data.get("cooldown_bars", 0),
        )


@dataclass
class PilotPreset:
    """Pilot preset with automation rules and sequences."""

    name: str
    enabled: bool
    rules: List[AutomationRule]
    sequences: Dict[str, Any] = None  # Stores sequences data for this pilot

    def __post_init__(self):
        """Ensure sequences is initialized."""
        if self.sequences is None:
            self.sequences = {"sequences": []}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "rules": [r.to_dict() for r in self.rules],
            "sequences": self.sequences or {"sequences": []},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PilotPreset:
        return cls(
            name=data["name"],
            enabled=data["enabled"],
            rules=[AutomationRule.from_dict(r) for r in data.get("rules", [])],
            sequences=data.get("sequences", {"sequences": []}),
        )


class PilotPresetManager:
    """Manage pilot presets and rules."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize preset manager.

        Args:
            config_path: Path to pilots.json, or None for default location
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "pilots.json"

        self.config_path = config_path
        self.presets: List[PilotPreset] = []
        self.load()

    def load(self) -> bool:
        """Load presets from file."""
        previous_presets = list(self.presets)
        if not self.config_path.exists():
            logger.warning("No pilots.json found at %s; keeping current presets", self.config_path)
            # Do not create a new file automatically; keep in-memory presets
            if not self.presets:
                self.presets = [self._create_default_preset()]
            return False

        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)

            self.presets = [PilotPreset.from_dict(p) for p in data.get("presets", [])]
            logger.info(
                f"Loaded {len(self.presets)} pilot presets from {self.config_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load pilots.json: {e}")
            # Keep the last known good presets to avoid overwriting with defaults
            # in case of a transient read/parse error.
            if previous_presets:
                self.presets = previous_presets
            else:
                self.presets = [self._create_default_preset()]
            return False

    def save(self) -> bool:
        """Save presets to file."""
        tmp_path: Optional[Path] = None
        try:
            data = {"version": "1.0", "presets": [p.to_dict() for p in self.presets]}

            # Write atomically to avoid corrupting the main file if writing fails
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=str(self.config_path.parent),
                prefix=f"{self.config_path.stem}_",
                suffix=self.config_path.suffix,
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, default=_json_default)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                tmp_path = Path(tmp_file.name)

            tmp_path.replace(self.config_path)

            logger.info(
                f"Saved {len(self.presets)} pilot presets to {self.config_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save pilots.json: {e}")
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    logger.debug("Failed to remove temporary pilots file", exc_info=True)
            return False

    def _create_default_preset(self) -> PilotPreset:
        """Create default pilot preset with example rules."""
        return PilotPreset(
            name="Default Pilot",
            enabled=True,
            rules=[
                # Example: Every 16 bars during breakdown, activate a sequence
                AutomationRule(
                    name="Breakdown Every 16 Bars",
                    enabled=False,
                    condition=RuleCondition(
                        condition_type=ConditionType.AFTER_PHRASE_TYPE,
                        phrase_type="breakdown",
                        duration_bars=16,
                    ),
                    action=RuleAction(
                        action_type=ActionType.ACTIVATE_SEQUENCE,
                        sequences=[
                            SequenceChoice(sequence_index="0.0", weight=0.7),
                            SequenceChoice(sequence_index="0.1", weight=0.3),
                        ],
                    ),
                    cooldown_bars=8,
                ),
            ],
        )

    # CRUD operations
    def add_preset(self, preset: PilotPreset) -> None:
        """Add a new preset."""
        self.presets.append(preset)
        self.save()

    def remove_preset(self, index: int) -> bool:
        """Remove a preset by index."""
        if 0 <= index < len(self.presets):
            del self.presets[index]
            self.save()
            return True
        return False

    def update_preset(self, index: int, preset: PilotPreset) -> bool:
        """Update a preset by index."""
        if 0 <= index < len(self.presets):
            self.presets[index] = preset
            self.save()
            return True
        return False

    def get_preset(self, index: int) -> Optional[PilotPreset]:
        """Get a preset by index."""
        if 0 <= index < len(self.presets):
            return self.presets[index]
        return None

    def get_active_preset(self) -> Optional[PilotPreset]:
        """Get the first enabled preset."""
        for preset in self.presets:
            if preset.enabled:
                return preset
        return None
