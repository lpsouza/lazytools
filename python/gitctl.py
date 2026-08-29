#!/usr/bin/env python3
"""
gitctl - Unified Git & GitHub CLI Launcher.
"""

import os
import sys

# Ensure the directory containing the gitctl package is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from gitctl.cli import main

if __name__ == "__main__":
    sys.exit(main())
