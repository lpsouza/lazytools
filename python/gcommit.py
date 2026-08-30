#!/usr/bin/env python3
"""
gcommit - Standalone AI-powered Git commit generator launcher for lazytools.
"""

import os
import sys

# Ensure the directory containing the gitctl package is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from gitctl.cli import main

if __name__ == "__main__":
    # Run gitctl in 'commit' mode forwarding all CLI flags
    sys.exit(main(["commit"] + sys.argv[1:]))
