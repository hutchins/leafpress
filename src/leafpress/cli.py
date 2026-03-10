"""Typer CLI application for leafpress."""

from __future__ import annotations

import platform
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from leafpress import __version__
from leafpress.config import DEFAULT_CONFIG_TEMPLATE, load_config
from leafpress.exceptions import LeafpressError
from leafpress.git_info import extract_git_info
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config
from leafpress.source import resolve_source

cli = typer.Typer(
    name="leafpress",
    help="Convert MkDocs sites to PDF and Word documents with branding.  [bold]leafpress[/bold] contributors",
    epilog="For detailed usage instructions, see the documentation at https://leafpress.dev",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


class OutputFormat(str, Enum):
    pdf = "pdf"
    docx = "docx"
    both = "both"


def version_callback(value: bool) -> None:
    if value:
        console.print(f"leafpress version {__version__}")
        raise typer.Exit()


@cli.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """leafpress - Convert MkDocs sites to PDF and Word documents."""


@cli.command()
def convert(
    source: str = typer.Argument(
        help="Path to local MkDocs directory or a git repo URL.",
    ),
    output: Path = typer.Option(
        Path("output"),
        "--output",
        "-o",
        help="Output directory for generated files.",
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.pdf,
        "--format",
        "-f",
        help="Output format: pdf, docx, or both.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to leafpress branding config YAML file.",
    ),
    mkdocs_config: Optional[Path] = typer.Option(
        None,
        "--mkdocs-config",
        help="Override path to mkdocs.yml.",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        "-b",
        help="Git branch to clone (only for git URL sources).",
    ),
    cover_page: bool = typer.Option(
        True,
        "--cover-page/--no-cover-page",
        help="Include a cover page.",
    ),
    toc: bool = typer.Option(
        True,
        "--toc/--no-toc",
        help="Include a table of contents.",
    ),
    open_after: bool = typer.Option(
        False,
        "--open",
        help="Open the generated file(s) after conversion.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output.",
    ),
) -> None:
    """Convert an MkDocs site to PDF and/or DOCX."""
    console.print(
        Panel(
            f"[bold]leafpress[/bold] v{__version__}",
            subtitle="MkDocs to PDF/DOCX converter",
            style="blue",
        )
    )

    try:
        from leafpress.pipeline import convert as pipeline_convert

        generated = pipeline_convert(
            source=source,
            output_dir=output,
            format=format.value,
            config_path=config,
            mkdocs_config_path=mkdocs_config,
            branch=branch,
            cover_page=cover_page,
            include_toc=toc,
        )

        if generated:
            console.print(f"\n[bold green]Done![/bold green] Generated {len(generated)} file(s).")
            if open_after:
                for path in generated:
                    _open_file(path)
        else:
            console.print("\n[yellow]No files were generated.[/yellow]")

    except LeafpressError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


@cli.command()
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


@cli.command()
def info(
    source: str = typer.Argument(
        help="Path to MkDocs directory or git URL.",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        "-b",
        help="Git branch (for git URLs).",
    ),
) -> None:
    """Display detected MkDocs site info."""
    try:
        with resolve_source(source, branch) as project_dir:
            # Find config
            config_file = None
            for name in ("mkdocs.yml", "mkdocs.yaml"):
                candidate = project_dir / name
                if candidate.exists():
                    config_file = candidate
                    break

            if not config_file:
                console.print("[red]No mkdocs.yml found.[/red]")
                raise typer.Exit(code=1)

            mkdocs_cfg = parse_mkdocs_config(config_file)

            # Site info panel
            console.print(Panel(f"[bold]{mkdocs_cfg.site_name}[/bold]", style="blue"))

            # Nav structure
            pages = flatten_nav(mkdocs_cfg.nav_items)
            table = Table(title="Navigation Structure")
            table.add_column("Title", style="cyan")
            table.add_column("Path", style="dim")
            table.add_column("Level", justify="right")

            for item in pages:
                indent = "  " * item.level
                path_str = str(item.path) if item.path else "[section]"
                table.add_row(f"{indent}{item.title}", path_str, str(item.level))
            console.print(table)

            # Extensions
            if mkdocs_cfg.markdown_extensions:
                ext_table = Table(title="Markdown Extensions")
                ext_table.add_column("Extension")
                for ext in mkdocs_cfg.markdown_extensions:
                    if isinstance(ext, str):
                        ext_table.add_row(ext)
                    elif isinstance(ext, dict):
                        for name in ext:
                            ext_table.add_row(name)
                console.print(ext_table)

            # Git info
            git_info = extract_git_info(project_dir)
            if git_info:
                git_table = Table(title="Git Information")
                git_table.add_column("Property", style="cyan")
                git_table.add_column("Value")
                git_table.add_row("Branch", git_info.branch)
                git_table.add_row("Commit", git_info.commit_hash)
                git_table.add_row("Date", git_info.commit_date.strftime("%Y-%m-%d %H:%M"))
                if git_info.tag:
                    git_table.add_row("Tag", git_info.tag)
                git_table.add_row("Dirty", str(git_info.is_dirty))
                git_table.add_row("Version String", git_info.format_version_string())
                console.print(git_table)

    except LeafpressError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@cli.command()
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
    except ImportError:
        console.print("[bold red]PyQt6 is required for the UI.[/bold red]")
        console.print(
            r"Install it with: [cyan]uv add 'leafpress\[ui]'[/cyan]"
            r"  or  [cyan]pip install 'leafpress\[ui]'[/cyan]"
        )
        raise typer.Exit(code=1)
    run_ui(show=show)


def _open_file(path: Path) -> None:
    """Open a file with the system default application."""
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    elif system == "Windows":
        subprocess.run(["start", "", str(path)], shell=True, check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


if __name__ == "__main__":
    cli()
