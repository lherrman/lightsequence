"""
Unified Sequence Controller

Manages all sequences (including "presets" which are just 1-step sequences).
Handles playback, storage, and state management.
"""

import json
import logging
import threading
import time
import typing as t
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class SequenceStep:
    """Represents a single step in a sequence."""
    scenes: t.List[t.Tuple[int, int]]  # List of scene coordinates as tuples
    duration: float  # Duration in seconds
    name: str = ""  # Optional name for the step


class PlaybackState(str, Enum):
    """Playback states for sequences."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class SequenceController:
    """
    Unified controller for all sequences (presets are 1-step sequences).
    
    Handles:
    - Storage and retrieval
    - Playback management
    - Step transitions
    """
    
    def __init__(self, storage_file: Path):
        """Initialize sequence controller."""
        self.storage_file = storage_file
        self.sequences: t.Dict[t.Tuple[int, int], t.List[SequenceStep]] = {}
        self.loop_settings: t.Dict[t.Tuple[int, int], bool] = {}
        
        # Playback state
        self.active_sequence: t.Optional[t.Tuple[int, int]] = None
        self.current_step_index: int = 0
        self.playback_state = PlaybackState.STOPPED
        self.playback_thread: t.Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Callbacks
        self.on_step_change: t.Optional[t.Callable[[t.List[t.Tuple[int, int]]], None]] = None
        self.on_sequence_complete: t.Optional[t.Callable[[], None]] = None
        self.on_playback_state_change: t.Optional[t.Callable[[PlaybackState], None]] = None
        
        # Load sequences from storage
        self._load_from_storage()
    
    # ============================================================================
    # STORAGE METHODS
    # ============================================================================
    
    def _load_from_storage(self) -> None:
        """Load all sequences from storage file."""
        try:
            if not self.storage_file.exists():
                self._create_empty_storage()
                return
            
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict) or 'sequences' not in data:
                logger.warning("Invalid storage format, creating new")
                self._create_empty_storage()
                return
            
            # Parse sequences
            for seq_data in data.get('sequences', []):
                index = tuple(seq_data['index'])
                loop = seq_data.get('loop', True)
                
                steps = []
                for step_data in seq_data.get('steps', []):
                    step = SequenceStep(
                        scenes=[tuple(s) for s in step_data['scenes']],
                        duration=step_data.get('duration', 1.0),
                        name=step_data.get('name', '')
                    )
                    steps.append(step)
                
                if steps:
                    self.sequences[index] = steps
                    self.loop_settings[index] = loop
            
            logger.info(f"Loaded {len(self.sequences)} sequences from storage")
            
        except Exception as e:
            logger.error(f"Error loading sequences: {e}")
            self._create_empty_storage()
    
    def _create_empty_storage(self) -> None:
        """Create empty storage file."""
        try:
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({'sequences': []}, f, indent=2)
            logger.info("Created empty sequence storage")
        except Exception as e:
            logger.error(f"Error creating storage: {e}")
    
    def _save_to_storage(self) -> None:
        """Save all sequences to storage file."""
        try:
            sequences_data = []
            for index, steps in self.sequences.items():
                seq_data = {
                    'index': list(index),
                    'loop': self.loop_settings.get(index, True),
                    'steps': [
                        {
                            'scenes': [list(s) for s in step.scenes],
                            'duration': step.duration,
                            'name': step.name
                        }
                        for step in steps
                    ]
                }
                sequences_data.append(seq_data)
            
            # Atomic write
            temp_file = self.storage_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump({'sequences': sequences_data}, f, indent=2)
            temp_file.replace(self.storage_file)
            
            logger.debug(f"Saved {len(sequences_data)} sequences")
            
        except Exception as e:
            logger.error(f"Error saving sequences: {e}")
    
    # ============================================================================
    # SEQUENCE MANAGEMENT
    # ============================================================================
    
    def save_sequence(
        self,
        index: t.Tuple[int, int],
        steps: t.List[SequenceStep],
        loop: bool = True
    ) -> None:
        """Save or update a sequence."""
        if not steps:
            logger.warning(f"Cannot save empty sequence at {index}")
            return
        
        self.sequences[index] = steps
        self.loop_settings[index] = loop
        self._save_to_storage()
        
        logger.info(f"Saved sequence {index} with {len(steps)} steps (loop={loop})")
    
    def get_sequence(self, index: t.Tuple[int, int]) -> t.Optional[t.List[SequenceStep]]:
        """Get sequence steps."""
        return self.sequences.get(index)
    
    def delete_sequence(self, index: t.Tuple[int, int]) -> bool:
        """Delete a sequence."""
        if index in self.sequences:
            # Stop if currently playing
            if self.active_sequence == index:
                self.stop_playback()
            
            del self.sequences[index]
            self.loop_settings.pop(index, None)
            self._save_to_storage()
            logger.info(f"Deleted sequence {index}")
            return True
        return False
    
    def get_all_indices(self) -> t.Set[t.Tuple[int, int]]:
        """Get all sequence indices."""
        return set(self.sequences.keys())
    
    def is_multi_step(self, index: t.Tuple[int, int]) -> bool:
        """Check if sequence has multiple steps (not a simple preset)."""
        sequence = self.sequences.get(index)
        return sequence is not None and len(sequence) > 1
    
    def get_loop_setting(self, index: t.Tuple[int, int]) -> bool:
        """Get loop setting for a sequence."""
        return self.loop_settings.get(index, True)
    
    # ============================================================================
    # PLAYBACK CONTROL
    # ============================================================================
    
    def start_playback(self, index: t.Tuple[int, int], keep_state: bool = False) -> bool:
        """
        Start playing a sequence.
        
        Args:
            index: The sequence to play
            keep_state: If True, maintain current playback state when switching sequences
        """
        if index not in self.sequences:
            logger.warning(f"Sequence {index} not found")
            return False
        
        # Store current state
        was_playing = self.playback_state == PlaybackState.PLAYING
        
        # Stop any current playback thread
        if self.playback_state != PlaybackState.STOPPED:
            self.stop_event.set()
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=1.0)
        
        # Switch to new sequence
        self.active_sequence = index
        self.current_step_index = 0
        self.stop_event.clear()
        
        # Determine playback state
        if keep_state and was_playing:
            self.playback_state = PlaybackState.PLAYING
        else:
            self.playback_state = PlaybackState.PLAYING
        
        # Notify state change
        if self.on_playback_state_change:
            self.on_playback_state_change(self.playback_state)
        
        # For single-step sequences, just trigger the step
        sequence = self.sequences[index]
        if len(sequence) == 1:
            if self.on_step_change:
                self.on_step_change(sequence[0].scenes)
            logger.debug(f"Activated single-step sequence {index}")
            return True
        
        # For multi-step sequences, start playback thread if playing
        if self.playback_state == PlaybackState.PLAYING:
            self.playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self.playback_thread.start()
            logger.debug(f"Started playback of sequence {index}")
        else:
            # If paused, trigger first step but don't start thread
            if self.on_step_change:
                self.on_step_change(sequence[0].scenes)
        
        return True
    
    def stop_playback(self) -> None:
        """Stop current playback."""
        if self.playback_state != PlaybackState.STOPPED:
            self.playback_state = PlaybackState.STOPPED
            self.stop_event.set()
            
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=1.0)
            
            self.active_sequence = None
            self.current_step_index = 0
            
            # Notify state change
            if self.on_playback_state_change:
                self.on_playback_state_change(self.playback_state)
            
            logger.debug("Playback stopped")
    
    def pause_playback(self) -> None:
        """Pause current playback."""
        if self.playback_state == PlaybackState.PLAYING:
            self.playback_state = PlaybackState.PAUSED
            
            # Notify state change
            if self.on_playback_state_change:
                self.on_playback_state_change(self.playback_state)
            
            logger.debug("Playback paused")
    
    def resume_playback(self) -> None:
        """Resume paused playback."""
        if self.playback_state == PlaybackState.PAUSED:
            self.playback_state = PlaybackState.PLAYING
            
            # Notify state change
            if self.on_playback_state_change:
                self.on_playback_state_change(self.playback_state)
            
            logger.debug("Playback resumed")
    
    def next_step(self) -> bool:
        """Advance to next step manually."""
        if not self.active_sequence or self.playback_state == PlaybackState.STOPPED:
            return False
        
        sequence = self.sequences.get(self.active_sequence)
        if not sequence or len(sequence) <= 1:
            return False
        
        self.current_step_index = (self.current_step_index + 1) % len(sequence)
        
        if self.on_step_change:
            self.on_step_change(sequence[self.current_step_index].scenes)
        
        logger.debug(f"Advanced to step {self.current_step_index + 1}/{len(sequence)}")
        return True
    
    def _playback_loop(self) -> None:
        """Main playback loop (runs in thread)."""
        if not self.active_sequence:
            return
        
        sequence = self.sequences[self.active_sequence]
        should_loop = self.loop_settings.get(self.active_sequence, True)
        
        while self.playback_state != PlaybackState.STOPPED and not self.stop_event.is_set():
            # Handle pause
            if self.playback_state == PlaybackState.PAUSED:
                time.sleep(0.1)
                continue
            
            # Get current step
            if not (0 <= self.current_step_index < len(sequence)):
                break
            
            step = sequence[self.current_step_index]
            
            # Trigger step change
            if self.on_step_change:
                try:
                    self.on_step_change(step.scenes)
                except Exception as e:
                    logger.error(f"Error in step change callback: {e}")
            
            # Wait for step duration
            end_time = time.time() + step.duration
            while time.time() < end_time and not self.stop_event.is_set():
                if self.playback_state == PlaybackState.PAUSED:
                    pause_start = time.time()
                    while self.playback_state == PlaybackState.PAUSED and not self.stop_event.is_set():
                        time.sleep(0.1)
                    if not self.stop_event.is_set():
                        end_time += time.time() - pause_start
                time.sleep(0.1)
            
            if self.stop_event.is_set():
                break
            
            # Advance to next step
            self.current_step_index += 1
            
            # Check for sequence completion
            if self.current_step_index >= len(sequence):
                if should_loop:
                    self.current_step_index = 0
                else:
                    if self.on_sequence_complete:
                        try:
                            self.on_sequence_complete()
                        except Exception as e:
                            logger.error(f"Error in complete callback: {e}")
                    self.playback_state = PlaybackState.STOPPED
                    break
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_playback()
