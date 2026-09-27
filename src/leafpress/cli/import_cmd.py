"""`leafpress import`: convert DOCX/PPTX/XLSX/TeX files or URLs to Markdown."""

from __future__ import annotations

import contextlib
import dataclasses
import tempfile
from collections.abc import Generator
from pathlib import Path

import typer
from rich.markup import escape
from rich.table import Table

from leafpress.cli.app import console
from leafpress.exceptions import LeafpressError
from leafpress.importer.base import ImportResult, resolve_output_path


def import_file(
    sources: list[str] = typer.Argument(
        help="One or more .docx, .pptx, .xlsx, or .tex files or URLs to import.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output .md file path or directory. Defaults to <stem>.md.",
    ),
    extract_images: bool = typer.Option(
        True,
        "--extract-images/--no-extract-images",
        help="Extract embedded images to an assets/ folder.",
    ),
    code_styles: str | None = typer.Option(
        None,
        "--code-styles",
        help="Comma-separated Word style names to treat as code blocks (DOCX only).",
    ),
    include_notes: bool = typer.Option(
        True,
        "--notes/--no-notes",
        help="Include speaker notes as blockquotes (PPTX only).",
    ),
) -> None:
    """Import Word, PowerPoint, Excel, or LaTeX documents and convert them to Markdown."""
    # When multiple sources are given, -o must be a directory (or omitted)
    if output and len(sources) > 1 and output.suffix:
        console.print(
            "\n[bold red]Error:[/bold red] Use a directory for --output "
            "when importing multiple files."
        )
        raise typer.Exit(code=1)

    outcomes: list[_ImportOutcome] = []
    # Output .md path -> source that produced it, to catch same-name inputs
    # (a/report.docx, b/report.docx) overwriting each other in one -o dir
    written: dict[Path, str] = {}

    for source in sources:
        is_url = source.startswith(("http://", "https://"))
        # A URL is downloaded to a temp dir that is deleted afterwards, so its
        # default output (next to the input) must be the current directory
        effective_output = output if output is not None or not is_url else Path.cwd()
        try:
            with _resolve_import_source(source) as file:
                target = resolve_output_path(file, effective_output).resolve()
                if target in written:
                    raise LeafpressError(
                        f"Output {target.name} would overwrite the import of "
                        f"{written[target]}; import these separately or use different -o paths"
                    )
                result = _import_single_file(
                    file,
                    output=effective_output,
                    extract_images=extract_images,
                    code_styles=code_styles,
                    include_notes=include_notes,
                )
            written[target] = source
            outcomes.append(_ImportOutcome(source, result=result))
            console.print(f"\n[bold green]Done![/bold green] {result.markdown_path}")
            if result.images:
                console.print(f"  [green]Images:[/green] {len(result.images)} extracted to assets/")
            if result.warnings:
                n = len(result.warnings)
                console.print(f"  [yellow]Warnings:[/yellow] {n}")
                shown = 10
                for w in result.warnings[:shown]:
                    console.print(f"    [yellow]⚠[/yellow] {escape(w)}")
                if n > shown:
                    console.print(f"    [dim]… and {n - shown} more[/dim]")

        except LeafpressError as e:
            outcomes.append(_ImportOutcome(source, error=str(e)))
            console.print(f"\n[bold red]Error:[/bold red] {escape(source)}: {escape(str(e))}")
        except Exception as e:
            # Keep going: one malformed file shouldn't abort the whole batch
            outcomes.append(_ImportOutcome(source, error=f"{type(e).__name__}: {e}"))
            console.print(
                f"\n[bold red]Error:[/bold red] {escape(source)}: unexpected "
                f"{type(e).__name__}: {escape(str(e))}"
            )

    if len(outcomes) > 1:
        console.print()
        console.print(_import_summary_table(outcomes))

    failed = sum(1 for o in outcomes if o.error is not None)
    if failed:
        console.print(f"\n[yellow]{failed} of {len(outcomes)} file(s) failed to import.[/yellow]")
        raise typer.Exit(code=1)


@dataclasses.dataclass
class _ImportOutcome:
    """Result of importing one source in a batch: either a result or an error."""

    source: str
    result: ImportResult | None = None
    error: str | None = None


def _import_summary_table(outcomes: list[_ImportOutcome]) -> Table:
    """Build a per-file summary table for multi-file imports."""
    table = Table(title="Import summary")
    table.add_column("Source", overflow="fold")
    table.add_column("Status")
    table.add_column("Output / error", overflow="fold")
    table.add_column("Images", justify="right")
    table.add_column("Warnings", justify="right")
    for o in outcomes:
        if o.result is not None:
            table.add_row(
                escape(o.source),
                "[green]ok[/green]",
                escape(str(o.result.markdown_path)),
                str(len(o.result.images)),
                str(len(o.result.warnings)),
            )
        else:
            table.add_row(escape(o.source), "[red]failed[/red]", escape(o.error or ""), "-", "-")
    return table


_SUPPORTED_IMPORT_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".tex"}


_DOC_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/x-tex": ".tex",
    "application/x-tex": ".tex",
    "application/x-latex": ".tex",
}


@contextlib.contextmanager
def _resolve_import_source(source: str) -> Generator[Path]:
    """Resolve an import source (local path or URL) to a local file path.

    For local paths, yields the path directly. For URLs, downloads to a
    temp directory and yields the downloaded file path, cleaning up after.
    """
    if source.startswith(("http://", "https://")):
        with tempfile.TemporaryDirectory(prefix="leafpress_import_") as tmp:
            file = _download_import_file(source, Path(tmp))
            yield file
    else:
        yield Path(source)


_MAX_IMPORT_BYTES = 200 * 1024 * 1024


def _download_import_file(url: str, dest_dir: Path) -> Path:
    """Download a file from a URL for import.

    Infers file type from the URL path extension, falling back to the
    Content-Type header. Raises LeafpressError on failure.
    """
    from urllib.parse import urlparse

    url_path = urlparse(url).path
    ext = Path(url_path).suffix.lower() if url_path else ""

    from leafpress.downloads import DownloadError, download

    console.print(f"  [blue]Downloading[/blue] {url}")
    try:
        body, headers = download(url, max_bytes=_MAX_IMPORT_BYTES, timeout=60)
    except DownloadError as e:
        raise LeafpressError(str(e)) from e

    # Fall back to Content-Type if URL has no recognized extension
    if ext not in _SUPPORTED_IMPORT_EXTENSIONS:
        content_type = headers.get("content-type", "").split(";")[0].strip()
        ext = _DOC_CONTENT_TYPE_TO_EXT.get(content_type, ext)

    if ext not in _SUPPORTED_IMPORT_EXTENSIONS:
        raise LeafpressError(
            f"Cannot determine file type for {url}. "
            f"URL has no recognized extension and Content-Type "
            f"'{headers.get('content-type', '')}' is not a supported format."
        )

    # Derive filename from URL path or use a default
    stem = Path(url_path).stem if url_path and Path(url_path).stem else "download"
    dest = dest_dir / f"{stem}{ext}"

    dest.write_bytes(body)
    return dest


def _import_single_file(
    file: Path,
    *,
    output: Path | None,
    extract_images: bool,
    code_styles: str | None,
    include_notes: bool,
) -> ImportResult:
    """Import a single .docx, .pptx, .xlsx, or .tex file and return the result."""
    suffix = file.suffix.lower()

    if suffix == ".docx":
        from leafpress.importer.converter import import_docx as do_import

        style_list = (
            [s.strip() for s in code_styles.split(",") if s.strip()] if code_styles else None
        )
        return do_import(
            docx_path=file,
            output_path=output,
            extract_images=extract_images,
            code_styles=style_list,
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

        return import_xlsx(
            xlsx_path=file,
            output_path=output,
        )

    if suffix == ".tex":
        from leafpress.importer.converter_tex import import_tex

        return import_tex(
            tex_path=file,
            output_path=output,
            extract_images=extract_images,
        )

    raise LeafpressError(f"Unsupported file type '{suffix}'. Use .docx, .pptx, .xlsx, or .tex")
