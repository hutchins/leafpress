"""CSS generation for self-contained HTML output."""

from __future__ import annotations

from leafpress.config import BrandingConfig


def _watermark_display(branding: BrandingConfig | None) -> str:
    if branding and branding.watermark.text:
        return "block"
    return "none"


def _watermark_color(branding: BrandingConfig | None) -> str:
    if branding and branding.watermark.text:
        return branding.watermark.color
    return "#cccccc"


def _watermark_opacity(branding: BrandingConfig | None) -> float:
    if branding and branding.watermark.text:
        return branding.watermark.opacity
    return 0.15


def _watermark_angle(branding: BrandingConfig | None) -> int:
    if branding and branding.watermark.text:
        return branding.watermark.angle
    return -45


def generate_html_css(branding: BrandingConfig | None) -> str:
    """Generate complete CSS for standalone HTML output."""
    primary = branding.primary_color if branding else "#1a73e8"
    accent = branding.accent_color if branding else "#ffffff"

    return f"""
/* LeafPress HTML Output Styles */
:root {{
    --lp-primary: {primary};
    --lp-accent: {accent};
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial,
        sans-serif;
    font-size: 16px;
    line-height: 1.7;
    color: #333;
    background: #fff;
}}

/* Navigation sidebar */
.lp-sidebar {{
    position: fixed;
    top: 0;
    left: 0;
    width: 280px;
    height: 100vh;
    overflow-y: auto;
    background: #fafafa;
    border-right: 1px solid #e0e0e0;
    padding: 24px 16px;
    z-index: 100;
}}

.lp-sidebar h2 {{
    font-size: 14px;
    color: var(--lp-primary);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--lp-primary);
}}

.lp-sidebar a {{
    display: block;
    padding: 4px 8px;
    color: #555;
    text-decoration: none;
    font-size: 13px;
    border-radius: 4px;
    margin-bottom: 2px;
}}

.lp-sidebar a:hover {{
    background: #e8e8e8;
    color: var(--lp-primary);
}}

.lp-sidebar a.level-1 {{ padding-left: 24px; font-size: 12px; }}
.lp-sidebar a.level-2 {{ padding-left: 40px; font-size: 12px; }}

/* Main content area */
.lp-main {{
    margin-left: 280px;
    max-width: 900px;
    padding: 40px 48px;
}}

/* Cover page */
.lp-cover {{
    text-align: center;
    padding: 80px 20px 60px;
    border-bottom: 2px solid #e0e0e0;
    margin-bottom: 40px;
}}

.lp-cover img {{ max-width: 180px; margin-bottom: 32px; }}
.lp-cover .company {{ font-size: 14px; color: #666; text-transform: uppercase;
    letter-spacing: 2px; margin-bottom: 8px; }}
.lp-cover h1 {{ font-size: 36px; color: var(--lp-primary); margin-bottom: 12px; }}
.lp-cover .subtitle {{ font-size: 18px; color: #666; margin-bottom: 40px; }}
.lp-cover .meta {{ font-size: 13px; color: #999; }}
.lp-cover .meta p {{ margin-bottom: 4px; }}

/* TOC */
.lp-toc {{
    padding: 24px 0;
    border-bottom: 1px solid #e0e0e0;
    margin-bottom: 40px;
}}

.lp-toc h2 {{ font-size: 24px; margin-bottom: 16px; color: var(--lp-primary); }}
.lp-toc a {{ color: #333; text-decoration: none; display: block; padding: 4px 0;
    border-bottom: 1px dotted #ddd; }}
.lp-toc a:hover {{ color: var(--lp-primary); }}
.lp-toc .toc-level-1 {{ padding-left: 20px; }}
.lp-toc .toc-level-2 {{ padding-left: 40px; }}
.lp-toc .toc-section {{ font-weight: 700; padding-top: 8px; }}

/* Content */
article.page-content {{
    padding: 24px 0;
    border-bottom: 1px solid #f0f0f0;
    margin-bottom: 24px;
}}

.section-break {{
    padding: 32px 0 16px;
}}

/* Typography */
h1 {{ font-size: 28px; margin: 24px 0 12px; color: var(--lp-primary); }}
h2 {{ font-size: 22px; margin: 20px 0 10px; color: #1a1a1a;
    border-bottom: 1px solid #eee; padding-bottom: 6px; }}
h3 {{ font-size: 18px; margin: 16px 0 8px; color: #1a1a1a; }}
h4 {{ font-size: 16px; margin: 14px 0 6px; color: #1a1a1a; }}

p {{ margin-bottom: 12px; }}

a {{ color: var(--lp-primary); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* Code */
code {{
    font-family: "JetBrains Mono", "Source Code Pro", "Courier New", monospace;
    font-size: 14px;
    background: #f5f5f5;
    padding: 2px 6px;
    border-radius: 3px;
}}

pre {{
    background: #f5f5f5;
    padding: 16px;
    border-radius: 6px;
    overflow-x: auto;
    border: 1px solid #e0e0e0;
    margin: 16px 0;
    line-height: 1.5;
}}

pre code {{
    background: none;
    padding: 0;
    font-size: 13px;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 14px;
}}

th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
th {{ background: #f5f5f5; font-weight: 600; }}
tr:nth-child(even) {{ background: #fafafa; }}

/* Lists */
ul, ol {{ margin: 0 0 12px 24px; }}
li {{ margin-bottom: 4px; }}

/* Blockquotes */
blockquote {{
    border-left: 4px solid #e0e0e0;
    margin: 16px 0;
    padding: 12px 20px;
    color: #555;
    background: #fafafa;
    border-radius: 0 6px 6px 0;
}}

/* Images */
img {{ max-width: 100%; height: auto; }}
img.emojione, img.twemoji, img.gemoji {{
    height: 1.2em; width: auto; vertical-align: middle;
}}

/* Admonitions */
.admonition {{
    border-left: 4px solid #448aff;
    padding: 16px 20px;
    margin: 16px 0;
    background: #f8f9fa;
    border-radius: 0 6px 6px 0;
}}

.admonition-title {{ font-weight: 700; margin-bottom: 4px; }}
.admonition.note {{ border-left-color: #448aff; }}
.admonition.warning {{ border-left-color: #ff9100; }}
.admonition.danger, .admonition.error {{ border-left-color: #ff1744; }}
.admonition.tip, .admonition.hint {{ border-left-color: #00c853; }}
.admonition.info {{ border-left-color: #2196f3; }}
.admonition.example {{ border-left-color: #7c4dff; }}

/* Task lists */
.task-list {{ list-style: none; padding-left: 0; }}
.task-list-item {{ list-style: none; }}
.task-checkbox {{ font-size: 18px; margin-right: 6px; }}
.task-checkbox.checked {{ color: #00c853; }}

/* Horizontal rules */
hr {{ border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }}

/* Details */
details {{
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 16px;
    margin: 16px 0;
}}

summary {{ font-weight: 600; cursor: pointer; }}

/* Footer */
.lp-footer {{
    margin-top: 60px;
    padding: 20px 0;
    border-top: 1px solid #e0e0e0;
    font-size: 12px;
    color: #999;
    text-align: center;
}}

/* Pygments syntax highlighting */
.highlight .hll {{ background-color: #ffffcc; }}
.highlight .c {{ color: #6a737d; }}
.highlight .k {{ color: #d73a49; }}
.highlight .o {{ color: #d73a49; }}
.highlight .cm {{ color: #6a737d; }}
.highlight .cp {{ color: #d73a49; }}
.highlight .c1 {{ color: #6a737d; }}
.highlight .cs {{ color: #6a737d; }}
.highlight .gd {{ color: #b31d28; background-color: #ffeef0; }}
.highlight .gi {{ color: #22863a; background-color: #f0fff4; }}
.highlight .gs {{ font-weight: bold; }}
.highlight .gu {{ color: #6f42c1; }}
.highlight .kc {{ color: #005cc5; }}
.highlight .kd {{ color: #d73a49; }}
.highlight .kn {{ color: #d73a49; }}
.highlight .kp {{ color: #d73a49; }}
.highlight .kr {{ color: #d73a49; }}
.highlight .kt {{ color: #6f42c1; }}
.highlight .m {{ color: #005cc5; }}
.highlight .s {{ color: #032f62; }}
.highlight .na {{ color: #6f42c1; }}
.highlight .nb {{ color: #005cc5; }}
.highlight .nc {{ color: #6f42c1; }}
.highlight .no {{ color: #005cc5; }}
.highlight .nd {{ color: #6f42c1; }}
.highlight .nf {{ color: #6f42c1; }}
.highlight .nn {{ color: #005cc5; }}
.highlight .nt {{ color: #22863a; }}
.highlight .nv {{ color: #e36209; }}
.highlight .mi {{ color: #005cc5; }}
.highlight .mf {{ color: #005cc5; }}
.highlight .sa {{ color: #032f62; }}
.highlight .sb {{ color: #032f62; }}
.highlight .sc {{ color: #032f62; }}
.highlight .dl {{ color: #032f62; }}
.highlight .sd {{ color: #032f62; }}
.highlight .s2 {{ color: #032f62; }}
.highlight .se {{ color: #032f62; }}
.highlight .si {{ color: #032f62; }}
.highlight .s1 {{ color: #032f62; }}
.highlight .ss {{ color: #005cc5; }}
.highlight .sr {{ color: #032f62; }}

/* Watermark overlay */
.lp-watermark {{
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%) rotate({_watermark_angle(branding)}deg);
    font-size: 80pt;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-weight: bold;
    color: {_watermark_color(branding)};
    opacity: {_watermark_opacity(branding)};
    white-space: nowrap;
    pointer-events: none;
    z-index: 9999;
    display: {_watermark_display(branding)};
}}

/* Print styles */
@media print {{
    .lp-sidebar {{ display: none; }}
    .lp-main {{ margin-left: 0; max-width: 100%; padding: 0; }}
    article.page-content {{ page-break-before: always; }}
    article.page-content:first-of-type {{ page-break-before: auto; }}
    pre {{ white-space: pre-wrap; }}
}}
"""
