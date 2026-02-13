from enum import Enum


class ButtonType(str, Enum):
    """Types of buttons in the system."""
    SCENE = "scene"
    SEQUENCE = "sequence"
    CONTROL = "control"
    UNKNOWN = "unknown"


def get_button_type_enum(button_type_str: str) -> "ButtonType":
    """Convert button type string to ButtonType enum."""
    button_type_map = {
        "CONTROL": ButtonType.CONTROL,
        "TOP": ButtonType.CONTROL,      # legacy alias
        "RIGHT": ButtonType.CONTROL,    # legacy alias
        "SCENE": ButtonType.SCENE,
        "PRESET": ButtonType.SEQUENCE,  # legacy alias
        "SEQUENCE": ButtonType.SEQUENCE,
    }
    return button_type_map.get(button_type_str.upper(), ButtonType.UNKNOWN)


class AppState(str, Enum):
    """Application states."""

    NORMAL = "normal"
    SAVE_MODE = "save_mode"
    SAVE_SHIFT_MODE = "save_shift_mode"
    PILOT_SELECT_MODE = "pilot_select_mode"