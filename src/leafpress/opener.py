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
        os.startfile(path)  # noqa: S606 - the point: open with the default app, no shell
        return
    # Fixed argv (no shell), the system opener resolved from PATH by design
    if platform.system() == "Darwin":
        subprocess.run(["open", str(path)], check=False)  # noqa: S603, S607
    else:
        subprocess.run(["xdg-open", str(path)], check=False)  # noqa: S603, S607
