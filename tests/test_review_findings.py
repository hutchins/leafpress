"""Regression tests for issues found in the 0.8.3 stack code review."""

from __future__ import annotations

import base64
import logging
import re
import socket
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from leafpress.exceptions import SourceError
from leafpress.pipeline import convert
from tests.helpers import make_png

SECRET = "REVIEW-SECRET-4410"
PNG = make_png()


class _Clone:
    """Stand-in for a cloned (untrusted) source that isn't deleted on exit."""

    is_temporary = True

    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *args: object) -> None:
        pass


def _embedded_payloads(html: str) -> list[str]:
    return [
        base64.b64decode(m).decode("utf-8", "replace")
        for m in re.findall(r"data:[^;\"]+;base64,([A-Za-z0-9+/=]+)", html)
    ]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "secret.txt").write_text(SECRET)
    proj = tmp_path / "repo"
    (proj / "docs").mkdir(parents=True)
    (proj / "mkdocs.yml").write_text("site_name: R\n")
    (proj / "docs" / "index.md").write_text("# Hi\n")
    return proj


# ---------------------------------------------------------------------------
# 1. logo_path from an untrusted repo config
# ---------------------------------------------------------------------------


class TestUntrustedLogo:
    def _convert_clone(self, repo: Path, out: Path) -> str:
        from leafpress import pipeline

        with patch.object(pipeline, "resolve_source", return_value=_Clone(repo)):
            convert("https://example.com/r.git", out, format="html", mermaid=False)
        return next(out.glob("*.html")).read_text()

    def test_logo_outside_clone_is_ignored(
        self, repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LEAFPRESS_LOGO_PATH", raising=False)
        (repo / "leafpress.yml").write_text(
            f"company_name: A\nproject_name: B\nlogo_path: {tmp_path / 'secret.txt'}\n"
        )
        html = self._convert_clone(repo, tmp_path / "out")
        assert not any(SECRET in p for p in _embedded_payloads(html))

    def test_non_image_logo_inside_clone_not_embedded(
        self, repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LEAFPRESS_LOGO_PATH", raising=False)
        (repo / "notes.png").write_text(SECRET)  # not actually an image
        (repo / "leafpress.yml").write_text(
            "company_name: A\nproject_name: B\nlogo_path: notes.png\n"
        )
        html = self._convert_clone(repo, tmp_path / "out")
        assert not any(SECRET in p for p in _embedded_payloads(html))

    def test_real_logo_inside_clone_still_embedded(
        self, repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LEAFPRESS_LOGO_PATH", raising=False)
        (repo / "logo.png").write_bytes(PNG)
        (repo / "leafpress.yml").write_text(
            "company_name: A\nproject_name: B\nlogo_path: logo.png\n"
        )
        html = self._convert_clone(repo, tmp_path / "out")
        assert base64.b64encode(PNG).decode() in html

    def test_operator_logo_outside_clone_kept(
        self, repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        logo = tmp_path / "brand.png"
        logo.write_bytes(PNG)
        monkeypatch.setenv("LEAFPRESS_LOGO_PATH", str(logo))
        (repo / "leafpress.yml").write_text("company_name: A\nproject_name: B\n")
        html = self._convert_clone(repo, tmp_path / "out")
        assert base64.b64encode(PNG).decode() in html

    def test_asset_policy_rejects_non_image_logo(self, tmp_path: Path) -> None:
        from leafpress.base_renderer import build_asset_policy
        from leafpress.config import BrandingConfig
        from leafpress.mkdocs_parser import MkDocsConfig

        fake = tmp_path / "key.png"
        fake.write_text("-----BEGIN PRIVATE KEY-----")
        branding = BrandingConfig(company_name="A", project_name="B", logo_path=str(fake))
        cfg = MkDocsConfig("x", tmp_path / "p" / "docs", [], [], None, [], tmp_path / "p" / "m.yml")
        assert not build_asset_policy(cfg, branding).allows(fake)


# ---------------------------------------------------------------------------
# 2. Credentials on cross-origin redirects
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, body: bytes = b"ok", location: str | None = None) -> None:
        self._body = body
        self.status_code = 302 if location else 200
        self.headers = {"Location": location} if location else {}
        self.is_redirect = location is not None

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        pass

    def raise_for_status(self) -> None:
        pass

    def iter_content(self, chunk_size: int = 1) -> list[bytes]:
        return [self._body]


@pytest.mark.parametrize(
    ("first", "redirect", "keeps_auth"),
    [
        ("https://api.lucid.co/doc", "https://s3.amazonaws.com/signed", False),
        ("https://api.lucid.co/doc", "/documents/2", True),  # same origin
        ("https://api.lucid.co/doc", "http://api.lucid.co/doc", False),  # downgrade
    ],
)
def test_credentials_not_forwarded_cross_origin(
    first: str, redirect: str, keeps_auth: bool
) -> None:
    from leafpress.downloads import download

    responses = [_Resp(location=redirect), _Resp(b"PNG")]
    with patch("leafpress.downloads.requests.get", side_effect=responses) as get:
        download(first, max_bytes=100, headers={"Authorization": "Bearer t", "Accept": "x"})
    second_headers = get.call_args_list[1].kwargs["headers"]
    assert ("Authorization" in second_headers) is keeps_auth
    assert second_headers["Accept"] == "x"


# ---------------------------------------------------------------------------
# 3. Log handler cleanup when the source can't be resolved
# ---------------------------------------------------------------------------


def test_failed_source_resolution_detaches_log_handler(tmp_path: Path) -> None:
    logger = logging.getLogger("leafpress")
    before = list(logger.handlers)
    level = logger.level
    for _ in range(3):
        with pytest.raises(SourceError):
            convert(str(tmp_path / "missing"), tmp_path / "out", format="html")
    assert logger.handlers == before
    assert logger.level == level


# ---------------------------------------------------------------------------
# 4. Images from monorepo url: projects survive until rendering
# ---------------------------------------------------------------------------


def test_monorepo_url_project_images_embedded(tmp_path: Path) -> None:
    from leafpress import pipeline
    from leafpress.source import ResolvedSource

    top = tmp_path / "top"
    top.mkdir()
    (top / "leafpress.yml").write_text(
        "company_name: A\nproject_name: Mono\nprojects:\n  - url: https://example.com/sub.git\n"
    )
    clone = Path(tempfile.mkdtemp(prefix="leafpress_test_clone_"))
    (clone / "docs").mkdir()
    (clone / "mkdocs.yml").write_text("site_name: Sub\n")
    (clone / "docs" / "index.md").write_text("# Sub\n\n![pic](pic.png)\n")
    (clone / "docs" / "pic.png").write_bytes(PNG)

    real_resolve = pipeline.resolve_source

    def resolve(source: str, branch: str | None = None) -> ResolvedSource:
        if source.startswith("https://"):
            return ResolvedSource(clone, is_temporary=True)  # really deleted on exit
        return real_resolve(source, branch)

    out = tmp_path / "out"
    with patch.object(pipeline, "resolve_source", side_effect=resolve):
        convert(str(top), out, format="docx", mermaid=False)
    with zipfile.ZipFile(next(out.glob("*.docx"))) as z:
        assert any(n.startswith("word/media/") for n in z.namelist())
    assert not clone.exists()  # still cleaned up afterwards


# ---------------------------------------------------------------------------
# 5. Images elsewhere in a trusted local source
# ---------------------------------------------------------------------------


def test_local_image_outside_mkdocs_dir_but_inside_source(tmp_path: Path) -> None:
    from leafpress.markdown_renderer import MarkdownRenderer

    repo = tmp_path / "repo"
    (repo / "shared").mkdir(parents=True)
    (repo / "shared" / "logo.png").write_bytes(PNG)
    proj = repo / "projects" / "api"
    (proj / "docs").mkdir(parents=True)
    page = proj / "docs" / "index.md"
    md = "![l](../../../shared/logo.png)\n\n![s](../../../../secret.png)\n"

    confined = MarkdownRenderer([], proj / "docs", project_root=proj)
    html, _ = confined.render(md, page)
    assert 'src=""' in html  # without the source root, both are blocked

    renderer = MarkdownRenderer([], proj / "docs", project_root=proj, asset_roots=[repo])
    html, _ = renderer.render(md, page)
    assert (repo / "shared" / "logo.png").resolve().as_uri() in html
    assert html.count('src=""') == 1  # the one outside the repo stays blocked


# ---------------------------------------------------------------------------
# 6. mermaid.server from an untrusted repo config must be public
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cloned", "env_server", "expected"),
    [(True, None, True), (True, "http://10.0.0.5:8080", False), (False, None, False)],
)
def test_mermaid_server_public_only_for_untrusted_config(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cloned: bool,
    env_server: str | None,
    expected: bool,
) -> None:
    from leafpress import pipeline

    if env_server:
        monkeypatch.setenv("LEAFPRESS_MERMAID_SERVER", env_server)
    else:
        monkeypatch.delenv("LEAFPRESS_MERMAID_SERVER", raising=False)
    (repo / "mkdocs.yml").write_text(
        "site_name: R\nmarkdown_extensions:\n  - pymdownx.superfences\n"
    )
    (repo / "leafpress.yml").write_text(
        "company_name: A\nproject_name: B\nmermaid:\n  server: http://10.0.0.5:8080\n"
    )
    (repo / "docs" / "index.md").write_text("```mermaid\ngraph TD\n  A-->B\n```\n")
    src = _Clone(repo) if cloned else pipeline.resolve_source(str(repo))
    with (
        patch.object(pipeline, "resolve_source", return_value=src),
        patch(
            "leafpress.mermaid.download", return_value=(PNG, {"Content-Type": "image/png"})
        ) as dl,
    ):
        convert("https://example.com/r.git" if cloned else str(repo), tmp_path / "o", format="html")
    assert dl.call_args.kwargs["require_public_host"] is expected


# ---------------------------------------------------------------------------
# 7. SVG images in ODT
# ---------------------------------------------------------------------------


def test_odt_embeds_svg_with_viewbox_size(tmp_path: Path) -> None:
    from leafpress.mkdocs_parser import MkDocsConfig, NavItem
    from leafpress.odt.renderer import OdtRenderer

    (tmp_path / "docs").mkdir()
    svg = tmp_path / "docs" / "arch.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200"><rect/></svg>')
    cfg = MkDocsConfig("T", tmp_path / "docs", [], [], None, [], tmp_path / "mkdocs.yml")
    html = f'<p><img alt="a" src="{svg.resolve().as_uri()}"></p>'
    out = tmp_path / "o.odt"
    OdtRenderer(None, None, cfg).render(
        [(NavItem(title="P", path=Path("index.md")), html)], out, cover_page=False
    )
    with zipfile.ZipFile(out) as z:
        assert any(n.startswith("Pictures/") and n.endswith(".svg") for n in z.namelist())
        content = z.read("content.xml").decode()
    assert 'svg:width="4.17in"' in content and 'svg:height="2.08in"' in content


# ---------------------------------------------------------------------------
# 9. IPv4 tunnelled in IPv6
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "addr",
    ["64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe", "::ffff:10.0.0.1", "2002:a9fe:a9fe::1"],
)
def test_ipv6_wrapped_internal_addresses_not_public(
    addr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from leafpress.asset_policy import is_public_host

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a: [(0, 0, 0, "", (addr, 0))])
    assert not is_public_host("wrapped.example")


def test_public_ipv6_still_public(monkeypatch: pytest.MonkeyPatch) -> None:
    from leafpress.asset_policy import is_public_host

    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a: [(0, 0, 0, "", ("2001:4860:4860::8888", 0))]
    )
    assert is_public_host("dns.example")


# ---------------------------------------------------------------------------
# 10. One shared open-file helper
# ---------------------------------------------------------------------------


def test_cli_and_ui_share_open_file() -> None:
    import importlib

    from leafpress import opener

    convert_cmd = importlib.import_module("leafpress.cli.convert")

    assert convert_cmd.open_file is opener.open_file
    ui = pytest.importorskip("leafpress.ui.app", exc_type=ImportError)
    assert ui.open_file is opener.open_file


def test_env_bool_shared() -> None:
    import os

    from leafpress.config import env_bool

    os.environ["LEAFPRESS_TEST_BOOL"] = " Yes "
    try:
        assert env_bool("LEAFPRESS_TEST_BOOL") is True
    finally:
        del os.environ["LEAFPRESS_TEST_BOOL"]
    assert env_bool("LEAFPRESS_TEST_BOOL") is None


# ---------------------------------------------------------------------------
# 1b. Non-image files inside the project are never embedded
# ---------------------------------------------------------------------------


def test_project_env_file_not_embedded_via_img_or_attachment(repo: Path, tmp_path: Path) -> None:
    """A CI checkout's .env (operator secrets) must not be pulled in by page content."""
    (repo / ".env").write_text(f"LEAFPRESS_LUCIDCHART_TOKEN={SECRET}\n")
    env_uri = (repo / ".env").resolve().as_uri()
    (repo / "docs" / "index.md").write_text(
        f'# Hi\n\n<img src="../.env">\n\n<img src="{env_uri}">\n\n'
        f'<a rel="attachment" href="{env_uri}">a</a>\n'
    )
    try:
        import weasyprint  # noqa: F401

        fmt = "all"
    except (ImportError, OSError):
        fmt = "html"
    out = tmp_path / "out"
    convert(str(repo), out, format=fmt, mermaid=False)
    html = next(out.glob("*.html")).read_text()
    assert not any(SECRET in p for p in _embedded_payloads(html))
    for pdf in out.glob("*.pdf"):
        assert b"/EmbeddedFile" not in pdf.read_bytes()
