"""Tests for __main__.py entry point."""

import runpy
from unittest.mock import patch

import pytest


def test_main_invocation() -> None:
    """python -m leafpress calls the CLI and exits."""
    with patch("sys.argv", ["leafpress", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("leafpress", run_name="__main__")
    assert exc_info.value.code == 0
