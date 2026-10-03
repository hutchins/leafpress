"""`leafpress ui`: launch the menu bar / system tray app."""

from __future__ import annotations

import typer
from rich.panel import Panel

from leafpress.cli.app import console


def ui(
    show: bool = typer.Option(
        False,
        "--show",
        help="Open the window immediately on launch.",
    ),
) -> None:
    """Launch the leafpress menu bar / system tray app."""
    try:
        from leafpress.ui.app import run_ui
    except ImportError as e:
        console.print()
        console.print(
            Panel(
                "[bold]PyQt6[/bold] is required for the desktop UI.\n\n"
                "Install the UI extra with one of the following:\n\n"
                "  [cyan]uv add 'leafpress\\[ui]'[/cyan]\n"
                "  [cyan]pip install 'leafpress\\[ui]'[/cyan]\n"
                "  [cyan]pipx inject leafpress 'leafpress\\[ui]'[/cyan]\n\n"
                "Then run [bold]leafpress ui[/bold] again.",
                title="[bold red]Missing dependency[/bold red]",
                border_style="red",
            )
        )
        raise typer.Exit(code=1) from e
    run_ui(show=show)
