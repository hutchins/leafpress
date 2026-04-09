"""Render Mermaid diagram code blocks to SVG/PNG images."""

from __future__ import annotations

import base64
import hashlib
import html as html_mod
import logging
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from leafpress.exceptions import DiagramError

logger = logging.getLogger(__name__)

_MERMAID_INK_PNG_BASE = "https://mermaid.ink/img"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_MERMAID_INK_SVG_BASE = "https://mermaid.ink/svg"


def _is_valid_png(path: Path) -> bool:
    """Check that a file exists and starts with the PNG magic bytes."""
    try:
        with path.open("rb") as f:
            header = f.read(8)
        return header == _PNG_MAGIC
    except OSError:
        return False


def _unescape_html_entities(source: str) -> str:
    """Decode residual HTML entities (e.g. ``&lt;`` → ``<``, ``&amp;`` → ``&``).

    BeautifulSoup's ``get_text()`` handles most decoding, but some entities
    may survive depending on the parser. This is a belt-and-suspenders pass.
    """
    return html_mod.unescape(source)


def _replace_literal_backslash_n(source: str) -> str:
    r"""Convert literal ``\n`` (backslash + n) to ``<br/>`` tags.

    Users often write ``\n`` in mermaid labels expecting a line break, but
    mermaid has no escape sequences — ``\n`` renders as literal text.
    """
    return source.replace("\\n", "<br/>")


def _replace_newlines_in_quoted_labels(source: str) -> str:
    """Convert actual newlines inside double-quoted strings to ``<br/>`` tags.

    Mermaid node labels like ``A["Line 1\\nLine 2"]`` need explicit ``<br/>``
    for line breaks. Actual newline characters inside quotes would render as
    literal ``\\n`` text on mermaid.ink.
    """

    def _nl_to_br(match: re.Match[str]) -> str:
        return match.group(0).replace("\n", "<br/>")

    return re.sub(r'"[^"]*"', _nl_to_br, source)


def _sanitize_mermaid_source(source: str) -> str:
    """Clean up mermaid source extracted from HTML for rendering.

    Applies three transformations in order:

    1. Decode residual HTML entities
    2. Convert literal ``\\n`` to ``<br/>``
    3. Convert newlines inside quoted labels to ``<br/>``
    """
    source = _unescape_html_entities(source)
    source = _replace_literal_backslash_n(source)
    source = _replace_newlines_in_quoted_labels(source)
    return source


def render_mermaid(source: str, dest: Path, timeout: int = 30) -> Path:
    """Render mermaid source to a PNG image via mermaid.ink.

    Args:
        source: Mermaid diagram source text.
        dest: Path to write the PNG file.
        timeout: HTTP request timeout in seconds.

    Returns:
        The dest path on success.

    Raises:
        DiagramError: If rendering fails.
    """
    encoded = base64.urlsafe_b64encode(source.encode()).decode()
    url = f"{_MERMAID_INK_PNG_BASE}/{encoded}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise DiagramError(f"Failed to render mermaid diagram: {e}") from e

    content_type = resp.headers.get("Content-Type", "")
    if "image" not in content_type:
        raise DiagramError(f"mermaid.ink returned unexpected content type '{content_type}'")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest


def render_mermaid_svg(source: str, dest: Path, timeout: int = 30) -> Path:
    """Render mermaid source to an SVG image via mermaid.ink.

    Args:
        source: Mermaid diagram source text.
        dest: Path to write the SVG file.
        timeout: HTTP request timeout in seconds.

    Returns:
        The dest path on success.

    Raises:
        DiagramError: If rendering fails.
    """
    encoded = base64.urlsafe_b64encode(source.encode()).decode()
    url = f"{_MERMAID_INK_SVG_BASE}/{encoded}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise DiagramError(f"Failed to render mermaid SVG: {e}") from e

    content_type = resp.headers.get("Content-Type", "")
    if "svg" not in content_type and "image" not in content_type:
        raise DiagramError(f"mermaid.ink returned unexpected content type '{content_type}'")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return dest


def _find_mermaid_blocks(soup: BeautifulSoup) -> list[Tag]:
    """Find all mermaid code blocks in parsed HTML.

    Detects multiple patterns:
      - <pre><code class="language-mermaid">...</code></pre>
      - <pre class="mermaid"><code>...</code></pre>
      - <pre><code class="mermaid">...</code></pre>
    """
    blocks: list[Tag] = []

    for pre in soup.find_all("pre"):
        code = pre.find("code")
        if not code:
            continue

        code_classes = list(code.get("class") or [])
        pre_classes = list(pre.get("class") or [])

        if (
            "language-mermaid" in code_classes
            or "mermaid" in code_classes
            or "mermaid" in pre_classes
        ):
            blocks.append(pre)

    return blocks


def render_mermaid_blocks(
    html: str,
    output_dir: Path,
    source_path: Path | None = None,
) -> tuple[str, list[str]]:
    """Find mermaid code blocks in HTML, render to images, and replace them.

    Args:
        html: HTML string potentially containing mermaid code blocks.
        output_dir: Directory to store rendered PNG images.
        source_path: Path to the source .md file (for warning context).

    Returns:
        Tuple of (HTML string with mermaid blocks replaced, list of warning messages).
    """
    soup = BeautifulSoup(html, "lxml")
    blocks = _find_mermaid_blocks(soup)
    warnings: list[str] = []

    if not blocks:
        return html, warnings

    page_label = source_path.name if source_path else "unknown page"
    rendered_ok = 0
    rendered_fail = 0

    for pre in blocks:
        code = pre.find("code")
        assert isinstance(code, Tag)
        source = _sanitize_mermaid_source(code.get_text())
        if not source.strip():
            continue

        # Content-addressed filename for deduplication
        digest = hashlib.sha256(source.encode()).hexdigest()[:12]
        dest = output_dir / f"mermaid-{digest}.png"

        # First line of source as a snippet for diagnostics
        snippet = source.strip().split("\n", 1)[0][:60]

        try:
            if not dest.exists() or not _is_valid_png(dest):
                render_mermaid(source, dest)

            img = soup.new_tag(
                "img",
                src=dest.resolve().as_uri(),
                alt="Mermaid diagram",
            )
            img["style"] = "max-width: 100%; max-height: 700px; object-fit: contain;"
            pre.replace_with(img)
            rendered_ok += 1
        except DiagramError as exc:
            msg = f"Mermaid diagram failed in {page_label} ({snippet}): {exc}"
            logger.warning(msg)
            warnings.append(msg)
            rendered_fail += 1

    # Summary message so the user sees mermaid activity in the output.
    # Only add when at least one diagram was actually attempted (skip if all
    # blocks were empty/whitespace-only).
    total = rendered_ok + rendered_fail
    if total > 0:
        if rendered_fail:
            warnings.insert(
                0,
                f"Rendered {rendered_ok}/{total} mermaid diagram(s) in {page_label}"
                f" ({rendered_fail} failed)",
            )
        else:
            warnings.insert(0, f"Rendered {rendered_ok} mermaid diagram(s) in {page_label}")

    return str(soup), warnings
