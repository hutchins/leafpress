"""Render Mermaid diagram code blocks to PNG images."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

from leafpress.exceptions import DiagramError

logger = logging.getLogger(__name__)

_MERMAID_INK_BASE = "https://mermaid.ink/img"


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
    url = f"{_MERMAID_INK_BASE}/{encoded}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise DiagramError(f"Failed to render mermaid diagram: {e}") from e

    content_type = resp.headers.get("Content-Type", "")
    if "image" not in content_type:
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


def render_mermaid_blocks(html: str, output_dir: Path) -> str:
    """Find mermaid code blocks in HTML, render to images, and replace them.

    Args:
        html: HTML string potentially containing mermaid code blocks.
        output_dir: Directory to store rendered PNG images.

    Returns:
        HTML string with mermaid blocks replaced by <img> tags.
    """
    soup = BeautifulSoup(html, "lxml")
    blocks = _find_mermaid_blocks(soup)

    if not blocks:
        return html

    for pre in blocks:
        code = pre.find("code")
        source = code.get_text()
        if not source.strip():
            continue

        # Content-addressed filename for deduplication
        digest = hashlib.sha256(source.encode()).hexdigest()[:12]
        dest = output_dir / f"mermaid-{digest}.png"

        try:
            if not dest.exists():
                render_mermaid(source, dest)

            img = soup.new_tag("img", src=dest.resolve().as_uri(), alt="Mermaid diagram")
            img["style"] = "max-width: 100%;"
            pre.replace_with(img)
        except DiagramError:
            logger.warning("Failed to render mermaid diagram, keeping code block")

    return str(soup)
