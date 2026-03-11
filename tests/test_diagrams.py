"""Tests for diagrams fetch module."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from leafpress.config import DiagramsConfig, DiagramSource
from leafpress.diagrams import (
    _is_stale,
    _resolve_lucidchart_token,
    fetch_diagrams,
    fetch_lucidchart,
    fetch_url,
)
from leafpress.exceptions import DiagramError

# --- Config model tests ---


class TestDiagramSource:
    def test_url_source(self) -> None:
        src = DiagramSource(url="https://example.com/img.png", dest="out/img.png")
        assert src.url == "https://example.com/img.png"
        assert src.lucidchart is None

    def test_lucidchart_source(self) -> None:
        src = DiagramSource(lucidchart="abc123", dest="out/diagram.png")
        assert src.lucidchart == "abc123"
        assert src.url is None
        assert src.page == 1

    def test_lucidchart_custom_page(self) -> None:
        src = DiagramSource(lucidchart="abc123", dest="out/diagram.png", page=3)
        assert src.page == 3

    def test_empty_dest_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DiagramSource(url="https://example.com/img.png", dest="  ")

    def test_page_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            DiagramSource(lucidchart="abc", dest="out.png", page=0)


class TestDiagramsConfig:
    def test_defaults(self) -> None:
        cfg = DiagramsConfig()
        assert cfg.lucidchart_token is None
        assert cfg.cache_max_age == 3600
        assert cfg.sources == []

    def test_from_dict(self) -> None:
        cfg = DiagramsConfig(
            cache_max_age=0,
            sources=[
                DiagramSource(url="https://example.com/a.svg", dest="a.svg"),
            ],
        )
        assert cfg.cache_max_age == 0
        assert len(cfg.sources) == 1


# --- Cache staleness tests ---


class TestIsStale:
    def test_missing_file_is_stale(self, tmp_path: Path) -> None:
        assert _is_stale(tmp_path / "nonexistent.png", 3600) is True

    def test_zero_max_age_always_stale(self, tmp_path: Path) -> None:
        f = tmp_path / "file.png"
        f.write_bytes(b"data")
        assert _is_stale(f, 0) is True

    def test_fresh_file_not_stale(self, tmp_path: Path) -> None:
        f = tmp_path / "file.png"
        f.write_bytes(b"data")
        assert _is_stale(f, 3600) is False

    def test_old_file_is_stale(self, tmp_path: Path) -> None:
        f = tmp_path / "file.png"
        f.write_bytes(b"data")
        old_time = time.time() - 7200
        import os

        os.utime(f, (old_time, old_time))
        assert _is_stale(f, 3600) is True


# --- Token resolution tests ---


class TestResolveToken:
    def test_from_config(self) -> None:
        cfg = DiagramsConfig(lucidchart_token="tok123")
        assert _resolve_lucidchart_token(cfg) == "tok123"

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LEAFPRESS_LUCIDCHART_TOKEN", "envtok")
        cfg = DiagramsConfig()
        assert _resolve_lucidchart_token(cfg) == "envtok"

    def test_missing_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LEAFPRESS_LUCIDCHART_TOKEN", raising=False)
        cfg = DiagramsConfig()
        with pytest.raises(DiagramError, match="token required"):
            _resolve_lucidchart_token(cfg)


# --- fetch_url tests ---


class TestFetchUrl:
    @patch("leafpress.diagrams.requests.get")
    def test_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"PNG_DATA"]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        dest = tmp_path / "subdir" / "diagram.png"
        result = fetch_url("https://example.com/diagram.png", dest)

        assert result == dest
        assert dest.read_bytes() == b"PNG_DATA"
        mock_get.assert_called_once_with("https://example.com/diagram.png", stream=True, timeout=30)

    @patch("leafpress.diagrams.requests.get")
    def test_http_error(self, mock_get: MagicMock, tmp_path: Path) -> None:
        import requests

        mock_get.side_effect = requests.ConnectionError("refused")

        with pytest.raises(DiagramError, match="Failed to download"):
            fetch_url("https://example.com/bad.png", tmp_path / "out.png")


# --- fetch_lucidchart tests ---


class TestFetchLucidchart:
    @patch("leafpress.diagrams.requests.get")
    def test_success(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "image/png"}
        mock_resp.content = b"PNG_IMAGE_DATA"
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        dest = tmp_path / "lucid.png"
        result = fetch_lucidchart("doc123", dest, "mytoken", page=2)

        assert result == dest
        assert dest.read_bytes() == b"PNG_IMAGE_DATA"
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer mytoken"
        assert call_kwargs.kwargs["headers"]["Accept"] == "image/png"
        assert call_kwargs.kwargs["params"]["pageIndex"] == 1  # 0-based

    @patch("leafpress.diagrams.requests.get")
    def test_bad_content_type(self, mock_get: MagicMock, tmp_path: Path) -> None:
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        with pytest.raises(DiagramError, match="unexpected content type"):
            fetch_lucidchart("doc123", tmp_path / "out.png", "tok")

    @patch("leafpress.diagrams.requests.get")
    def test_auth_error(self, mock_get: MagicMock, tmp_path: Path) -> None:
        import requests

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        mock_get.return_value = mock_resp

        with pytest.raises(DiagramError, match="Failed to export"):
            fetch_lucidchart("doc123", tmp_path / "out.png", "badtok")


# --- Orchestrator tests ---


class TestFetchDiagrams:
    def test_empty_sources(self, tmp_path: Path) -> None:
        cfg = DiagramsConfig()
        result = fetch_diagrams(cfg, tmp_path)
        assert result == []

    @patch("leafpress.diagrams.fetch_url")
    def test_url_source_fetched(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        dest = tmp_path / "img.svg"
        mock_fetch.return_value = dest

        cfg = DiagramsConfig(
            sources=[DiagramSource(url="https://example.com/img.svg", dest="img.svg")]
        )
        result = fetch_diagrams(cfg, tmp_path, refresh=True)

        assert len(result) == 1
        mock_fetch.assert_called_once_with("https://example.com/img.svg", dest)

    @patch("leafpress.diagrams.fetch_url")
    def test_cached_file_skipped(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        dest = tmp_path / "img.svg"
        dest.write_bytes(b"cached")

        cfg = DiagramsConfig(
            sources=[DiagramSource(url="https://example.com/img.svg", dest="img.svg")]
        )
        result = fetch_diagrams(cfg, tmp_path)

        assert len(result) == 1
        mock_fetch.assert_not_called()

    @patch("leafpress.diagrams.fetch_url")
    def test_refresh_overrides_cache(self, mock_fetch: MagicMock, tmp_path: Path) -> None:
        dest = tmp_path / "img.svg"
        dest.write_bytes(b"cached")
        mock_fetch.return_value = dest

        cfg = DiagramsConfig(
            sources=[DiagramSource(url="https://example.com/img.svg", dest="img.svg")]
        )
        result = fetch_diagrams(cfg, tmp_path, refresh=True)

        assert len(result) == 1
        mock_fetch.assert_called_once()

    def test_lucidchart_missing_token(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LEAFPRESS_LUCIDCHART_TOKEN", raising=False)
        cfg = DiagramsConfig(sources=[DiagramSource(lucidchart="doc1", dest="d.png")])
        with pytest.raises(DiagramError, match="token required"):
            fetch_diagrams(cfg, tmp_path, refresh=True)

    @patch("leafpress.diagrams.fetch_lucidchart")
    def test_lucidchart_with_env_token(
        self,
        mock_fetch: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("LEAFPRESS_LUCIDCHART_TOKEN", "envtok")
        dest = tmp_path / "d.png"
        mock_fetch.return_value = dest

        cfg = DiagramsConfig(sources=[DiagramSource(lucidchart="doc1", dest="d.png")])
        result = fetch_diagrams(cfg, tmp_path, refresh=True)

        assert len(result) == 1
        mock_fetch.assert_called_once_with("doc1", dest, "envtok", 1)

    def test_no_source_type_skipped(self, tmp_path: Path) -> None:
        cfg = DiagramsConfig(sources=[DiagramSource(dest="orphan.png")])
        result = fetch_diagrams(cfg, tmp_path, refresh=True)
        assert result == []
