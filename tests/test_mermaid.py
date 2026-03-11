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
    with (
        patch(
            "leafpress.mermaid.requests.get",
            return_value=_FakeResponse(status_code=400),
        ),
        pytest.raises(DiagramError, match="Failed to render mermaid"),
    ):
        render_mermaid(SAMPLE_MERMAID, dest)


def test_render_mermaid_bad_content_type(tmp_path: Path) -> None:
    resp = _FakeResponse()
    resp.headers = {"Content-Type": "text/html"}
    dest = tmp_path / "diagram.png"
    with (
        patch("leafpress.mermaid.requests.get", return_value=resp),
        pytest.raises(DiagramError, match="unexpected content type"),
    ):
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


# --- flowchart and diagram type tests ---


def test_render_blocks_flowchart_with_labels(tmp_path: Path) -> None:
    """Flowchart with node labels, decision nodes, and edge labels."""
    mermaid_src = (
        "graph TD\n"
        "    A[Start] --> B{Decision}\n"
        "    B -->|Yes| C[OK]\n"
        "    B -->|No| D[End]"
    )
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result
    assert "<pre>" not in result
    pngs = list(tmp_path.glob("mermaid-*.png"))
    assert len(pngs) == 1


def test_render_blocks_subgraph(tmp_path: Path) -> None:
    """Flowchart with subgraph grouping."""
    mermaid_src = (
        "graph TD\n"
        "    subgraph Backend\n"
        "        A[API] --> B[DB]\n"
        "    end\n"
        "    subgraph Frontend\n"
        "        C[UI] --> A\n"
        "    end"
    )
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result
    assert "<pre>" not in result


def test_render_blocks_sequence_diagram(tmp_path: Path) -> None:
    """Sequence diagram with different arrow types."""
    mermaid_src = (
        "sequenceDiagram\n"
        "    Alice->>John: Hello John\n"
        "    John-->>Alice: Hi Alice\n"
        "    Alice->>John: How are you?\n"
        "    John-->>Alice: Great!"
    )
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result


def test_render_blocks_class_diagram(tmp_path: Path) -> None:
    """Class diagram with methods and relationships."""
    mermaid_src = (
        "classDiagram\n"
        "    Animal <|-- Duck\n"
        "    Animal <|-- Fish\n"
        "    Animal : +int age\n"
        "    Animal : +String gender\n"
        "    Animal: +isMammal()\n"
        "    Duck : +String beakColor\n"
        "    Duck : +swim()"
    )
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result


def test_render_blocks_state_diagram(tmp_path: Path) -> None:
    """State diagram with transitions."""
    mermaid_src = (
        "stateDiagram-v2\n"
        "    [*] --> Still\n"
        "    Still --> [*]\n"
        "    Still --> Moving\n"
        "    Moving --> Still\n"
        "    Moving --> Crash\n"
        "    Crash --> [*]"
    )
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result


def test_render_blocks_gantt_chart(tmp_path: Path) -> None:
    """Gantt chart diagram."""
    mermaid_src = (
        "gantt\n"
        "    title A Gantt Diagram\n"
        "    dateFormat  YYYY-MM-DD\n"
        "    section Section\n"
        "    A task           :a1, 2024-01-01, 30d\n"
        "    Another task     :after a1, 20d"
    )
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result


def test_render_blocks_special_characters(tmp_path: Path) -> None:
    """Diagram with special characters in node labels."""
    mermaid_src = 'graph TD\n    A["Node with quotes"] --> B[Node and stuff]'
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result


def test_render_blocks_empty_source_skipped(tmp_path: Path) -> None:
    """Empty or whitespace-only mermaid blocks are skipped."""
    html = '<pre><code class="language-mermaid">   \n  \n  </code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()) as mock_get:
        result = render_mermaid_blocks(html, tmp_path)

    # Should not call the API for empty content
    mock_get.assert_not_called()
    # Original block preserved (no img replacement)
    assert "<img" not in result


def test_render_blocks_invalid_syntax_preserved(tmp_path: Path) -> None:
    """Invalid mermaid syntax: API returns 400, block is preserved."""
    html = '<pre><code class="language-mermaid">this is not valid mermaid</code></pre>'
    with patch(
        "leafpress.mermaid.requests.get",
        return_value=_FakeResponse(status_code=400),
    ):
        result = render_mermaid_blocks(html, tmp_path)

    # Block should be preserved on failure
    assert "<code" in result
    assert "<img" not in result


def test_render_blocks_timeout(tmp_path: Path) -> None:
    """Timeout during rendering preserves the code block."""
    html = '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
    with patch(
        "leafpress.mermaid.requests.get",
        side_effect=requests.exceptions.Timeout("Connection timed out"),
    ):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<code" in result
    assert "<img" not in result


def test_render_blocks_mixed_mermaid_and_code(tmp_path: Path) -> None:
    """HTML with both mermaid and regular code blocks — only mermaid replaced."""
    html = (
        '<pre><code class="language-python">print("hello")</code></pre>'
        '<pre><code class="language-mermaid">graph TD\n    A --> B</code></pre>'
        '<pre><code class="language-javascript">console.log("hi")</code></pre>'
    )
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert result.count("<img") == 1
    assert "print" in result  # python block preserved
    assert "console.log" in result  # javascript block preserved


def test_render_blocks_flowchart_lr_direction(tmp_path: Path) -> None:
    """Left-to-right flowchart direction."""
    mermaid_src = "graph LR\n    A[Input] --> B[Process] --> C[Output]"
    html = f'<pre><code class="language-mermaid">{mermaid_src}</code></pre>'
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        result = render_mermaid_blocks(html, tmp_path)

    assert "<img" in result


def test_render_mermaid_base64_encoding_roundtrip() -> None:
    """Verify base64 encoding produces valid URL-safe strings."""
    import base64

    sources = [
        "graph TD\n    A --> B",
        "graph TD\n    A[Start] --> B{Decision}\n    B -->|Yes| C",
        "sequenceDiagram\n    Alice->>John: Hello",
    ]
    for source in sources:
        encoded = base64.urlsafe_b64encode(source.encode()).decode()
        # URL-safe base64 should not contain + or /
        assert "+" not in encoded
        assert "/" not in encoded
        # Should roundtrip
        decoded = base64.urlsafe_b64decode(encoded).decode()
        assert decoded == source


def test_render_blocks_content_addressed_filename(tmp_path: Path) -> None:
    """Different diagrams produce different filenames based on content hash."""
    import hashlib

    source1 = "graph TD\n    A --> B"
    source2 = "graph LR\n    X --> Y"
    digest1 = hashlib.sha256(source1.encode()).hexdigest()[:12]
    digest2 = hashlib.sha256(source2.encode()).hexdigest()[:12]

    assert digest1 != digest2

    html = (
        f'<pre><code class="language-mermaid">{source1}</code></pre>'
        f'<pre><code class="language-mermaid">{source2}</code></pre>'
    )
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        render_mermaid_blocks(html, tmp_path)

    assert (tmp_path / f"mermaid-{digest1}.png").exists()
    assert (tmp_path / f"mermaid-{digest2}.png").exists()


# --- end-to-end pipeline tests ---


def test_pipeline_flowchart_fixture(sample_mkdocs_dir: Path, tmp_path: Path) -> None:
    """The sample fixture has a flowchart with decision nodes — verify rendering."""
    renderer = MarkdownRenderer(
        extensions=["fenced_code"],
        docs_dir=sample_mkdocs_dir / "docs",
        mermaid_output_dir=tmp_path,
    )
    # Build a markdown doc with a complex flowchart
    md_content = (
        "# Test\n\n"
        "```mermaid\n"
        "graph TD\n"
        "    A[Start] --> B{Decision}\n"
        "    B -->|Yes| C[OK]\n"
        "    B -->|No| D[End]\n"
        "```\n"
    )
    md_file = sample_mkdocs_dir / "docs" / "index.md"
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        html = renderer.render(md_content, md_file)

    assert "<img" in html
    pngs = list(tmp_path.glob("mermaid-*.png"))
    assert len(pngs) == 1


def test_pipeline_architecture_flowchart(sample_mkdocs_dir: Path, tmp_path: Path) -> None:
    """Real-world architecture flowchart from docs — uses 'flowchart TD' and quoted labels."""
    renderer = MarkdownRenderer(
        extensions=["fenced_code"],
        docs_dir=sample_mkdocs_dir / "docs",
        mermaid_output_dir=tmp_path,
    )
    md_content = (
        "# Architecture\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        '    CLI["CLI (cli.py)"] --> |"source arg or auto-detect"| '
        'SR["Source Resolution (source.py)"]\n'
        '    SR --> |"ResolvedSource"| PL["Pipeline Orchestrator (pipeline.py)"]\n'
        '    PL --> CFG["Config Loading (config.py)"]\n'
        '    PL --> MKP["MkDocs Parsing (mkdocs_parser.py)"]\n'
        '    PL --> GIT["Git Info (git_info.py)"]\n'
        '    CFG --> |"BrandingConfig"| PL\n'
        '    MKP --> |"MkDocsConfig + NavItems"| PL\n'
        '    GIT --> |"GitVersion"| PL\n'
        '    PL --> MR["Markdown Rendering (markdown_renderer.py)"]\n'
        '    MR --> MM["Mermaid Diagrams (mermaid.py)"]\n'
        '    MR --> AN["Annotations (annotations.py)"]\n'
        '    MM --> |"HTML with images"| MR\n'
        '    AN --> |"HTML with footnotes"| MR\n'
        '    MR --> |"list of NavItem, HTML"| PL\n'
        '    PL --> PDF["PDF Renderer"]\n'
        '    PL --> HTML["HTML Renderer"]\n'
        '    PL --> DOCX["DOCX Renderer"]\n'
        '    PL --> ODT["ODT Renderer"]\n'
        '    PL --> EPUB["EPUB Renderer"]\n'
        '    PDF --> OUT["Output Files"]\n'
        '    HTML --> OUT\n'
        '    DOCX --> OUT\n'
        '    ODT --> OUT\n'
        '    EPUB --> OUT\n'
        "```\n"
    )
    md_file = sample_mkdocs_dir / "docs" / "index.md"
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        html = renderer.render(md_content, md_file)

    assert "<img" in html
    pngs = list(tmp_path.glob("mermaid-*.png"))
    assert len(pngs) == 1


def test_pipeline_import_flowchart(sample_mkdocs_dir: Path, tmp_path: Path) -> None:
    """Import pipeline flowchart from docs — second real-world diagram."""
    renderer = MarkdownRenderer(
        extensions=["fenced_code"],
        docs_dir=sample_mkdocs_dir / "docs",
        mermaid_output_dir=tmp_path,
    )
    md_content = (
        "# Import Pipeline\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        '    CLI["CLI (cli.py)"] --> |"file path + options"| DET["Format Detection"]\n'
        '    DET --> |".docx"| DOCXI["DOCX Converter (importer/converter.py)"]\n'
        '    DET --> |".pptx"| PPTXI["PPTX Converter (importer/converter_pptx.py)"]\n'
        '    DOCXI --> MAM["mammoth (HTML to Markdown)"]\n'
        '    PPTXI --> PPT["python-pptx (slides to Markdown)"]\n'
        '    MAM --> IMG["Image Handler (importer/image_handler.py)"]\n'
        '    PPT --> IMG\n'
        '    IMG --> |"assets/"| OUT["Output .md + images"]\n'
        '    MAM --> OUT\n'
        '    PPT --> OUT\n'
        "```\n"
    )
    md_file = sample_mkdocs_dir / "docs" / "index.md"
    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        html = renderer.render(md_content, md_file)

    assert "<img" in html
    pngs = list(tmp_path.glob("mermaid-*.png"))
    assert len(pngs) == 1


def test_pipeline_renders_mermaid_in_fixture(sample_mkdocs_dir: Path, tmp_path: Path) -> None:
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


def test_mermaid_source_not_in_rendered_output(tmp_path: Path) -> None:
    """Mermaid source text like 'flowchart TD' must not appear in rendered HTML."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    md_file = docs_dir / "test.md"
    md_file.write_text(
        "# Test\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        "    CLI --> SR\n"
        "    SR --> PL\n"
        "```\n"
    )

    renderer = MarkdownRenderer(
        extensions=["pymdownx.superfences"],
        docs_dir=docs_dir,
        mermaid_output_dir=tmp_path / "mermaid",
    )

    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        html = renderer.render(md_file.read_text(), md_file)

    assert "<img" in html
    assert "flowchart TD" not in html
    assert "CLI -->" not in html


def test_mermaid_with_python_name_config(tmp_path: Path) -> None:
    """Mermaid renders even when mkdocs.yml has !!python/name: format strings."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    md_file = docs_dir / "test.md"
    md_file.write_text(
        "```mermaid\n"
        "graph LR\n"
        "    A --> B\n"
        "```\n"
    )

    # Simulate the config that comes from yaml.safe_load of a mkdocs.yml
    # with !!python/name: tags (unresolved as raw strings)
    renderer = MarkdownRenderer(
        extensions=[
            {
                "pymdownx.superfences": {
                    "custom_fences": [
                        {
                            "name": "mermaid",
                            "class": "mermaid",
                            "format": "!!python/name:pymdownx.superfences.fence_code_format",
                        }
                    ]
                }
            }
        ],
        docs_dir=docs_dir,
        mermaid_output_dir=tmp_path / "mermaid",
    )

    with patch("leafpress.mermaid.requests.get", return_value=_FakeResponse()):
        html = renderer.render(md_file.read_text(), md_file)

    assert "<img" in html
    assert "graph LR" not in html
