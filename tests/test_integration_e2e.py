"""End-to-end tests: real pipeline and CLI runs across every output format.

These exercise features together the way users hit them, with only the
network call to the mermaid rendering server mocked:

- a deliberately malicious repository converted to all formats must not
  leak local files, embed attachments, or run code;
- local images and mermaid diagrams must end up inside every output
  (self-contained HTML, packaged EPUB, ODT/DOCX pictures), rendered by the
  server configured in leafpress.yml, with the temp directory cleaned up;
- CLI flags (--no-mermaid, --sanitize-html, --watermark) must reach output.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.pipeline import convert
from tests.helpers import make_png

SECRET = "E2E-SECRET-7731"
PNG = make_png()


def _distinct_png(color: str) -> bytes:
    """A PNG unlike PNG above (DOCX stores byte-identical images only once)."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 20), color).save(buf, format="PNG")
    return buf.getvalue()


MERMAID_PNG = _distinct_png("blue")


def _weasyprint_available() -> bool:
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


FORMATS = "all" if _weasyprint_available() else "docx"
needs_pdf = pytest.mark.skipif(not _weasyprint_available(), reason="WeasyPrint unavailable")


def _all_text(out: Path) -> str:
    """Every byte of text in every output, including inside ZIP containers."""
    parts: list[str] = []
    for f in out.iterdir():
        if f.suffix in (".docx", ".odt", ".epub"):
            with zipfile.ZipFile(f) as z:
                parts += [z.read(n).decode("utf-8", "replace") for n in z.namelist()]
        else:
            parts.append(f.read_bytes().decode("utf-8", "replace"))
    return "\n".join(parts)


def _mermaid_dirs() -> set[Path]:
    return set(Path(tempfile.gettempdir()).glob("leafpress-mermaid-*"))


# ---------------------------------------------------------------------------
# Malicious repository
# ---------------------------------------------------------------------------


@pytest.fixture
def evil_project(tmp_path: Path) -> Path:
    secret = tmp_path / "secret.txt"
    secret.write_text(SECRET)
    proj = tmp_path / "evil"
    (proj / "docs").mkdir(parents=True)
    (proj / "docs" / "ok.png").write_bytes(PNG)
    (proj / "docs" / "link.md").symlink_to(secret)
    (proj / "mkdocs.yml").write_text(
        "site_name: Evil\n"
        "nav:\n  - index.md\n  - Leak: ../../secret.txt\n  - link.md\n"
        "markdown_extensions:\n"
        "  - pymdownx.snippets:\n"
        f'      base_path: ["/", "{tmp_path}"]\n'
        "      restrict_base_path: false\n"
        "  - subprocess:Popen:\n"
        f'      args: ["touch", "{tmp_path / "pwned"}"]\n'
    )
    (proj / "docs" / "index.md").write_text(
        "# Hi\n\n![ok](ok.png)\n\n"
        f'--8<-- "{secret}"\n\n--8<-- "../secret.txt"\n\n'
        f'<img src="{secret.as_uri()}">\n\n'
        f"<img src={secret.as_uri()}>\n\n"
        f'<a rel="attachment" href="{secret.as_uri()}">att</a>\n\n'
        '<img src="http://169.254.169.254/latest/meta-data/">\n\n'
        "<script>alert(1)</script>\n"
    )
    return proj


def test_malicious_repo_leaks_nothing_in_any_format(evil_project: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    generated = convert(str(evil_project), out, format=FORMATS, mermaid=False)
    assert generated

    assert SECRET not in _all_text(out)
    assert not (tmp_path / "pwned").exists()  # subprocess:Popen never instantiated
    for pdf in out.glob("*.pdf"):
        assert b"/EmbeddedFile" not in pdf.read_bytes()  # rel=attachment blocked
    # The legitimate image still made it into DOCX
    with zipfile.ZipFile(next(out.glob("*.docx"))) as z:
        assert any(n.startswith("word/media/") for n in z.namelist())


def test_cloned_malicious_repo_is_sanitized_and_env_ignored(
    evil_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from leafpress import pipeline

    (evil_project / ".env").write_text("LEAFPRESS_COMPANY_NAME=Evil\nGIT_SSH_COMMAND=boom\n")
    monkeypatch.delenv("LEAFPRESS_COMPANY_NAME", raising=False)
    monkeypatch.delenv("GIT_SSH_COMMAND", raising=False)

    class _Clone:
        is_temporary = True

        def __enter__(self) -> Path:
            return evil_project

        def __exit__(self, *a: object) -> None:
            pass

    with patch.object(pipeline, "resolve_source", return_value=_Clone()):
        convert("https://example.com/evil.git", tmp_path / "out", format="html", mermaid=False)

    html = next((tmp_path / "out").glob("*.html")).read_text()
    assert "<script>" not in html and "alert(1)" not in html
    assert SECRET not in html
    import os

    assert "GIT_SSH_COMMAND" not in os.environ and "LEAFPRESS_COMPANY_NAME" not in os.environ


# ---------------------------------------------------------------------------
# Images and mermaid across formats
# ---------------------------------------------------------------------------


@pytest.fixture
def diagram_project(tmp_path: Path) -> Path:
    proj = tmp_path / "diag"
    (proj / "docs").mkdir(parents=True)
    (proj / "docs" / "photo.png").write_bytes(PNG)
    (proj / "mkdocs.yml").write_text(
        "site_name: Diagrams\nmarkdown_extensions:\n  - pymdownx.superfences\n"
    )
    (proj / "leafpress.yml").write_text(
        "company_name: Acme\nproject_name: Diagrams\n"
        "mermaid:\n  server: https://mermaid.internal.example\n"
    )
    (proj / "docs" / "index.md").write_text(
        "# Hi\n\n![photo](photo.png)\n\n```mermaid\ngraph TD\n  A-->B\n```\n"
    )
    return proj


def test_images_and_mermaid_embedded_in_every_format(diagram_project: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    before = _mermaid_dirs()
    with patch(
        "leafpress.mermaid.download", return_value=(MERMAID_PNG, {"Content-Type": "image/png"})
    ) as dl:
        convert(str(diagram_project), out, format=FORMATS)

    # Rendered by the server configured in leafpress.yml
    assert dl.call_args.args[0].startswith("https://mermaid.internal.example/img/")
    # Temp dir removed after the run
    assert _mermaid_dirs() == before

    with zipfile.ZipFile(next(out.glob("*.docx"))) as z:
        assert len([n for n in z.namelist() if n.startswith("word/media/")]) >= 2
    if FORMATS == "all":
        html = next(out.glob("*.html")).read_text()
        assert "file://" not in html
        assert len(re.findall(r'src="data:image/png;base64,', html)) >= 2
        with zipfile.ZipFile(next(out.glob("*.epub"))) as z:
            names = z.namelist()
            chapters = "".join(z.read(n).decode() for n in names if n.endswith(".xhtml"))
        assert len([n for n in names if "/images/" in n]) >= 2
        assert "file://" not in chapters
        with zipfile.ZipFile(next(out.glob("*.odt"))) as z:
            assert len([n for n in z.namelist() if n.startswith("Pictures/")]) >= 2


# ---------------------------------------------------------------------------
# CLI flags end to end
# ---------------------------------------------------------------------------


def test_cli_flags_reach_output(diagram_project: Path, tmp_path: Path) -> None:
    (diagram_project / "docs" / "index.md").write_text(
        '# Hi\n\n<p onclick="x()">click</p>\n\n```mermaid\ngraph TD\n  A-->B\n```\n'
    )
    out = tmp_path / "out"
    with patch("leafpress.mermaid.download") as dl:
        result = CliRunner().invoke(
            cli,
            [
                "convert",
                str(diagram_project),
                "-f",
                "html",
                "-o",
                str(out),
                "--no-mermaid",
                "--sanitize-html",
                "--watermark",
                "CONFIDENTIAL",
            ],
        )
    assert result.exit_code == 0, result.output
    dl.assert_not_called()  # --no-mermaid: nothing sent
    html = next(out.glob("*.html")).read_text()
    assert 'class="mermaid"' in html  # diagram kept as code
    assert "onclick" not in html  # sanitized
    assert "CONFIDENTIAL" in html  # watermark


def test_cli_import_multi_file_latex_project(tmp_path: Path) -> None:
    paper = tmp_path / "paper"
    (paper / "sections").mkdir(parents=True)
    (paper / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}"
        "\\input{sections/intro}\\section{Results}\\label{sec:res}"
        "See Section~\\ref{sec:intro}. \\SI{3e8}{\\metre\\per\\second}"
        "\\end{document}"
    )
    (paper / "sections" / "intro.tex").write_text(
        '\\section{Introduction}\\label{sec:intro}Sch\\"on --- see \\ref{sec:res}.'
    )
    result = CliRunner().invoke(cli, ["import", str(paper / "main.tex"), "-o", str(tmp_path)])
    assert result.exit_code == 0, result.output
    md = (tmp_path / "main.md").read_text()
    assert "## Introduction" in md and "## Results" in md
    assert "Schön — see 2." in " ".join(md.split())
    assert "See Section 1." in md
    assert "3 × 10⁸ m·s⁻¹" in md


@needs_pdf
def test_pdf_watermark_and_image_text(diagram_project: Path, tmp_path: Path) -> None:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext not installed")
    out = tmp_path / "out"
    convert(str(diagram_project), out, format="pdf", mermaid=False, watermark="DRAFT")
    text = subprocess.run(
        ["pdftotext", "-raw", str(next(out.glob("*.pdf"))), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "DRAFT" in "".join(text.split())
