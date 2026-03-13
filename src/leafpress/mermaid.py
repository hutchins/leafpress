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
_MERMAID_INK_SVG_BASE = "https://mermaid.ink/svg"


def _sanitize_mermaid_source(source: str) -> str:
    """Clean up mermaid source extracted from HTML for rendering.

    Handles three issues:
    1. HTML entities left over from Markup.escape() that get_text() decoded
       (e.g. ``&lt;br&gt;`` → ``<br>`` is fine, but we also unescape any
       remaining entities).
    2. Literal ``\\n`` text (backslash + n) anywhere in the source which users
       write expecting a line break — mermaid doesn't interpret ``\\n`` as a
       newline, so we convert it to ``<br/>``.
    3. Actual newline characters inside quoted or bracketed node labels which
       mermaid.ink renders as literal ``\\n`` text.  The correct mermaid syntax
       for line breaks inside labels is ``<br/>``.
    """
    # Decode any residual HTML entities (belt-and-suspenders)
    source = html_mod.unescape(source)

    # Replace literal \n (two chars: backslash + n) with <br/> everywhere.
    # Mermaid has no escape sequences, so \n is never meaningful as-is.
    source = source.replace("\\n", "<br/>")

    # Replace actual newline characters inside quoted strings with <br/>
    def _nl_to_br(match: re.Match[str]) -> str:
        return match.group(0).replace("\n", "<br/>")

    source = re.sub(r'"[^"]*"', _nl_to_br, source)

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
        raise DiagramError(
            f"mermaid.ink returned unexpected content type '{content_type}'"
        )

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

        code_classes = code.get("class", [])
        pre_classes = pre.get("class", [])

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
        source = _sanitize_mermaid_source(code.get_text())
        if not source.strip():
            continue

        # Content-addressed filename for deduplication
        digest = hashlib.sha256(source.encode()).hexdigest()[:12]
        dest = output_dir / f"mermaid-{digest}.png"

        # First line of source as a snippet for diagnostics
        snippet = source.strip().split("\n", 1)[0][:60]

        try:
            if not dest.exists():
                render_mermaid(source, dest)

            img = soup.new_tag(
                "img",
                src=dest.resolve().as_uri(),
                alt="Mermaid diagram",
            )
            img["style"] = (
                "max-width: 100%; max-height: 700px; object-fit: contain;"
            )
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
            warnings.insert(
                0, f"Rendered {rendered_ok} mermaid diagram(s) in {page_label}"
            )

    return str(soup), warnings
