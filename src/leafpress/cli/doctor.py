"""`leafpress doctor`: check the environment and optional dependencies."""

from __future__ import annotations

import typer

from leafpress.cli.app import console


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
