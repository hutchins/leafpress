"""HTML sanitizing for content from untrusted sources.

Markdown allows raw HTML, so a page can carry ``<script>``, ``onerror=``
handlers, or ``javascript:`` links straight into the HTML and EPUB output
(stored XSS once that output is hosted). :func:`sanitize_html` removes active
content while keeping everything MkDocs / Material / pymdown-extensions
normally produce: admonitions, tabs, details, tables, footnotes, task lists,
highlighted code, math, emoji, and images.

It runs automatically for repositories cloned from a git URL and can be
enabled for any source (see :func:`should_sanitize`).
"""

from __future__ import annotations

import os

import nh3

_ALLOWED_TAGS = {
    # Structure and text
    "a", "abbr", "address", "article", "aside", "b", "bdi", "bdo", "blockquote",
    "br", "caption", "center", "cite", "code", "col", "colgroup", "dd", "del",
    "details", "dfn", "div", "dl", "dt", "em", "figcaption", "figure", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr", "i", "img",
    "ins", "kbd", "label", "li", "main", "mark", "nav", "ol", "p", "picture",
    "pre", "q", "rp", "rt", "ruby", "s", "samp", "section", "small", "source",
    "span", "strike", "strong", "sub", "summary", "sup", "table", "tbody", "td",
    "tfoot", "th", "thead", "time", "tr", "tt", "u", "ul", "var", "wbr",
    # Task-list checkboxes (pymdownx.tasklist) and tab radios (pymdownx.tabbed)
    "input",
}  # fmt: skip

_GENERIC_ATTRIBUTES = {"class", "id", "title", "lang", "dir", "style", "role", "aria-hidden"}

_TAG_ATTRIBUTES = {
    "a": {"href", "name", "target"},
    "img": {"src", "alt", "width", "height", "loading"},
    "source": {"srcset", "media", "type"},
    "input": {"type", "checked", "disabled", "name"},
    "div": {"data-tabs"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align", "scope"},
    "col": {"span", "width"},
    "ol": {"start", "type", "reversed"},
    "li": {"value"},
    "details": {"open"},
    "label": {"for"},
    "time": {"datetime"},
    "code": {"data-lang"},
}

# Inline CSS properties that can't load resources or overlay the page
_ALLOWED_STYLE_PROPERTIES = {
    "color", "background-color", "font-weight", "font-style", "font-size",
    "text-align", "text-decoration", "vertical-align", "white-space",
    "width", "height", "max-width", "max-height", "min-width", "min-height",
    "object-fit", "margin", "margin-left", "margin-right", "margin-top",
    "margin-bottom", "padding", "padding-left", "padding-right", "padding-top",
    "padding-bottom", "border", "border-collapse", "display", "float", "clear",
    "line-height", "list-style-type",
}  # fmt: skip

# file: and data: are needed for local/mermaid images before they are embedded
_URL_SCHEMES = {"http", "https", "mailto", "file", "data"}

_ALLOWED_INPUT_TYPES = {"checkbox", "radio"}


def _filter_attribute(tag: str, attribute: str, value: str) -> str | None:
    """Drop attribute values that are dangerous even on allowed tags."""
    lowered = value.strip().lower()
    # data: is fine for images but can carry a whole HTML document in a link
    if attribute == "href" and lowered.startswith("data:"):
        return None
    if tag == "input" and attribute == "type" and lowered not in _ALLOWED_INPUT_TYPES:
        return None
    return value


def sanitize_html(html: str) -> str:
    """Remove scripts, event handlers, and other active content from ``html``.

    Example:
        >>> sanitize_html('<p onclick="x()">Hi<script>alert(1)</script></p>')
        '<p>Hi</p>'
    """
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        clean_content_tags={"script", "style"},
        attributes={
            "*": _GENERIC_ATTRIBUTES,
            **_TAG_ATTRIBUTES,
        },
        attribute_filter=_filter_attribute,
        url_schemes=_URL_SCHEMES,
        filter_style_properties=_ALLOWED_STYLE_PROPERTIES,
        link_rel=None,
        strip_comments=True,
    )


_BOOL_ENV = {"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False}


def should_sanitize(
    *,
    cli_override: bool | None,
    untrusted_source: bool,
    config_value: bool,
) -> bool:
    """Decide whether page HTML is sanitized.

    Precedence: ``--sanitize-html/--no-sanitize-html`` flag, then the
    ``LEAFPRESS_SANITIZE_HTML`` env var, then *always on* for untrusted
    (cloned) sources, then ``sanitize_html`` from leafpress.yml. A cloned
    repo's own leafpress.yml therefore can't turn sanitizing off.

    Args:
        cli_override: Value of the CLI flag, or None if not given.
        untrusted_source: True for content cloned from a git URL.
        config_value: ``sanitize_html`` from leafpress.yml (False if unset).
    """
    if cli_override is not None:
        return cli_override
    env = _BOOL_ENV.get(os.environ.get("LEAFPRESS_SANITIZE_HTML", "").strip().lower())
    if env is not None:
        return env
    return untrusted_source or config_value
