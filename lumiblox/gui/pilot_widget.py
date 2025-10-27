"""
Pilot Widget (Redesigned)

Modern, compact GUI for MIDI clock sync and phrase detection with automation rules.
"""

import logging
from typing import Optional, Callable

import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QRect, QTimer
from PySide6.QtGui import QColor, QPainter, QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QGroupBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QToolButton,
    QFrame,
)

from lumiblox.pilot.phrase_detector import CaptureRegion
from lumiblox.pilot.pilot_preset import PilotPresetManager
from lumiblox.pilot.midi_actions import MidiActionConfig, MidiActionType
from lumiblox.gui.rule_editor import PresetEditorDialog
from lumiblox.common.config import get_config
from lumiblox.gui.ui_constants import (
    BUTTON_SIZE_LARGE,
    BUTTON_SIZE_SMALL,
    ICON_SIZE_MEDIUM,
    BUTTON_STYLE,
    VALUE_LABEL_STYLE,
    HEADER_LABEL_STYLE,
    ICON_SIZE_SMALL,
    COLOR_BG_NORMAL,
    COLOR_BG_LIGHT,
    COLOR_BG_DARK,
)

logger = logging.getLogger(__name__)


# Region selector and config dialog remain the same
class FixedSizeRegionSelector(QWidget):
    """Draggable fixed-size overlay window for region selection."""

    region_confirmed = Signal(QRect)
    selection_cancelled = Signal()

    def __init__(self, region_type: str):
        """
        Create a fixed-size region selector.

        Args:
            region_type: Either "button" or "timeline"
        """
        super().__init__(
            None,
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool,  # Prevents Windows system sounds
        )
        self.setWindowOpacity(0.7)
        self.region_type = region_type

        # Set fixed size based on region type
        if region_type == "button":
            self.setFixedSize(64, 22)  # Master button size
            self._title = "Master Button"
        else:
            self.setFixedSize(220, 88)  # Timeline size
            self._title = "Timeline"

        # Blue background
        self.setStyleSheet("background-color: #0078d4;")

        # Dragging state
        self._drag_position = None

    def paintEvent(self, event) -> None:
        """Draw title bar."""
        painter = QPainter(self)
        painter.fillRect(0, 0, self.width(), 20, QColor(0, 120, 200))

        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.width(), 20), Qt.AlignmentFlag.AlignCenter, self._title
        )
        painter.end()

    def mousePressEvent(self, event) -> None:
        """Start dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Store offset from mouse to window top-left
            global_pos = event.globalPosition()
            window_pos = self.pos()
            self._drag_position = global_pos.toPoint() - window_pos
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Handle dragging."""
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_position is not None
        ):
            # Move window to follow mouse
            global_pos = event.globalPosition()
            new_pos = global_pos.toPoint() - self._drag_position
            self.move(new_pos)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        """End dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = None
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Escape:
            self.selection_cancelled.emit()
            self.close()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.confirm_region()

    def confirm_region(self) -> None:
        """Confirm the current position and emit the region."""
        geometry = self.frameGeometry()
        self.region_confirmed.emit(geometry)
        self.close()


class RegionConfigDialog(QDialog):
    """Dialog for configuring both capture regions for a deck."""

    regions_configured = Signal(str, QRect, QRect)

    def __init__(self, deck_name: str, parent=None):
        super().__init__(parent)
        self.deck_name = deck_name
        self.button_rect = None
        self.timeline_rect = None
        self.button_overlay: Optional[FixedSizeRegionSelector] = None
        self.timeline_overlay: Optional[FixedSizeRegionSelector] = None

        self.setWindowTitle(f"Configure Deck {deck_name} Capture Regions")
        self.setModal(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            f"1. Click 'Show Overlay Windows' below\n"
            f"2. Drag the blue overlay windows to align with Deck {deck_name}\n"
            f"3. Press Enter on each window when positioned correctly\n"
            f"4. Click 'Save & Close' when both are set\n"
            f"(Press Escape on a window to cancel)"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(
            "padding: 10px; background-color: #2d2d2d; border-radius: 5px;"
        )
        layout.addWidget(instructions)

        # Button to show overlays
        show_btn = QPushButton("Show Overlay Windows")
        show_btn.clicked.connect(self._show_overlays)
        layout.addWidget(show_btn)

        # Status labels
        self.button_status = QLabel("Master Button: Not set")
        self.timeline_status = QLabel("Timeline: Not set")
        layout.addWidget(self.button_status)
        layout.addWidget(self.timeline_status)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Save & Close")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(button_box)

        self.button_box = button_box

        # Load existing regions and populate status immediately (must be after ok_button creation)
        self._load_existing_regions()

    def _load_existing_regions(self) -> None:
        """Load existing regions from config and populate status labels."""
        config = get_config()
        button_region = config.get_deck_region(self.deck_name, "master_button_region")
        timeline_region = config.get_deck_region(self.deck_name, "timeline_region")

        if button_region:
            rect = QRect(
                button_region["x"],
                button_region["y"],
                button_region["width"],
                button_region["height"],
            )
            self.button_rect = rect
            self.button_status.setText(
                f"Master Button: Set at ({rect.x()}, {rect.y()})"
            )
            logger.info(
                f"Loaded button region for deck {self.deck_name}: {button_region}"
            )

        if timeline_region:
            rect = QRect(
                timeline_region["x"],
                timeline_region["y"],
                timeline_region["width"],
                timeline_region["height"],
            )
            self.timeline_rect = rect
            self.timeline_status.setText(f"Timeline: Set at ({rect.x()}, {rect.y()})")
            logger.info(
                f"Loaded timeline region for deck {self.deck_name}: {timeline_region}"
            )

        # Enable Save button if both regions are already set
        self._check_completion()

    def _show_overlays(self) -> None:
        """Show both overlay windows for positioning."""
        self.button_overlay = FixedSizeRegionSelector("button")
        self.button_overlay.region_confirmed.connect(self._on_button_confirmed)
        self.button_overlay.selection_cancelled.connect(self._on_cancelled)

        self.timeline_overlay = FixedSizeRegionSelector("timeline")
        self.timeline_overlay.region_confirmed.connect(self._on_timeline_confirmed)
        self.timeline_overlay.selection_cancelled.connect(self._on_cancelled)

        # Position overlays at existing locations if available, otherwise center them
        screen = QGuiApplication.primaryScreen().geometry()
        center_x = screen.center().x()
        center_y = screen.center().y()

        # Use already-loaded regions if available
        if self.button_rect:
            self.button_overlay.move(self.button_rect.x(), self.button_rect.y())
        else:
            self.button_overlay.move(center_x - 200, center_y - 50)

        if self.timeline_rect:
            self.timeline_overlay.move(self.timeline_rect.x(), self.timeline_rect.y())
        else:
            self.timeline_overlay.move(center_x + 50, center_y - 50)

        # Show both
        self.button_overlay.show()
        self.button_overlay.raise_()
        self.button_overlay.activateWindow()

        self.timeline_overlay.show()
        self.timeline_overlay.raise_()
        self.timeline_overlay.activateWindow()

    def _on_button_confirmed(self, rect: QRect) -> None:
        """Handle button region confirmation."""
        self.button_rect = rect
        self.button_status.setText(f"Master Button: Set at ({rect.x()}, {rect.y()})")
        logger.info(f"Button region confirmed: {rect.x()}, {rect.y()}")
        self._check_completion()

    def _on_timeline_confirmed(self, rect: QRect) -> None:
        """Handle timeline region confirmation."""
        self.timeline_rect = rect
        self.timeline_status.setText(f"Timeline: Set at ({rect.x()}, {rect.y()})")
        logger.info(f"Timeline region confirmed: {rect.x()}, {rect.y()}")
        self._check_completion()

    def _check_completion(self) -> None:
        """Check if both regions are set."""
        if self.button_rect and self.timeline_rect:
            self.ok_button.setEnabled(True)

    def _on_cancelled(self) -> None:
        """Handle cancellation."""
        if self.button_overlay:
            self.button_overlay.close()
            self.button_overlay = None
        if self.timeline_overlay:
            self.timeline_overlay.close()
            self.timeline_overlay = None

    def accept(self) -> None:
        """Handle dialog acceptance."""
        # Capture current overlay positions even if Enter wasn't pressed
        if self.button_overlay:
            self.button_rect = self.button_overlay.frameGeometry()
            self.button_overlay.close()
            self.button_overlay = None
        if self.timeline_overlay:
            self.timeline_rect = self.timeline_overlay.frameGeometry()
            self.timeline_overlay.close()
            self.timeline_overlay = None

        if self.button_rect and self.timeline_rect:
            self.regions_configured.emit(
                self.deck_name, self.button_rect, self.timeline_rect
            )
        super().accept()


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
        # Future action types can be added here
        # self.action_type_combo.addItem("Switch Sequence", MidiActionType.SEQUENCE_SWITCH.value)
        config_layout.addWidget(self.action_type_combo)

        self.config_widget.setVisible(False)
        layout.addWidget(self.config_widget)

        # Dialog buttons
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


class PilotWidget(QWidget):
    """Compact pilot control widget with automation rules."""

    pilot_enable_requested = Signal(bool)
    phrase_detection_enable_requested = Signal(bool)
    align_requested = Signal()
    deck_region_configured = Signal(str, str, CaptureRegion)
    midi_action_added = Signal(object)  # Emits MidiActionConfig
    midi_action_removed = Signal(str)  # Emits action name

    def __init__(
        self,
        refresh_callback: Optional[Callable[[], None]] = None,
        pilot_controller=None,
    ):
        super().__init__()
        self.refresh_callback = refresh_callback
        self.pilot_controller = pilot_controller
        self.phrase_detection_enabled = False
        self.preset_manager = PilotPresetManager()

        self.setup_ui()
        self._load_presets()

    def setup_ui(self) -> None:
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # === HEADER: Control buttons + Status bar ===
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        header_layout.setContentsMargins(0, 2, 0, 5)

        # Control buttons (proper QPushButton style with icons)
        self.pilot_toggle_btn = QPushButton()
        self.pilot_toggle_btn.setCheckable(True)
        self.pilot_toggle_btn.setToolTip("Start/Stop Pilot")
        self.pilot_toggle_btn.setFixedSize(BUTTON_SIZE_LARGE)
        self.pilot_toggle_btn.setStyleSheet(BUTTON_STYLE)
        self.pilot_toggle_btn.setIcon(qta.icon("fa5s.robot", color="white"))
        self.pilot_toggle_btn.setIconSize(ICON_SIZE_MEDIUM)
        self.pilot_toggle_btn.toggled.connect(self._on_pilot_toggle)
        header_layout.addWidget(self.pilot_toggle_btn)

        self.phrase_detection_btn = QPushButton()
        self.phrase_detection_btn.setCheckable(True)
        self.phrase_detection_btn.setToolTip("Enable/Disable Phrase Detection")
        self.phrase_detection_btn.setFixedSize(BUTTON_SIZE_LARGE)
        self.phrase_detection_btn.setStyleSheet(BUTTON_STYLE)
        self.phrase_detection_btn.setIcon(qta.icon("fa5s.eye", color="white"))
        self.phrase_detection_btn.setIconSize(ICON_SIZE_MEDIUM)
        self.phrase_detection_btn.toggled.connect(self._on_phrase_detection_toggle)
        header_layout.addWidget(self.phrase_detection_btn)

        self.align_btn = QPushButton()
        self.align_btn.setToolTip("Align to Beat")
        self.align_btn.setFixedSize(BUTTON_SIZE_LARGE)
        self.align_btn.setStyleSheet(BUTTON_STYLE)
        self.align_btn.setIcon(qta.icon("fa5s.crosshairs", color="white"))
        self.align_btn.setIconSize(ICON_SIZE_MEDIUM)
        self.align_btn.clicked.connect(self._on_align_requested)
        header_layout.addWidget(self.align_btn)

        settings_btn = QPushButton()
        settings_btn.setToolTip("Pilot Settings")
        settings_btn.setFixedSize(BUTTON_SIZE_LARGE)
        settings_btn.setStyleSheet(BUTTON_STYLE)
        settings_btn.setIcon(qta.icon("fa5s.cog", color="white"))
        settings_btn.setIconSize(ICON_SIZE_MEDIUM)
        settings_btn.clicked.connect(self._on_settings_requested)
        header_layout.addWidget(settings_btn)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setFixedWidth(2)
        header_layout.addWidget(separator)

        # Status info grid (BPM, Bar, Beat in columns)
        from PySide6.QtWidgets import QGridLayout

        status_grid = QGridLayout()
        status_grid.setSpacing(4)
        status_grid.setContentsMargins(8, 0, 8, 0)
        status_grid.setVerticalSpacing(0)
        status_grid.setHorizontalSpacing(12)

        # Headers (small text)
        bpm_header = QLabel("BPM")
        bpm_header.setStyleSheet(HEADER_LABEL_STYLE)
        bpm_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bar_header = QLabel("Bar")
        bar_header.setStyleSheet(HEADER_LABEL_STYLE)
        bar_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        beat_header = QLabel("Beat")
        beat_header.setStyleSheet(HEADER_LABEL_STYLE)
        beat_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        deck_header = QLabel("Deck")
        deck_header.setStyleSheet(HEADER_LABEL_STYLE)
        deck_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        phrase_type_header = QLabel("Phrase")
        phrase_type_header.setStyleSheet(HEADER_LABEL_STYLE)
        phrase_type_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        status_grid.addWidget(bpm_header, 0, 0)
        status_grid.addWidget(bar_header, 0, 1)
        status_grid.addWidget(beat_header, 0, 2)
        status_grid.addWidget(deck_header, 0, 3)
        status_grid.addWidget(phrase_type_header, 0, 4)

        # Values (larger text)
        self.bpm_value = QLabel("--")
        self.bpm_value.setStyleSheet(VALUE_LABEL_STYLE)
        self.bpm_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bpm_value.setMinimumWidth(30)

        self.bar_value = QLabel("--")
        self.bar_value.setStyleSheet(VALUE_LABEL_STYLE)
        self.bar_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bar_value.setMinimumWidth(25)

        self.beat_value = QLabel("--")
        self.beat_value.setStyleSheet(VALUE_LABEL_STYLE)
        self.beat_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.beat_value.setMinimumWidth(25)

        self.deck_value = QLabel("--")
        self.deck_value.setStyleSheet(VALUE_LABEL_STYLE)
        self.deck_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.deck_value.setMinimumWidth(20)

        self.phrase_type = QLabel("--")
        self.phrase_type.setStyleSheet(VALUE_LABEL_STYLE)
        self.phrase_type.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phrase_type.setMinimumWidth(80)

        status_grid.addWidget(self.bpm_value, 1, 0)
        status_grid.addWidget(self.bar_value, 1, 1)
        status_grid.addWidget(self.beat_value, 1, 2)
        status_grid.addWidget(self.phrase_type, 1, 4)
        status_grid.addWidget(self.deck_value, 1, 3)

        header_layout.addLayout(status_grid)

        header_layout.addStretch()  # Push everything to the left

        main_layout.addLayout(header_layout)

        # Progress bar (horizontal, below controls)
        self.phrase_progress_bar = QProgressBar()
        self.phrase_progress_bar.setOrientation(Qt.Orientation.Horizontal)
        self.phrase_progress_bar.setTextVisible(False)
        self.phrase_progress_bar.setFixedHeight(6)
        self.phrase_progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #444;
                border-radius: 2px;
                background-color: #2a2a2a;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 2px;
            }
            """
        )
        main_layout.addWidget(self.phrase_progress_bar)

        # === PILOT PRESETS LIST ===
        presets_layout = QVBoxLayout()
        presets_layout.setSpacing(4)

        # Preset selector
        preset_header = QHBoxLayout()
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_header.addWidget(self.preset_combo, 1)

        self.add_preset_btn = QToolButton()
        self.add_preset_btn.setToolTip("Add New Pilot")
        self.add_preset_btn.setFixedSize(BUTTON_SIZE_SMALL)
        self.add_preset_btn.setStyleSheet(BUTTON_STYLE)
        self.add_preset_btn.setIcon(qta.icon("fa5s.plus", color="white"))
        self.add_preset_btn.setIconSize(ICON_SIZE_SMALL)
        self.add_preset_btn.clicked.connect(self._on_add_preset)
        preset_header.addWidget(self.add_preset_btn)

        self.edit_preset_btn = QToolButton()
        self.edit_preset_btn.setToolTip("Edit Pilot Rules")
        self.edit_preset_btn.setFixedSize(BUTTON_SIZE_SMALL)
        self.edit_preset_btn.setStyleSheet(BUTTON_STYLE)
        self.edit_preset_btn.setIcon(qta.icon("fa5s.edit", color="white"))
        self.edit_preset_btn.setIconSize(ICON_SIZE_SMALL)
        self.edit_preset_btn.clicked.connect(self._on_edit_preset)
        preset_header.addWidget(self.edit_preset_btn)

        self.delete_preset_btn = QToolButton()
        self.delete_preset_btn.setIcon(qta.icon("fa5s.trash", color="white"))
        self.delete_preset_btn.setToolTip("Delete Pilot")
        self.delete_preset_btn.setFixedSize(BUTTON_SIZE_SMALL)
        self.delete_preset_btn.setStyleSheet(BUTTON_STYLE)
        self.delete_preset_btn.setIconSize(ICON_SIZE_SMALL)
        self.delete_preset_btn.clicked.connect(self._on_delete_preset)

        preset_header.addWidget(self.delete_preset_btn)

        presets_layout.addLayout(preset_header)

        # Rules list with flash indicators
        self.rules_container = QVBoxLayout()
        self.rules_container.setSpacing(2)
        self.rule_widgets = {}  # rule_name -> QLabel widget
        presets_layout.addLayout(self.rules_container)

        # Add stretch to push rules to the top
        presets_layout.addStretch()

        main_layout.addLayout(presets_layout)

        # Add stretch to main layout to keep everything at the top
        main_layout.addStretch()

    def _on_pilot_toggle(self, checked: bool) -> None:
        """Handle pilot enable/disable."""
        self.pilot_enable_requested.emit(checked)
        if checked:
            QTimer.singleShot(200, self.align_requested.emit)

    def _on_phrase_detection_toggle(self, checked: bool) -> None:
        """Handle phrase detection enable/disable."""
        self.phrase_detection_enabled = checked
        self.phrase_detection_enable_requested.emit(checked)

    def _on_align_requested(self) -> None:
        """Handle manual alignment request."""
        self.align_requested.emit()

    def _on_settings_requested(self) -> None:
        """Show comprehensive pilot settings dialog."""
        from lumiblox.gui.pilot_settings import PilotSettingsDialog

        dialog = PilotSettingsDialog(self.pilot_controller, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Connect signals
        dialog.regions_configured.connect(
            lambda deck, btn, tl: self.deck_region_configured.emit(
                deck, "timeline", CaptureRegion(tl.x(), tl.y(), tl.width(), tl.height())
            )
        )
        dialog.midi_action_added.connect(
            lambda action: self.midi_action_added.emit(action)
        )
        dialog.midi_action_removed.connect(
            lambda name: self.midi_action_removed.emit(name)
        )

        # Refresh MIDI actions display when dialog closes
        if self.refresh_callback:
            dialog.accepted.connect(self.refresh_callback)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # Update methods
    def update_position(
        self, beat_in_bar: int, bar_in_phrase: int, bar_index: int, phrase_index: int
    ) -> None:
        """Update position display."""
        # Update bar position (bar in phrase out of 8)
        self.bar_value.setText(f"{bar_in_phrase + 1}/4")

        # Update beat position (beat in bar out of 4)
        self.beat_value.setText(f"{beat_in_bar + 1}/4")

    def update_status(
        self,
        pilot_state: str,
        bpm: Optional[float] = None,
        aligned: bool = False,
        active_deck: Optional[str] = None,
        phrase_type: Optional[str] = None,
        phrase_duration: Optional[tuple[int, int]] = None,
    ) -> None:
        """Update status display."""
        if aligned:
            # Update BPM value
            if bpm:
                self.bpm_value.setText(f"{bpm:.0f}")
            else:
                self.bpm_value.setText("--")

            # Update large phrase type indicator (M for BODY, B for BREAKDOWN)
            if phrase_type and self.phrase_detection_enabled:
                # Use M for Main/BODY, B for BREAKDOWN
                if phrase_type.upper() == "BODY":
                    self.phrase_type.setText("BODY")
                elif phrase_type.upper() == "BREAKDOWN":
                    self.phrase_type.setText("BREAK")
                self.phrase_type.setVisible(True)
            else:
                self.phrase_type.setVisible(False)

            # Update large deck indicator
            if active_deck and self.phrase_detection_enabled:
                self.deck_value.setText(active_deck)
                self.deck_value.setVisible(True)
            else:
                self.deck_value.setVisible(False)
        else:
            # Not aligned - reset all values
            self.bpm_value.setText("--")
            self.bar_value.setText("--")
            self.beat_value.setText("--")
            self.deck_value.setText("--")
            self.phrase_type.setText("--")

    def update_phrase_progress(self, progress: float) -> None:
        """Update phrase progress bar."""
        self.phrase_progress_bar.setValue(int(progress * 100))

    def set_not_aligned(self) -> None:
        """Reset display when not aligned."""
        self.bpm_value.setText("--")
        self.bar_value.setText("--")
        self.beat_value.setText("--")
        self.phrase_progress_bar.setValue(0)
        self.phrase_type.setVisible(False)
        self.deck_value.setVisible(False)

    def set_capturing(self, is_capturing: bool) -> None:
        """Show/hide minimal capture indicator.

        Args:
            is_capturing: True when actively capturing/analyzing, False otherwise
        """
        # if is_capturing:
        #     self.capture_indicator.setStyleSheet(
        #         f"color: {COLOR_SUCCESS}; font-size: {FONT_SIZE_SMALL}; padding: 0px 4px;"
        #     )
        #     self.capture_indicator.setVisible(True)
        # else:
        #     self.capture_indicator.setVisible(False)

    # Preset management methods
    def _load_presets(self) -> None:
        """Load presets from preset manager into combo box."""
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()

        for i, preset in enumerate(self.preset_manager.presets):
            status = "✓" if preset.enabled else "✗"
            self.preset_combo.addItem(f"{status} {preset.name}", i)

        # Select first enabled preset
        for i, preset in enumerate(self.preset_manager.presets):
            if preset.enabled:
                self.preset_combo.setCurrentIndex(i)
                break

        self.preset_combo.blockSignals(False)
        self._update_rules_preview()

    def _update_rules_preview(self) -> None:
        """Update the rules list with individual rule widgets."""
        # Clear existing rule widgets from layout
        while self.rules_container.count():
            item = self.rules_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self.rule_widgets.clear()

        current_index = self.preset_combo.currentIndex()
        if 0 <= current_index < len(self.preset_manager.presets):
            preset = self.preset_manager.presets[current_index]
            if preset.rules:
                for rule in preset.rules:
                    # Create rule label
                    rule_label = QLabel()
                    rule_label.setWordWrap(True)
                    rule_label.setStyleSheet(
                        "color: #999999; font-size: 10px; padding: 2px 4px; "
                        "background: {COLOR_BG_LIGHT}; border-radius: 3px; margin: 1px;"
                    )
                    self._update_rule_label(rule_label, rule, False)

                    self.rules_container.addWidget(rule_label)
                    self.rule_widgets[rule.name] = rule_label
            else:
                # Show "no rules" message
                no_rules_label = QLabel("No rules defined")
                no_rules_label.setStyleSheet(
                    "color: #666666; font-size: 10px; padding: 4px;"
                )
                self.rules_container.addWidget(no_rules_label)
        else:
            # Show "no preset" message
            no_preset_label = QLabel("No preset selected")
            no_preset_label.setStyleSheet(
                "color: #666666; font-size: 10px; padding: 4px;"
            )
            self.rules_container.addWidget(no_preset_label)

    def _update_rule_label(self, label: QLabel, rule, is_firing: bool) -> None:
        """Update rule label text and style."""
        status = ""
        condition_str = f"{rule.condition.condition_type.value}"
        if rule.condition.phrase_type:
            condition_str += f" ({rule.condition.phrase_type})"
        if rule.condition.duration_bars:
            condition_str += f" {rule.condition.duration_bars}bars"

        label.setText(f"{status} {rule.name}: {condition_str}")

        # Flash effect when firing
        if is_firing:
            label.setStyleSheet(
                "color: #00ff00; font-size: 10px; padding: 2px 4px; "
                "background: #004400;  border-radius: 3px; margin: 1px;"
            )
        elif rule.enabled:
            label.setStyleSheet(
                "color: #cccccc; font-size: 10px; padding: 2px 4px; "
                f"background: {COLOR_BG_LIGHT}; border-radius: 3px; margin: 1px;"
            )
        else:
            label.setStyleSheet(
                "color: #666666; font-size: 10px; padding: 2px 4px; "
                f"background: {COLOR_BG_DARK}; border-radius: 3px; margin: 1px;"
            )

    def flash_rule(self, rule_name: str) -> None:
        """Flash a rule indicator when it fires."""
        # Only flash if we have a widget and the rule is enabled
        widget = self.rule_widgets.get(rule_name)
        if not widget:
            return

        current_index = self.preset_combo.currentIndex()
        if not (0 <= current_index < len(self.preset_manager.presets)):
            return

        preset = self.preset_manager.presets[current_index]
        # Find the matching rule object
        matched_rule = None
        for rule in preset.rules:
            if rule.name == rule_name:
                matched_rule = rule
                break

        if not matched_rule or not matched_rule.enabled:
            return

        # Flash on briefly then restore default appearance
        self._update_rule_label(widget, matched_rule, True)

        from PySide6.QtCore import QTimer

        def _flash_off(w=widget, r=matched_rule, rn=rule_name):
            if rn in self.rule_widgets:
                self._update_rule_label(w, r, False)

        QTimer.singleShot(500, _flash_off)

    def _on_preset_changed(self, index: int) -> None:
        """Handle preset selection change."""
        if 0 <= index < len(self.preset_manager.presets):
            # Enable this preset, disable others
            for i, preset in enumerate(self.preset_manager.presets):
                preset.enabled = i == index
            self.preset_manager.save()
            self._update_rules_preview()
            logger.info(f"Switched to preset: {self.preset_combo.currentText()}")

    def _on_add_preset(self) -> None:
        """Show dialog to create a new preset."""
        dialog = PresetEditorDialog(preset=None, parent=self)
        if dialog.exec():
            # Get the new preset from dialog
            new_preset = dialog.get_preset()
            if new_preset:
                self.preset_manager.add_preset(new_preset)
                self._load_presets()
                # Select the newly added preset (last one)
                self.preset_combo.setCurrentIndex(self.preset_combo.count() - 1)

    def _on_edit_preset(self) -> None:
        """Show dialog to edit the current preset."""
        current_index = self.preset_combo.currentIndex()
        if 0 <= current_index < len(self.preset_manager.presets):
            current_preset = self.preset_manager.presets[current_index]
            dialog = PresetEditorDialog(preset=current_preset, parent=self)
            if dialog.exec():
                # Update the preset
                updated_preset = dialog.get_preset()
                if updated_preset:
                    self.preset_manager.update_preset(current_index, updated_preset)
                    self._load_presets()
                    # Restore selection
                    self.preset_combo.setCurrentIndex(current_index)

    def _on_delete_preset(self) -> None:
        """Delete the current preset."""
        current_index = self.preset_combo.currentIndex()
        if 0 <= current_index < len(self.preset_manager.presets):
            preset = self.preset_manager.presets[current_index]
            # Confirm deletion
            from PySide6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "Delete Preset",
                f"Are you sure you want to delete '{preset.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.preset_manager.remove_preset(current_index)
                self._load_presets()

    def set_pilot_controller(self, pilot_controller) -> None:
        """Set the pilot controller reference (called after initialization)."""
        self.pilot_controller = pilot_controller
