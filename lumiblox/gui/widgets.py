"""
Reusable GUI Widgets

Common widgets used across the GUI application.
"""

from PySide6.QtWidgets import (
    QPushButton,
    QLineEdit,
    QSizePolicy,
)
from PySide6.QtCore import Signal

from lumiblox.gui.ui_constants import COLOR_ACTIVE, COLOR_ACTIVE_DARK


class SelectAllLineEdit(QLineEdit):
    """QLineEdit that automatically selects all text when clicked or focused."""

    def mousePressEvent(self, event):
        """Override mouse press to select all text."""
        super().mousePressEvent(event)
        self.selectAll()

    def focusInEvent(self, event):
        """Override focus in to select all text."""
        super().focusInEvent(event)
        self.selectAll()


class SceneButton(QPushButton):
    """Custom button for scene grid."""

    scene_toggled = Signal(int, int, bool)

    def __init__(self, x: int, y: int):
        super().__init__("")
        self.coord_x = x
        self.coord_y = y
        self.is_active = False
        self.setCheckable(True)
        self.setMinimumSize(8, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.clicked.connect(self._on_clicked)
        self.update_style()

    def _on_clicked(self):
        self.is_active = self.isChecked()
        self.update_style()
        self.scene_toggled.emit(self.coord_x, self.coord_y, self.is_active)

    def set_active(self, active: bool):
        self.is_active = active
        self.setChecked(active)
        self.update_style()

    def update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #45a049;
                    border-radius: 5px;
                    font-weight: normal;
                    padding: 0px;
                    margin: 0px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #3c3c3c;
                    color: #cccccc;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    font-weight: normal;
                    padding: 0px;
                    margin: 0px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
            """)


class PresetButton(QPushButton):
    """Custom button for preset grid."""

    preset_selected = Signal(int, int)

    def __init__(self, x: int, y: int):
        super().__init__()
        self.coord_x = x
        self.coord_y = y
        self.preset_coords = [x, y]
        self.has_preset = False
        self.has_sequence = False
        self.is_active_preset = False

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )  # Expand horizontally
        self.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #666666;
                border: 1px solid #555555;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        self.setCheckable(True)
        self.clicked.connect(self._on_preset_clicked)
        self.update_appearance()

    def _on_preset_clicked(self):
        """Handle button click."""
        self.preset_selected.emit(self.coord_x, self.coord_y)

    def set_preset_info(self, has_preset: bool, has_sequence: bool = False):
        """Update preset information."""
        self.has_preset = has_preset
        self.has_sequence = has_sequence
        self.update_appearance()

    def set_active_preset(self, is_active: bool):
        """Set whether this preset is currently active."""
        self.is_active_preset = is_active
        self.setChecked(is_active)
        self.update_appearance()

    def update_appearance(self):
        """Update button appearance based on state."""
        if not self.has_preset:
            self.setText(f"{self.coord_x},{self.coord_y}")
            base_color = COLOR_ACTIVE_DARK if self.is_active_preset else "#3c3c3c"
            hover_color = COLOR_ACTIVE if self.is_active_preset else "#4a4a4a"
            text_color = "#ffffff" if self.is_active_preset else "#666666"
            border_color = "ffffff" if self.is_active_preset else "555555"
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {base_color};
                    color: {text_color};
                    border: 1px solid #{border_color};
                    border-radius: 3px;
                    font-size: 10px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:checked {{
                    border: 1px solid #ffffff;
                }}
            """)
        else:

            base_color = COLOR_ACTIVE_DARK if self.is_active_preset else "#4a4a4a"
            hover_color = COLOR_ACTIVE if self.is_active_preset else "#5a5a5a"

            # Set border color based on active state
            border_color = "ffffff" if self.is_active_preset else "666666"

            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {base_color};
                    color: #ffffff;
                    border: 0px solid #{border_color};
                    border-radius: 3px;
                    font-size: 10px;
                    font-weight: bold;

                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:checked {{
                    border: 1px solid #ffffff;
                }}
            """)
