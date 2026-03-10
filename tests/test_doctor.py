"""Tests for the leafpress doctor command."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.doctor import (
    CheckResult,
    DoctorReport,
    _check_core_dep,
    _check_pyobjc,
    _check_pyqt6,
    _check_python,
    _check_weasyprint_package,
    _check_weasyprint_system_libs,
    print_report,
    run_doctor,
)

runner = CliRunner()


# --- CheckResult / DoctorReport dataclasses ---


def test_check_result_defaults() -> None:
    """CheckResult has sensible defaults."""
    r = CheckResult(name="test", passed=True)
    assert r.version is None
    assert r.message == ""
    assert r.install_hint == ""


def test_doctor_report_all_passed() -> None:
    """all_passed is True when every check passes."""
    report = DoctorReport(checks=[
        CheckResult(name="a", passed=True),
        CheckResult(name="b", passed=True),
    ])
    assert report.all_passed is True


def test_doctor_report_not_all_passed() -> None:
    """all_passed is False when any check fails."""
    report = DoctorReport(checks=[
        CheckResult(name="a", passed=True),
        CheckResult(name="b", passed=False),
    ])
    assert report.all_passed is False


def test_doctor_report_empty_checks() -> None:
    """all_passed is True when there are no checks."""
    report = DoctorReport(checks=[])
    assert report.all_passed is True


# --- Python version check ---


def test_check_python_passes() -> None:
    """Passes on current interpreter (>= 3.13)."""
    result = _check_python()
    assert result.passed is True
    assert result.version is not None
    assert "3." in result.version


def test_check_python_fails_old(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails when Python version is below 3.13."""
    fake_info = (3, 12, 0, "final", 0)
    monkeypatch.setattr("leafpress.doctor.sys.version_info", fake_info)
    result = _check_python()
    assert result.passed is False
    assert "3.12" in result.message


# --- Core dependency checks ---


def test_check_core_dep_present() -> None:
    """Passes for an installed core dep (typer is always available in tests)."""
    result = _check_core_dep("typer", "typer")
    assert result.passed is True
    assert result.version is not None


def test_check_core_dep_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails when a core dep cannot be imported."""
    monkeypatch.setitem(sys.modules, "nonexistent_pkg_xyz", None)
    result = _check_core_dep("nonexistent-pkg", "nonexistent_pkg_xyz")
    assert result.passed is False
    assert "Not installed" in result.message
    assert "pip install nonexistent-pkg" in result.install_hint


# --- WeasyPrint package check ---


def test_weasyprint_package_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails with install hint when weasyprint is not importable."""
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    result = _check_weasyprint_package()
    assert result.passed is False
    assert "leafpress[pdf]" in result.install_hint


def test_weasyprint_package_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passes when weasyprint is importable with __version__."""
    mock_wp = MagicMock()
    mock_wp.__version__ = "62.1"
    monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)
    result = _check_weasyprint_package()
    assert result.passed is True
    assert result.version == "62.1"


# --- WeasyPrint system libs check ---


def test_weasyprint_syslibs_skipped_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns None when weasyprint package is not installed."""
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    result = _check_weasyprint_system_libs()
    assert result is None


def test_weasyprint_syslibs_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails with platform-specific hints when write_pdf() raises OSError."""
    mock_html_cls = MagicMock()
    mock_html_cls.return_value.write_pdf.side_effect = OSError("cannot load library 'libcairo'")
    mock_wp = MagicMock()

    monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)
    monkeypatch.setitem(sys.modules, "weasyprint.HTML", mock_html_cls)

    with patch("leafpress.doctor.HTML", mock_html_cls, create=True):
        # We need to patch the import inside the function
        pass

    # Call the actual function — it imports weasyprint, then from weasyprint import HTML
    # Mock the weasyprint module so it has HTML
    mock_wp.HTML = mock_html_cls
    # Also need weasyprint to be importable (not None)
    monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)

    result = _check_weasyprint_system_libs()
    assert result is not None
    assert result.passed is False
    assert "libcairo" in result.message
    assert "brew" in result.install_hint or "apt" in result.install_hint


def test_weasyprint_syslibs_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passes when write_pdf() succeeds without error."""
    mock_html_cls = MagicMock()
    mock_html_cls.return_value.write_pdf.return_value = b"%PDF-1.4"
    mock_wp = MagicMock()
    mock_wp.HTML = mock_html_cls
    monkeypatch.setitem(sys.modules, "weasyprint", mock_wp)

    result = _check_weasyprint_system_libs()
    assert result is not None
    assert result.passed is True


# --- PyQt6 check ---


def test_pyqt6_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails with install hint when PyQt6 is not importable."""
    monkeypatch.setitem(sys.modules, "PyQt6", None)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", None)
    result = _check_pyqt6()
    assert result.passed is False
    assert "leafpress[ui]" in result.install_hint


def test_pyqt6_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passes when PyQt6.QtCore is importable with version."""
    mock_core = MagicMock()
    mock_core.PYQT_VERSION_STR = "6.7.0"
    mock_pyqt6 = MagicMock()
    monkeypatch.setitem(sys.modules, "PyQt6", mock_pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", mock_core)
    result = _check_pyqt6()
    assert result.passed is True
    assert result.version == "6.7.0"


# --- pyobjc check ---


def test_pyobjc_none_on_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns None on non-macOS platforms."""
    monkeypatch.setattr("leafpress.doctor.platform.system", lambda: "Linux")
    result = _check_pyobjc()
    assert result is None


def test_pyobjc_missing_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails on macOS when objc/AppKit are not importable."""
    monkeypatch.setattr("leafpress.doctor.platform.system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "objc", None)
    result = _check_pyobjc()
    assert result is not None
    assert result.passed is False
    assert "leafpress[ui]" in result.install_hint


def test_pyobjc_present_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passes on macOS when objc and AppKit are importable."""
    monkeypatch.setattr("leafpress.doctor.platform.system", lambda: "Darwin")
    mock_objc = MagicMock()
    mock_objc.__version__ = "10.3"
    mock_appkit = MagicMock()
    monkeypatch.setitem(sys.modules, "objc", mock_objc)
    monkeypatch.setitem(sys.modules, "AppKit", mock_appkit)
    result = _check_pyobjc()
    assert result is not None
    assert result.passed is True
    assert result.version == "10.3"


# --- run_doctor orchestrator ---


def test_run_doctor_returns_report() -> None:
    """run_doctor returns a DoctorReport with version strings and checks."""
    report = run_doctor()
    assert report.leafpress_version != ""
    assert report.python_version != ""
    assert report.platform_info != ""
    assert len(report.checks) >= 3  # python, weasyprint pkg, pyqt6 at minimum


def test_run_doctor_verbose_includes_core_deps() -> None:
    """verbose=True includes core dependency names like typer, rich."""
    report = run_doctor(verbose=True)
    names = {c.name for c in report.checks}
    assert "typer" in names
    assert "rich" in names


def test_run_doctor_non_verbose_skips_core_deps() -> None:
    """verbose=False does not include core dep names."""
    report = run_doctor(verbose=False)
    names = {c.name for c in report.checks}
    assert "typer" not in names
    assert "rich" not in names


# --- print_report renderer ---


def test_print_report_no_crash() -> None:
    """print_report does not raise on a report with mixed pass/fail checks."""
    import io

    from rich.console import Console

    report = DoctorReport(
        leafpress_version="0.3.0",
        python_version="3.13.2",
        platform_info="Darwin 24.6.0 (arm64)",
        checks=[
            CheckResult(name="Python", passed=True, version="3.13.2"),
            CheckResult(
                name="WeasyPrint",
                passed=False,
                message="Not installed",
                install_hint="pip install 'leafpress[pdf]'",
            ),
        ],
    )
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    print_report(report, console)
    output = buf.getvalue()
    assert "leafpress doctor" in output
    assert "Python" in output
    assert "WeasyPrint" in output


# --- CLI integration ---


def test_doctor_cli_runs() -> None:
    """leafpress doctor produces output containing leafpress and Python."""
    result = runner.invoke(cli, ["doctor"])
    assert "leafpress" in result.output
    assert "Python" in result.output


def test_doctor_cli_verbose() -> None:
    """leafpress doctor --verbose includes core dep names."""
    result = runner.invoke(cli, ["doctor", "--verbose"])
    assert "typer" in result.output
    assert "rich" in result.output


def test_doctor_cli_exit_code_zero_all_pass() -> None:
    """Exit code 0 when all checks pass."""
    all_pass = DoctorReport(
        leafpress_version="0.2.2",
        python_version="3.13.2",
        platform_info="test",
        checks=[CheckResult(name="test", passed=True)],
    )
    with patch("leafpress.doctor.run_doctor", return_value=all_pass), \
         patch("leafpress.doctor.print_report"):
        result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0


def test_doctor_cli_exit_code_one_on_failure() -> None:
    """Exit code 1 when any check fails."""
    has_fail = DoctorReport(
        leafpress_version="0.2.2",
        python_version="3.13.2",
        platform_info="test",
        checks=[CheckResult(name="broken", passed=False)],
    )
    with patch("leafpress.doctor.run_doctor", return_value=has_fail), \
         patch("leafpress.doctor.print_report"):
        result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 1


# --- Rich escape regression ---


def test_error_message_preserves_brackets() -> None:
    """Error messages with [brackets] are not swallowed by Rich markup."""
    import io
    import re

    from rich.console import Console
    from rich.markup import escape

    msg = "Install with: pip install 'leafpress[pdf]'"
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    console.print(f"[bold red]Error:[/bold red] {escape(msg)}")
    output = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
    assert "[pdf]" in output
