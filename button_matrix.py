"""
Button Matrix Management for Novation Launchpad MK2

This module provides button and grid management functionality for the
Launchpad MK2's 8x8 grid and side buttons.
"""

from typing import Tuple, List, Optional, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ButtonType(Enum):
    """Types of buttons on the Launchpad MK2."""

    GRID = "grid"  # Main 8x8 grid buttons
    TOP_ROW = "top_row"  # Top row scene buttons (8 buttons)
    RIGHT_COL = "right_col"  # Right column scene buttons (8 buttons)


class ButtonMatrix:
    """
    Button matrix manager for Launchpad MK2.

    Handles button coordinate validation, mapping, and provides utilities
    for working with the 8x8 grid and scene buttons.
    """

    # Grid dimensions
    GRID_SIZE = 8

    # Valid coordinate ranges
    MIN_COORD = 0
    MAX_COORD = 7

    # Special button coordinates
    TOP_ROW_Y = 8  # Top row buttons have y=8
    RIGHT_COL_X = 8  # Right column buttons have x=8

    def __init__(self):
        """Initialize the button matrix."""
        self._button_states: dict = {}
        self._pressed_buttons: Set[Tuple[int, int]] = set()

    def is_valid_coordinate(self, x: int, y: int) -> bool:
        """
        Check if coordinates are valid for any button.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if coordinates are valid
        """
        # Main grid (0-7, 0-7)
        if (
            self.MIN_COORD <= x <= self.MAX_COORD
            and self.MIN_COORD <= y <= self.MAX_COORD
        ):
            return True

        # Top row buttons (0-7, 8)
        if self.MIN_COORD <= x <= self.MAX_COORD and y == self.TOP_ROW_Y:
            return True

        # Right column buttons (8, 0-7)
        if x == self.RIGHT_COL_X and self.MIN_COORD <= y <= self.MAX_COORD:
            return True

        return False

    def is_grid_button(self, x: int, y: int) -> bool:
        """
        Check if coordinates are for a main grid button.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if coordinates are for main grid
        """
        return (
            self.MIN_COORD <= x <= self.MAX_COORD
            and self.MIN_COORD <= y <= self.MAX_COORD
        )

    def is_top_row_button(self, x: int, y: int) -> bool:
        """
        Check if coordinates are for a top row button.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if coordinates are for top row
        """
        return self.MIN_COORD <= x <= self.MAX_COORD and y == self.TOP_ROW_Y

    def is_right_column_button(self, x: int, y: int) -> bool:
        """
        Check if coordinates are for a right column button.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if coordinates are for right column
        """
        return x == self.RIGHT_COL_X and self.MIN_COORD <= y <= self.MAX_COORD

    def get_button_type(self, x: int, y: int) -> Optional[ButtonType]:
        """
        Get the type of button at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            ButtonType if coordinates are valid, None otherwise
        """
        if self.is_grid_button(x, y):
            return ButtonType.GRID
        elif self.is_top_row_button(x, y):
            return ButtonType.TOP_ROW
        elif self.is_right_column_button(x, y):
            return ButtonType.RIGHT_COL
        else:
            return None

    def get_grid_coordinates(self) -> List[Tuple[int, int]]:
        """
        Get all grid button coordinates.

        Returns:
            List of (x, y) tuples for all grid buttons
        """
        coordinates = []
        for x in range(self.GRID_SIZE):
            for y in range(self.GRID_SIZE):
                coordinates.append((x, y))
        return coordinates

    def get_top_row_coordinates(self) -> List[Tuple[int, int]]:
        """
        Get all top row button coordinates.

        Returns:
            List of (x, y) tuples for top row buttons
        """
        return [(x, self.TOP_ROW_Y) for x in range(self.GRID_SIZE)]

    def get_right_column_coordinates(self) -> List[Tuple[int, int]]:
        """
        Get all right column button coordinates.

        Returns:
            List of (x, y) tuples for right column buttons
        """
        return [(self.RIGHT_COL_X, y) for y in range(self.GRID_SIZE)]

    def get_all_coordinates(self) -> List[Tuple[int, int]]:
        """
        Get all valid button coordinates.

        Returns:
            List of (x, y) tuples for all buttons
        """
        coordinates = []
        coordinates.extend(self.get_grid_coordinates())
        coordinates.extend(self.get_top_row_coordinates())
        coordinates.extend(self.get_right_column_coordinates())
        return coordinates

    def get_neighbors(
        self, x: int, y: int, include_diagonal: bool = False
    ) -> List[Tuple[int, int]]:
        """
        Get neighboring button coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            include_diagonal: Whether to include diagonal neighbors

        Returns:
            List of valid neighboring coordinates
        """
        if not self.is_valid_coordinate(x, y):
            return []

        neighbors = []

        # Define offset patterns
        if include_diagonal:
            offsets = [
                (-1, -1),
                (-1, 0),
                (-1, 1),
                (0, -1),
                (0, 1),
                (1, -1),
                (1, 0),
                (1, 1),
            ]
        else:
            offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]

        # Only check grid neighbors (scene buttons don't have meaningful neighbors)
        if self.is_grid_button(x, y):
            for dx, dy in offsets:
                nx, ny = x + dx, y + dy
                if self.is_grid_button(nx, ny):
                    neighbors.append((nx, ny))

        return neighbors

    def get_row(self, y: int) -> List[Tuple[int, int]]:
        """
        Get all coordinates in a row.

        Args:
            y: Row number (0-7 for grid, 8 for top row)

        Returns:
            List of coordinates in the row
        """
        if y == self.TOP_ROW_Y:
            return self.get_top_row_coordinates()
        elif self.MIN_COORD <= y <= self.MAX_COORD:
            return [(x, y) for x in range(self.GRID_SIZE)]
        else:
            return []

    def get_column(self, x: int) -> List[Tuple[int, int]]:
        """
        Get all coordinates in a column.

        Args:
            x: Column number (0-7 for grid, 8 for right column)

        Returns:
            List of coordinates in the column
        """
        if x == self.RIGHT_COL_X:
            return self.get_right_column_coordinates()
        elif self.MIN_COORD <= x <= self.MAX_COORD:
            return [(x, y) for y in range(self.GRID_SIZE)]
        else:
            return []

    def get_diagonal_coordinates(
        self, main_diagonal: bool = True
    ) -> List[Tuple[int, int]]:
        """
        Get coordinates along a diagonal (grid only).

        Args:
            main_diagonal: True for main diagonal (top-left to bottom-right),
                          False for anti-diagonal (top-right to bottom-left)

        Returns:
            List of diagonal coordinates
        """
        coordinates = []

        if main_diagonal:
            # Main diagonal: (0,0), (1,1), (2,2), ...
            for i in range(self.GRID_SIZE):
                coordinates.append((i, i))
        else:
            # Anti-diagonal: (0,7), (1,6), (2,5), ...
            for i in range(self.GRID_SIZE):
                coordinates.append((i, self.GRID_SIZE - 1 - i))

        return coordinates

    def get_border_coordinates(self) -> List[Tuple[int, int]]:
        """
        Get coordinates of border buttons (grid only).

        Returns:
            List of border coordinates
        """
        coordinates = []

        # Top and bottom rows
        for x in range(self.GRID_SIZE):
            coordinates.append((x, 0))  # Top row
            coordinates.append((x, self.GRID_SIZE - 1))  # Bottom row

        # Left and right columns (excluding corners already added)
        for y in range(1, self.GRID_SIZE - 1):
            coordinates.append((0, y))  # Left column
            coordinates.append((self.GRID_SIZE - 1, y))  # Right column

        return coordinates

    def get_center_coordinates(self) -> List[Tuple[int, int]]:
        """
        Get coordinates of center buttons (grid only).

        Returns:
            List of center coordinates (2x2 in middle for 8x8 grid)
        """
        center = self.GRID_SIZE // 2
        return [
            (center - 1, center - 1),
            (center, center - 1),
            (center - 1, center),
            (center, center),
        ]

    def get_ring_coordinates(
        self, center_x: int, center_y: int, radius: int
    ) -> List[Tuple[int, int]]:
        """
        Get coordinates in a ring around a center point.

        Args:
            center_x: Center X coordinate
            center_y: Center Y coordinate
            radius: Ring radius

        Returns:
            List of coordinates in the ring
        """
        if not self.is_grid_button(center_x, center_y):
            return []

        coordinates = []

        for x in range(self.GRID_SIZE):
            for y in range(self.GRID_SIZE):
                # Calculate Manhattan distance
                distance = abs(x - center_x) + abs(y - center_y)
                if distance == radius:
                    coordinates.append((x, y))

        return coordinates

    def coordinate_to_index(self, x: int, y: int) -> Optional[int]:
        """
        Convert coordinate to linear index (for grid buttons only).

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Linear index (0-63) or None if not a grid button
        """
        if self.is_grid_button(x, y):
            return y * self.GRID_SIZE + x
        return None

    def index_to_coordinate(self, index: int) -> Optional[Tuple[int, int]]:
        """
        Convert linear index to coordinate (for grid buttons only).

        Args:
            index: Linear index (0-63)

        Returns:
            (x, y) coordinate or None if index out of range
        """
        if 0 <= index < self.GRID_SIZE * self.GRID_SIZE:
            x = index % self.GRID_SIZE
            y = index // self.GRID_SIZE
            return (x, y)
        return None

    def update_button_state(self, x: int, y: int, pressed: bool) -> None:
        """
        Update the state of a button.

        Args:
            x: X coordinate
            y: Y coordinate
            pressed: Whether button is pressed
        """
        if not self.is_valid_coordinate(x, y):
            return

        coord = (x, y)
        self._button_states[coord] = pressed

        if pressed:
            self._pressed_buttons.add(coord)
        else:
            self._pressed_buttons.discard(coord)

    def is_button_pressed(self, x: int, y: int) -> bool:
        """
        Check if a button is currently pressed.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if button is pressed
        """
        return (x, y) in self._pressed_buttons

    def get_pressed_buttons(self) -> Set[Tuple[int, int]]:
        """Get set of all currently pressed button coordinates."""
        return self._pressed_buttons.copy()

    def clear_button_states(self) -> None:
        """Clear all button state tracking."""
        self._button_states.clear()
        self._pressed_buttons.clear()
