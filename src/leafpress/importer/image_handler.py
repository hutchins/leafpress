"""Image extraction handler for document import converters."""

from __future__ import annotations

import hashlib
from pathlib import Path


class ImageHandler:
    """Saves extracted images to disk for the DOCX, PPTX, and LaTeX importers.

    Each image is saved with a content-hash filename to avoid duplicates.
    The DOCX importer uses ``handle_image()`` as a mammoth callback; the
    PPTX and LaTeX importers call ``save_image()`` directly.
    """

    def __init__(self, assets_dir: Path) -> None:
        self._assets_dir = assets_dir
        self._saved_images: list[Path] = []
        self._counter = 0

    @property
    def saved_images(self) -> list[Path]:
        return list(self._saved_images)

    def save_image(self, image_bytes: bytes, content_type: str) -> str:
        """Save image bytes to disk and return the relative markdown path.

        Args:
            image_bytes: Raw image data.
            content_type: MIME type (e.g. "image/png").

        Returns:
            Relative path string for use in markdown (e.g. "assets/image-001-abc123.png").
        """
        ext = _extension_for_content_type(content_type)

        self._counter += 1
        content_hash = hashlib.sha256(image_bytes).hexdigest()[:12]
        filename = f"image-{self._counter:03d}-{content_hash}{ext}"

        self._assets_dir.mkdir(parents=True, exist_ok=True)
        image_path = self._assets_dir / filename
        image_path.write_bytes(image_bytes)
        self._saved_images.append(image_path)

        return f"assets/{filename}"

    def handle_image(self, image) -> dict[str, str]:
        """Mammoth image conversion callback.

        Args:
            image: mammoth image element with open() and content_type.

        Returns:
            Dict with 'src' key for the HTML img tag.
        """
        with image.open() as img_file:
            image_bytes = img_file.read()

        src = self.save_image(image_bytes, image.content_type)
        return {"src": src}


_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
    "image/webp": ".webp",
    "image/x-emf": ".emf",
    "image/x-wmf": ".wmf",
}

_EXT_TO_CONTENT_TYPE: dict[str, str] = {v: k for k, v in _CONTENT_TYPE_TO_EXT.items()}
# .jpeg is a common alias for .jpg
_EXT_TO_CONTENT_TYPE[".jpeg"] = "image/jpeg"


def _extension_for_content_type(content_type: str) -> str:
    """Map MIME content type to file extension."""
    return _CONTENT_TYPE_TO_EXT.get(content_type, ".png")


def content_type_for_extension(ext: str) -> str:
    """Map file extension to MIME content type."""
    return _EXT_TO_CONTENT_TYPE.get(ext, "image/png")
