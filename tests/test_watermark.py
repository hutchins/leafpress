"""Tests for watermark configuration and rendering."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from leafpress.config import BrandingConfig, WatermarkConfig, load_config
from leafpress.html.styles import generate_html_css
from leafpress.pdf.styles import generate_pdf_css


class TestWatermarkConfig:
    """Test WatermarkConfig model and loading."""

    def test_default_no_watermark(self) -> None:
        """Watermark is disabled by default (text is None)."""
        cfg = BrandingConfig(company_name="Test", project_name="Test")
        assert cfg.watermark.text is None
        assert cfg.watermark.color == "#cccccc"
        assert cfg.watermark.opacity == 0.15
        assert cfg.watermark.angle == -45

    def test_watermark_from_yaml(self, tmp_path: Path) -> None:
        """Watermark config loads from YAML."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text(
            "company_name: Test\n"
            "project_name: Test\n"
            "watermark:\n"
            '  text: "DRAFT"\n'
            '  color: "#ff0000"\n'
            "  opacity: 0.3\n"
            "  angle: -30\n"
        )
        cfg = load_config(config_file)
        assert cfg.watermark.text == "DRAFT"
        assert cfg.watermark.color == "#ff0000"
        assert cfg.watermark.opacity == 0.3
        assert cfg.watermark.angle == -30

    def test_watermark_env_override_text(self, tmp_path: Path) -> None:
        """LEAFPRESS_WATERMARK_TEXT env var overrides config."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text("company_name: Test\nproject_name: Test\n")
        with patch.dict(os.environ, {"LEAFPRESS_WATERMARK_TEXT": "CONFIDENTIAL"}):
            cfg = load_config(config_file)
        assert cfg.watermark.text == "CONFIDENTIAL"

    def test_watermark_env_override_color(self, tmp_path: Path) -> None:
        """LEAFPRESS_WATERMARK_COLOR env var overrides config."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text("company_name: Test\nproject_name: Test\n")
        with patch.dict(os.environ, {"LEAFPRESS_WATERMARK_COLOR": "#aabbcc"}):
            cfg = load_config(config_file)
        assert cfg.watermark.color == "#aabbcc"

    def test_watermark_env_override_opacity(self, tmp_path: Path) -> None:
        """LEAFPRESS_WATERMARK_OPACITY env var overrides config."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text("company_name: Test\nproject_name: Test\n")
        with patch.dict(os.environ, {"LEAFPRESS_WATERMARK_OPACITY": "0.5"}):
            cfg = load_config(config_file)
        assert cfg.watermark.opacity == 0.5

    def test_watermark_env_override_angle(self, tmp_path: Path) -> None:
        """LEAFPRESS_WATERMARK_ANGLE env var overrides config."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text("company_name: Test\nproject_name: Test\n")
        with patch.dict(os.environ, {"LEAFPRESS_WATERMARK_ANGLE": "-60"}):
            cfg = load_config(config_file)
        assert cfg.watermark.angle == -60

    def test_watermark_invalid_opacity_ignored(self, tmp_path: Path) -> None:
        """Invalid LEAFPRESS_WATERMARK_OPACITY is silently ignored."""
        config_file = tmp_path / "leafpress.yml"
        config_file.write_text("company_name: Test\nproject_name: Test\n")
        with patch.dict(os.environ, {"LEAFPRESS_WATERMARK_OPACITY": "not_a_number"}):
            cfg = load_config(config_file)
        assert cfg.watermark.opacity == 0.15  # default

    def test_watermark_opacity_validation(self) -> None:
        """Opacity must be between 0.0 and 1.0."""
        with pytest.raises(ValidationError):
            WatermarkConfig(opacity=1.5)
        with pytest.raises(ValidationError):
            WatermarkConfig(opacity=-0.1)

    def test_watermark_angle_validation(self) -> None:
        """Angle must be between -90 and 90."""
        with pytest.raises(ValidationError):
            WatermarkConfig(angle=100)
        with pytest.raises(ValidationError):
            WatermarkConfig(angle=-100)


class TestWatermarkPdfCss:
    """Test watermark CSS generation for PDF."""

    def _make_branding(self, **wm_kwargs: object) -> BrandingConfig:
        return BrandingConfig(
            company_name="Test",
            project_name="Test",
            watermark=WatermarkConfig(**wm_kwargs),
        )

    def test_no_watermark_css_when_disabled(self) -> None:
        """No watermark CSS when watermark text is None."""
        cfg = BrandingConfig(company_name="Test", project_name="Test")
        css = generate_pdf_css(cfg, None)
        assert ".watermark" not in css

    def test_watermark_css_generated(self) -> None:
        """Watermark CSS is generated when text is set."""
        cfg = self._make_branding(text="DRAFT")
        css = generate_pdf_css(cfg, None)
        assert ".watermark" in css
        assert "rotate(-45deg)" in css
        assert "#cccccc" in css
        assert "0.15" in css

    def test_watermark_css_custom_values(self) -> None:
        """Custom watermark values appear in CSS."""
        cfg = self._make_branding(
            text="CONFIDENTIAL",
            color="#ff0000",
            opacity=0.3,
            angle=-30,
        )
        css = generate_pdf_css(cfg, None)
        assert "#ff0000" in css
        assert "0.3" in css
        assert "rotate(-30deg)" in css


class TestWatermarkHtmlCss:
    """Test watermark CSS generation for HTML."""

    def _make_branding(self, **wm_kwargs: object) -> BrandingConfig:
        return BrandingConfig(
            company_name="Test",
            project_name="Test",
            watermark=WatermarkConfig(**wm_kwargs),
        )

    def test_no_watermark_display_none(self) -> None:
        """Watermark div is display:none when no text."""
        cfg = BrandingConfig(company_name="Test", project_name="Test")
        css = generate_html_css(cfg)
        assert "display: none" in css

    def test_watermark_display_block(self) -> None:
        """Watermark div is display:block when text is set."""
        cfg = self._make_branding(text="DRAFT")
        css = generate_html_css(cfg)
        assert "display: block" in css

    def test_watermark_custom_color_in_html_css(self) -> None:
        """Custom color appears in HTML CSS."""
        cfg = self._make_branding(text="DRAFT", color="#ff0000")
        css = generate_html_css(cfg)
        assert "#ff0000" in css
