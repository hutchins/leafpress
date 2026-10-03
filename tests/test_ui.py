"""Tests for the desktop UI windows and workers (headless Qt; skipped without PyQt6)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

from leafpress.ui.app import ImportWorker  # noqa: E402

TEX = "\\documentclass{article}\\begin{document}Hello\\end{document}"


@pytest.fixture(scope="module", autouse=True)
def qapp() -> object:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _run(files: list[Path], output_dir: Path | None) -> tuple[list[str], tuple[bool, str]]:
    worker = ImportWorker(
        files=files, output_dir=output_dir, extract_images=False, include_notes=True
    )
    logs: list[str] = []
    finished: list[tuple[bool, str]] = []
    worker.log.connect(logs.append)
    worker.finished.connect(lambda ok, msg: finished.append((ok, msg)))
    worker.run()  # synchronous: signals are delivered directly on this thread
    return logs, finished[0]


def test_bad_file_does_not_stop_batch(tmp_path: Path) -> None:
    bad = tmp_path / "bad.docx"
    bad.write_text("not a zip")
    good = tmp_path / "good.tex"
    good.write_text(TEX)
    _logs, (ok, message) = _run([bad, good], tmp_path / "out")
    assert not ok
    assert "Imported 1 of 2" in message and "bad.docx" in message
    assert (tmp_path / "out" / "good.md").exists()


def test_same_name_inputs_do_not_overwrite(tmp_path: Path) -> None:
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        (tmp_path / sub / "report.tex").write_text(TEX.replace("Hello", f"From {sub}"))
    _logs, (ok, message) = _run(
        [tmp_path / "a" / "report.tex", tmp_path / "b" / "report.tex"], tmp_path / "out"
    )
    assert not ok and "would overwrite" in message
    assert "From a" in (tmp_path / "out" / "report.md").read_text()


def test_default_output_is_next_to_source(tmp_path: Path) -> None:
    src = tmp_path / "paper.tex"
    src.write_text(TEX)
    _logs, (ok, message) = _run([src], None)
    assert ok and message == "Imported 1 of 1 file(s)."
    assert (tmp_path / "paper.md").exists()


def test_unsupported_file_skipped(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text("hi")
    logs, (ok, _message) = _run([txt], tmp_path / "out")
    assert ok
    assert any("Skipped (unsupported: .txt)" in line for line in logs)


# ---------------------------------------------------------------------------
# Convert window options
# ---------------------------------------------------------------------------


def test_convert_options_default_to_config() -> None:
    from leafpress.ui.app import LeafpressWindow

    window = LeafpressWindow()
    assert window._extra_options() == {
        "branch": None,
        "watermark": None,
        "mermaid": None,
        "sanitize_html": None,
    }


def test_convert_options_map_to_pipeline_arguments() -> None:
    from leafpress.ui.app import LeafpressWindow

    window = LeafpressWindow()
    window._branch.setText("  release/1.0 ")
    window._watermark.setText("DRAFT")
    window._mermaid.setCurrentIndex(2)  # Keep as code
    window._sanitize.setCurrentIndex(1)  # On
    assert window._extra_options() == {
        "branch": "release/1.0",
        "watermark": "DRAFT",
        "mermaid": False,
        "sanitize_html": True,
    }


def test_convert_worker_passes_options(tmp_path: Path) -> None:
    from unittest.mock import patch

    from leafpress.ui.app import ConvertWorker

    worker = ConvertWorker(
        source="https://example.com/r.git",
        output_dir=tmp_path,
        fmt="html",
        config_path=None,
        cover_page=True,
        include_toc=True,
        branch="main",
        watermark="DRAFT",
        mermaid=False,
        sanitize_html=None,
    )
    finished: list[tuple[bool, str]] = []
    worker.finished.connect(lambda ok, msg: finished.append((ok, msg)))
    with patch("leafpress.pipeline.convert", return_value=[]) as convert:
        worker.run()
    kwargs = convert.call_args.kwargs
    assert kwargs["branch"] == "main" and kwargs["watermark"] == "DRAFT"
    assert kwargs["mermaid"] is False and kwargs["sanitize_html"] is None
    assert finished == [(True, "Generated 0 file(s).")]


# ---------------------------------------------------------------------------
# Window interactions (dialogs patched out)
# ---------------------------------------------------------------------------


class TestConvertWindow:
    def test_empty_source_warns_and_does_not_start(self) -> None:
        from unittest.mock import patch

        from leafpress.ui import app as ui

        window = ui.LeafpressWindow()
        with (
            patch.object(ui.QMessageBox, "warning") as warn,
            patch.object(ui, "ConvertWorker") as worker,
        ):
            window._run_convert()
        warn.assert_called_once()
        worker.assert_not_called()

    def test_run_starts_worker_with_form_values(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from leafpress.ui import app as ui

        window = ui.LeafpressWindow()
        window._source.setText(str(tmp_path))
        window._output.setText(str(tmp_path / "out"))
        window._config.setText(str(tmp_path / "leafpress.yml"))
        window._format.setCurrentText("html")
        window._toc.setChecked(False)
        with patch.object(ui, "ConvertWorker") as worker:
            window._run_convert()
        kwargs = worker.call_args.kwargs
        assert kwargs["source"] == str(tmp_path)
        assert kwargs["fmt"] == "html" and kwargs["include_toc"] is False
        assert kwargs["config_path"] == tmp_path / "leafpress.yml"
        worker.return_value.start.assert_called_once()
        assert not window._convert_btn.isEnabled()

    def test_finished_shows_result_and_reenables(self) -> None:
        from unittest.mock import patch

        from leafpress.ui import app as ui

        window = ui.LeafpressWindow()
        window._convert_btn.setEnabled(False)
        with (
            patch.object(ui.QMessageBox, "information") as info,
            patch.object(ui.QMessageBox, "critical") as crit,
        ):
            window._on_finished(True, "Generated 1 file(s).")
            window._on_finished(False, "boom")
        info.assert_called_once()
        crit.assert_called_once()
        assert window._convert_btn.isEnabled()

    def test_browse_fills_fields(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from leafpress.ui import app as ui

        window = ui.LeafpressWindow()
        with (
            patch.object(ui.QFileDialog, "getExistingDirectory", return_value=str(tmp_path)),
            patch.object(
                ui.QFileDialog, "getOpenFileName", return_value=(str(tmp_path / "l.yml"), "")
            ),
        ):
            window._browse_source()
            window._browse_output()
            window._browse_config()
        assert window._source.text() == str(tmp_path)
        assert window._output.text() == str(tmp_path)
        assert window._config.text() == str(tmp_path / "l.yml")

    def test_worker_reports_errors(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from leafpress.ui.app import ConvertWorker

        worker = ConvertWorker(
            source=str(tmp_path),
            output_dir=tmp_path,
            fmt="pdf",
            config_path=None,
            cover_page=True,
            include_toc=True,
        )
        finished: list[tuple[bool, str]] = []
        worker.finished.connect(lambda ok, msg: finished.append((ok, msg)))
        with patch("leafpress.pipeline.convert", side_effect=RuntimeError("nope")):
            worker.run()
        assert finished == [(False, "nope")]


class TestImportWindow:
    def test_no_files_warns(self) -> None:
        from unittest.mock import patch

        from leafpress.ui import app as ui

        window = ui.ImportWindow()
        with (
            patch.object(ui.QMessageBox, "warning") as warn,
            patch.object(ui, "ImportWorker") as worker,
        ):
            window._run_import()
        warn.assert_called_once()
        worker.assert_not_called()

    def test_browse_and_run(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from leafpress.ui import app as ui

        window = ui.ImportWindow()
        files = [str(tmp_path / "a.docx"), str(tmp_path / "b.tex")]
        with (
            patch.object(ui.QFileDialog, "getOpenFileNames", return_value=(files, "")),
            patch.object(ui.QFileDialog, "getExistingDirectory", return_value=str(tmp_path)),
            patch.object(ui, "ImportWorker") as worker,
        ):
            window._browse_files()
            window._browse_output()
            window._run_import()
        assert window._files.text() == "a.docx, b.tex"
        kwargs = worker.call_args.kwargs
        assert kwargs["files"] == [Path(f) for f in files]
        assert kwargs["output_dir"] == tmp_path
        worker.return_value.start.assert_called_once()


class TestTray:
    def test_menu_and_actions(self) -> None:
        from unittest.mock import patch

        from leafpress.ui import app as ui

        tray = ui.LeafpressTray(QtWidgets.QApplication.instance())
        labels = [a.text() for a in tray.contextMenu().actions() if a.text()]
        assert labels == ["Open leafpress", "Import files...", "About leafpress", "Quit leafpress"]
        tray._show_window()
        assert tray._window.isVisible()
        tray._show_import()
        assert tray._import_window.isVisible()
        tray._on_activated(ui.QSystemTrayIcon.ActivationReason.Trigger)
        with patch.object(ui.QMessageBox, "about") as about:
            tray._show_about()
        assert "leafpress" in about.call_args.args[2]
        tray._window.close()
        tray._import_window.close()


class TestLogConsole:
    def test_line_emitter_splits_and_skips_blank_lines(self) -> None:
        from leafpress.ui.app import _LineEmitter

        lines: list[str] = []
        stream = _LineEmitter(lines.append)
        stream.write("first\n\n  second")
        assert lines == ["first"]
        stream.write(" half\n")
        stream.write("tail")
        stream.flush()
        assert lines == ["first", "  second half", "tail"]

    def test_worker_routes_pipeline_output_to_log(self, tmp_path: Path) -> None:
        from unittest.mock import patch

        from leafpress.ui.app import ConvertWorker

        worker = ConvertWorker(
            source=str(tmp_path),
            output_dir=tmp_path,
            fmt="html",
            config_path=None,
            cover_page=True,
            include_toc=True,
        )
        logged: list[str] = []
        worker.log.connect(logged.append)

        def fake_convert(**kwargs: object) -> list[Path]:
            kwargs["console"].print("  [green]Site:[/green] Demo")  # type: ignore[union-attr]
            return []

        with patch("leafpress.pipeline.convert", side_effect=fake_convert):
            worker.run()
        assert "  Site: Demo" in logged
