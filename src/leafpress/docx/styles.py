"""DOCX style configuration for branding."""

from __future__ import annotations

from docx.document import Document as DocxDocument
from docx.shared import Pt, RGBColor

from leafpress.config import BrandingConfig


def apply_branding_styles(doc: DocxDocument, branding: BrandingConfig | None) -> None:
    """Apply branding styles to a DOCX document."""
    style = doc.styles

    # Normal paragraph style
    normal = style["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    # Heading styles
    primary_color = _parse_hex_color(branding.primary_color if branding else "#1a73e8")

    for level in range(1, 5):
        heading_style = style[f"Heading {level}"]
        heading_style.font.name = "Calibri"
        heading_style.font.color.rgb = primary_color

        if level == 1:
            heading_style.font.size = Pt(24)
            heading_style.paragraph_format.space_before = Pt(24)
            heading_style.paragraph_format.space_after = Pt(12)
        elif level == 2:
            heading_style.font.size = Pt(18)
            heading_style.paragraph_format.space_before = Pt(18)
            heading_style.paragraph_format.space_after = Pt(8)
        elif level == 3:
            heading_style.font.size = Pt(14)
            heading_style.paragraph_format.space_before = Pt(14)
            heading_style.paragraph_format.space_after = Pt(6)
        else:
            heading_style.font.size = Pt(12)
            heading_style.paragraph_format.space_before = Pt(12)
            heading_style.paragraph_format.space_after = Pt(4)


def _parse_hex_color(hex_color: str) -> RGBColor:
    """Parse a hex color string to RGBColor."""
    stripped = hex_color.lstrip("#")
    if len(stripped) != 6:
        raise ValueError(f"Invalid hex color: {hex_color!r} (expected 6-digit hex, e.g. #1a73e8)")
    r = int(stripped[0:2], 16)
    g = int(stripped[2:4], 16)
    b = int(stripped[4:6], 16)
    return RGBColor(r, g, b)
