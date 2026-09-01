#!/usr/bin/env python3
"""
nodetop - btop-inspired terminal monitoring dashboard for Prometheus node_exporter.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from nodetop.cli import main

if __name__ == "__main__":
    sys.exit(main())
