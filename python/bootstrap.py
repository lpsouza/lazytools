"""
Runtime environment bootstrapper for lazytools.
Ensures Python scripts execute inside the project's isolated virtual environment (.venv).
"""

from __future__ import annotations

import os
from pathlib import Path
import sys


def ensure_venv() -> None:
    """Auto-detect and re-exec inside repository .venv if available and not already active."""
    # Prevent recursive re-exec loops
    if os.environ.get("_LAZYTOOLS_VENV_ACTIVE") == "1":
        return

    # Project root is the parent directory of python/
    repo_root = Path(__file__).resolve().parent.parent
    venv_dir = repo_root / ".venv"

    if not venv_dir.is_dir():
        return

    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.is_file():
        return

    # Check if we are already running inside this virtual environment
    try:
        current_exe = Path(sys.executable).resolve()
        target_exe = venv_python.resolve()
        if current_exe == target_exe:
            return
    except Exception:
        pass

    os.environ["_LAZYTOOLS_VENV_ACTIVE"] = "1"
    script_path = str(Path(sys.argv[0]).resolve())
    exec_args = [str(venv_python), script_path] + sys.argv[1:]

    if sys.platform == "win32":
        import subprocess
        sys.exit(subprocess.call(exec_args))
    else:
        os.execv(str(venv_python), exec_args)
