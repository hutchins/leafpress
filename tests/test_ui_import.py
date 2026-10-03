"""Tests for the desktop UI's import worker (headless Qt; skipped without PyQt6)."""

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
