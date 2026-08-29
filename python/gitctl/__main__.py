"""
Executable entrypoint when running `python3 -m gitctl`.
"""

import sys
from gitctl.cli import main

if __name__ == "__main__":
    sys.exit(main())
