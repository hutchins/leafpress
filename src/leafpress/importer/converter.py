"""DOCX to Markdown import converter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import mammoth
from rich.console import Console

from leafpress.exceptions import DocxImportError
from leafpress.importer.image_handler import ImageHandler
from leafpress.importer.markdown_converter import LeafpressMarkdownConverter

console = Console()


@dataclass
class ImportResult:
    """Result of a DOCX import operation."""

    markdown_path: Path
    images: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def import_docx(
    docx_path: Path,
    output_path: Path | None = None,
    extract_images: bool = True,
    code_styles: list[str] | None = None,
) -> ImportResult:
    """Convert a DOCX file to Markdown.

    Args:
        docx_path: Path to the input .docx file.
        output_path: Output .md file path or directory. If None, uses
                      docx_path stem + .md in the same directory.
        extract_images: Whether to extract embedded images to assets/.
        code_styles: Word style names to treat as code blocks.

    Returns:
        ImportResult with paths to generated files and any warnings.

    Raises:
        DocxImportError: If the input file is invalid or conversion fails.
    """
    if not docx_path.exists():
        raise DocxImportError(f"File not found: {docx_path}")
    if docx_path.suffix.lower() != ".docx":
        raise DocxImportError(f"Not a .docx file: {docx_path}")

    # Resolve output path
    md_path = _resolve_output_path(docx_path, output_path)

    # Set up image handler
    assets_dir = md_path.parent / "assets" if extract_images else None
    image_handler = ImageHandler(assets_dir) if assets_dir else None

    # Build mammoth style map
    style_map = _build_style_map(code_styles or [])

    # Convert DOCX -> HTML via mammoth
    with console.status("[bold blue]Converting DOCX to HTML..."):
        convert_image = (
            mammoth.images.img_element(image_handler.handle_image) if image_handler else None
        )
        try:
            with open(docx_path, "rb") as docx_fh:
                kwargs: dict = {}
                if style_map:
                    kwargs["style_map"] = style_map
                if convert_image:
                    kwargs["convert_image"] = convert_image
                result = mammoth.convert_to_html(docx_fh, **kwargs)
        except Exception as e:
            raise DocxImportError(f"Failed to convert DOCX: {e}") from e

    warnings = [msg.message for msg in result.messages]

    # Convert HTML -> Markdown
    with console.status("[bold blue]Converting HTML to Markdown..."):
        converter = LeafpressMarkdownConverter()
        markdown = converter.convert(result.value)

    # Post-process markdown
    markdown = _postprocess_markdown(markdown)

    # Write output
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")

    return ImportResult(
        markdown_path=md_path,
        images=image_handler.saved_images if image_handler else [],
        warnings=warnings,
    )


def _resolve_output_path(docx_path: Path, output_path: Path | None) -> Path:
    """Determine the output .md file path."""
    if output_path is None:
        return docx_path.with_suffix(".md")
    if output_path.is_dir() or not output_path.suffix:
        return output_path / f"{docx_path.stem}.md"
    return output_path


def _build_style_map(code_styles: list[str]) -> str:
    """Build a mammoth style map string for code block detection."""
    lines = []
    for style_name in code_styles:
        lines.append(f"p[style-name='{style_name}'] => pre:separator('\\n')")
    return "\n".join(lines)


def _postprocess_markdown(markdown: str) -> str:
    """Clean up generated markdown."""
    # Collapse 3+ newlines to 2
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    # Strip trailing whitespace per line
    markdown = "\n".join(line.rstrip() for line in markdown.split("\n"))
    # Ensure file ends with single newline
    return markdown.strip() + "\n"
