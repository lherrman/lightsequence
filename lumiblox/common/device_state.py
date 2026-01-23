"""
Device State Management

Provides device state tracking and connection management for all hardware devices.
"""

import logging
import time
import typing as t
from enum import Enum
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


class DeviceState(str, Enum):
    """Device connection states."""
    
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class DeviceType(str, Enum):
    """Types of devices managed by the system."""
    
    LAUNCHPAD = "launchpad"
    LIGHT_SOFTWARE = "light_software"


@dataclass
class DeviceStatus:
    """Status information for a device."""
    
    device_type: DeviceType
    state: DeviceState
    last_connected: t.Optional[float] = None
    last_error: t.Optional[str] = None
    reconnect_attempts: int = 0
    
    def is_connected(self) -> bool:
        """Check if device is currently connected."""
        return self.state == DeviceState.CONNECTED
    
    def mark_connected(self) -> None:
        """Mark device as connected."""
        self.state = DeviceState.CONNECTED
        self.last_connected = time.time()
        self.reconnect_attempts = 0
        self.last_error = None
    
    def mark_disconnected(self) -> None:
        """Mark device as disconnected."""
        self.state = DeviceState.DISCONNECTED
        self.last_error = None
    
    def mark_connecting(self) -> None:
        """Mark device as attempting connection."""
        self.state = DeviceState.CONNECTING
        self.reconnect_attempts += 1
    
    def mark_error(self, error_msg: str) -> None:
        """Mark device as in error state."""
        self.state = DeviceState.ERROR
        self.last_error = error_msg


class DeviceManager:
    """
    Manages connection state for all hardware devices.
    
    Provides thread-safe state tracking and connection management.
    """
    
    def __init__(self):
        self._devices: t.Dict[DeviceType, DeviceStatus] = {}
        self._lock = Lock()
        self._state_change_callbacks: t.List[t.Callable[[DeviceType, DeviceState], None]] = []
        
        # Initialize device statuses
        for device_type in DeviceType:
            self._devices[device_type] = DeviceStatus(
                device_type=device_type,
                state=DeviceState.DISCONNECTED
            )
    
    def get_status(self, device_type: DeviceType) -> DeviceStatus:
        """Get current status of a device."""
        with self._lock:
            return self._devices[device_type]
    
    def get_state(self, device_type: DeviceType) -> DeviceState:
        """Get current state of a device."""
        with self._lock:
            return self._devices[device_type].state
    
    def is_connected(self, device_type: DeviceType) -> bool:
        """Check if a device is connected."""
        with self._lock:
            return self._devices[device_type].is_connected()
    
    def set_connected(self, device_type: DeviceType) -> None:
        """Mark a device as connected."""
        with self._lock:
            old_state = self._devices[device_type].state
            self._devices[device_type].mark_connected()
            new_state = DeviceState.CONNECTED
        
        if old_state != new_state:
            logger.info(f"{device_type.value} connected")
            self._notify_state_change(device_type, new_state)
    
    def set_disconnected(self, device_type: DeviceType) -> None:
        """Mark a device as disconnected."""
        with self._lock:
            old_state = self._devices[device_type].state
            self._devices[device_type].mark_disconnected()
            new_state = DeviceState.DISCONNECTED
        
        if old_state != new_state:
            logger.warning(f"{device_type.value} disconnected")
            self._notify_state_change(device_type, new_state)
    
    def set_connecting(self, device_type: DeviceType) -> None:
        """Mark a device as attempting connection."""
        with self._lock:
            old_state = self._devices[device_type].state
            self._devices[device_type].mark_connecting()
            new_state = DeviceState.CONNECTING
        
        if old_state != new_state:
            attempts = self._devices[device_type].reconnect_attempts
            logger.info(f"{device_type.value} connecting (attempt {attempts})...")
            self._notify_state_change(device_type, new_state)
    
    def set_error(self, device_type: DeviceType, error_msg: str) -> None:
        """Mark a device as in error state."""
        with self._lock:
            old_state = self._devices[device_type].state
            self._devices[device_type].mark_error(error_msg)
            new_state = DeviceState.ERROR
        
        if old_state != new_state:
            logger.error(f"⚠️ {device_type.value} error: {error_msg}")
            self._notify_state_change(device_type, new_state)
    
    def get_reconnect_attempts(self, device_type: DeviceType) -> int:
        """Get number of reconnection attempts for a device."""
        with self._lock:
            return self._devices[device_type].reconnect_attempts
    
    def reset_reconnect_attempts(self, device_type: DeviceType) -> None:
        """Reset reconnection attempt counter."""
        with self._lock:
            self._devices[device_type].reconnect_attempts = 0
    
    def get_last_error(self, device_type: DeviceType) -> t.Optional[str]:
        """Get last error message for a device."""
        with self._lock:
            return self._devices[device_type].last_error
    
    def register_state_change_callback(
        self, callback: t.Callable[[DeviceType, DeviceState], None]
    ) -> None:
        """Register a callback to be notified of state changes."""
        self._state_change_callbacks.append(callback)
    
    def unregister_state_change_callback(
        self, callback: t.Callable[[DeviceType, DeviceState], None]
    ) -> None:
        """Unregister a state change callback."""
        if callback in self._state_change_callbacks:
            self._state_change_callbacks.remove(callback)
    
    def _notify_state_change(self, device_type: DeviceType, new_state: DeviceState) -> None:
        """Notify all registered callbacks of a state change."""
        for callback in self._state_change_callbacks:
            try:
                callback(device_type, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
