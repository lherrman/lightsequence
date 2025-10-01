#!/usr/bin/env python3
"""
Light Sequence Controller Launcher

This script can launch either:
1. The GUI application (default)
2. The standalone controller (command line argument)
"""

import sys
import argparse
import logging
from pathlib import Path

# Add the controller directory to the path
controller_dir = Path(__file__).parent / "src" / "controller"
sys.path.insert(0, str(controller_dir))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Light Sequence Controller Launcher")
    parser.add_argument(
        "--mode",
        choices=["gui", "controller"],
        default="gui",
        help="Launch mode: 'gui' for the configuration interface, 'controller' for standalone controller",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    if args.mode == "gui":
        try:
            logger.info("Starting GUI application...")
            from controller.sequence_gui import main as gui_main

            gui_main()
        except ImportError as e:
            logger.error(f"Failed to import GUI components: {e}")
            logger.error("Make sure PySide6 is installed: pip install PySide6")
            sys.exit(1)
        except Exception as e:
            logger.error(f"GUI application error: {e}")
            sys.exit(1)

    elif args.mode == "controller":
        try:
            logger.info("Starting standalone controller...")
            from controller.main import main as controller_main

            controller_main()
        except Exception as e:
            logger.error(f"Controller error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
