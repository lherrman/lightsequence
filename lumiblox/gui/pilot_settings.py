"""
Pilot Settings Dialog

Comprehensive settings panel for pilot system configuration.
"""

import logging
from typing import Optional

import qtawesome as qta
import pygame.midi
from PySide6.QtCore import Qt, Signal, QRect, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QComboBox,
    QGroupBox,
    QScrollArea,
    QFrame,
)

from lumiblox.pilot.phrase_detector import CaptureRegion
from lumiblox.pilot.midi_actions import MidiActionConfig, MidiActionType
from lumiblox.common.config import get_config
from lumiblox.gui.ui_constants import (
    BUTTON_SIZE_SMALL,
    BUTTON_SIZE_LARGE,
    ICON_SIZE_SMALL,
    ICON_SIZE_MEDIUM,
    BUTTON_STYLE,
    HEADER_LABEL_STYLE,
    VALUE_LABEL_STYLE,
)

logger = logging.getLogger(__name__)


class MidiDeviceSelector(QWidget):
    """Widget for selecting a MIDI device."""

    device_changed = Signal(str)  # Emits device name

    def __init__(self, label: str, device_keyword: str = "", parent=None):
        super().__init__(parent)
        self.device_keyword = device_keyword

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Label
        label_widget = QLabel(label)
        label_widget.setFixedWidth(150)
        layout.addWidget(label_widget)

        # Combo box
        self.combo = QComboBox()
        self.combo.currentTextChanged.connect(self.device_changed.emit)
        layout.addWidget(self.combo, 1)

        # Refresh button
        refresh_btn = QPushButton()
        refresh_btn.setIcon(qta.icon("fa5s.sync", color="white"))
        refresh_btn.setIconSize(ICON_SIZE_SMALL)
        refresh_btn.setFixedSize(BUTTON_SIZE_SMALL)
        refresh_btn.setStyleSheet(BUTTON_STYLE)
        refresh_btn.setToolTip("Refresh MIDI devices")
        refresh_btn.clicked.connect(self.refresh_devices)
        layout.addWidget(refresh_btn)

        self.refresh_devices()

    def refresh_devices(self) -> None:
        """Refresh the list of MIDI devices."""
        current = self.combo.currentText()

        self.combo.blockSignals(True)
        self.combo.clear()

        try:
            if not pygame.midi.get_init():
                pygame.midi.init()

            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                if not info:
                    continue
                _interface, name, is_input, is_output, _opened = info
                decoded = name.decode() if isinstance(name, bytes) else str(name)

                # Add device to list
                self.combo.addItem(decoded)

            # Try to restore previous selection or select matching keyword
            if current and self.combo.findText(current) >= 0:
                self.combo.setCurrentText(current)
            elif self.device_keyword:
                # Find device matching keyword
                for i in range(self.combo.count()):
                    if self.device_keyword.lower() in self.combo.itemText(i).lower():
                        self.combo.setCurrentIndex(i)
                        break

        except Exception as e:
            logger.error(f"Error refreshing MIDI devices: {e}")

        self.combo.blockSignals(False)

    def get_device(self) -> str:
        """Get the currently selected device name."""
        return self.combo.currentText()

    def set_device(self, device_name: str) -> None:
        """Set the current device by name."""
        index = self.combo.findText(device_name)
        if index >= 0:
            self.combo.setCurrentIndex(index)


class DeckRegionWidget(QWidget):
    """Widget for configuring a single deck's regions."""

    configure_requested = Signal(str)  # Emits deck name

    def __init__(self, deck_name: str, parent=None):
        super().__init__(parent)
        self.deck_name = deck_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Deck label
        deck_label = QLabel(f"Deck {deck_name}")
        deck_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        deck_label.setFixedWidth(60)
        layout.addWidget(deck_label)

        # Status labels
        status_layout = QVBoxLayout()
        status_layout.setSpacing(2)

        self.button_status = QLabel("Button: Not set")
        self.button_status.setStyleSheet("font-size: 10px; color: #999;")
        status_layout.addWidget(self.button_status)

        self.timeline_status = QLabel("Timeline: Not set")
        self.timeline_status.setStyleSheet("font-size: 10px; color: #999;")
        status_layout.addWidget(self.timeline_status)

        layout.addLayout(status_layout, 1)

        # Configure button
        config_btn = QPushButton("Set Regions")
        config_btn.setFixedSize(BUTTON_SIZE_LARGE)
        config_btn.setStyleSheet(BUTTON_STYLE)
        config_btn.clicked.connect(lambda: self.configure_requested.emit(deck_name))
        layout.addWidget(config_btn)

        # Load current status
        self.refresh_status()

    def refresh_status(self) -> None:
        """Refresh the status display from config."""
        config = get_config()
        button_region = config.get_deck_region(self.deck_name, "master_button_region")
        timeline_region = config.get_deck_region(self.deck_name, "timeline_region")

        if button_region:
            self.button_status.setText(
                f"Button: ({button_region['x']}, {button_region['y']})"
            )
            self.button_status.setStyleSheet("font-size: 10px; color: #4f4;")
        else:
            self.button_status.setText("Button: Not set")
            self.button_status.setStyleSheet("font-size: 10px; color: #999;")

        if timeline_region:
            self.timeline_status.setText(
                f"Timeline: ({timeline_region['x']}, {timeline_region['y']})"
            )
            self.timeline_status.setStyleSheet("font-size: 10px; color: #4f4;")
        else:
            self.timeline_status.setText("Timeline: Not set")
            self.timeline_status.setStyleSheet("font-size: 10px; color: #999;")


class MidiMonitorWidget(QWidget):
    """Widget for monitoring MIDI messages."""

    def __init__(self, pilot_controller=None, parent=None):
        super().__init__(parent)
        self.pilot_controller = pilot_controller
        self.monitoring = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header = QHBoxLayout()
        header_label = QLabel("MIDI Monitor")
        header_label.setStyleSheet(HEADER_LABEL_STYLE)
        header.addWidget(header_label)
        header.addStretch()

        # Monitor toggle button
        self.monitor_btn = QPushButton("Start Monitoring")
        self.monitor_btn.setFixedSize(BUTTON_SIZE_LARGE)
        self.monitor_btn.setStyleSheet(BUTTON_STYLE)
        self.monitor_btn.clicked.connect(self._toggle_monitoring)
        header.addWidget(self.monitor_btn)

        layout.addLayout(header)

        # Monitor display (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #555; background: #1a1a1a; }"
        )

        self.monitor_content = QWidget()
        self.monitor_layout = QVBoxLayout(self.monitor_content)
        self.monitor_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.monitor_layout.setSpacing(2)

        scroll.setWidget(self.monitor_content)
        layout.addWidget(scroll)

        # Timer for polling MIDI
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_midi)
        self.poll_timer.setInterval(50)  # 50ms

        # Message history
        self.message_history = []
        self.max_messages = 50

    def set_pilot_controller(self, pilot_controller) -> None:
        """Set the pilot controller reference."""
        self.pilot_controller = pilot_controller

    def _toggle_monitoring(self) -> None:
        """Toggle MIDI monitoring."""
        if self.monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self) -> None:
        """Start monitoring MIDI messages."""
        if not self.pilot_controller:
            return

        self.monitoring = True
        self.monitor_btn.setText("Stop Monitoring")
        self.monitor_btn.setStyleSheet(
            BUTTON_STYLE + "QPushButton { background-color: #c44; }"
        )

        # Clear previous messages
        self.message_history.clear()
        while self.monitor_layout.count():
            item = self.monitor_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Clear pending messages
        if (
            self.pilot_controller.clock_sync.midi_in
            and self.pilot_controller.clock_sync.midi_in.poll()
        ):
            self.pilot_controller.clock_sync.midi_in.read(128)

        self.poll_timer.start()

    def _stop_monitoring(self) -> None:
        """Stop monitoring MIDI messages."""
        self.monitoring = False
        self.poll_timer.stop()
        self.monitor_btn.setText("Start Monitoring")
        self.monitor_btn.setStyleSheet(BUTTON_STYLE)

    def _poll_midi(self) -> None:
        """Poll for MIDI messages."""
        if not self.monitoring or not self.pilot_controller:
            return

        midi_in = self.pilot_controller.clock_sync.midi_in
        if not midi_in or not midi_in.poll():
            return

        # Read messages
        for data, _timestamp in midi_in.read(128):
            if not data or isinstance(data, int):
                continue

            # Ignore clock messages
            if data[0] in {0xF8, 0xFA, 0xFB, 0xFC}:
                continue

            # Add to display
            self._add_message(data)

    def _add_message(self, data: list) -> None:
        """Add a MIDI message to the display."""
        status = data[0]
        data1 = data[1] if len(data) > 1 else None
        data2 = data[2] if len(data) > 2 else None

        # Format message
        msg_type = self._get_message_type(status)
        msg_text = f"0x{status:02X} ({msg_type})"
        if data1 is not None:
            msg_text += f" - Data1: {data1}"
        if data2 is not None:
            msg_text += f" - Data2: {data2}"

        # Create label
        label = QLabel(msg_text)
        label.setStyleSheet(
            "font-size: 10px; padding: 4px; color: #4f4; background: #1a1a1a; font-family: monospace;"
        )

        # Add to top
        self.monitor_layout.insertWidget(0, label)
        self.message_history.insert(0, label)

        # Remove old messages
        while len(self.message_history) > self.max_messages:
            old = self.message_history.pop()
            self.monitor_layout.removeWidget(old)
            old.deleteLater()

    def _get_message_type(self, status: int) -> str:
        """Get message type name."""
        if status >= 0x90 and status <= 0x9F:
            return "Note On"
        elif status >= 0x80 and status <= 0x8F:
            return "Note Off"
        elif status >= 0xB0 and status <= 0xBF:
            return "CC"
        elif status >= 0xC0 and status <= 0xCF:
            return "Prog Change"
        else:
            return "Other"

    def cleanup(self) -> None:
        """Cleanup when dialog closes."""
        if self.monitoring:
            self._stop_monitoring()


class MidiLearnDialog(QDialog):
    """Dialog for learning MIDI messages and creating actions."""

    action_configured = Signal(object)  # Emits MidiActionConfig

    def __init__(self, pilot_controller, parent=None):
        super().__init__(parent)
        self.pilot_controller = pilot_controller
        self.learned_message = None
        self.listening = False

        self.setWindowTitle("MIDI Learn")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "1. Click 'Start Learning' below\n"
            "2. Press a button/pad on your MIDI controller\n"
            "3. Give the action a name and select its type\n"
            "4. Click 'Save' to create the action"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "padding: 10px; background-color: #2d2d2d; border-radius: 5px;"
        )
        layout.addWidget(instructions)

        # Learn button
        self.learn_btn = QPushButton("Start Learning")
        self.learn_btn.clicked.connect(self._toggle_learning)
        self.learn_btn.setStyleSheet(BUTTON_STYLE)
        layout.addWidget(self.learn_btn)

        # Status label
        self.status_label = QLabel("Not learning")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 12px; padding: 10px;")
        layout.addWidget(self.status_label)

        # MIDI message details (hidden initially)
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)

        self.status_byte_label = QLabel()
        self.data1_label = QLabel()
        self.data2_label = QLabel()

        details_layout.addWidget(self.status_byte_label)
        details_layout.addWidget(self.data1_label)
        details_layout.addWidget(self.data2_label)

        self.details_widget.setVisible(False)
        layout.addWidget(self.details_widget)

        # Action configuration (hidden initially)
        self.config_widget = QWidget()
        config_layout = QVBoxLayout(self.config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)

        # Action name
        from PySide6.QtWidgets import QLineEdit

        config_layout.addWidget(QLabel("Action Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Phrase Sync")
        config_layout.addWidget(self.name_input)

        # Action type
        config_layout.addWidget(QLabel("Action Type:"))
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItem("Phrase Sync", MidiActionType.PHRASE_SYNC.value)
        config_layout.addWidget(self.action_type_combo)

        self.config_widget.setVisible(False)
        layout.addWidget(self.config_widget)

        # Dialog buttons
        from PySide6.QtWidgets import QDialogButtonBox

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = button_box.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.accept)
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(button_box)

        # Start listening timer (polls for MIDI messages)
        self.listen_timer = QTimer(self)
        self.listen_timer.timeout.connect(self._check_for_midi)
        self.listen_timer.setInterval(50)  # Check every 50ms

    def _toggle_learning(self) -> None:
        """Toggle MIDI learning mode."""
        if self.listening:
            self._stop_learning()
        else:
            self._start_learning()

    def _start_learning(self) -> None:
        """Start listening for MIDI messages."""
        self.listening = True
        self.learned_message = None
        self.learn_btn.setText("Stop Learning")
        self.learn_btn.setStyleSheet(
            BUTTON_STYLE + "QPushButton { background-color: #c44; }"
        )
        self.status_label.setText("Listening... Press a MIDI button/pad")
        self.status_label.setStyleSheet("font-size: 12px; padding: 10px; color: #4f4;")
        self.details_widget.setVisible(False)
        self.config_widget.setVisible(False)
        self.save_button.setEnabled(False)

        # Clear any pending MIDI messages
        if self.pilot_controller and self.pilot_controller.clock_sync.midi_in:
            self.pilot_controller.clock_sync.midi_in.read(128)

        self.listen_timer.start()

    def _stop_learning(self) -> None:
        """Stop listening for MIDI messages."""
        self.listening = False
        self.listen_timer.stop()
        self.learn_btn.setText("Start Learning")
        self.learn_btn.setStyleSheet(BUTTON_STYLE)
        if not self.learned_message:
            self.status_label.setText("Not learning")
            self.status_label.setStyleSheet("font-size: 12px; padding: 10px;")

    def _check_for_midi(self) -> None:
        """Check for incoming MIDI messages during learning."""
        if not self.listening or not self.pilot_controller:
            return

        midi_in = self.pilot_controller.clock_sync.midi_in
        if not midi_in or not midi_in.poll():
            return

        # Read MIDI messages
        for data, _timestamp in midi_in.read(128):
            if not data or isinstance(data, int):
                continue

            # Ignore MIDI clock messages
            if data[0] in {0xF8, 0xFA, 0xFB, 0xFC}:
                continue

            # Got a valid message!
            self._on_midi_learned(data)
            break

    def _on_midi_learned(self, data: list) -> None:
        """Handle a learned MIDI message."""
        self.learned_message = data
        self._stop_learning()

        # Display message details
        status = data[0]
        data1 = data[1] if len(data) > 1 else None
        data2 = data[2] if len(data) > 2 else None

        self.status_byte_label.setText(f"Status: 0x{status:02X} ({status})")
        self.data1_label.setText(
            f"Data 1: {data1}" if data1 is not None else "Data 1: None"
        )
        self.data2_label.setText(
            f"Data 2: {data2}" if data2 is not None else "Data 2: None"
        )

        self.details_widget.setVisible(True)
        self.config_widget.setVisible(True)
        self.status_label.setText("MIDI message learned! Configure the action below.")
        self.status_label.setStyleSheet("font-size: 12px; padding: 10px; color: #4f4;")
        self.save_button.setEnabled(True)

        # Suggest a default name
        msg_type = self._get_message_type_name(status)
        self.name_input.setText(f"{msg_type} {data1 if data1 is not None else ''}")

    def _get_message_type_name(self, status: int) -> str:
        """Get a human-readable name for a MIDI message type."""
        if status >= 0x90 and status <= 0x9F:
            return "Note On"
        elif status >= 0x80 and status <= 0x8F:
            return "Note Off"
        elif status >= 0xB0 and status <= 0xBF:
            return "CC"
        elif status >= 0xC0 and status <= 0xCF:
            return "Program Change"
        else:
            return f"MIDI 0x{status:02X}"

    def accept(self) -> None:
        """Handle dialog acceptance - create the action."""
        if not self.learned_message or not self.name_input.text().strip():
            return

        # Create action config
        status = self.learned_message[0]
        data1 = self.learned_message[1] if len(self.learned_message) > 1 else None
        # Note: data2 is intentionally ignored - we trigger on any velocity/value

        action = MidiActionConfig(
            name=self.name_input.text().strip(),
            action_type=MidiActionType(self.action_type_combo.currentData()),
            status=status,
            data1=data1,
            data2=None,  # Ignore velocity/value for now (trigger on any value)
            parameters={},
        )

        self.action_configured.emit(action)
        super().accept()


class PilotSettingsDialog(QDialog):
    """Comprehensive pilot settings dialog."""

    regions_configured = Signal(
        str, QRect, QRect
    )  # deck_name, button_rect, timeline_rect
    midi_action_added = Signal(object)  # MidiActionConfig
    midi_action_removed = Signal(str)  # action name

    def __init__(self, pilot_controller=None, parent=None):
        super().__init__(parent)
        self.pilot_controller = pilot_controller

        self.setWindowTitle("Pilot System Settings")
        self.setModal(False)
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(15)

        # === MIDI DEVICES SECTION ===
        devices_group = QGroupBox("MIDI Devices")
        devices_layout = QVBoxLayout(devices_group)

        # MIDI Clock device
        self.midiclock_selector = MidiDeviceSelector("MIDI Clock:", "midiclock")
        devices_layout.addWidget(self.midiclock_selector)

        # LightSoftware In
        self.lightsw_in_selector = MidiDeviceSelector(
            "LightSoftware In:", "lightsoftware_in"
        )
        devices_layout.addWidget(self.lightsw_in_selector)

        # LightSoftware Out
        self.lightsw_out_selector = MidiDeviceSelector(
            "LightSoftware Out:", "lightsoftware_out"
        )
        devices_layout.addWidget(self.lightsw_out_selector)

        layout.addWidget(devices_group)

        # === DECK REGIONS SECTION ===
        decks_group = QGroupBox("Deck Capture Regions")
        decks_layout = QVBoxLayout(decks_group)

        self.deck_widgets = {}
        for deck in ["A", "B", "C", "D"]:
            deck_widget = DeckRegionWidget(deck)
            deck_widget.configure_requested.connect(self._configure_deck)
            self.deck_widgets[deck] = deck_widget
            decks_layout.addWidget(deck_widget)

        layout.addWidget(decks_group)

        # === MIDI ACTIONS SECTION ===
        actions_group = QGroupBox("MIDI Actions")
        actions_layout = QVBoxLayout(actions_group)

        # Header with learn button
        actions_header = QHBoxLayout()
        actions_header.addWidget(QLabel("Configured Actions:"))
        actions_header.addStretch()

        learn_btn = QPushButton("Learn New Action")
        learn_btn.setIcon(qta.icon("fa5s.wifi", color="white"))
        learn_btn.setIconSize(ICON_SIZE_SMALL)
        learn_btn.setFixedSize(BUTTON_SIZE_LARGE)
        learn_btn.setStyleSheet(BUTTON_STYLE)
        learn_btn.clicked.connect(self._on_midi_learn)
        actions_header.addWidget(learn_btn)

        actions_layout.addLayout(actions_header)

        # Actions list
        self.actions_container = QVBoxLayout()
        self.actions_container.setSpacing(2)
        actions_layout.addLayout(self.actions_container)

        layout.addWidget(actions_group)

        # === MIDI MONITOR SECTION ===
        monitor_group = QGroupBox("MIDI Monitor")
        monitor_layout = QVBoxLayout(monitor_group)

        self.midi_monitor = MidiMonitorWidget(pilot_controller)
        monitor_layout.addWidget(self.midi_monitor)

        layout.addWidget(monitor_group)

        # Add stretch at the end
        layout.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Bottom buttons
        from PySide6.QtWidgets import QDialogButtonBox

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = button_box.button(QDialogButtonBox.StandardButton.Close)
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(button_box)

        # Load current configuration
        self._load_midi_actions()

    def set_pilot_controller(self, pilot_controller) -> None:
        """Set the pilot controller reference."""
        self.pilot_controller = pilot_controller
        self.midi_monitor.set_pilot_controller(pilot_controller)
        self._load_midi_actions()

    def _configure_deck(self, deck_name: str) -> None:
        """Open region configuration for a specific deck."""
        from lumiblox.gui.pilot_widget import RegionConfigDialog

        config_dialog = RegionConfigDialog(deck_name, self)
        config_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        config_dialog.regions_configured.connect(self._on_regions_configured)
        config_dialog.accepted.connect(
            lambda: self.deck_widgets[deck_name].refresh_status()
        )
        config_dialog.show()
        config_dialog.raise_()
        config_dialog.activateWindow()

    def _on_regions_configured(
        self, deck_name: str, button_rect: QRect, timeline_rect: QRect
    ) -> None:
        """Handle deck region configuration."""
        # Save to config with correct region type names
        config = get_config()
        config.set_deck_region(
            deck_name,
            "master_button_region",
            {
                "x": button_rect.x(),
                "y": button_rect.y(),
                "width": button_rect.width(),
                "height": button_rect.height(),
            },
        )
        config.set_deck_region(
            deck_name,
            "timeline_region",
            {
                "x": timeline_rect.x(),
                "y": timeline_rect.y(),
                "width": timeline_rect.width(),
                "height": timeline_rect.height(),
            },
        )

        # Configure on pilot controller if available
        if self.pilot_controller:
            button_region = CaptureRegion(
                button_rect.x(),
                button_rect.y(),
                button_rect.width(),
                button_rect.height(),
            )
            timeline_region = CaptureRegion(
                timeline_rect.x(),
                timeline_rect.y(),
                timeline_rect.width(),
                timeline_rect.height(),
            )
            self.pilot_controller.configure_deck(
                deck_name, button_region, timeline_region
            )

        # Emit signal
        self.regions_configured.emit(deck_name, button_rect, timeline_rect)

        # Refresh status
        self.deck_widgets[deck_name].refresh_status()

        logger.info(f"Configured regions for deck {deck_name}")

    def _load_midi_actions(self) -> None:
        """Load MIDI actions from config and display them."""
        # Clear existing widgets
        while self.actions_container.count():
            item = self.actions_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        # Load from config
        config = get_config()
        actions = config.get_midi_actions()

        if not actions:
            # Show "no actions" message
            no_actions_label = QLabel("No MIDI actions configured")
            no_actions_label.setStyleSheet(
                "color: #666666; font-size: 10px; padding: 4px;"
            )
            self.actions_container.addWidget(no_actions_label)
            return

        # Create widget for each action
        for action_dict in actions:
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(4)

            # Action info label
            name = action_dict.get("name", "Unknown")
            action_type = action_dict.get("action_type", "unknown")
            status = action_dict.get("status", 0)
            data1 = action_dict.get("data1")

            info_text = f"{name} ({action_type}): 0x{status:02X}"
            if data1 is not None:
                info_text += f" {data1}"

            info_label = QLabel(info_text)
            info_label.setStyleSheet(
                "color: #cccccc; font-size: 10px; padding: 2px 4px;"
            )
            action_layout.addWidget(info_label, 1)

            # Delete button
            from PySide6.QtWidgets import QToolButton

            delete_btn = QToolButton()
            delete_btn.setIcon(qta.icon("fa5s.trash", color="white"))
            delete_btn.setToolTip(f"Delete {name}")
            delete_btn.setFixedSize(20, 20)
            delete_btn.setStyleSheet(BUTTON_STYLE)
            delete_btn.clicked.connect(
                lambda checked=False, n=name: self._on_delete_midi_action(n)
            )
            action_layout.addWidget(delete_btn)

            self.actions_container.addWidget(action_widget)

    def _on_midi_learn(self) -> None:
        """Open MIDI learn dialog."""
        if not self.pilot_controller:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Pilot Not Available",
                "Please start the pilot system first.",
            )
            return

        dialog = MidiLearnDialog(self.pilot_controller, self)
        dialog.action_configured.connect(self._on_midi_action_configured)
        dialog.exec()

    def _on_midi_action_configured(self, action: MidiActionConfig) -> None:
        """Handle newly configured MIDI action."""
        # Save to config
        config = get_config()
        config.add_midi_action(action.to_dict())

        # Add to pilot controller if available
        if self.pilot_controller:
            self.pilot_controller.add_midi_action(action)

        # Reload display
        self._load_midi_actions()

        # Emit signal
        self.midi_action_added.emit(action)

        logger.info(f"MIDI action configured: {action.name}")

    def _on_delete_midi_action(self, name: str) -> None:
        """Delete a MIDI action."""
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Delete MIDI Action",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Remove from config
            config = get_config()
            config.remove_midi_action(name)

            # Remove from pilot controller
            if self.pilot_controller:
                self.pilot_controller.remove_midi_action(name)

            # Reload display
            self._load_midi_actions()

            # Emit signal
            self.midi_action_removed.emit(name)

            logger.info(f"MIDI action deleted: {name}")

    def closeEvent(self, event) -> None:
        """Handle dialog close."""
        self.midi_monitor.cleanup()
        super().closeEvent(event)
