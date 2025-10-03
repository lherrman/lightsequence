import logging
import typing as t

logger = logging.getLogger(__name__)



def hex_to_rgb(hex_color: str) -> t.List[float]:
    """Convert hex color to RGB float list (0.0-1.0)."""
    if hex_color.startswith("#"):
        hex_color = hex_color[1:]
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return [r, g, b]
    except (ValueError, IndexError):
        logger.warning(f"Invalid hex color '{hex_color}', using black")
        return [0.0, 0.0, 0.0]
