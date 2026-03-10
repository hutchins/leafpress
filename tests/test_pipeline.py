"""Tests for the conversion pipeline."""

from pathlib import Path

import pytest

from leafpress.exceptions import LeafpressError
from leafpress.pipeline import _find_mkdocs_config, _safe_filename, convert


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
    assert len(result) == 5
    suffixes = {f.suffix for f in result}
    assert suffixes == {".pdf", ".docx", ".html", ".odt", ".epub"}


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
