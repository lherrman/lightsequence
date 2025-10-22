"""
Device Monitor

Background thread that monitors device connections and attempts automatic reconnection.
"""

import logging
import threading
import time
import typing as t

from lumiblox.common.device_state import DeviceManager, DeviceType, DeviceState

logger = logging.getLogger(__name__)


class DeviceMonitor:
    """
    Background thread that monitors device connection status and attempts reconnection.
    """
    
    def __init__(
        self,
        device_manager: DeviceManager,
        check_interval: float = 3.0,
        max_reconnect_attempts: int = 3
    ):
        """
        Initialize device monitor.
        
        Args:
            device_manager: The device manager to monitor
            check_interval: Seconds between connection checks
            max_reconnect_attempts: Max consecutive reconnection attempts before backing off
        """
        self.device_manager = device_manager
        self.check_interval = check_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        
        self._thread: t.Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False
        
        # Reconnection callbacks - device-specific
        self._reconnect_callbacks: t.Dict[DeviceType, t.Callable[[], bool]] = {}
    
    def register_reconnect_callback(
        self,
        device_type: DeviceType,
        callback: t.Callable[[], bool]
    ) -> None:
        """
        Register a callback function to attempt reconnection for a device.
        
        Args:
            device_type: The type of device
            callback: Function that attempts to reconnect, returns True if successful
        """
        self._reconnect_callbacks[device_type] = callback
        logger.debug(f"Registered reconnect callback for {device_type.value}")
    
    def start(self) -> None:
        """Start the device monitoring thread."""
        if self._is_running:
            logger.warning("Device monitor already running")
            return
        
        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Device monitor started")
    
    def stop(self) -> None:
        """Stop the device monitoring thread."""
        if not self._is_running:
            return
        
        self._is_running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        
        logger.info("Device monitor stopped")
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop - runs in background thread."""
        logger.debug("Device monitor loop started")
        
        while not self._stop_event.is_set():
            try:
                # Check each registered device
                for device_type, reconnect_callback in self._reconnect_callbacks.items():
                    if self._stop_event.is_set():
                        break
                    
                    self._check_device(device_type, reconnect_callback)
                
                # Sleep with ability to be interrupted
                self._stop_event.wait(timeout=self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in device monitor loop: {e}")
                time.sleep(1.0)  # Brief pause on error
        
        logger.debug("Device monitor loop ended")
    
    def _check_device(
        self,
        device_type: DeviceType,
        reconnect_callback: t.Callable[[], bool]
    ) -> None:
        """
        Check a specific device and attempt reconnection if needed.
        
        Args:
            device_type: The type of device to check
            reconnect_callback: Function to call to attempt reconnection
        """
        current_state = self.device_manager.get_state(device_type)
        
        # Only attempt reconnection if disconnected or in error state
        if current_state not in [DeviceState.DISCONNECTED, DeviceState.ERROR]:
            return
        
        # Check if we've exceeded max reconnection attempts
        attempts = self.device_manager.get_reconnect_attempts(device_type)
        if attempts >= self.max_reconnect_attempts:
            # Back off - don't spam reconnection attempts
            # Reset counter after some time has passed
            if attempts == self.max_reconnect_attempts:
                logger.info(
                    f"Max reconnection attempts reached for {device_type.value}, "
                    "will retry less frequently"
                )
                # Artificially increase attempts to trigger backoff
                self.device_manager.set_connecting(device_type)
            
            # Only retry every 5th check cycle when backed off
            if attempts % 5 != 0:
                return
        
        # Attempt reconnection
        logger.debug(f"Attempting to reconnect {device_type.value}...")
        
        try:
            success = reconnect_callback()
            
            if success:
                logger.info(f"✅ Successfully reconnected {device_type.value}")
                self.device_manager.reset_reconnect_attempts(device_type)
            else:
                logger.debug(f"Reconnection attempt failed for {device_type.value}")
                
        except Exception as e:
            logger.error(f"Error during {device_type.value} reconnection: {e}")
            self.device_manager.set_error(device_type, str(e))
    
    def is_running(self) -> bool:
        """Check if the monitor is currently running."""
        return self._is_running
