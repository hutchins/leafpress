"""Route a document to the right importer by file extension.

Shared by the ``leafpress import`` command and the desktop UI's import
window so both support the same formats with the same behavior.
"""

from __future__ import annotations

from pathlib import Path

from leafpress.exceptions import LeafpressError
from leafpress.importer.base import ImportResult

SUPPORTED_IMPORT_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".tex"}


def import_document(
    file: Path,
    *,
    output: Path | None = None,
    extract_images: bool = True,
    code_styles: list[str] | None = None,
    include_notes: bool = True,
) -> ImportResult:
    """Import one .docx, .pptx, .xlsx, or .tex file to Markdown.

    Args:
        file: Document to import.
        output: Output .md path or directory; None writes next to ``file``.
        extract_images: Save embedded images to ``assets/`` (DOCX, PPTX, TeX).
        code_styles: Word style names to treat as code blocks (DOCX only).
        include_notes: Include speaker notes as blockquotes (PPTX only).

    Raises:
        LeafpressError: For unsupported file types or import failures.

    Example:
        >>> import_document(Path("report.docx"), output=Path("docs/"))  # doctest: +SKIP
    """
    suffix = file.suffix.lower()

    if suffix == ".docx":
        from leafpress.importer.converter import import_docx

        return import_docx(
            docx_path=file,
            output_path=output,
            extract_images=extract_images,
            code_styles=code_styles,
        )
    if suffix == ".pptx":
        from leafpress.importer.converter_pptx import import_pptx

        return import_pptx(
            pptx_path=file,
            output_path=output,
            extract_images=extract_images,
            include_notes=include_notes,
        )
    if suffix == ".xlsx":
        from leafpress.importer.converter_xlsx import import_xlsx

        return import_xlsx(xlsx_path=file, output_path=output)
    if suffix == ".tex":
        from leafpress.importer.converter_tex import import_tex

        return import_tex(tex_path=file, output_path=output, extract_images=extract_images)

    raise LeafpressError(f"Unsupported file type '{suffix}'. Use .docx, .pptx, .xlsx, or .tex")
