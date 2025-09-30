#!/usr/bin/env python3
"""
Light Controller - Quick launcher
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from lightcontroller.gui import main

if __name__ == "__main__":
    main()
