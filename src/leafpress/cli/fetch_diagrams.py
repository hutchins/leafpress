"""`leafpress fetch-diagrams`: download diagrams configured in leafpress.yml."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape

from leafpress.cli.app import console
from leafpress.exceptions import LeafpressError


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
