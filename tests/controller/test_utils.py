"""Test utility functions"""
import pytest
from controller.common.utils import hex_to_rgb


def test_hex_to_rgb_with_hash():
    """Test hex to RGB conversion with hash prefix"""
    assert hex_to_rgb("#ff0000") == [1.0, 0.0, 0.0]
    assert hex_to_rgb("#00ff00") == [0.0, 1.0, 0.0]
    assert hex_to_rgb("#0000ff") == [0.0, 0.0, 1.0]
    assert hex_to_rgb("#ffffff") == [1.0, 1.0, 1.0]
    assert hex_to_rgb("#000000") == [0.0, 0.0, 0.0]


def test_hex_to_rgb_without_hash():
    """Test hex to RGB conversion without hash prefix"""
    assert hex_to_rgb("ff0000") == [1.0, 0.0, 0.0]
    assert hex_to_rgb("00ff00") == [0.0, 1.0, 0.0]
    assert hex_to_rgb("0000ff") == [0.0, 0.0, 1.0]


def test_hex_to_rgb_mixed_case():
    """Test hex to RGB conversion with mixed case"""
    assert hex_to_rgb("#FF0000") == [1.0, 0.0, 0.0]
    assert hex_to_rgb("#Ff0000") == [1.0, 0.0, 0.0]
    assert hex_to_rgb("fF0000") == [1.0, 0.0, 0.0]


def test_hex_to_rgb_partial_values():
    """Test hex to RGB conversion with partial values"""
    result = hex_to_rgb("#7f7f7f")
    # Should be approximately 0.498 for each channel (127/255)
    for value in result:
        assert 0.49 < value < 0.50


def test_hex_to_rgb_invalid_input():
    """Test hex to RGB conversion with invalid input"""
    # Should handle gracefully or return default
    try:
        result = hex_to_rgb("invalid")
        # If it doesn't raise, check it returns something sensible
        assert isinstance(result, list)
        assert len(result) == 3
    except (ValueError, AttributeError):
        # It's acceptable to raise an exception for invalid input
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
