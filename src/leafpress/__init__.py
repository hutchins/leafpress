"""leafpress - Convert MkDocs sites to PDF, Word, HTML, and ODT documents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("leafpress")
except PackageNotFoundError:
    __version__ = "0.0.0"

from leafpress.pipeline import convert  # noqa: F401
