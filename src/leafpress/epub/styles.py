"""CSS generation for EPUB output."""

from __future__ import annotations

from leafpress.config import BrandingConfig


def generate_epub_css(branding: BrandingConfig | None) -> str:
    """Generate CSS for EPUB chapters."""
    primary = branding.primary_color if branding else "#1a73e8"

    return f"""
/* LeafPress EPUB Styles */
body {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 1em;
    line-height: 1.7;
    color: #333;
    margin: 1em;
}}

/* Cover page */
.lp-cover {{
    text-align: center;
    padding: 3em 1em 2em;
    margin-bottom: 2em;
}}

.lp-cover img {{ max-width: 60%; margin-bottom: 1.5em; }}
.lp-cover .company {{ font-size: 0.85em; color: #666; text-transform: uppercase;
    letter-spacing: 0.15em; margin-bottom: 0.5em; }}
.lp-cover h1 {{ font-size: 2em; color: {primary}; margin-bottom: 0.5em; }}
.lp-cover .subtitle {{ font-size: 1.1em; color: #666; margin-bottom: 2em; }}
.lp-cover .meta {{ font-size: 0.8em; color: #999; }}
.lp-cover .meta p {{ margin-bottom: 0.25em; }}

/* TOC */
.lp-toc h2 {{ font-size: 1.5em; margin-bottom: 0.75em; color: {primary}; }}
.lp-toc a {{ color: #333; text-decoration: none; display: block; padding: 0.25em 0;
    border-bottom: 1px dotted #ddd; }}
.lp-toc .toc-level-1 {{ padding-left: 1.25em; }}
.lp-toc .toc-level-2 {{ padding-left: 2.5em; }}
.lp-toc .toc-section {{ font-weight: 700; padding-top: 0.5em; }}

/* Typography */
h1 {{ font-size: 1.75em; margin: 1em 0 0.5em; color: {primary}; }}
h2 {{ font-size: 1.4em; margin: 1em 0 0.5em; color: #1a1a1a;
    border-bottom: 1px solid #eee; padding-bottom: 0.25em; }}
h3 {{ font-size: 1.15em; margin: 0.75em 0 0.4em; color: #1a1a1a; }}
h4 {{ font-size: 1em; margin: 0.6em 0 0.3em; color: #1a1a1a; }}

p {{ margin-bottom: 0.75em; }}

a {{ color: {primary}; text-decoration: none; }}

/* Code */
code {{
    font-family: "Courier New", Courier, monospace;
    font-size: 0.9em;
    background: #f5f5f5;
    padding: 0.1em 0.3em;
    border-radius: 3px;
}}

pre {{
    background: #f5f5f5;
    padding: 1em;
    border-radius: 4px;
    overflow-x: auto;
    border: 1px solid #e0e0e0;
    margin: 1em 0;
    line-height: 1.4;
}}

pre code {{
    background: none;
    padding: 0;
    font-size: 0.85em;
}}

/* Tables */
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.9em;
}}

th, td {{ border: 1px solid #ddd; padding: 0.5em 0.75em; text-align: left; }}
th {{ background: #f5f5f5; font-weight: 600; }}

/* Lists */
ul, ol {{ margin: 0 0 0.75em 1.5em; }}
li {{ margin-bottom: 0.25em; }}

/* Blockquotes */
blockquote {{
    border-left: 4px solid #e0e0e0;
    margin: 1em 0;
    padding: 0.75em 1.25em;
    color: #555;
    background: #fafafa;
}}

/* Images */
img {{ max-width: 100%; height: auto; }}
img.emojione, img.twemoji, img.gemoji {{
    height: 1.2em; width: auto; vertical-align: middle;
}}

/* Admonitions */
.admonition {{
    border-left: 4px solid #448aff;
    padding: 1em 1.25em;
    margin: 1em 0;
    background: #f8f9fa;
}}

.admonition-title {{ font-weight: 700; margin-bottom: 0.25em; }}
.admonition.note {{ border-left-color: #448aff; }}
.admonition.warning {{ border-left-color: #ff9100; }}
.admonition.danger, .admonition.error {{ border-left-color: #ff1744; }}
.admonition.tip, .admonition.hint {{ border-left-color: #00c853; }}
.admonition.info {{ border-left-color: #2196f3; }}
.admonition.example {{ border-left-color: #7c4dff; }}

/* Task lists */
.task-list {{ list-style: none; padding-left: 0; }}
.task-list-item {{ list-style: none; }}
.task-checkbox {{ font-size: 1.1em; margin-right: 0.4em; }}
.task-checkbox.checked {{ color: #00c853; }}

/* Horizontal rules */
hr {{ border: none; border-top: 1px solid #e0e0e0; margin: 1.5em 0; }}

/* Details */
details {{
    border: 1px solid #e0e0e0;
    padding: 1em;
    margin: 1em 0;
}}

summary {{ font-weight: 600; }}

/* Annotations (Material for MkDocs) */
.annotation-ref {{
    color: {primary};
    font-weight: 600;
    font-size: 0.8em;
    vertical-align: super;
}}

.annotation-list {{
    border-top: 1px solid #e0e0e0;
    margin-top: 1em;
    padding-top: 0.5em;
    font-size: 0.9em;
    color: #555;
}}

.annotation-item {{
    margin-bottom: 0.25em;
}}

.annotation-item sup {{
    color: {primary};
    font-weight: 600;
    margin-right: 0.25em;
}}

/* Footer */
.lp-footer {{
    margin-top: 3em;
    padding: 1em 0;
    border-top: 1px solid #e0e0e0;
    font-size: 0.75em;
    color: #999;
    text-align: center;
}}

/* Watermark */
.lp-watermark {{
    text-align: center;
    font-size: 3em;
    font-weight: bold;
    color: #cccccc;
    opacity: 0.15;
    margin: 2em 0;
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
"""
