"""Open a file with the system's default application.

Shared by the CLI (``convert --open``, ``import``) and the desktop UI so the
Windows hardening (no ``cmd.exe``) lives in one place.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


def open_file(path: Path) -> None:
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
