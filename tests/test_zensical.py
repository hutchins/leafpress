"""Tests for experimental zensical.toml support."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from leafpress.cli import cli
from leafpress.exceptions import ConfigError
from leafpress.mkdocs_parser import find_site_config, flatten_nav, parse_mkdocs_config
from leafpress.zensical_parser import flatten_markdown_extensions, load_zensical_project

ZENSICAL_TOML = """\
[project]
site_name = "Zen Docs"
docs_dir = "content"
nav = [
  { "Home" = "index.md" },
  { "Guide" = [
    "guide/setup.md",
    { "Usage" = "guide/usage.md" },
  ] },
  { "Book" = "https://book.example.com" },
]

[project.theme]
variant = "classic"

[project.markdown_extensions.admonition]
[project.markdown_extensions.toc]
permalink = true
[project.markdown_extensions.pymdownx.details]
[project.markdown_extensions.pymdownx.emoji]
emoji_index = "zensical.extensions.emoji.twemoji"
emoji_generator = "zensical.extensions.emoji.to_svg"
[project.markdown_extensions.pymdownx.superfences]
custom_fences = [
  { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" },
]
[project.markdown_extensions.footnotes]
"""


@pytest.fixture
def zen_project(tmp_path: Path) -> Path:
    proj = tmp_path / "zen"
    (proj / "content" / "guide").mkdir(parents=True)
    (proj / "zensical.toml").write_text(ZENSICAL_TOML)
    (proj / "content" / "index.md").write_text("# Home\n\n!!! note\n    Admonition body\n")
    (proj / "content" / "guide" / "setup.md").write_text("# Setup\n\nSetup text[^1]\n\n[^1]: fn\n")
    (proj / "content" / "guide" / "usage.md").write_text("# Usage\n\nUsage text\n")
    return proj


class TestFlattenExtensions:
    def test_namespaces_nested_and_config(self) -> None:
        entries = flatten_markdown_extensions(
            {
                "admonition": {},
                "toc": {"permalink": True},
                "pymdownx": {"details": {}, "blocks": {"caption": {}}},
                "markdown": {"extensions": {"tables": {}}},
            }
        )
        assert entries == [
            "admonition",
            {"toc": {"permalink": True}},
            "pymdownx.details",
            "pymdownx.blocks.caption",
            "markdown.extensions.tables",
        ]

    def test_disabled_extension_skipped(self) -> None:
        assert flatten_markdown_extensions({"abbr": False, "toc": {}}) == ["toc"]

    def test_callable_name_strings_dropped(self) -> None:
        entries = flatten_markdown_extensions(
            {
                "pymdownx": {
                    "emoji": {"emoji_index": "x.y", "options": {"a": 1}},
                    "superfences": {
                        "custom_fences": [{"name": "mermaid", "class": "mermaid", "format": "x.y"}]
                    },
                }
            }
        )
        assert entries == [
            {"pymdownx.emoji": {"options": {"a": 1}}},
            {"pymdownx.superfences": {"custom_fences": [{"name": "mermaid", "class": "mermaid"}]}},
        ]

    def test_unknown_extension_with_table_config_is_not_a_namespace(self) -> None:
        entries = flatten_markdown_extensions({"no_such_ext_xyz": {"opts": {"a": 1}}})
        assert entries == [{"no_such_ext_xyz": {"opts": {"a": 1}}}]


class TestLoadProject:
    def test_requires_project_table(self, tmp_path: Path) -> None:
        cfg = tmp_path / "zensical.toml"
        cfg.write_text('site_name = "x"\n')
        with pytest.raises(ConfigError, match=r"\[project\]"):
            load_zensical_project(cfg)

    def test_invalid_toml(self, tmp_path: Path) -> None:
        cfg = tmp_path / "zensical.toml"
        cfg.write_text("[project\n")
        with pytest.raises(ConfigError, match="Invalid TOML"):
            load_zensical_project(cfg)

    def test_toml_1_1_multiline_inline_tables(self, tmp_path: Path) -> None:
        """Real configs (e.g. pixi) use TOML 1.1 syntax that stdlib tomllib rejects."""
        cfg = tmp_path / "zensical.toml"
        cfg.write_text(
            '[project]\nsite_name = "x"\nnav = [\n  {\n    "Guide" = [\n'
            '      { "A" = "a.md" },\n    ],\n  },\n]\n'
        )
        assert load_zensical_project(cfg)["nav"] == [{"Guide": [{"A": "a.md"}]}]


class TestParseConfig:
    def test_fields_mapped(self, zen_project: Path) -> None:
        cfg = parse_mkdocs_config(zen_project / "zensical.toml")
        assert cfg.site_name == "Zen Docs"
        assert cfg.docs_dir == (zen_project / "content").resolve()
        pages = [str(p.path) for p in flatten_nav(cfg.nav_items) if p.path]
        # External link entries have no page and are skipped
        assert pages == ["index.md", "guide/setup.md", "guide/usage.md"]
        names = [e if isinstance(e, str) else next(iter(e)) for e in cfg.markdown_extensions]
        assert names == [
            "admonition",
            "toc",
            "pymdownx.details",
            "pymdownx.emoji",
            "pymdownx.superfences",
            "footnotes",
        ]

    def test_docs_dir_confined(self, tmp_path: Path) -> None:
        (tmp_path / "outside").mkdir()
        proj = tmp_path / "p"
        proj.mkdir()
        (proj / "zensical.toml").write_text('[project]\nsite_name = "x"\ndocs_dir = "../outside"\n')
        with pytest.raises(ConfigError, match="inside the project"):
            parse_mkdocs_config(proj / "zensical.toml")

    def test_mkdocs_yml_url_nav_entries_skipped_too(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "mkdocs.yml").write_text(
            "site_name: x\nnav:\n  - index.md\n  - Book: https://book.example.com\n"
            "  - mailto:me@example.com\n"
        )
        cfg = parse_mkdocs_config(tmp_path / "mkdocs.yml")
        assert [str(p.path) for p in cfg.nav_items] == ["index.md"]


class TestDiscovery:
    def test_find_site_config_order(self, tmp_path: Path) -> None:
        assert find_site_config(tmp_path) is None
        (tmp_path / "zensical.toml").write_text("[project]\n")
        assert find_site_config(tmp_path) == tmp_path / "zensical.toml"
        (tmp_path / "mkdocs.yml").write_text("site_name: x\n")
        assert find_site_config(tmp_path) == tmp_path / "mkdocs.yml"

    def test_detect_project_finds_zensical_only(
        self, zen_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from leafpress.project import detect_project

        monkeypatch.chdir(zen_project)
        assert detect_project() == zen_project.resolve()


class TestEndToEnd:
    def test_convert_zensical_project(
        self, zen_project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from leafpress.pipeline import convert

        out = tmp_path / "out"
        convert(str(zen_project), out, format="html", mermaid=False)
        html = next(out.glob("*.html")).read_text()
        assert "Admonition body" in html and 'class="admonition note"' in html
        assert "Setup text" in html and "Usage text" in html
        assert "footnote" in html
        assert "experimental Zensical support" in capsys.readouterr().out

    def test_mkdocs_yml_wins_when_both_exist(
        self, zen_project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from leafpress.pipeline import convert

        (zen_project / "docs").mkdir()
        (zen_project / "docs" / "index.md").write_text("# From mkdocs\n\nMKDOCS-PAGE\n")
        (zen_project / "mkdocs.yml").write_text("site_name: From MkDocs\n")
        out = tmp_path / "out"
        convert(str(zen_project), out, format="markdown", mermaid=False)
        text = next(out.glob("*.md")).read_text()
        assert "MKDOCS-PAGE" in text
        assert "using mkdocs.yml" in " ".join(capsys.readouterr().out.split())

    def test_explicit_zensical_config_overrides(self, zen_project: Path, tmp_path: Path) -> None:
        from leafpress.pipeline import convert

        (zen_project / "docs").mkdir()
        (zen_project / "mkdocs.yml").write_text("site_name: From MkDocs\n")
        out = tmp_path / "out"
        convert(
            str(zen_project),
            out,
            format="markdown",
            mkdocs_config_path=zen_project / "zensical.toml",
            mermaid=False,
        )
        assert "Usage text" in next(out.glob("*.md")).read_text()

    def test_info_command(self, zen_project: Path) -> None:
        result = CliRunner().invoke(cli, ["info", str(zen_project)])
        assert result.exit_code == 0, result.output
        assert "Zen Docs" in result.output
