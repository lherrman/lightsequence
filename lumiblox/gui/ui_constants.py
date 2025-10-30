"""
UI Constants

Centralized styling constants for consistent GUI appearance.
"""

from PySide6.QtCore import QSize

# ============================================================================
# SIZES
# ============================================================================

# Button sizes
BUTTON_SIZE_TINY = QSize(20, 20)  # Extra small buttons (e.g., close icons)
BUTTON_SIZE_SMALL = QSize(26, 26)  # Small tool buttons (+, -, edit icons)
BUTTON_SIZE_MEDIUM = QSize(32, 32)  # Control buttons (play, settings, etc.)
BUTTON_SIZE_LARGE = QSize(46, 46)  # Large indicator buttons (A, B, M, B)

# Input field sizes
INPUT_FIELD_WIDTH_SMALL = 30
INPUT_FIELD_HEIGHT_SMALL = 24


# Icon sizes
ICON_SIZE_SMALL = QSize(12, 12)
ICON_SIZE_MEDIUM = QSize(16, 16)
ICON_SIZE_LARGE = QSize(24, 24)

# ============================================================================
# COLORS
# ============================================================================

# Background colors
COLOR_BG_DARK = "#1a1a1a"
COLOR_BG_NORMAL = "#2a2a2a"
COLOR_BG_LIGHT = "#3a3a3a"
COLOR_BG_HOVER = "#3a3a3a"

# Border colors
COLOR_BORDER_DARK = "#333"
COLOR_BORDER_NORMAL = "#444"
COLOR_BORDER_LIGHT = "#666"

# Text colors
COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#cccccc"
COLOR_TEXT_DISABLED = "#666666"
COLOR_TEXT_DIM = "#888888"
COLOR_TEXT_SUBTLE = "#999999"

# Status colors
COLOR_ACTIVE = "#0078d4"
COLOR_ACTIVE_DARK = "#005a9e"
COLOR_SUCCESS = "#00ff00"
COLOR_WARNING = "#ff8800"
COLOR_WARNING_DARK = "#cc6600"
COLOR_ERROR = "#ff4444"

# Phrase type colors
COLOR_BODY = "#ff8800"  # Orange
COLOR_BODY_BORDER = "#cc6600"
COLOR_BREAKDOWN = "#0078d4"  # Blue
COLOR_BREAKDOWN_BORDER = "#005a9e"

# ============================================================================
# FONT SIZES
# ============================================================================

FONT_SIZE_SMALL = "10px"
FONT_SIZE_NORMAL = "10px"
FONT_SIZE_MEDIUM = "11px"
FONT_SIZE_LARGE = "18px"

# ============================================================================
# STYLE TEMPLATES
# ============================================================================

BUTTON_STYLE = f"""
    QPushButton, QToolButton {{
        background-color: {COLOR_BG_NORMAL};
        border: 1px solid {COLOR_BORDER_NORMAL};
        border-radius: 2px;
        color: {COLOR_TEXT_PRIMARY};
        font-size: {FONT_SIZE_MEDIUM};
        padding: 2px;
        margin: 2px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background-color: {COLOR_BG_HOVER};
        border: 1px solid {COLOR_BORDER_LIGHT};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background-color: {COLOR_BG_DARK};
    }}
    QPushButton:checked, QToolButton:checked {{
        background-color: {COLOR_ACTIVE};
        border: 1px solid {COLOR_ACTIVE_DARK};
    }}
"""

BUTTON_STYLE_ACTIVE = f"""
    QPushButton, QToolButton {{
        background-color: {COLOR_ACTIVE};
        border: 1px solid {COLOR_ACTIVE_DARK};
        border-radius: 2px;
        color: {COLOR_TEXT_PRIMARY};
        font-size: {FONT_SIZE_MEDIUM};
        padding: 2px;
        margin: 2px;
    }}
    QPushButton:hover, QToolButton:hover {{
        background-color: {COLOR_ACTIVE_DARK};
    }}
    QPushButton:pressed, QToolButton:pressed {{
        background-color: {COLOR_ACTIVE};
    }}
"""

EDIT_FIELD_STYLE = f"""
    QLineEdit {{ 
        background-color: {COLOR_BG_NORMAL};
        border: 1px solid {COLOR_BORDER_NORMAL};
        border-radius: 3px;
        color: {COLOR_TEXT_PRIMARY};
        font-size: {FONT_SIZE_MEDIUM};
        padding: 2px;
    }}
    QToolButton:hover {{
        background-color: {COLOR_BG_HOVER};
        border: 1px solid {COLOR_BORDER_LIGHT};
    }}
    QToolButton:pressed {{
        background-color: {COLOR_BG_DARK};
    }}
"""


VALUE_LABEL_STYLE = f"""
    color: {COLOR_TEXT_PRIMARY};
    font-size: {FONT_SIZE_LARGE};
    font-weight: bold;
"""

HEADER_LABEL_STYLE = f"""
    color: {COLOR_TEXT_DISABLED};
    font-size: {FONT_SIZE_SMALL};
    border: none;
    font-weight: normal;
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        color: {COLOR_TEXT_PRIMARY};
        font-size: {FONT_SIZE_MEDIUM};
        border: none;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 3px;
    }}
    QCheckBox::indicator:checked {{
        background-color: {COLOR_ACTIVE};
        border: 1px solid {COLOR_ACTIVE_DARK};
    }}
    QCheckBox::indicator:unchecked {{
        background-color: {COLOR_BG_NORMAL};
        border: 1px solid {COLOR_BORDER_NORMAL};
    }}
"""
