"""Tests for mermaid diagram rendering."""

from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from leafpress.exceptions import DiagramError
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mermaid import (
    _find_mermaid_blocks,
    render_mermaid,
    render_mermaid_blocks,
)

# A 1x1 transparent PNG for mocking HTTP responses
_FAKE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

SAMPLE_MERMAID = "graph TD\n    A --> B"


class _FakeResponse:
    """Minimal mock for requests.get response."""

    def __init__(self, content: bytes = _FAKE_PNG, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code
        self.headers = {"Content-Type": "image/png"}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            from requests.exceptions import HTTPError

            raise HTTPError(f"{self.status_code}")


# --- render_mermaid ---


def test_render_mermaid_success(tmp_path: Path) -> None:
    dest = tmp_path / "diagram.png"
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid(SAMPLE_MERMAID, dest)

    assert result == dest
    assert dest.exists()
    assert dest.read_bytes() == _FAKE_PNG


def test_render_mermaid_http_error(tmp_path: Path) -> None:
    dest = tmp_path / "diagram.png"
    with patch(
        "leafpress.mermaid.requests.get",
        return_value=_FakeResponse(status_code=400),
    ):
        with pytest.raises(DiagramError, match="Failed to render mermaid"):
            render_mermaid(SAMPLE_MERMAID, dest)


def test_render_mermaid_bad_content_type(tmp_path: Path) -> None:
    resp = _FakeResponse()
    resp.headers = {"Content-Type": "text/html"}
    dest = tmp_path / "diagram.png"
    with patch("leafpress.mermaid.requests.get", return_value=resp):
        with pytest.raises(DiagramError, match="unexpected content type"):
            render_mermaid(SAMPLE_MERMAID, dest)


# --- _find_mermaid_blocks ---


def test_find_blocks_language_mermaid() -> None:
    from bs4 import BeautifulSoup

    html = '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
    soup = BeautifulSoup(html, "lxml")
    blocks = _find_mermaid_blocks(soup)
    assert len(blocks) == 1


def test_find_blocks_class_mermaid_on_pre() -> None:
    from bs4 import BeautifulSoup

    html = '<pre class="mermaid"><code>graph TD\n    A --> B</code></pre>'
    soup = BeautifulSoup(html, "lxml")
    blocks = _find_mermaid_blocks(soup)
    assert len(blocks) == 1


def test_find_blocks_class_mermaid_on_code() -> None:
    from bs4 import BeautifulSoup

    html = '<pre><code class="mermaid">graph TD\n    A --> B</code></pre>'
    soup = BeautifulSoup(html, "lxml")
    blocks = _find_mermaid_blocks(soup)
    assert len(blocks) == 1


def test_find_blocks_ignores_regular_code() -> None:
    from bs4 import BeautifulSoup

    html = '<pre><code class="language-python">print("hi")</code></pre>'
    soup = BeautifulSoup(html, "lxml")
    blocks = _find_mermaid_blocks(soup)
    assert len(blocks) == 0


# --- render_mermaid_blocks ---


def test_render_mermaid_blocks_replaces_with_img(tmp_path: Path) -> None:
    html = '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result
    assert "mermaid-" in result
    assert "<pre>" not in result


def test_render_mermaid_blocks_no_mermaid_passthrough(tmp_path: Path) -> None:
    html = "<p>Hello world</p>"
    result = render_mermaid_blocks(html, tmp_path)
    assert result == html


def test_render_mermaid_blocks_keeps_block_on_failure(tmp_path: Path) -> None:
    html = '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
    with patch(
        "leafpress.mermaid.requests.get",
        side_effect=requests.RequestException("network error"),
    ):
        result = render_mermaid_blocks(html, tmp_path)

    # Original code block should be preserved
    assert "<code" in result


def test_render_mermaid_blocks_deduplication(tmp_path: Path) -> None:
    html = (
        '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
        '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
    )
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()) as mock_get:
        result = render_mermaid_blocks(html, tmp_path)

    # Same diagram should only be fetched once (second uses cached file)
    assert mock_get.call_count == 1
    assert result.count("<img") == 2


def test_render_mermaid_blocks_multiple_different(tmp_path: Path) -> None:
    html = (
        '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
        '<pre><code class="language-mermaid">graph LR\n    X --> Y</code></pre>'
    )
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert result.count("<img") == 2
    # Two different diagrams should produce two different files
    pngs = list(tmp_path.glob("mermaid-*.png"))
    assert len(pngs) == 2


# --- end-to-end pipeline test ---


def test_pipeline_renders_mermaid_in_fixture(
    sample_mkdocs_dir: Path, tmp_path: Path
) -> None:
    """The sample fixture contains a mermaid block; verify it becomes an <img>."""
    renderer = MarkdownRenderer(
        extensions=["fenced_code"],
        docs_dir=sample_mkdocs_dir / "docs",
        mermaid_output_dir=tmp_path,
    )
    md_file = sample_mkdocs_dir / "docs" / "index.md"
    md_content = md_file.read_text(encoding="utf-8")

    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        html = renderer.render(md_content, md_file)

    assert "<img" in html
    assert "mermaid-" in html
    # The regular code block should still be present
    assert "hello" in html.lower()
    # A PNG should have been written
    pngs = list(tmp_path.glob("mermaid-*.png"))
    assert len(pngs) == 1
