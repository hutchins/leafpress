"""Shared Typer application, console, and global options for the leafpress CLI."""

from __future__ import annotations

from enum import StrEnum

import typer
from rich.console import Console

from leafpress import __version__

cli = typer.Typer(
    name="leafpress",
    help="Convert MkDocs sites to PDF, Word, HTML, ODT, and EPUB documents with branding.",
    epilog="For detailed usage instructions, see the documentation at https://leafpress.dev",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


console = Console()


class OutputFormat(StrEnum):
    pdf = "pdf"
    docx = "docx"
    html = "html"
    odt = "odt"
    epub = "epub"
    markdown = "markdown"
    both = "both"
    all = "all"


def version_callback(value: bool) -> None:
    if value:
        console.print(f"leafpress version {__version__}")
        raise typer.Exit()


@cli.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """leafpress - Convert MkDocs sites to PDF, Word, HTML, ODT, and EPUB documents."""
