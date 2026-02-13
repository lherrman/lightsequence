"""
Project Data Repository

Repository pattern for managing pilots with embedded sequences.
Handles loading, saving, and CRUD operations for the project data file (pilots.json).
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from lumiblox.pilot.pilot_preset import PilotPreset, _json_default

logger = logging.getLogger(__name__)


class ProjectDataRepository:
    """Repository for managing project data (pilots with their embedded sequences)."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize pilot repository.

        Args:
            config_path: Path to pilots.json, or None for default location
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "pilots.json"

        self.config_path = config_path
        self.pilots: List[PilotPreset] = []
        self._active_pilot_index: int = 0
        self.load()
        
        # Set active pilot index based on enabled field
        for i, pilot in enumerate(self.pilots):
            if pilot.enabled:
                self._active_pilot_index = i
                break

    def load(self) -> bool:
        """Load pilots from file."""
        previous_pilots = list(self.pilots)
        if not self.config_path.exists():
            logger.warning(
                f"No pilots.json found at {self.config_path}; creating default pilot"
            )
            self.pilots = [self._create_default_pilot()]
            self.save()
            return True

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.pilots = [PilotPreset.from_dict(p) for p in data.get("presets", [])]
            
            # Ensure each pilot has sequences dict
            for pilot in self.pilots:
                if pilot.sequences is None:
                    pilot.sequences = {"sequences": []}
            
            logger.info(
                f"Loaded {len(self.pilots)} pilots from {self.config_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load pilots.json: {e}")
            if previous_pilots:
                self.pilots = previous_pilots
            else:
                self.pilots = [self._create_default_pilot()]
            return False

    def save(self) -> bool:
        """Save pilots to file."""
        tmp_path: Optional[Path] = None
        try:
            data = {"version": "1.0", "presets": [p.to_dict() for p in self.pilots]}

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

            logger.info(f"Saved {len(self.pilots)} pilots to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save pilots.json: {e}")
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    logger.debug(
                        "Failed to remove temporary pilots file", exc_info=True
                    )
            return False

    def _create_default_pilot(self) -> PilotPreset:
        """Create default pilot with empty sequences."""
        return PilotPreset(
            name="Default Pilot",
            enabled=True,
            rules=[],
            sequences={"sequences": []},
        )

    # ============================================================================
    # Pilot CRUD Operations
    # ============================================================================

    def add_pilot(self, pilot: PilotPreset) -> int:
        """Add a new pilot and return its index."""
        if pilot.sequences is None:
            pilot.sequences = {"sequences": []}
        self.pilots.append(pilot)
        self.save()
        return len(self.pilots) - 1

    def remove_pilot(self, index: int) -> bool:
        """Remove a pilot by index."""
        if 0 <= index < len(self.pilots):
            # Don't allow removing the last pilot
            if len(self.pilots) == 1:
                logger.warning("Cannot remove the last pilot")
                return False
            
            del self.pilots[index]
            
            # Adjust active pilot index if needed
            if self._active_pilot_index >= len(self.pilots):
                self._active_pilot_index = len(self.pilots) - 1
            
            self.save()
            return True
        return False

    def update_pilot(self, index: int, pilot: PilotPreset) -> bool:
        """Update a pilot by index."""
        if 0 <= index < len(self.pilots):
            if pilot.sequences is None:
                pilot.sequences = {"sequences": []}
            self.pilots[index] = pilot
            self.save()
            return True
        return False

    def get_pilot(self, index: int) -> Optional[PilotPreset]:
        """Get a pilot by index."""
        if 0 <= index < len(self.pilots):
            return self.pilots[index]
        return None

    def get_active_pilot(self) -> Optional[PilotPreset]:
        """Get the active pilot."""
        if 0 <= self._active_pilot_index < len(self.pilots):
            return self.pilots[self._active_pilot_index]
        return None

    def get_active_pilot_index(self) -> int:
        """Get the active pilot index."""
        return self._active_pilot_index

    def set_active_pilot(self, index: int) -> bool:
        """Set the active pilot by index and persist to disk."""
        if 0 <= index < len(self.pilots):
            # Update enabled field for all pilots
            for i, pilot in enumerate(self.pilots):
                pilot.enabled = (i == index)
            
            self._active_pilot_index = index
            
            # Persist the change
            self.save()
            
            logger.info(f"Switched to pilot: {self.pilots[index].name}")
            return True
        return False

    # ============================================================================
    # Sequence Operations for Active Pilot
    # ============================================================================

    def get_sequences(self, pilot_index: Optional[int] = None) -> Dict[str, Any]:
        """
        Get sequences for a pilot.

        Args:
            pilot_index: Index of pilot, or None for active pilot

        Returns:
            Dictionary with "sequences" key containing list of sequence data
        """
        if pilot_index is None:
            pilot_index = self._active_pilot_index
        
        pilot = self.get_pilot(pilot_index)
        if pilot and pilot.sequences:
            return pilot.sequences
        return {"sequences": []}

    def save_sequences(self, sequences_data: Dict[str, Any], pilot_index: Optional[int] = None) -> bool:
        """
        Save sequences for a pilot.

        Args:
            sequences_data: Dictionary with "sequences" key containing list of sequence data
            pilot_index: Index of pilot, or None for active pilot

        Returns:
            True if successful
        """
        if pilot_index is None:
            pilot_index = self._active_pilot_index
        
        pilot = self.get_pilot(pilot_index)
        if pilot:
            pilot.sequences = sequences_data
            return self.save()
        return False
