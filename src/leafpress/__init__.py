"""leafpress - Convert MkDocs sites to PDF, Word, HTML, ODT, and EPUB documents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("leafpress")
except PackageNotFoundError:
    __version__ = "0.0.0"
