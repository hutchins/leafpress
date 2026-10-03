"""`leafpress init`: write a starter leafpress.yml."""

from __future__ import annotations

from pathlib import Path

import typer

from leafpress.cli.app import console
from leafpress.config import DEFAULT_CONFIG_TEMPLATE


def init(
    path: Path = typer.Argument(
        Path("."),
        help="Directory to create the config file in.",
    ),
) -> None:
    """Generate a starter leafpress.yml branding config file."""
    config_path = path / "leafpress.yml"
    if config_path.exists():
        console.print(f"[yellow]Config already exists:[/yellow] {config_path}")
        raise typer.Exit(code=1)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE)
    console.print(f"[green]Created:[/green] {config_path}")
    console.print("Edit this file to configure branding for your documentation.")
