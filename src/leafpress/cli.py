"""Typer CLI application for leafpress."""

from __future__ import annotations

import platform
import subprocess
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from leafpress import __version__
from leafpress.config import DEFAULT_CONFIG_TEMPLATE
from leafpress.exceptions import LeafpressError
from leafpress.git_info import extract_git_info
from leafpress.importer.converter import ImportResult
from leafpress.mkdocs_parser import flatten_nav, parse_mkdocs_config
from leafpress.source import resolve_source

cli = typer.Typer(
    name="leafpress",
    help="Convert MkDocs sites to PDF, Word, HTML, ODT, and EPUB documents with branding.",
    epilog="For detailed usage instructions, see the documentation at https://leafpress.dev",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


class OutputFormat(str, Enum):
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


@cli.command()
def convert(
    source: str | None = typer.Argument(
        None,
        help="Path to local MkDocs directory or a git repo URL. Auto-detected if omitted.",
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
        help="Output format: pdf, docx, html, odt, epub, both (pdf+docx), or all.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to leafpress branding config YAML file.",
    ),
    mkdocs_config: Path | None = typer.Option(
        None,
        "--mkdocs-config",
        help="Override path to mkdocs.yml.",
    ),
    branch: str | None = typer.Option(
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
    local_time: bool = typer.Option(
        False,
        "--local-time",
        help="Use local timezone for dates instead of UTC.",
    ),
    footer_render_date: bool | None = typer.Option(
        None,
        "--footer-date/--no-footer-date",
        help="Include the generation date in the footer.",
    ),
    watermark: str | None = typer.Option(
        None,
        "--watermark",
        "-w",
        help='Watermark text overlay (e.g. "DRAFT", "CONFIDENTIAL").',
    ),
    fetch_diagrams_flag: bool = typer.Option(
        False,
        "--fetch-diagrams",
        help="Fetch diagrams from external sources before converting.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output.",
    ),
) -> None:
    """Convert an MkDocs site to PDF, DOCX, HTML, ODT, and/or EPUB."""
    console.print(
        Panel(
            f"[bold]leafpress[/bold] v{__version__}",
            subtitle="MkDocs to PDF/DOCX/HTML/ODT/EPUB converter",
            style="blue",
        )
    )

    try:
        if source is None:
            # Monorepo mode: if -c config has projects:, use config dir as source
            if config is not None:
                from leafpress.config import load_config as _peek_config

                _peek_branding = _peek_config(config)
                if _peek_branding.projects:
                    source = str(config.resolve().parent)
                    console.print(f"[dim]Monorepo mode: using config directory {source}[/dim]")

            if source is None:
                from leafpress.project import detect_project

                detected = detect_project()
                source = str(detected)
                console.print(f"[dim]Detected project: {detected}[/dim]")

        if fetch_diagrams_flag and config:
            from leafpress.config import load_config as _load_config
            from leafpress.diagrams import fetch_diagrams as _do_fetch

            branding = _load_config(config)
            if branding.diagrams.sources:
                console.print("\n[bold]Fetching diagrams...[/bold]")
                _do_fetch(branding.diagrams, config.parent.resolve(), console=console)

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
            local_time=local_time,
            watermark=watermark,
            footer_render_date=footer_render_date,
            verbose=verbose,
        )

        if generated:
            console.print(f"\n[bold green]Done![/bold green] Generated {len(generated)} file(s).")
            if open_after:
                for path in generated:
                    _open_file(path)
        else:
            console.print("\n[yellow]No files were generated.[/yellow]")

    except LeafpressError as e:
        console.print(f"\n[bold red]Error:[/bold red] {escape(str(e))}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {escape(str(e))}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1) from e


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


@cli.command()
def doctor(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Also check core dependencies (normally guaranteed to be installed).",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show captured error output from failed checks for troubleshooting.",
    ),
) -> None:
    """Check your environment and show the status of optional dependencies."""
    from leafpress.doctor import print_report, run_doctor

    report = run_doctor(verbose=verbose)
    print_report(report, console, debug=debug)
    if not report.all_passed:
        raise typer.Exit(code=1)


@cli.command(name="fetch-diagrams")
def fetch_diagrams_cmd(
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to leafpress.yml config file.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Force re-download even if cached files exist.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Enable verbose output.",
    ),
) -> None:
    """Fetch diagrams from external sources (URLs, Lucidchart API)."""
    import leafpress.config as _config_mod
    import leafpress.diagrams as _diagrams_mod

    # Auto-detect config if not specified
    if config is None:
        for name in ("leafpress.yml", "leafpress.yaml"):
            candidate = Path(name)
            if candidate.exists():
                config = candidate
                break

    if config is None or not config.exists():
        console.print("[red]No leafpress.yml config file found.[/red]")
        raise typer.Exit(code=1)

    try:
        branding = _config_mod.load_config(config)
    except LeafpressError as e:
        console.print(f"\n[bold red]Error:[/bold red] {escape(str(e))}")
        raise typer.Exit(code=1) from e

    if not branding.diagrams.sources:
        console.print("[yellow]No diagram sources configured.[/yellow]")
        raise typer.Exit()

    try:
        console.print(f"[bold]Fetching {len(branding.diagrams.sources)} diagram(s)...[/bold]\n")
        fetched = _diagrams_mod.fetch_diagrams(
            branding.diagrams,
            config.parent.resolve(),
            refresh=refresh,
            console=console,
        )
        console.print(f"\n[bold green]Done![/bold green] {len(fetched)} diagram(s) fetched.")

    except LeafpressError as e:
        console.print(f"\n[bold red]Error:[/bold red] {escape(str(e))}")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {escape(str(e))}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1) from e


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


@cli.command(name="import")
def import_file(
    files: list[Path] = typer.Argument(
        help="One or more .docx, .pptx, or .xlsx files to import.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output .md file path or directory. Defaults to <stem>.md.",
    ),
    extract_images: bool = typer.Option(
        True,
        "--extract-images/--no-extract-images",
        help="Extract embedded images to an assets/ folder.",
    ),
    code_styles: str | None = typer.Option(
        None,
        "--code-styles",
        help="Comma-separated Word style names to treat as code blocks (DOCX only).",
    ),
    include_notes: bool = typer.Option(
        True,
        "--notes/--no-notes",
        help="Include speaker notes as blockquotes (PPTX only).",
    ),
) -> None:
    """Import Word, PowerPoint, or Excel documents and convert them to Markdown."""
    # When multiple files are given, -o must be a directory (or omitted)
    if output and len(files) > 1 and output.suffix:
        console.print(
            "\n[bold red]Error:[/bold red] Use a directory for --output "
            "when importing multiple files."
        )
        raise typer.Exit(code=1)

    errors = 0
    for file in files:
        try:
            result = _import_single_file(
                file,
                output=output,
                extract_images=extract_images,
                code_styles=code_styles,
                include_notes=include_notes,
            )
            console.print(f"\n[bold green]Done![/bold green] {result.markdown_path}")
            if result.images:
                console.print(f"  [green]Images:[/green] {len(result.images)} extracted to assets/")
            if result.warnings:
                console.print(f"  [yellow]Warnings:[/yellow] {len(result.warnings)}")
                for w in result.warnings[:5]:
                    console.print(f"    - {w}")

        except LeafpressError as e:
            console.print(f"\n[bold red]Error:[/bold red] {escape(str(e))}")
            errors += 1

    if errors:
        console.print(f"\n[yellow]{errors} file(s) failed to import.[/yellow]")
        raise typer.Exit(code=1)


def _import_single_file(
    file: Path,
    *,
    output: Path | None,
    extract_images: bool,
    code_styles: str | None,
    include_notes: bool,
) -> ImportResult:
    """Import a single .docx, .pptx, or .xlsx file and return the result."""
    suffix = file.suffix.lower()

    if suffix == ".docx":
        from leafpress.importer.converter import import_docx as do_import

        style_list = (
            [s.strip() for s in code_styles.split(",") if s.strip()] if code_styles else None
        )
        return do_import(
            docx_path=file,
            output_path=output,
            extract_images=extract_images,
            code_styles=style_list,
        )

    if suffix == ".pptx":
        from leafpress.importer.converter_pptx import import_pptx

        return import_pptx(
            pptx_path=file,
            output_path=output,
            extract_images=extract_images,
            include_notes=include_notes,
        )

    if suffix == ".xlsx":
        from leafpress.importer.converter_xlsx import import_xlsx

        return import_xlsx(
            xlsx_path=file,
            output_path=output,
        )

    raise LeafpressError(f"Unsupported file type '{suffix}'. Use .docx, .pptx, or .xlsx")


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
