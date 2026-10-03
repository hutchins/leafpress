"""`leafpress info`: show detected MkDocs site information."""

from __future__ import annotations

import typer
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from leafpress.cli.app import console
from leafpress.exceptions import LeafpressError
from leafpress.git_info import extract_git_info
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config
from leafpress.source import resolve_source


def info(
    source: str | None = typer.Argument(
        None,
        help="Path to MkDocs directory or git URL. Auto-detected if omitted.",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        "-b",
        help="Git branch (for git URLs).",
    ),
) -> None:
    """Display detected MkDocs site info."""
    try:
        if source is None:
            from leafpress.project import detect_project

            detected = detect_project()
            source = str(detected)
            console.print(f"[dim]Detected project: {detected}[/dim]")

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
        console.print(f"[bold red]Error:[/bold red] {escape(str(e))}")
        raise typer.Exit(code=1) from e
