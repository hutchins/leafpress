"""Security tests for downloads, diagram fetching, credential redaction, and imports."""

from __future__ import annotations

import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from leafpress.config import DiagramsConfig, DiagramSource
from leafpress.downloads import DownloadError, download
from leafpress.exceptions import DiagramError, SourceError
from leafpress.source import redact_url


class _Resp:
    """Streaming response stand-in for requests.get(..., stream=True)."""

    def __init__(
        self,
        body: bytes = b"data",
        status: int = 200,
        headers: dict[str, str] | None = None,
        location: str | None = None,
    ) -> None:
        self._body = body
        self.status_code = status
        self.headers = dict(headers or {})
        if location:
            self.headers["Location"] = location
        self.is_redirect = location is not None

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, chunk_size: int = 1) -> list[bytes]:
        return [self._body[i : i + 1000] for i in range(0, len(self._body), 1000)] or [b""]


def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(host: str, *args: object) -> list[tuple[object, ...]]:
        ip = "169.254.169.254" if host == "metadata.internal" else "93.184.216.34"
        return [(0, 0, 0, "", (ip, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


class TestDownload:
    def test_returns_body_and_headers(self) -> None:
        with patch("leafpress.downloads.requests.get", return_value=_Resp(b"abc")):
            body, _ = download("https://example.com/x", max_bytes=10)
        assert body == b"abc"

    def test_rejects_non_http_schemes(self) -> None:
        for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://x"):
            with pytest.raises(DownloadError, match="http"):
                download(url, max_bytes=10)

    def test_streamed_body_over_cap_rejected(self) -> None:
        with (
            patch("leafpress.downloads.requests.get", return_value=_Resp(b"x" * 5000)),
            pytest.raises(DownloadError, match="too large"),
        ):
            download("https://example.com/big", max_bytes=4096)

    def test_declared_content_length_over_cap_rejected(self) -> None:
        resp = _Resp(b"x", headers={"Content-Length": "999999999"})
        with (
            patch("leafpress.downloads.requests.get", return_value=resp),
            pytest.raises(DownloadError, match="too large"),
        ):
            download("https://example.com/big", max_bytes=1024)

    def test_redirects_are_followed_and_revalidated(self) -> None:
        responses = [_Resp(location="file:///etc/passwd")]
        with (
            patch("leafpress.downloads.requests.get", side_effect=responses),
            pytest.raises(DownloadError, match="http"),
        ):
            download("https://example.com/x", max_bytes=10)

    def test_relative_redirect_followed(self) -> None:
        responses = [_Resp(location="/final"), _Resp(b"ok")]
        with patch("leafpress.downloads.requests.get", side_effect=responses) as get:
            body, _ = download("https://example.com/start", max_bytes=10)
        assert body == b"ok"
        assert get.call_args.args[0] == "https://example.com/final"

    def test_too_many_redirects(self) -> None:
        with (
            patch(
                "leafpress.downloads.requests.get",
                side_effect=lambda *a, **k: _Resp(location="https://example.com/loop"),
            ),
            pytest.raises(DownloadError, match="redirects"),
        ):
            download("https://example.com/loop", max_bytes=10)

    def test_require_public_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _public_dns(monkeypatch)
        with pytest.raises(DownloadError, match="non-public"):
            download("http://metadata.internal/", max_bytes=10, require_public_host=True)

    def test_redirect_to_internal_host_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _public_dns(monkeypatch)
        with (
            patch(
                "leafpress.downloads.requests.get",
                return_value=_Resp(location="http://metadata.internal/latest"),
            ),
            pytest.raises(DownloadError, match="non-public"),
        ):
            download("https://example.com/logo.png", max_bytes=10, require_public_host=True)


class TestDiagramFetching:
    def test_dest_outside_project_rejected(self, tmp_path: Path) -> None:
        from leafpress.diagrams import fetch_diagrams

        for dest in ("../../.bashrc", "/tmp/evil.png"):
            cfg = DiagramsConfig(
                sources=[DiagramSource(url="https://example.com/a.png", dest=dest)]
            )
            with (
                patch("leafpress.diagrams.fetch_url") as fetch,
                pytest.raises(DiagramError, match="inside the project"),
            ):
                fetch_diagrams(cfg, tmp_path / "project")
            fetch.assert_not_called()

    def test_dest_inside_project_allowed(self, tmp_path: Path) -> None:
        from leafpress.diagrams import fetch_diagrams

        cfg = DiagramsConfig(
            sources=[DiagramSource(url="https://example.com/a.png", dest="docs/img/a.png")]
        )
        with patch("leafpress.diagrams.fetch_url") as fetch:
            result = fetch_diagrams(cfg, tmp_path, refresh=True)
        fetch.assert_called_once()
        assert result == [tmp_path / "docs/img/a.png"]

    def test_lucidchart_id_validated(self, tmp_path: Path) -> None:
        from leafpress.diagrams import fetch_lucidchart

        for bad in ("../../users/me", "abc?x=1", "a/b"):
            with pytest.raises(DiagramError, match="Invalid Lucidchart"):
                fetch_lucidchart(bad, tmp_path / "x.png", "token")


class TestCredentialRedaction:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("https://user:ghp_secret@github.com/o/r.git", "https://***@github.com/o/r.git"),
            ("https://ghp_secret@github.com/o/r", "https://***@github.com/o/r"),
            ("https://github.com/o/r", "https://github.com/o/r"),
            ("git@github.com:o/r.git", "git@github.com:o/r.git"),
            (
                "Cmd('git') failed: git clone https://x:tok@h/r /tmp/y",
                "Cmd('git') failed: git clone https://***@h/r /tmp/y",
            ),
        ],
    )
    def test_redact_url(self, raw: str, expected: str) -> None:
        assert redact_url(raw) == expected

    def test_clone_failure_does_not_leak_token(self) -> None:
        from leafpress.source import _clone_repo

        url = "https://user:ghp_SUPERSECRET@example.invalid/o/r.git"
        err = RuntimeError(f"git clone {url} failed")
        with (
            patch("leafpress.source.Repo.clone_from", side_effect=err),
            pytest.raises(SourceError) as exc_info,
        ):
            _clone_repo(url, None)
        assert "ghp_SUPERSECRET" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None


class TestTexImageConfinement:
    def test_includegraphics_outside_tex_dir_skipped(self, tmp_path: Path) -> None:
        from leafpress.importer.converter_tex import _TexToMarkdownConverter
        from leafpress.importer.image_handler import ImageHandler

        secret = tmp_path / "secret.png"
        secret.write_bytes(b"\x89PNG secret")
        tex_dir = tmp_path / "paper"
        tex_dir.mkdir()
        assets = tmp_path / "out" / "assets"
        conv = _TexToMarkdownConverter(tex_dir=tex_dir, image_handler=ImageHandler(assets))

        conv.convert(f"\\includegraphics{{{secret}}}\n\\includegraphics{{../secret.png}}")

        assert not assets.exists() or not any(assets.iterdir())

    def test_includegraphics_inside_tex_dir_copied(self, tmp_path: Path) -> None:
        from leafpress.importer.converter_tex import _TexToMarkdownConverter
        from leafpress.importer.image_handler import ImageHandler

        tex_dir = tmp_path / "paper"
        (tex_dir / "figs").mkdir(parents=True)
        (tex_dir / "figs" / "plot.png").write_bytes(b"\x89PNG ok")
        assets = tmp_path / "out" / "assets"
        conv = _TexToMarkdownConverter(tex_dir=tex_dir, image_handler=ImageHandler(assets))

        conv.convert("\\includegraphics{figs/plot}")

        assert len(list(assets.iterdir())) == 1


class TestOpenFile:
    def test_windows_uses_startfile_not_shell(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os
        import sys

        from leafpress.cli import _files as cli_files

        startfile = MagicMock()
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(os, "startfile", startfile, raising=False)
        with patch("leafpress.cli._files.subprocess.run") as run:
            cli_files._open_file(tmp_path / "a & calc.pdf")
        startfile.assert_called_once_with(tmp_path / "a & calc.pdf")
        run.assert_not_called()
