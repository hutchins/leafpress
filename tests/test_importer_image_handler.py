"""Tests for the importer ImageHandler."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from helpers import make_png

from leafpress.importer.image_handler import (
    ImageHandler,
    content_type_for_extension,
)


class TestSaveImage:
    def test_writes_file_to_assets_dir(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        data = make_png()

        rel_path = handler.save_image(data, "image/png")

        saved = tmp_path / "assets" / Path(rel_path).name
        assert saved.exists()
        assert saved.read_bytes() == data

    def test_returns_relative_markdown_path(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        rel_path = handler.save_image(make_png(), "image/png")
        assert rel_path.startswith("assets/image-001-")
        assert rel_path.endswith(".png")

    def test_filename_includes_counter_and_hash(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        data = make_png()
        expected_hash = hashlib.sha256(data).hexdigest()[:12]

        rel_path = handler.save_image(data, "image/png")

        assert f"image-001-{expected_hash}.png" in rel_path

    def test_counter_increments_across_calls(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        first = handler.save_image(make_png(), "image/png")
        second = handler.save_image(b"other-bytes", "image/jpeg")

        assert "image-001-" in first
        assert "image-002-" in second
        assert second.endswith(".jpg")

    def test_creates_assets_dir_if_missing(self, tmp_path: Path) -> None:
        assets_dir = tmp_path / "deep" / "nested" / "assets"
        assert not assets_dir.exists()

        handler = ImageHandler(assets_dir)
        handler.save_image(make_png(), "image/png")

        assert assets_dir.is_dir()

    def test_unknown_content_type_defaults_to_png(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        rel_path = handler.save_image(b"data", "application/octet-stream")
        assert rel_path.endswith(".png")

    @pytest.mark.parametrize(
        ("content_type", "expected_ext"),
        [
            ("image/png", ".png"),
            ("image/jpeg", ".jpg"),
            ("image/gif", ".gif"),
            ("image/svg+xml", ".svg"),
            ("image/bmp", ".bmp"),
            ("image/tiff", ".tiff"),
            ("image/webp", ".webp"),
            ("image/x-emf", ".emf"),
            ("image/x-wmf", ".wmf"),
        ],
    )
    def test_extension_mapping(self, tmp_path: Path, content_type: str, expected_ext: str) -> None:
        handler = ImageHandler(tmp_path / "assets")
        rel_path = handler.save_image(b"x", content_type)
        assert rel_path.endswith(expected_ext)

    def test_saved_images_tracks_paths(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        handler.save_image(make_png(), "image/png")
        handler.save_image(b"x", "image/jpeg")

        assert len(handler.saved_images) == 2
        assert all(p.exists() for p in handler.saved_images)

    def test_saved_images_returns_copy(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        handler.save_image(make_png(), "image/png")

        snapshot = handler.saved_images
        snapshot.clear()

        assert len(handler.saved_images) == 1


class TestHandleImage:
    def test_reads_image_via_open_callback(self, tmp_path: Path) -> None:
        handler = ImageHandler(tmp_path / "assets")
        data = make_png()

        class FakeMammothImage:
            content_type = "image/png"

            def open(self) -> BytesIO:
                return BytesIO(data)

        result = handler.handle_image(FakeMammothImage())

        assert "src" in result
        assert result["src"].startswith("assets/image-001-")
        assert result["src"].endswith(".png")
        assert len(handler.saved_images) == 1


class TestContentTypeForExtension:
    @pytest.mark.parametrize(
        ("ext", "expected"),
        [
            (".png", "image/png"),
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".gif", "image/gif"),
            (".svg", "image/svg+xml"),
            (".bmp", "image/bmp"),
            (".tiff", "image/tiff"),
            (".webp", "image/webp"),
            (".emf", "image/x-emf"),
            (".wmf", "image/x-wmf"),
        ],
    )
    def test_known_extensions(self, ext: str, expected: str) -> None:
        assert content_type_for_extension(ext) == expected

    def test_unknown_extension_defaults_to_png(self) -> None:
        assert content_type_for_extension(".xyz") == "image/png"
