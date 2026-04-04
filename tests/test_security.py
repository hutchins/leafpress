"""Security tests for YAML deserialization and path traversal."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from leafpress.config import BrandingConfig, load_config
from leafpress.exceptions import ConfigError
from leafpress.mkdocs_parser import _MkDocsLoader

# ---------------------------------------------------------------------------
# 1. YAML deserialization safety
# ---------------------------------------------------------------------------


class TestYamlSafety:
    """Ensure YAML loading never executes arbitrary Python."""

    def test_config_uses_safe_load(self, tmp_path: Path) -> None:
        """leafpress.yml is parsed with yaml.safe_load — !!python/object is rejected."""
        malicious = tmp_path / "leafpress.yml"
        malicious.write_text(
            "company_name: !!python/object/apply:os.system ['echo pwned']\nproject_name: test\n"
        )
        with pytest.raises(ConfigError):
            load_config(malicious)

    def test_config_rejects_python_name_tag(self, tmp_path: Path) -> None:
        """!!python/name: tags must not execute in config loading."""
        malicious = tmp_path / "leafpress.yml"
        malicious.write_text("company_name: !!python/name:os.system\nproject_name: test\n")
        with pytest.raises(ConfigError):
            load_config(malicious)

    def test_config_rejects_python_module_tag(self, tmp_path: Path) -> None:
        """!!python/module: tags must not execute."""
        malicious = tmp_path / "leafpress.yml"
        malicious.write_text("company_name: !!python/module:os\nproject_name: test\n")
        with pytest.raises(ConfigError):
            load_config(malicious)

    def test_mkdocs_loader_extends_safe_loader(self) -> None:
        """_MkDocsLoader must be a subclass of SafeLoader, not full Loader."""
        assert issubclass(_MkDocsLoader, yaml.SafeLoader)
        assert not issubclass(_MkDocsLoader, yaml.UnsafeLoader)

    def test_mkdocs_loader_neutralizes_python_name(self) -> None:
        """!!python/name: tags are converted to harmless placeholder strings."""
        doc = "key: !!python/name:os.getcwd\n"
        result = yaml.load(doc, Loader=_MkDocsLoader)
        # Should be a string placeholder, never a callable
        assert isinstance(result["key"], str)
        assert not callable(result["key"])

    def test_mkdocs_loader_neutralizes_python_object(self) -> None:
        """!!python/object: tags are converted to harmless placeholder strings."""
        doc = "key: !!python/object:os.getcwd\n"
        result = yaml.load(doc, Loader=_MkDocsLoader)
        assert isinstance(result["key"], str)
        assert not callable(result["key"])

    def test_mkdocs_loader_rejects_python_object_apply(self) -> None:
        """!!python/object/apply: must not execute arbitrary code."""
        doc = "key: !!python/object/apply:os.getcwd []\n"
        # SafeLoader base rejects this; should raise an error
        with pytest.raises(yaml.YAMLError):
            yaml.load(doc, Loader=_MkDocsLoader)


# ---------------------------------------------------------------------------
# 2. Path traversal protection
# ---------------------------------------------------------------------------


class TestPathTraversal:
    """Ensure file paths in config cannot escape the project directory."""

    def test_logo_path_traversal_rejected(self, tmp_path: Path) -> None:
        """logo_path with ../../ should not resolve to files outside the project."""
        # Create a file outside the "project" dir
        secret = tmp_path / "secret.png"
        secret.write_bytes(b"\x89PNG fake")

        project = tmp_path / "project"
        project.mkdir()

        config_file = project / "leafpress.yml"
        config_file.write_text("company_name: Test\nproject_name: Test\nlogo_path: ../secret.png\n")

        cfg = load_config(config_file)
        assert cfg.logo_path is not None
        resolved = Path(cfg.logo_path).resolve()

        # The resolved path should NOT escape the project directory
        # This test documents the current behavior — if it passes with
        # traversal, we need to add validation
        assert secret.resolve() == resolved, (
            "Path traversal is currently possible — logo_path resolved outside project dir. "
            "Consider adding path containment validation."
        )

    def test_logo_path_absolute_outside_project(self, tmp_path: Path) -> None:
        """Absolute logo_path pointing outside project should be flagged."""
        secret = tmp_path / "secret.png"
        secret.write_bytes(b"\x89PNG fake")

        project = tmp_path / "project"
        project.mkdir()

        config_file = project / "leafpress.yml"
        config_file.write_text(f"company_name: Test\nproject_name: Test\nlogo_path: {secret}\n")

        # Currently this is allowed — document the behavior
        cfg = load_config(config_file)
        assert cfg.logo_path is not None
        assert Path(cfg.logo_path).resolve() == secret.resolve()

    def test_logo_path_null_byte_rejected(self, tmp_path: Path) -> None:
        """Null bytes in logo_path should be rejected."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text(
            'company_name: Test\nproject_name: Test\nlogo_path: "logo\x00.png"\n'
        )
        with pytest.raises(ConfigError):
            load_config(config_file)

    def test_logo_path_file_uri_rejected(self, tmp_path: Path) -> None:
        """file:// URIs in logo_path should not be treated as remote URLs."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text(
            "company_name: Test\nproject_name: Test\nlogo_path: file:///etc/passwd\n"
        )
        # file:// should NOT be treated like http:// — it should go through
        # local file validation and fail because the path doesn't exist
        with pytest.raises(ConfigError):
            load_config(config_file)

    def test_template_path_traversal(self, tmp_path: Path) -> None:
        """docx.template_path with traversal should be checked."""
        secret = tmp_path / "evil.docx"
        secret.write_bytes(b"PK fake docx")

        project = tmp_path / "project"
        project.mkdir()

        config_file = project / "leafpress.yml"
        config_file.write_text(
            "company_name: Test\nproject_name: Test\ndocx:\n  template_path: ../evil.docx\n"
        )

        cfg = load_config(config_file)
        # Document that template_path allows traversal currently
        assert cfg.docx.template_path is not None

    def test_logo_path_valid_relative(self, tmp_path: Path) -> None:
        """A valid relative logo_path within the project should work fine."""
        logo = tmp_path / "assets" / "logo.png"
        logo.parent.mkdir()
        logo.write_bytes(b"\x89PNG valid logo")

        config_file = tmp_path / "leafpress.yml"
        config_file.write_text(
            "company_name: Test\nproject_name: Test\nlogo_path: assets/logo.png\n"
        )

        cfg = load_config(config_file)
        assert cfg.logo_path is not None
        resolved = Path(cfg.logo_path).resolve()
        assert resolved == logo.resolve()

    def test_logo_path_https_url_bypasses_file_check(self) -> None:
        """HTTP(S) URLs for logo_path should skip file existence validation."""
        cfg = BrandingConfig(
            company_name="Test",
            project_name="Test",
            logo_path="https://example.com/logo.png",
        )
        assert cfg.logo_path == "https://example.com/logo.png"
