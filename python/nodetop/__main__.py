"""
Executable entrypoint for python -m nodetop.
"""

import sys
from nodetop.cli import main

if __name__ == "__main__":
    sys.exit(main())
