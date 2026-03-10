"""CSS generation for PDF branding, headers, footers, and page layout."""

from __future__ import annotations

from importlib.resources import files

from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion


def generate_pdf_css(
    branding: BrandingConfig | None,
    git_info: GitVersion | None,
) -> str:
    """Generate complete CSS for PDF rendering via WeasyPrint.

    Combines the base stylesheet with dynamically generated @page rules
    for branding headers/footers.
    """
    # Load base CSS
    base_css = files("leafpress.pdf.templates").joinpath("base.css").read_text(encoding="utf-8")

    # Build @page rules
    page_css = _build_page_rules(branding, git_info)

    # Brand color overrides
    color_css = _build_color_overrides(branding)

    watermark_css = _build_watermark_css(branding)

    return f"{base_css}\n\n{page_css}\n\n{color_css}\n\n{watermark_css}"


def _build_page_rules(
    branding: BrandingConfig | None,
    git_info: GitVersion | None,
) -> str:
    """Build CSS @page rules for headers, footers, and page setup."""
    # Page size and margins
    page_size = "A4"
    margin_top = "25mm"
    margin_bottom = "25mm"
    margin_left = "20mm"
    margin_right = "20mm"

    if branding:
        page_size = branding.pdf.page_size
        margin_top = branding.pdf.margin_top
        margin_bottom = branding.pdf.margin_bottom
        margin_left = branding.pdf.margin_left
        margin_right = branding.pdf.margin_right

    # Header content
    top_left = ""
    top_right = ""
    if branding:
        top_left = branding.company_name
        top_right = branding.project_name

    # Footer content
    footer_parts: list[str] = []
    if branding and branding.footer.custom_text:
        footer_parts.append(branding.footer.custom_text)
    if branding and branding.footer.repo_url:
        footer_parts.append(branding.footer.repo_url)
    if git_info:
        version_parts: list[str] = []
        if (branding is None or branding.footer.include_tag) and git_info.tag:
            if git_info.tag_distance and git_info.tag_distance > 0:
                version_parts.append(f"{git_info.tag}+{git_info.tag_distance}")
            else:
                version_parts.append(git_info.tag)
        if branding is None or branding.footer.include_commit:
            version_parts.append(git_info.commit_hash)
        if branding is None or branding.footer.include_date:
            version_parts.append(git_info.commit_date.strftime("%Y-%m-%d"))
        if branding and branding.footer.include_branch:
            version_parts.append(git_info.branch)
        if version_parts:
            footer_parts.append(" | ".join(version_parts))

    footer_parts.append("Made with LeafPress · leafpress.dev")
    footer_center = " - ".join(footer_parts)

    # Escape quotes for CSS content strings
    top_left = top_left.replace('"', '\\"')
    top_right = top_right.replace('"', '\\"')
    footer_center = footer_center.replace('"', '\\"')

    return f"""
@page {{
    size: {page_size};
    margin: {margin_top} {margin_right} {margin_bottom} {margin_left};

    @top-left {{
        content: "{top_left}";
        font-size: 8pt;
        color: #666;
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    }}
    @top-right {{
        content: "{top_right}";
        font-size: 8pt;
        color: #666;
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    }}
    @bottom-center {{
        content: "{footer_center}";
        font-size: 7pt;
        color: #999;
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    }}
    @bottom-right {{
        content: "Page " counter(page) " of " counter(pages);
        font-size: 8pt;
        color: #999;
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    }}
}}

@page :first {{
    @top-left {{ content: none; }}
    @top-right {{ content: none; }}
    @bottom-center {{ content: none; }}
    @bottom-right {{ content: none; }}
}}
"""


def _build_watermark_css(branding: BrandingConfig | None) -> str:
    """Build CSS for a diagonal text watermark overlay on every page."""
    if not branding or not branding.watermark.text:
        return ""

    wm = branding.watermark
    return f"""
/* Watermark overlay */
.watermark {{
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%) rotate({wm.angle}deg);
    font-size: 80pt;
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-weight: bold;
    color: {wm.color};
    opacity: {wm.opacity};
    white-space: nowrap;
    pointer-events: none;
    z-index: -1;
}}
"""


def _build_color_overrides(branding: BrandingConfig | None) -> str:
    """Build CSS color overrides from branding config."""
    if not branding:
        return ""

    return f"""
/* Brand color overrides */
a {{ color: {branding.primary_color}; }}
h1, h2, h3 {{ color: {branding.primary_color}; }}
.cover-project {{ color: {branding.primary_color}; }}
.admonition.note {{ border-left-color: {branding.primary_color}; }}
"""
