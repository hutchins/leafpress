"""Tests for leafpress package __init__.py."""

import leafpress


def test_version_is_string() -> None:
    assert isinstance(leafpress.__version__, str)
    assert leafpress.__version__ != ""


def test_version_not_fallback() -> None:
    """Installed package should have a real version, not the fallback."""
    assert leafpress.__version__ != "0.0.0"


def test_convert_importable() -> None:
    """The convert function is importable from the pipeline module."""
    from leafpress.pipeline import convert

    assert callable(convert)
