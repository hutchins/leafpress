"""Helpers for opening generated files with the system default application."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


def _open_file(path: Path) -> None:
    """Open a file with the system default application."""
    if sys.platform == "win32":
        # Opens via the shell association without spawning cmd.exe, so file
        # names can't be interpreted as shell syntax.
        os.startfile(path)
        return
    if platform.system() == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
