"""Environment diagnostics for leafpress."""

from __future__ import annotations

import io
import platform
import shutil
import sys
from contextlib import redirect_stderr
from dataclasses import dataclass, field

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

# (pip_name, import_name) for core dependencies
CORE_DEPS: list[tuple[str, str]] = [
    ("typer", "typer"),
    ("rich", "rich"),
    ("pyyaml", "yaml"),
    ("pydantic", "pydantic"),
    ("markdown", "markdown"),
    ("pymdown-extensions", "pymdownx"),
    ("pygments", "pygments"),
    ("python-docx", "docx"),
    ("gitpython", "git"),
    ("jinja2", "jinja2"),
    ("beautifulsoup4", "bs4"),
    ("lxml", "lxml"),
    ("requests", "requests"),
    ("python-dotenv", "dotenv"),
    ("odfpy", "odf"),
    ("ebooklib", "ebooklib"),
    ("mammoth", "mammoth"),
    ("markdownify", "markdownify"),
]


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    passed: bool
    version: str | None = None
    message: str = ""
    install_hint: str = ""
    debug_output: str = ""


@dataclass
class DoctorReport:
    """Aggregated results from all checks."""

    leafpress_version: str = ""
    python_version: str = ""
    platform_info: str = ""
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


def _check_python() -> CheckResult:
    """Check Python version meets minimum requirement."""
    vi = sys.version_info
    ver = f"{vi[0]}.{vi[1]}.{vi[2]}"
    if vi >= (3, 13):
        return CheckResult(name="Python", passed=True, version=ver)
    return CheckResult(
        name="Python",
        passed=False,
        version=ver,
        message=f"Python {ver} is below the minimum 3.13",
    )


def _check_core_dep(pip_name: str, import_name: str) -> CheckResult:
    """Check a single core dependency is importable."""
    try:
        mod = __import__(import_name)
        ver = getattr(mod, "__version__", None)
        if ver is None:
            ver = getattr(mod, "VERSION", None)
        ver_str = str(ver) if ver else "installed"
        return CheckResult(name=pip_name, passed=True, version=ver_str)
    except ImportError:
        return CheckResult(
            name=pip_name,
            passed=False,
            message="Not installed",
            install_hint=f"pip install {pip_name}",
        )


def _check_weasyprint_package() -> CheckResult:
    """Check if WeasyPrint Python package is installed."""
    # Capture stderr: WeasyPrint prints noisy error messages before raising
    # OSError when system libs (cairo, pango) are missing.
    captured = io.StringIO()
    try:
        with redirect_stderr(captured):
            import weasyprint

        ver = getattr(weasyprint, "__version__", "installed")
        return CheckResult(name="WeasyPrint", passed=True, version=str(ver))
    except ImportError:
        return CheckResult(
            name="WeasyPrint",
            passed=False,
            message="Not installed (optional — needed for PDF output)",
            install_hint=_install_hint("pdf"),
        )
    except OSError as e:
        # Package is installed but system libs are broken/missing
        return CheckResult(
            name="WeasyPrint",
            passed=False,
            message=f"Installed but system libs failed: {e}",
            install_hint=_weasyprint_syslib_hint(),
            debug_output=captured.getvalue(),
        )


def _check_weasyprint_system_libs() -> CheckResult | None:
    """Check if WeasyPrint system libraries (cairo, pango, etc.) work."""
    captured = io.StringIO()
    try:
        with redirect_stderr(captured):
            import weasyprint  # noqa: F401
    except ImportError:
        # Package not installed — skip system lib check
        return None
    except OSError as e:
        # Package installed but system libs fail at import time
        return CheckResult(
            name="WeasyPrint system libs",
            passed=False,
            message=str(e),
            install_hint=_weasyprint_syslib_hint(),
            debug_output=captured.getvalue(),
        )

    try:
        from weasyprint import HTML

        HTML(string="<p>test</p>").write_pdf()
        return CheckResult(
            name="WeasyPrint system libs",
            passed=True,
            version="OK",
        )
    except OSError as e:
        return CheckResult(
            name="WeasyPrint system libs",
            passed=False,
            message=str(e),
            install_hint=_weasyprint_syslib_hint(),
        )


def _pip_cmd() -> str:
    """Detect the pip-like installer the user likely used."""
    if shutil.which("pipx") and "pipx" in (sys.prefix or ""):
        return "pipx inject leafpress"
    if shutil.which("uv"):
        return "uv pip install"
    return "pip install"


def _install_hint(extra: str) -> str:
    """Return an install hint for a leafpress extra like 'pdf' or 'ui'."""
    return f"{_pip_cmd()} 'leafpress[{extra}]'"


def _weasyprint_syslib_hint() -> str:
    """Return platform-specific install hint for WeasyPrint system libs."""
    system = platform.system()
    docs = "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
    if system == "Darwin":
        return f"brew install cairo pango gdk-pixbuf libffi\nDocs: {docs}"
    if system == "Linux":
        return (
            "sudo apt install libcairo2-dev libpango1.0-dev "
            f"libgdk-pixbuf2.0-dev libffi-dev\nDocs: {docs}"
        )
    return f"See: {docs}"


def _check_pyqt6() -> CheckResult:
    """Check if PyQt6 is installed."""
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR

        return CheckResult(name="PyQt6", passed=True, version=PYQT_VERSION_STR)
    except ImportError:
        return CheckResult(
            name="PyQt6",
            passed=False,
            message="Not installed (optional — needed for desktop UI)",
            install_hint=_install_hint("ui"),
        )


def _check_pyobjc() -> CheckResult | None:
    """Check pyobjc-framework-Cocoa on macOS. Returns None on other platforms."""
    if platform.system() != "Darwin":
        return None

    try:
        import objc  # type: ignore[import-untyped]

        __import__("AppKit")
        ver = getattr(objc, "__version__", "installed")
        return CheckResult(name="pyobjc (macOS)", passed=True, version=str(ver))
    except ImportError:
        return CheckResult(
            name="pyobjc (macOS)",
            passed=False,
            message="Not installed (optional — needed for macOS UI extra)",
            install_hint=_install_hint("ui"),
        )


def run_doctor(*, verbose: bool = False) -> DoctorReport:
    """Run all environment checks and return a report."""
    from leafpress import __version__

    report = DoctorReport(
        leafpress_version=__version__,
        python_version=(
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        platform_info=f"{platform.system()} {platform.release()} ({platform.machine()})",
    )

    # Python version
    report.checks.append(_check_python())

    # Core dependencies (verbose only)
    if verbose:
        for pip_name, import_name in CORE_DEPS:
            report.checks.append(_check_core_dep(pip_name, import_name))

    # Optional: WeasyPrint
    report.checks.append(_check_weasyprint_package())
    syslib_check = _check_weasyprint_system_libs()
    if syslib_check is not None:
        report.checks.append(syslib_check)

    # Optional: PyQt6
    report.checks.append(_check_pyqt6())

    # Optional: pyobjc (macOS only)
    pyobjc_check = _check_pyobjc()
    if pyobjc_check is not None:
        report.checks.append(pyobjc_check)

    return report


def _extras_line(report: DoctorReport) -> str:
    """Build a summary line showing which extras are installed."""
    # Reuse already-computed check results instead of re-importing
    extra_names = {"WeasyPrint": "pdf", "PyQt6": "ui"}
    parts: list[str] = []
    for check in report.checks:
        extra = extra_names.get(check.name)
        if extra:
            mark = "[green]✓[/green]" if check.passed else "[red]✗[/red]"
            parts.append(f"{extra} {mark}")
    return "Extras: " + "  ".join(parts)


def print_report(report: DoctorReport, console: Console, *, debug: bool = False) -> None:
    """Render a DoctorReport to the console with Rich formatting."""
    # Header
    console.print(
        Panel(
            f"[bold]leafpress[/bold] {escape(report.leafpress_version)}\n"
            f"Python {escape(report.python_version)}\n"
            f"{escape(report.platform_info)}\n"
            f"{_extras_line(report)}",
            title="[bold]leafpress doctor[/bold]",
            border_style="blue",
        )
    )

    # Results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Status", width=3, justify="center")
    table.add_column("Component")
    table.add_column("Version / Info")

    for check in report.checks:
        status = "[green]✓[/green]" if check.passed else "[red]✗[/red]"
        info = escape(check.version) if check.passed and check.version else ""
        if not check.passed and check.message:
            info = f"[red]{escape(check.message)}[/red]"
        table.add_row(status, escape(check.name), info)

    console.print(table)

    # Suggested fixes
    failed = [c for c in report.checks if not c.passed and c.install_hint]
    if failed:
        console.print("\n[bold yellow]Suggested fixes:[/bold yellow]\n")
        for check in failed:
            console.print(f"  [bold]{escape(check.name)}[/bold]")
            for line in check.install_hint.splitlines():
                console.print(f"    {escape(line)}")
            console.print()

    # Debug output for failed checks
    if debug:
        debug_checks = [c for c in report.checks if not c.passed and c.debug_output]
        if debug_checks:
            console.print("\n[bold cyan]Debug output:[/bold cyan]\n")
            for check in debug_checks:
                console.print(f"  [bold]{escape(check.name)}[/bold]")
                console.print(
                    Panel(
                        escape(check.debug_output.strip()),
                        border_style="dim",
                    )
                )

    # Summary
    if report.all_passed:
        console.print("[bold green]All checks passed![/bold green]")
    else:
        fail_count = sum(1 for c in report.checks if not c.passed)
        console.print(f"[bold red]{fail_count} check(s) need attention.[/bold red]")
