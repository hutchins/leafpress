"""Custom exception hierarchy for leafpress."""


class LeafpressError(Exception):
    """Base exception for all leafpress errors."""


class SourceError(LeafpressError):
    """Error resolving input source (clone failure, dir not found)."""


class ConfigError(LeafpressError):
    """Error loading or validating configuration."""


class RenderError(LeafpressError):
    """Error during Markdown/HTML/PDF/DOCX rendering."""


class GitInfoError(LeafpressError):
    """Error extracting git information."""


class DiagramError(LeafpressError):
    """Error fetching or exporting diagrams."""


class DocxImportError(LeafpressError):
    """Error during DOCX-to-Markdown import."""
