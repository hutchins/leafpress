"""Environment diagnostics for leafpress."""

from __future__ import annotations

import ctypes
import ctypes.util
import io
import platform
import shutil
import sys
import tempfile
from contextlib import redirect_stderr
from dataclasses import dataclass, field

import requests
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


# (check_name, ctypes_name, brew_formula, apt_package)
_WEASYPRINT_SYSLIBS: list[tuple[str, str, str, str]] = [
    ("cairo", "cairo", "cairo", "libcairo2-dev"),
    ("pango", "pango-1.0", "pango", "libpango1.0-dev"),
    ("gdk-pixbuf", "gdk_pixbuf-2.0", "gdk-pixbuf", "libgdk-pixbuf2.0-dev"),
    ("libffi", "ffi", "libffi", "libffi-dev"),
]


def _find_syslib(ctypes_name: str) -> str | None:
    """Try to locate a system library. Returns path/name if found, None otherwise."""
    # Standard search via ctypes
    found = ctypes.util.find_library(ctypes_name)
    if found:
        try:
            ctypes.CDLL(found)
            return found
        except OSError:
            pass

    # Fallback: try Homebrew prefixes directly (helps inside uv isolated envs)
    system = platform.system()
    if system == "Darwin":
        machine = platform.machine()
        prefixes = (
            ["/opt/homebrew/lib", "/usr/local/lib"]
            if machine == "arm64"
            else ["/usr/local/lib", "/opt/homebrew/lib"]
        )
        candidates = [f"lib{ctypes_name}.dylib", f"lib{ctypes_name}-0.dylib"]
        for prefix in prefixes:
            for name in candidates:
                path = f"{prefix}/{name}"
                try:
                    ctypes.CDLL(path)
                    return path
                except OSError:
                    continue

    return None


def _check_weasyprint_syslibs_individual() -> list[CheckResult]:
    """Check each WeasyPrint system library individually."""
    results: list[CheckResult] = []
    system = platform.system()

    for display_name, ctypes_name, brew_formula, apt_pkg in _WEASYPRINT_SYSLIBS:
        path = _find_syslib(ctypes_name)
        if path:
            results.append(
                CheckResult(
                    name=f"  {display_name}",
                    passed=True,
                    version=path if path != display_name else "found",
                )
            )
        else:
            if system == "Darwin":
                hint = f"brew install {brew_formula}"
            elif system == "Linux":
                hint = f"sudo apt install {apt_pkg}"
            else:
                hint = ""
            results.append(
                CheckResult(
                    name=f"  {display_name}",
                    passed=False,
                    message="not found",
                    install_hint=hint,
                )
            )

    return results


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
        machine = platform.machine()
        hint = (
            "NOTE: 'brew install weasyprint' is NOT correct — that installs a\n"
            "  standalone CLI tool, not the libraries Python WeasyPrint needs.\n"
            "  Install the required system libraries instead:\n"
            "    brew install cairo pango gdk-pixbuf libffi"
        )
        if machine == "arm64":
            hint += (
                "\n\n  On Apple Silicon, Homebrew installs to /opt/homebrew/lib.\n"
                "  If WeasyPrint still can't find the libraries, add to your shell profile:\n"
                "    export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
            )
        hint += f"\n\nDocs: {docs}"
        return hint
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


# Import format checks — (format_label, import_name, pip_name)
_IMPORT_FORMATS: list[tuple[str, str, str]] = [
    ("docx", "mammoth", "mammoth"),
    ("pptx", "pptx", "python-pptx"),
    ("xlsx", "openpyxl", "openpyxl"),
    ("tex", "pylatexenc", "pylatexenc"),
]


def _check_import_formats() -> list[CheckResult]:
    """Check which import format dependencies are available."""
    results: list[CheckResult] = []
    for fmt, import_name, pip_name in _IMPORT_FORMATS:
        try:
            mod = __import__(import_name)
            ver = getattr(mod, "__version__", None) or getattr(mod, "VERSION", None)
            ver_str = str(ver) if ver else "installed"
            results.append(CheckResult(name=f"  .{fmt}", passed=True, version=ver_str))
        except ImportError:
            results.append(
                CheckResult(
                    name=f"  .{fmt}",
                    passed=False,
                    message="Not installed",
                    install_hint=f"{_pip_cmd()} {pip_name}",
                )
            )
    return results


def _check_temp_dir() -> CheckResult:
    """Check that the system temp directory is writable."""
    tmp_dir = tempfile.gettempdir()
    try:
        with tempfile.NamedTemporaryFile(dir=tmp_dir, prefix="leafpress_", delete=True) as f:
            f.write(b"test")
        free_mb = shutil.disk_usage(tmp_dir).free // (1024 * 1024)
        return CheckResult(
            name="Temp directory",
            passed=True,
            version=f"{tmp_dir} ({free_mb:,} MB free)",
        )
    except OSError as e:
        return CheckResult(
            name="Temp directory",
            passed=False,
            message=f"Cannot write to {tmp_dir}: {e}",
        )


def _check_latest_version(current: str) -> CheckResult:
    """Check if a newer version of leafpress is available on PyPI."""
    try:
        resp = requests.get("https://pypi.org/pypi/leafpress/json", timeout=5)
        resp.raise_for_status()
        latest = resp.json()["info"]["version"]
        if latest == current:
            return CheckResult(
                name="Latest version",
                passed=True,
                version=f"{current} (up to date)",
            )
        return CheckResult(
            name="Latest version",
            passed=False,
            version=current,
            message=f"Update available: {latest}",
            install_hint=f"{_pip_cmd()} --upgrade leafpress",
        )
    except Exception:
        return CheckResult(
            name="Latest version",
            passed=True,
            version=f"{current} (could not check PyPI)",
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
    for lib_check in _check_weasyprint_syslibs_individual():
        report.checks.append(lib_check)

    # Optional: PyQt6
    report.checks.append(_check_pyqt6())

    # Optional: pyobjc (macOS only)
    pyobjc_check = _check_pyobjc()
    if pyobjc_check is not None:
        report.checks.append(pyobjc_check)

    # Import format readiness
    report.checks.append(CheckResult(name="Import formats", passed=True, version=""))
    report.checks.extend(_check_import_formats())

    # Temp directory
    report.checks.append(_check_temp_dir())

    # Version check
    report.checks.append(_check_latest_version(__version__))

    return report


def _extras_line(report: DoctorReport) -> str:
    """Build a summary line showing which extras are installed."""
    extra_names = {"WeasyPrint": "pdf", "PyQt6": "ui"}
    parts: list[str] = []
    for check in report.checks:
        extra = extra_names.get(check.name)
        if extra:
            mark = "[green]✓[/green]" if check.passed else "[red]✗[/red]"
            parts.append(f"{extra} {mark}")
    return "Extras: " + "  ".join(parts)


def _import_formats_line(report: DoctorReport) -> str:
    """Build a summary line showing which import formats are available."""
    parts: list[str] = []
    for check in report.checks:
        # Import format checks are named "  .docx", "  .pptx", etc.
        name = check.name.strip()
        if name.startswith(".") and len(name) <= 5:
            mark = "[green]✓[/green]" if check.passed else "[red]✗[/red]"
            parts.append(f"{name} {mark}")
    return "Import: " + "  ".join(parts)


def print_report(report: DoctorReport, console: Console, *, debug: bool = False) -> None:
    """Render a DoctorReport to the console with Rich formatting."""
    # Header
    console.print(
        Panel(
            f"[bold]leafpress[/bold] {escape(report.leafpress_version)}\n"
            f"Python {escape(report.python_version)}\n"
            f"{escape(report.platform_info)}\n"
            f"{_extras_line(report)}\n"
            f"{_import_formats_line(report)}",
            title="[bold]leafpress doctor[/bold]",
            border_style="blue",
        )
    )

    # Results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Status", justify="center")
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
