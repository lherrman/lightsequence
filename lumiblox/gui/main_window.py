"""
Main GUI Window

Streamlined main window - delegates to specialized components.
"""

import sys
import logging
import typing as t

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMessageBox,
    QGridLayout,
)
from PySide6.QtCore import Signal
import qtawesome as qta


from lumiblox.gui.controller_thread import ControllerThread
from lumiblox.gui.device_status import DeviceStatusBar
from lumiblox.gui.ui_constants import BUTTON_SIZE_TINY, BUTTON_STYLE, HEADER_LABEL_STYLE
from lumiblox.gui.widgets import PresetButton
from lumiblox.gui.sequence_editor import PresetSequenceEditor
from lumiblox.gui.playback_controls import PlaybackControls
from lumiblox.gui.pilot_widget import PilotWidget
from lumiblox.controller.input_handler import ButtonEvent, ButtonType
from lumiblox.common.device_state import DeviceType
from lumiblox.pilot.phrase_detector import CaptureRegion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LightSequenceGUI(QMainWindow):
    """Main GUI application for light sequence configuration."""

    # Custom signals for thread-safe sequence updates and device status updates
    sequence_changed_signal = Signal(object)
    sequence_saved_signal = Signal()
    device_status_update_signal = Signal()
    playback_state_changed_signal = Signal(object)
    pilot_update_signal = Signal()  # For pilot updates from controller thread
    automation_rule_fired_signal = Signal(str)

    def __init__(self, simulation: bool = False):
        super().__init__()
        self.controller = None
        self.controller_thread: t.Optional[ControllerThread] = None
        self.current_editor: t.Optional[PresetSequenceEditor] = None
        self._updating_from_launchpad = False  # Flag to prevent infinite loops
        self.simulation = simulation

        # Connect the signals to the slots
        self.sequence_changed_signal.connect(self._update_sequence_from_launchpad)
        self.sequence_saved_signal.connect(self._handle_sequence_saved)
        self.device_status_update_signal.connect(self._update_device_status_display)
        self.playback_state_changed_signal.connect(self._update_playback_controls)
        self.pilot_update_signal.connect(self._update_pilot_display)

        self.setWindowTitle("Light Sequence Controller")
        self.setMinimumSize(470, 200)
        self.resize(600, 800)
        self.setup_ui()
        self.automation_rule_fired_signal.connect(self.pilot_widget.flash_rule)
        self.apply_dark_theme()
        self.start_controller()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout - device status, pilot, sequence editor, preset grid
        main_layout = QVBoxLayout(central_widget)

        # === Device Status Bar (Top) ===
        self.device_status_bar = DeviceStatusBar()
        main_layout.addWidget(self.device_status_bar)

        # === Pilot Widget (Fixed height) ===
        self.pilot_widget = PilotWidget()
        self.pilot_widget.setMinimumHeight(300)
        self.pilot_widget.setMaximumHeight(300)
        # Connect pilot signals
        self.pilot_widget.pilot_enable_requested.connect(
            self._on_pilot_enable_requested
        )
        self.pilot_widget.phrase_detection_enable_requested.connect(
            self._on_phrase_detection_enable_requested
        )
        self.pilot_widget.align_requested.connect(self._on_align_requested)
        self.pilot_widget.deck_region_configured.connect(
            self._on_deck_region_configured
        )
        main_layout.addWidget(self.pilot_widget)  # No stretch, fixed height

        # === Sequence Editor (Takes remaining space) ===
        self.editor_stack = QWidget()
        self.editor_stack.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        self.editor_layout = QVBoxLayout(self.editor_stack)
        self.editor_layout.setContentsMargins(5, 5, 5, 5)

        main_layout.addWidget(self.editor_stack, 1)  # Stretch to fill remaining space

        # === Playback Controls (Between editor and presets) ===
        self.playback_controls = PlaybackControls()
        self.playback_controls.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
            }
        """)
        self.playback_controls.play_pause_clicked.connect(self.on_play_pause_clicked)
        self.playback_controls.next_step_clicked.connect(self.on_next_step_clicked)
        self.playback_controls.clear_clicked.connect(self.on_clear_clicked)
        main_layout.addWidget(self.playback_controls)

        # Bottom area - Preset grid (3 rows x 8 columns) - more compact
        preset_panel = QWidget()  # Use plain widget instead of GroupBox
        preset_panel.setMaximumHeight(125)  # Slightly more height for better spacing

        preset_layout = QVBoxLayout(preset_panel)
        preset_layout.setContentsMargins(3, 3, 3, 3)  # Very tight margins
        preset_layout.setSpacing(2)

        # Header with title and refresh button in one line
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)

        # Title label
        title_label = QLabel("Sequences")
        title_label.setStyleSheet(HEADER_LABEL_STYLE)
        header_layout.addWidget(title_label)

        header_layout.addStretch()  # Push refresh button to right

        # Small refresh icon button in corner
        refresh_btn = QPushButton()
        refresh_btn.clicked.connect(self.refresh_presets)
        refresh_btn.setIcon(qta.icon("fa5s.sync", color="white"))
        refresh_btn.setIconSize(BUTTON_SIZE_TINY)
        refresh_btn.setFixedSize(BUTTON_SIZE_TINY)
        refresh_btn.setStyleSheet(BUTTON_STYLE)
        header_layout.addWidget(refresh_btn)
        preset_layout.addLayout(header_layout)

        # Sequence grid area
        self.preset_grid_widget = QWidget()
        preset_grid_layout = QGridLayout(self.preset_grid_widget)
        preset_grid_layout.setHorizontalSpacing(3)
        preset_grid_layout.setVerticalSpacing(6)
        preset_grid_layout.setContentsMargins(0, 2, 0, 2)
        # Remove borders in the preset grid area

        # Create 3x8 grid of preset buttons
        self.preset_buttons: t.Dict[t.Tuple[int, int], PresetButton] = {}
        for y in range(3):  # 3 rows
            for x in range(8):  # 8 columns
                btn = PresetButton(x, y)
                btn.preset_selected.connect(self.on_preset_button_selected)
                self.preset_buttons[(x, y)] = btn
                preset_grid_layout.addWidget(btn, y, x)

                # Make columns stretch equally to use full width
                preset_grid_layout.setColumnStretch(x, 1)

        preset_layout.addWidget(self.preset_grid_widget)
        main_layout.addWidget(preset_panel, 1)

        # Status bar
        self.statusBar().showMessage("Starting controller...")

    def apply_dark_theme(self):
        """Apply dark theme to the application."""
        dark_stylesheet = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QTreeWidget {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            selection-background-color: #4a4a4a;
        }
        QTreeWidget::item:selected {
            background-color: #4a4a4a;
        }
        QPushButton {
            background-color: #4a4a4a;
            color: #ffffff;
            border: 1px solid #666666;
            padding: 8px;
            border-radius: 2px;
        }
        QPushButton:hover {
            background-color: #5a5a5a;
        }
        QPushButton:pressed {
            background-color: #3a3a3a;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            padding: 4px;
            border-radius: 4px;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #555555;
            border-radius: 5px;
            margin: 10px 0px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QLabel {
            color: #ffffff;
        }
        QScrollArea {
            border: none;
        }
        """
        self.setStyleSheet(dark_stylesheet)

    # ============================================================================
    # CONTROLLER MANAGEMENT
    # ============================================================================

    def start_controller(self):
        """Start the light controller in a separate thread."""
        self.controller_thread = ControllerThread(simulation=self.simulation)
        self.controller_thread.controller_ready.connect(self.on_controller_ready)
        self.controller_thread.controller_error.connect(self.on_controller_error)
        self.controller_thread.capturing_signal.connect(self.pilot_widget.set_capturing)
        self.controller_thread.start()

    def on_controller_ready(self):
        """Called when controller is ready."""
        if self.controller_thread:
            self.controller = self.controller_thread.controller

            # Set pilot controller on pilot widget
            if self.controller_thread.pilot_controller:
                self.pilot_widget.set_pilot_controller(
                    self.controller_thread.pilot_controller
                )

            # Set up pilot update callback
            if self.controller_thread.pilot_controller:
                self.controller_thread.pilot_update_callback = (
                    lambda: self.pilot_update_signal.emit()
                )

            # Set up callbacks for sequence changes and saves
            if self.controller:
                self.controller.on_sequence_changed = self.on_launchpad_sequence_changed
                self.controller.on_sequence_saved = self.on_sequence_saved

                # Register playback state change callback
                if hasattr(self.controller, "sequence_ctrl"):
                    self.controller.sequence_ctrl.on_playback_state_change = (
                        self.on_playback_state_changed
                    )

                    # Update initial playback state
                    from lumiblox.controller.sequence_controller import PlaybackState

                    is_playing = (
                        self.controller.sequence_ctrl.playback_state
                        == PlaybackState.PLAYING
                    )
                    self.playback_controls.set_playing(is_playing)

                # Register device state change callback
                if hasattr(self.controller, "device_manager"):
                    self.controller.device_manager.register_state_change_callback(
                        self._on_device_state_changed
                    )
                    # Update initial device statuses
                    self._update_device_status_display()

            self.statusBar().showMessage("Controller connected successfully")
            self.refresh_presets()

    def on_controller_error(self, error: str):
        """Called when controller fails."""
        self.statusBar().showMessage(f"Controller error: {error}")
        QMessageBox.critical(
            self, "Controller Error", f"Failed to start light controller:\n{error}"
        )

    # ============================================================================
    # SEQUENCE MANAGEMENT
    # ============================================================================

    def on_sequence_saved(self):
        """Called when a sequence is saved from the launchpad (thread-unsafe callback)."""
        # Use signal to handle this in a thread-safe way
        self.sequence_saved_signal.emit()

    def _handle_sequence_saved(self):
        """Handle sequence saved signal (runs on GUI thread)."""
        # Refresh presets list to show the new/updated sequence
        self.refresh_presets()

    def refresh_presets(self):
        """Refresh the preset grid."""
        if not self.controller:
            return

        # Get all sequence indices
        sequence_indices = self.controller.sequence_ctrl.get_all_indices()

        # Update all preset buttons
        for (x, y), btn in self.preset_buttons.items():
            sequence_tuple = (x, y)
            if sequence_tuple in sequence_indices:
                # Check if it's a single-step sequence (preset) or multi-step
                seq_steps = self.controller.sequence_ctrl.get_sequence(sequence_tuple)
                has_sequence = len(seq_steps) > 1 if seq_steps else False
                btn.set_preset_info(True, has_sequence)
            else:
                btn.set_preset_info(False, False)

    def on_preset_button_selected(self, x: int, y: int):
        """Handle preset button selection."""
        if not self.controller:
            return

        sequence_tuple = (x, y)

        # Show sequence editor for this sequence
        self.show_sequence_editor(sequence_tuple)

        # Update button states - clear all first
        for btn in self.preset_buttons.values():
            btn.set_active_preset(False)

        # Set selected button as active
        if (x, y) in self.preset_buttons:
            self.preset_buttons[(x, y)].set_active_preset(True)

        # Also activate on the launchpad using new input system
        event = ButtonEvent(
            button_type=ButtonType.SEQUENCE,
            coordinates=sequence_tuple,
            pressed=True,
            source="gui",
        )
        self.controller.input_handler.handle_button_event(event)

    def show_sequence_editor(self, preset_index: t.Tuple[int, int]):
        """Show sequence editor for the selected preset."""
        # Clear current editor
        if self.current_editor:
            self.current_editor.deleteLater()
            self.current_editor = None

        # Create new editor
        self.current_editor = PresetSequenceEditor(preset_index, self.controller)
        self.editor_layout.addWidget(self.current_editor)

    def on_launchpad_sequence_changed(
        self, sequence_coords: t.Optional[t.Tuple[int, int]]
    ):
        """Called when sequence selection changes on the launchpad."""
        # Emit signal to handle on GUI thread
        self.sequence_changed_signal.emit(sequence_coords)

    def _update_sequence_from_launchpad(
        self, sequence_coords: t.Optional[t.Tuple[int, int]]
    ):
        """Update sequence selection from launchpad (runs on GUI thread)."""
        self._updating_from_launchpad = True
        try:
            # Clear all preset button selections first
            for btn in self.preset_buttons.values():
                btn.set_active_preset(False)

            if sequence_coords is None:
                # No sequence selected - clear editor and show default message
                if self.current_editor:
                    self.current_editor.deleteLater()
                    self.current_editor = None
                return

            # Select the matching sequence button
            if sequence_coords in self.preset_buttons:
                self.preset_buttons[sequence_coords].set_active_preset(True)
                # Also show the editor for this sequence
                self.show_sequence_editor(sequence_coords)
        finally:
            self._updating_from_launchpad = False

    # ============================================================================
    # DEVICE STATUS
    # ============================================================================

    def _on_device_state_changed(self, device_type: DeviceType, new_state):
        """Handle device state changes (called from device manager)."""
        # Emit signal to update GUI on main thread
        self.device_status_update_signal.emit()

    def _update_device_status_display(self):
        """Update device status indicators in GUI."""
        if not self.controller or not hasattr(self.controller, "device_manager"):
            return

        device_manager = self.controller.device_manager

        # Update Launchpad status
        launchpad_state = device_manager.get_state(DeviceType.LAUNCHPAD)
        self.device_status_bar.update_launchpad_status(launchpad_state)

        # Update LightSoftware status
        lightsw_state = device_manager.get_state(DeviceType.LIGHT_SOFTWARE)
        self.device_status_bar.update_lightsw_status(lightsw_state)

    # ============================================================================
    # PLAYBACK CONTROLS
    # ============================================================================

    def on_playback_state_changed(self, state):
        """Called when playback state changes (from any source - launchpad or GUI)."""
        # Use signal for thread-safe GUI update
        self.playback_state_changed_signal.emit(state)

    def _update_playback_controls(self, is_playing: bool):
        """Update playback controls based on state (runs on GUI thread)."""
        self.playback_controls.set_playing(is_playing)

    def on_play_pause_clicked(self):
        """Handle play/pause button click."""
        if not self.controller:
            return
        self.controller.sequence_ctrl.toggle_play_pause()

    def on_next_step_clicked(self):
        """Handle next step button click."""
        if not self.controller:
            return
        self.controller.sequence_ctrl.next_step()

    def on_clear_clicked(self):
        """Handle clear button click."""
        if not self.controller:
            return

        # Clear sequence
        self.controller.sequence_ctrl.clear()

        # Update controller state
        if self.controller.active_sequence:
            old_seq = self.controller.active_sequence
            self.controller.active_sequence = None
            self.controller.scene_ctrl.clear_controlled()
            self.controller.led_ctrl.update_sequence_led(old_seq, False)
            if self.controller.on_sequence_changed:
                self.controller.on_sequence_changed(None)

    # ============================================================================
    # PILOT CONTROL
    # ============================================================================

    def _on_pilot_enable_requested(self, enabled: bool) -> None:
        """Handle pilot enable/disable request from GUI."""
        if not self.controller_thread:
            logger.warning("Controller thread not available")
            return

        pilot = self.controller_thread.pilot_controller
        if enabled:
            # Try to start the pilot
            try:
                success = pilot.start(enable_phrase_detection=False)
                if not success:
                    self.pilot_widget.pilot_toggle_btn.setChecked(False)
                    QMessageBox.warning(
                        self,
                        "Pilot Error",
                        "Failed to start pilot. Check MIDI device connection.",
                    )
            except Exception as e:
                logger.error(f"Error starting pilot: {e}")
                self.pilot_widget.pilot_toggle_btn.setChecked(False)
                QMessageBox.warning(
                    self,
                    "Pilot Error",
                    f"Failed to start pilot: {e}",
                )
        else:
            try:
                pilot.stop()
            except Exception as e:
                logger.error(f"Error stopping pilot: {e}")
                QMessageBox.warning(
                    self,
                    "Pilot Error",
                    f"Failed to stop pilot: {e}",
                )

    def _on_phrase_detection_enable_requested(self, enabled: bool) -> None:
        """Handle phrase detection enable/disable request from GUI."""
        if not self.controller_thread:
            return

        pilot = self.controller_thread.pilot_controller
        if enabled:
            success = pilot.enable_phrase_detection()
            if not success:
                self.pilot_widget.phrase_detection_btn.setChecked(False)
                QMessageBox.warning(
                    self,
                    "Phrase Detection Error",
                    "Failed to enable phrase detection. Check configuration.",
                )
            else:
                # Enable automation with callbacks
                pilot.enable_automation(
                    on_sequence_switch=self._on_automation_sequence_switch,
                    on_rule_fired=self._on_automation_rule_fired,
                )
        else:
            pilot.disable_phrase_detection()
            pilot.disable_automation()

    def _on_align_requested(self) -> None:
        """Handle manual alignment request from GUI."""
        if not self.controller_thread:
            return

        pilot = self.controller_thread.pilot_controller
        pilot.align_to_beat()

    def _on_deck_region_configured(
        self, deck_name: str, region_type: str, region: CaptureRegion
    ) -> None:
        """Handle deck region configuration from GUI."""
        if not self.controller_thread:
            return

        pilot = self.controller_thread.pilot_controller

        if region_type == "button":
            pilot.configure_deck(deck_name, master_button_region=region)
        elif region_type == "timeline":
            pilot.configure_deck(deck_name, timeline_region=region)

        logger.info(f"Configured deck {deck_name} {region_type} region")

    def _update_pilot_display(self) -> None:
        """Update pilot widget display (called on main thread)."""
        if not self.controller_thread:
            return

        pilot = self.controller_thread.pilot_controller

        # Update progress and position
        if pilot.is_aligned():
            progress = pilot.get_phrase_progress()
            self.pilot_widget.update_phrase_progress(progress)

            beat_in_bar, bar_in_phrase, bar_index, phrase_index = (
                pilot.get_current_position()
            )
            self.pilot_widget.update_position(
                beat_in_bar, bar_in_phrase, bar_index, phrase_index
            )
        else:
            self.pilot_widget.set_not_aligned()

        # Update status (including active deck and phrase duration)
        state = pilot.get_state()
        bpm = pilot.get_bpm()
        aligned = pilot.is_aligned()
        active_deck = pilot.get_active_deck()
        phrase_type = pilot.get_current_phrase_type()
        phrase_duration = pilot.get_phrase_duration()
        self.pilot_widget.update_status(
            state.value, bpm, aligned, active_deck, phrase_type, phrase_duration
        )

    # ============================================================================
    # AUTOMATION CALLBACKS
    # ============================================================================

    def _on_automation_sequence_switch(self, sequence_index: str) -> None:
        """Handle automated sequence activation from pilot rules."""
        if not self.controller:
            return

        # Parse sequence index (format: "x.y")
        if "." in sequence_index:
            parts = sequence_index.split(".")
            index = (int(parts[0]), int(parts[1]))
        else:
            # Legacy format: single number (shouldn't happen anymore)
            idx = int(sequence_index)
            index = (idx % 8, idx // 8)

        logger.info(f"Automation activating sequence {index} (from {sequence_index})")

        # Validate that sequence exists
        if index not in self.controller.sequence_ctrl.sequences:
            logger.warning(f"Sequence {index} not found, cannot activate")
            return

        # Activate sequence using existing logic
        old_sequence = self.controller.active_sequence
        if old_sequence:
            self.controller.led_ctrl.update_sequence_led(old_sequence, False)

        self.controller.active_sequence = index
        self.controller.sequence_ctrl.activate_sequence(index)
        self.controller.led_ctrl.update_sequence_led(index, True)

        if self.controller.on_sequence_changed:
            self.controller.on_sequence_changed(index)

        logger.info(f"Activated sequence {index} (was {old_sequence})")

    def _on_automation_rule_fired(self, rule_name: str) -> None:
        """Handle rule firing notification - flash UI indicator."""
        self.automation_rule_fired_signal.emit(rule_name)

    # ============================================================================
    # LIFECYCLE
    # ============================================================================

    def closeEvent(self, event):
        """Handle application close."""
        if self.controller_thread:
            self.controller_thread.stop()
        event.accept()


def main(simulation: bool = False):
    """Main entry point for GUI application.

    Args:
        simulation: If True, use simulated lighting software instead of real one
    """
    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("Light Sequence Controller")
    app.setApplicationVersion("1.0")

    # Create and show main window
    window = LightSequenceGUI(simulation=simulation)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
