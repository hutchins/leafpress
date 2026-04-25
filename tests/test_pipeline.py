"""Tests for the conversion pipeline."""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from leafpress.exceptions import LeafpressError
from leafpress.pipeline import (
    _ConsoleWarningHandler,
    _find_mkdocs_config,
    _format_docx_error,
    _format_epub_error,
    _format_html_error,
    _format_odt_error,
    _safe_filename,
    convert,
)


def test_convert_pdf(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="pdf",
        config_path=sample_branding_config,
    )
    assert len(result) == 1
    assert result[0].suffix == ".pdf"
    assert result[0].exists()
    assert result[0].stat().st_size > 0


def test_convert_docx(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="docx",
        config_path=sample_branding_config,
    )
    assert len(result) == 1
    assert result[0].suffix == ".docx"
    assert result[0].exists()


def test_convert_html(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="html",
        config_path=sample_branding_config,
    )
    assert len(result) == 1
    assert result[0].suffix == ".html"
    assert result[0].exists()


def test_convert_odt(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="odt",
        config_path=sample_branding_config,
    )
    assert len(result) == 1
    assert result[0].suffix == ".odt"
    assert result[0].exists()


def test_convert_epub(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="epub",
        config_path=sample_branding_config,
    )
    assert len(result) == 1
    assert result[0].suffix == ".epub"
    assert result[0].exists()


def test_convert_both(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="both",
        config_path=sample_branding_config,
    )
    assert len(result) == 2
    suffixes = {f.suffix for f in result}
    assert suffixes == {".pdf", ".docx"}


def test_convert_all(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="all",
        config_path=sample_branding_config,
    )
    assert len(result) == 6
    suffixes = {f.suffix for f in result}
    assert suffixes == {".pdf", ".docx", ".html", ".odt", ".epub", ".md"}


def test_convert_without_branding(
    sample_mkdocs_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="pdf",
        cover_page=False,
        include_toc=False,
    )
    assert len(result) == 1
    assert result[0].exists()


def test_convert_with_local_time(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="html",
        config_path=sample_branding_config,
        local_time=True,
    )
    assert len(result) == 1
    assert result[0].exists()


def test_convert_creates_output_dir(
    sample_mkdocs_config: Path,
    tmp_path: Path,
) -> None:
    nested_output = tmp_path / "a" / "b" / "c"
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=nested_output,
        format="html",
    )
    assert len(result) == 1
    assert nested_output.exists()


def test_find_mkdocs_config(sample_mkdocs_config: Path) -> None:
    found = _find_mkdocs_config(sample_mkdocs_config.parent)
    assert found.name in ("mkdocs.yml", "mkdocs.yaml")
    assert found.exists()


def test_find_mkdocs_config_missing(tmp_path: Path) -> None:
    with pytest.raises(LeafpressError, match=r"No mkdocs\.yml"):
        _find_mkdocs_config(tmp_path)


def test_safe_filename() -> None:
    assert _safe_filename("My Project") == "My Project"
    assert _safe_filename("Hello/World!") == "Hello_World_"
    assert _safe_filename("a-b_c") == "a-b_c"
    assert _safe_filename("  spaced  ") == "spaced"


def test_pdf_missing_error_mentions_pdf_extra(
    sample_mkdocs_config: Path,
    tmp_output: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error message must include literal [pdf] and suggest doctor command."""
    import sys

    monkeypatch.setitem(sys.modules, "leafpress.pdf.renderer", None)

    with pytest.raises(LeafpressError) as exc_info:
        convert(
            source=str(sample_mkdocs_config.parent),
            output_dir=tmp_output,
            format="pdf",
        )
    msg = str(exc_info.value)
    assert "[pdf]" in msg
    assert "leafpress doctor" in msg


def test_pdf_oserror_mentions_system_libs(
    sample_mkdocs_config: Path,
    tmp_output: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSError on PdfRenderer import (system libs missing) must give a targeted hint."""
    import builtins
    import sys

    monkeypatch.delitem(sys.modules, "leafpress.pdf.renderer", raising=False)
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "leafpress.pdf.renderer":
            raise OSError("cannot load library 'pango-1.0'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(LeafpressError) as exc_info:
        convert(
            source=str(sample_mkdocs_config.parent),
            output_dir=tmp_output,
            format="pdf",
        )
    msg = str(exc_info.value)
    assert "system libraries" in msg
    assert "cairo" in msg
    assert "leafpress doctor" in msg
    assert "pango-1.0" in msg  # original error preserved


# --- _ConsoleWarningHandler ---


class TestConsoleWarningHandler:
    """Tests for the _ConsoleWarningHandler logging handler."""

    def test_handler_emits_warning_to_console(self) -> None:
        """WARNING-level log records are printed to the console."""
        con = Console(file=MagicMock())
        handler = _ConsoleWarningHandler(con)

        record = logging.LogRecord(
            name="leafpress.test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="SVG logos are not supported",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        con.file.write.assert_called()  # type: ignore[union-attr]

    def test_handler_default_level_is_warning(self) -> None:
        """Handler default level is WARNING, so DEBUG records are filtered."""
        con = Console(file=MagicMock())
        handler = _ConsoleWarningHandler(con)
        assert handler.level == logging.WARNING

    def test_handler_verbose_accepts_debug(self) -> None:
        """When level is set to DEBUG, debug records pass through."""
        con = Console(file=MagicMock())
        handler = _ConsoleWarningHandler(con)
        handler.setLevel(logging.DEBUG)

        record = logging.LogRecord(
            name="leafpress.test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="debug detail",
            args=(),
            exc_info=None,
        )
        # The handler should not filter this record
        assert handler.filter(record)


def test_convert_includes_package_version(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    """Package version from pyproject.toml should be detected during convert.

    This test runs inside the leafpress repo which has a pyproject.toml,
    so detect_package_version should find a version.
    """
    import dataclasses

    from leafpress.git_info import extract_git_info
    from leafpress.package_version import detect_package_version

    project_dir = sample_mkdocs_config.parent
    git_info = extract_git_info(project_dir)
    pkg_ver = detect_package_version(project_dir)

    if git_info and pkg_ver:
        combined = dataclasses.replace(git_info, package_version=pkg_ver)
        assert combined.package_version == pkg_ver
        assert combined.commit_hash == git_info.commit_hash
        assert combined.branch == git_info.branch
        # Version string should contain the package version
        version_str = combined.format_version_string()
        assert pkg_ver in version_str


def test_package_version_without_git(tmp_path: Path) -> None:
    """When there's no git repo but a manifest exists, version is still detected."""
    from leafpress.git_info import extract_git_info
    from leafpress.package_version import detect_package_version

    # tmp_path has no .git, so git_info should be None
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.0.0"\n')
    git_info = extract_git_info(tmp_path)
    pkg_ver = detect_package_version(tmp_path)

    assert git_info is None
    assert pkg_ver == "1.0.0"


def test_convert_verbose_param_accepted(
    sample_mkdocs_config: Path,
    sample_branding_config: Path,
    tmp_output: Path,
) -> None:
    """Verify that verbose=True is accepted without error."""
    result = convert(
        source=str(sample_mkdocs_config.parent),
        output_dir=tmp_output,
        format="docx",
        config_path=sample_branding_config,
        verbose=True,
    )
    assert len(result) >= 1


class TestFormatDocxError:
    def test_image_error(self) -> None:
        msg = _format_docx_error(Exception("Cannot load image data"))
        assert "DOCX rendering failed due to an image error" in msg
        assert "PNG, JPEG" in msg
        assert "SVG" in msg
        assert "leafpress doctor" in msg

    def test_generic_error(self) -> None:
        msg = _format_docx_error(Exception("something went wrong"))
        assert "DOCX rendering failed" in msg
        assert "leafpress doctor" in msg
        assert "report it at" in msg


class TestFormatHtmlError:
    def test_image_error(self) -> None:
        msg = _format_html_error(Exception("broken image reference"))
        assert "HTML rendering failed due to an image error" in msg
        assert "leafpress doctor" in msg

    def test_template_error(self) -> None:
        msg = _format_html_error(Exception("Jinja template not found"))
        assert "template error" in msg
        assert "reinstall" in msg

    def test_generic_error(self) -> None:
        msg = _format_html_error(Exception("something went wrong"))
        assert "HTML rendering failed" in msg
        assert "report it at" in msg


class TestFormatOdtError:
    def test_image_error(self) -> None:
        msg = _format_odt_error(Exception("Failed to embed image"))
        assert "ODT rendering failed due to an image error" in msg
        assert "SVG" in msg
        assert "PNG" in msg

    def test_generic_error(self) -> None:
        msg = _format_odt_error(Exception("something went wrong"))
        assert "ODT rendering failed" in msg
        assert "report it at" in msg


class TestFormatEpubError:
    def test_image_error(self) -> None:
        msg = _format_epub_error(Exception("Cannot process image"))
        assert "EPUB rendering failed due to an image error" in msg
        assert "embedded" in msg

    def test_encoding_error(self) -> None:
        msg = _format_epub_error(Exception("unicode decode error"))
        assert "encoding error" in msg
        assert "UTF-8" in msg

    def test_generic_error(self) -> None:
        msg = _format_epub_error(Exception("something went wrong"))
        assert "EPUB rendering failed" in msg
        assert "report it at" in msg
