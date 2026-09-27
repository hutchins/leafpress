"""Typer CLI application for leafpress.

The app object lives in :mod:`leafpress.cli.app`; each subcommand has its own
module. Commands are registered here explicitly so the ``--help`` listing order
is fixed and doesn't depend on import sorting.

``leafpress.cli:cli`` is the console-script entry point (see pyproject.toml).
"""

from __future__ import annotations

from leafpress.cli.app import cli
from leafpress.cli.convert import convert
from leafpress.cli.doctor import doctor
from leafpress.cli.fetch_diagrams import fetch_diagrams_cmd
from leafpress.cli.import_cmd import _resolve_import_source, import_file
from leafpress.cli.info import info
from leafpress.cli.init import init
from leafpress.cli.ui import ui

cli.command()(convert)
cli.command()(init)
cli.command()(info)
cli.command()(doctor)
cli.command(name="fetch-diagrams")(fetch_diagrams_cmd)
cli.command()(ui)
cli.command(name="import")(import_file)

__all__ = ["_resolve_import_source", "cli"]
