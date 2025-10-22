"""
Device Status Display

Widget for showing device connection status.
"""

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
)

from lumiblox.common.device_state import DeviceState


class DeviceStatusBar(QFrame):
    """Status bar showing device connection states."""

    def __init__(self):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setMaximumHeight(45)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the status bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Device status label
        status_label = QLabel("Devices:")
        status_label.setStyleSheet("color: #cccccc; font-weight: bold; font-size: 11px;")
        layout.addWidget(status_label)
        
        # Launchpad status
        launchpad_container = QHBoxLayout()
        launchpad_label = QLabel("Launchpad:")
        launchpad_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        launchpad_container.addWidget(launchpad_label)
        
        self.launchpad_indicator = QLabel("●")
        self.launchpad_indicator.setStyleSheet("color: #888888; font-size: 16px; font-weight: bold;")
        self.launchpad_text = QLabel("Disconnected")
        self.launchpad_text.setStyleSheet("color: #888888; font-size: 10px;")
        launchpad_container.addWidget(self.launchpad_indicator)
        launchpad_container.addWidget(self.launchpad_text)
        launchpad_container.addStretch()
        
        layout.addLayout(launchpad_container)
        layout.addSpacing(20)
        
        # LightSoftware status
        lightsw_container = QHBoxLayout()
        lightsw_label = QLabel("LightSoftware:")
        lightsw_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        lightsw_container.addWidget(lightsw_label)
        
        self.lightsw_indicator = QLabel("●")
        self.lightsw_indicator.setStyleSheet("color: #888888; font-size: 16px; font-weight: bold;")
        self.lightsw_text = QLabel("Disconnected")
        self.lightsw_text.setStyleSheet("color: #888888; font-size: 10px;")
        lightsw_container.addWidget(self.lightsw_indicator)
        lightsw_container.addWidget(self.lightsw_text)
        lightsw_container.addStretch()
        
        layout.addLayout(lightsw_container)
        layout.addStretch()
    
    def update_launchpad_status(self, state: DeviceState):
        """Update launchpad status indicator."""
        self._update_indicator(self.launchpad_indicator, self.launchpad_text, state)
    
    def update_lightsw_status(self, state: DeviceState):
        """Update light software status indicator."""
        self._update_indicator(self.lightsw_indicator, self.lightsw_text, state)
    
    def _update_indicator(self, indicator: QLabel, text: QLabel, state: DeviceState):
        """Update a single status indicator based on device state."""
        if state == DeviceState.CONNECTED:
            indicator.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold;")
            text.setStyleSheet("color: #4CAF50; font-size: 10px;")
            text.setText("Connected")
        elif state == DeviceState.CONNECTING:
            indicator.setStyleSheet("color: #FFA726; font-size: 16px; font-weight: bold;")
            text.setStyleSheet("color: #FFA726; font-size: 10px;")
            text.setText("Connecting...")
        elif state == DeviceState.ERROR:
            indicator.setStyleSheet("color: #F44336; font-size: 16px; font-weight: bold;")
            text.setStyleSheet("color: #F44336; font-size: 10px;")
            text.setText("Error")
        else:  # DISCONNECTED
            indicator.setStyleSheet("color: #888888; font-size: 16px; font-weight: bold;")
            text.setStyleSheet("color: #888888; font-size: 10px;")
            text.setText("Disconnected")
