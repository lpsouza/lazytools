#!/usr/bin/env python3
"""
git-ai - Git custom command wrapper for gitctl AI commit generator.
Enables running 'git ai' or 'git-ai' from anywhere.
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
