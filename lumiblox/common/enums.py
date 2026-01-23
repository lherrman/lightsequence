from enum import Enum

class AppState(str, Enum):
    """Application states."""

    NORMAL = "normal"
    SAVE_MODE = "save_mode"
    SAVE_SHIFT_MODE = "save_shift_mode"
    PILOT_SELECT_MODE = "pilot_select_mode"