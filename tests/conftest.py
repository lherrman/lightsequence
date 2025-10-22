"""Pytest configuration and shared fixtures"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    """Get the project root path"""
    return Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def reset_pygame_env():
    """Ensure pygame environment variable is set"""
    import os
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
