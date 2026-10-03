"""User-friendly messages for output-renderer failures.

One table of (pattern, explanation, hints) per output format replaces a
near-identical ``_format_<fmt>_error`` function per renderer. Anything that
matches no rule gets the generic "run doctor / report it" message.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

ISSUES_URL = "https://github.com/hutchins/leafpress/issues"
_DOCTOR = "Run 'leafpress doctor' to check your environment."


def _mentions_image(name: str, msg: str) -> bool:
    return "image" in msg or "image" in name.lower()


def _unrecognized_image(name: str, msg: str) -> bool:
    return "UnrecognizedImageError" in name or "unrecognized image" in msg


def _template_problem(_name: str, msg: str) -> bool:
    return "template" in msg or "jinja" in msg


def _encoding_problem(_name: str, msg: str) -> bool:
    return "encoding" in msg or "unicode" in msg


@dataclass(frozen=True)
class _Rule:
    """A known failure: ``matches(exc_name, lowercased_message)`` selects it."""

    matches: Callable[[str, str], bool]
    reason: str  # completes "<FMT> rendering failed <reason>."
    hints: tuple[str, ...]


_RULES: dict[str, tuple[_Rule, ...]] = {
    "PDF": (
        _Rule(
            _unrecognized_image,
            "due to an unrecognized image format",
            (
                "This often happens when an SVG image is used but the required",
                "system libraries (librsvg / libcairo) are not installed.",
                _DOCTOR,
                "Tip: Convert SVG images to PNG, or install librsvg:",
                "  macOS:  brew install librsvg",
                "  Ubuntu: sudo apt install librsvg2-dev",
            ),
        ),
        _Rule(
            _mentions_image,
            "due to an image error",
            (
                "Check that all images referenced in your docs exist and are in",
                "a supported format (PNG, JPEG, GIF, or SVG with librsvg).",
                _DOCTOR,
            ),
        ),
    ),
    "DOCX": (
        _Rule(
            _mentions_image,
            "due to an image error",
            (
                "Check that all images are in a supported format (PNG, JPEG).",
                "SVG images are not supported in DOCX output — convert them to PNG first.",
                _DOCTOR,
            ),
        ),
    ),
    "HTML": (
        _Rule(
            _mentions_image,
            "due to an image error",
            ("Check that all referenced images exist and paths are correct.", _DOCTOR),
        ),
        _Rule(
            _template_problem,
            "due to a template error",
            (
                "This may indicate a corrupted installation.",
                "Try reinstalling: pip install --force-reinstall leafpress",
            ),
        ),
    ),
    "ODT": (
        _Rule(
            _mentions_image,
            "due to an image error",
            (
                "Check that all images are in a supported format (PNG, JPEG).",
                "SVG images are not supported in ODT output — convert them to PNG first.",
                _DOCTOR,
            ),
        ),
    ),
    "EPUB": (
        _Rule(
            _mentions_image,
            "due to an image error",
            (
                "Check that all images are in a supported format (PNG, JPEG, GIF).",
                "EPUB requires images to be embedded — ensure files exist on disk.",
                _DOCTOR,
            ),
        ),
        _Rule(
            _encoding_problem,
            "due to an encoding error",
            ("Ensure all Markdown files are saved as UTF-8.",),
        ),
    ),
}


def format_render_error(label: str, exc: Exception) -> str:
    """Explain a renderer failure in terms the user can act on.

    Args:
        label: Output format as shown to the user ("PDF", "DOCX", ...).
        exc: The exception the renderer raised.

    Returns:
        A multi-line message ending with the original exception.
    """
    name = type(exc).__name__
    msg = str(exc)
    for rule in _RULES.get(label, ()):
        if rule.matches(name, msg.lower()):
            lines = [f"{label} rendering failed {rule.reason}."]
            lines += [f"  {hint}" for hint in rule.hints]
            lines.append(f"  Original error: {name}: {msg}")
            return "\n".join(lines)
    return (
        f"{label} rendering failed: {name}: {msg}\n"
        f"  {_DOCTOR}\n"
        f"  If this persists, please report it at {ISSUES_URL}"
    )
