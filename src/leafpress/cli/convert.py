"""`leafpress convert`: render an MkDocs site to PDF/DOCX/HTML/ODT/EPUB/Markdown."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape
from rich.panel import Panel

from leafpress import __version__
from leafpress.cli.app import OutputFormat, console
from leafpress.exceptions import LeafpressError
from leafpress.opener import open_file


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
        help="Output format: pdf, docx, html, odt, epub, markdown, both (pdf+docx), or all.",
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
        help="Override path to mkdocs.yml (or zensical.toml, experimental).",
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
    sanitize_html: bool | None = typer.Option(
        None,
        "--sanitize-html/--no-sanitize-html",
        help=(
            "Strip scripts, event handlers, and other active content from page HTML "
            "(default: on for git URL sources, else leafpress.yml sanitize_html)."
        ),
    ),
    mermaid: bool | None = typer.Option(
        None,
        "--mermaid/--no-mermaid",
        help=(
            "Render mermaid diagrams via the configured mermaid.ink server "
            "(--no-mermaid keeps them as code blocks; nothing is sent)."
        ),
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

        if fetch_diagrams_flag:
            _fetch_diagrams_before_convert(config, source)

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
            mermaid=mermaid,
            sanitize_html=sanitize_html,
            verbose=verbose,
        )

        if generated:
            console.print(f"\n[bold green]Done![/bold green] Generated {len(generated)} file(s).")
            if open_after:
                for path in generated:
                    open_file(path)
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


def _fetch_diagrams_before_convert(config: Path | None, source: str) -> None:
    """Run the ``--fetch-diagrams`` pre-step.

    Uses ``-c`` if given, otherwise auto-detects leafpress.yml/.yaml in a
    local source directory (the same files conversion itself picks up).
    """
    from leafpress.config import load_config
    from leafpress.diagrams import fetch_diagrams
    from leafpress.source import GIT_URL_PATTERN

    if config is None:
        if GIT_URL_PATTERN.match(source):
            console.print(
                "[yellow]--fetch-diagrams is ignored for git URL sources "
                "(run fetch-diagrams in the repository instead).[/yellow]"
            )
            return
        config = next(
            (
                candidate
                for name in ("leafpress.yml", "leafpress.yaml")
                if (candidate := Path(source) / name).exists()
            ),
            None,
        )
        if config is None:
            console.print(
                "[yellow]--fetch-diagrams: no leafpress.yml found; nothing to fetch.[/yellow]"
            )
            return

    branding = load_config(config)
    if not branding.diagrams.sources:
        console.print("[yellow]--fetch-diagrams: no diagram sources configured.[/yellow]")
        return
    console.print("\n[bold]Fetching diagrams...[/bold]")
    fetch_diagrams(branding.diagrams, config.parent.resolve(), console=console)
