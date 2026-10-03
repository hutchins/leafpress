"""Load the branding logo once, the same way for every output format.

``logo_path`` may come from an untrusted repository's leafpress.yml, so a
local logo must be a real image (judged by content, not name) and a remote
one is fetched only from a public host, with a size cap. Renderers embed the
returned bytes rather than linking to the original location, so every output
is self-contained.
"""

from __future__ import annotations

import base64
import gzip
import io
import logging
from dataclasses import dataclass
from pathlib import Path

from leafpress.base_renderer import is_image_file
from leafpress.config import BrandingConfig

logger = logging.getLogger(__name__)

MAX_LOGO_BYTES = 10 * 1024 * 1024
SVG_MIME = "image/svg+xml"


@dataclass(frozen=True)
class Logo:
    """Logo image bytes (SVGs already decompressed) and their MIME type."""

    data: bytes
    mime_type: str

    @property
    def is_svg(self) -> bool:
        return self.mime_type == SVG_MIME

    @property
    def extension(self) -> str:
        """File extension for packaging the logo, e.g. ``.png``."""
        subtype = self.mime_type.split("/", 1)[1]
        return {"svg+xml": ".svg", "jpeg": ".jpg"}.get(subtype, f".{subtype}")

    def data_uri(self) -> str:
        return f"data:{self.mime_type};base64,{base64.b64encode(self.data).decode('ascii')}"


def load_logo(branding: BrandingConfig | None) -> Logo | None:
    """Load ``branding.logo_path`` (local file or http(s) URL), or None to skip it.

    A missing, unreadable, or non-image logo is skipped with a warning rather
    than failing the conversion, as is a remote logo that can't be fetched.

    Example:
        >>> logo = load_logo(branding)
        >>> src = logo.data_uri() if logo else ""
    """
    if branding is None or not branding.logo_path:
        return None
    source = branding.logo_path
    if source.startswith(("http://", "https://")):
        from leafpress.downloads import DownloadError, download

        try:
            data, _ = download(
                source, max_bytes=MAX_LOGO_BYTES, timeout=30, require_public_host=True
            )
        except DownloadError as e:
            logger.warning("Could not fetch logo, skipping it: %s", e)
            return None
    else:
        path = Path(source)
        if not path.is_file():
            # The pipeline already reports "Logo not found"
            logger.debug("Logo file not found: %s", source)
            return None
        if not is_image_file(path):
            logger.warning("Logo is not a readable image, skipping: %s", source)
            return None
        data = _read_local(path)
        if data is None:
            logger.warning("Logo is too large or unreadable, skipping: %s", source)
            return None

    mime_type = _sniff_mime_type(data)
    if mime_type is None:
        logger.warning("Logo is not a readable image, skipping: %s", source)
        return None
    return Logo(data, mime_type)


def _read_local(path: Path) -> bytes | None:
    """Read a local logo, decompressing ``.svgz``; None if unreadable or over the cap."""
    try:
        if path.suffix.lower() == ".svgz":
            with gzip.open(path, "rb") as f:
                data = f.read(MAX_LOGO_BYTES + 1)
        else:
            with path.open("rb") as f:
                data = f.read(MAX_LOGO_BYTES + 1)
    except (OSError, EOFError):
        return None
    return data if len(data) <= MAX_LOGO_BYTES else None


def _sniff_mime_type(data: bytes) -> str | None:
    """MIME type of raster image or SVG bytes, or None if they aren't an image."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except Exception:
        # Not a raster image (or a decompression bomb): maybe an SVG
        return SVG_MIME if b"<svg" in data[: 1024 * 1024].lower() else None
    return Image.MIME.get(fmt or "", "image/png")
