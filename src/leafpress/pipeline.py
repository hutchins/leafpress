"""Conversion pipeline orchestrator."""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from leafpress.config import BrandingConfig, ProjectEntry, config_from_env, load_config
from leafpress.exceptions import LeafpressError, SourceError
from leafpress.git_info import extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import (
    NavItem,
    bump_nav_levels,
    flatten_nav,
    parse_mkdocs_config,
)
from leafpress.source import resolve_source

console = Console()


def convert(
    source: str,
    output_dir: Path,
    format: str = "pdf",
    config_path: Path | None = None,
    mkdocs_config_path: Path | None = None,
    branch: str | None = None,
    cover_page: bool = True,
    include_toc: bool = True,
    local_time: bool = False,
    watermark: str | None = None,
) -> list[Path]:
    """Main conversion pipeline.

    Args:
        source: Local path or git URL to an MkDocs project.
        output_dir: Directory for generated output files.
        format: Output format - "pdf", "docx", "html", "odt", or "all".
        config_path: Optional path to leafpress branding config YAML.
        mkdocs_config_path: Optional override path to mkdocs.yml.
        branch: Git branch to clone (only for git URL sources).
        cover_page: Include a cover page.
        include_toc: Include a table of contents.

    Returns:
        List of generated output file paths.
    """
    generated_files: list[Path] = []

    with resolve_source(source, branch) as project_dir:
        # Load .env from project dir (shell env takes priority via override=False)
        load_dotenv(project_dir / ".env", override=False)

        # Parse mkdocs.yml
        with console.status("[bold blue]Parsing MkDocs configuration..."):
            config_file = mkdocs_config_path or _find_mkdocs_config(project_dir)
            mkdocs_cfg = parse_mkdocs_config(config_file)
        console.print(f"  [green]Site:[/green] {mkdocs_cfg.site_name}")

        # Load branding config
        branding: BrandingConfig | None = None
        if config_path:
            branding = load_config(config_path)
        else:
            for name in ("leafpress.yml", "leafpress.yaml"):
                candidate = project_dir / name
                if candidate.exists():
                    branding = load_config(candidate)
                    console.print(f"  [green]Config:[/green] Auto-detected {candidate.name}")
                    break
            if branding is None:
                branding = config_from_env()
        # CLI --watermark flag overrides config
        if watermark and branding:
            branding = branding.model_copy(
                update={"watermark": branding.watermark.model_copy(update={"text": watermark})}
            )
        elif watermark and not branding:
            from leafpress.config import WatermarkConfig

            branding = BrandingConfig(
                company_name=mkdocs_cfg.site_name,
                project_name=mkdocs_cfg.site_name,
                watermark=WatermarkConfig(text=watermark),
            )

        if branding:
            console.print(
                f"  [green]Branding:[/green] {branding.company_name} / {branding.project_name}"
            )
            if branding.watermark.text:
                console.print(
                    f"  [green]Watermark:[/green] \"{branding.watermark.text}\""
                )

        # Extract git info
        git_info = extract_git_info(project_dir)
        if git_info:
            console.print(f"  [green]Version:[/green] {git_info.format_version_string()}")

        # Initialize temp dir for mermaid images
        mermaid_dir = Path(tempfile.mkdtemp(prefix="leafpress-mermaid-"))

        # Monorepo mode: collect pages from multiple projects
        if branding and branding.projects:
            config_dir = (config_path or project_dir).parent if config_path else project_dir
            html_pages, page_count = _collect_monorepo_pages(
                branding.projects, config_dir, mermaid_dir, branding, console,
            )
            console.print(
                f"  [green]Projects:[/green] {len(branding.projects)} "
                f"({page_count} documents)\n"
            )
        else:
            # Single-project mode (unchanged)
            renderer = MarkdownRenderer(
                extensions=mkdocs_cfg.markdown_extensions,
                docs_dir=mkdocs_cfg.docs_dir,
                mermaid_output_dir=mermaid_dir,
            )

            pages = flatten_nav(mkdocs_cfg.nav_items)
            page_count = sum(1 for p in pages if p.path is not None)
            console.print(f"  [green]Pages:[/green] {page_count} documents to convert\n")

            html_pages: list[tuple[NavItem, str]] = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Converting Markdown to HTML", total=page_count)
                for item in pages:
                    if item.path is None:
                        html_pages.append((item, ""))
                        continue
                    md_file = mkdocs_cfg.docs_dir / item.path
                    if not md_file.exists():
                        console.print(f"  [yellow]Warning:[/yellow] File not found: {item.path}")
                        progress.update(task, advance=1)
                        continue
                    md_content = md_file.read_text(encoding="utf-8")
                    html = renderer.render(md_content, md_file)
                    html_pages.append((item, html))
                    progress.update(task, advance=1)

        # Generate outputs
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(mkdocs_cfg.site_name)

        if format in ("pdf", "both", "all"):
            try:
                from leafpress.pdf.renderer import PdfRenderer
            except (ImportError, OSError) as e:
                raise LeafpressError(
                    "PDF output requires WeasyPrint and its system dependencies.\n"
                    "  Run 'leafpress doctor' to diagnose your environment.\n"
                    "  Install with: pip install 'leafpress[pdf]'\n"
                    "  System deps: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html"
                ) from e

            pdf_path = output_dir / f"{safe_name}.pdf"
            with console.status("[bold blue]Generating PDF..."):
                pdf_renderer = PdfRenderer(branding, git_info, mkdocs_cfg)
                pdf_renderer.render(
                    html_pages,
                    pdf_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                    local_time=local_time,
                )
            generated_files.append(pdf_path)
            console.print(f"  [bold green]PDF:[/bold green] {pdf_path}")

        if format in ("docx", "both", "all"):
            from leafpress.docx.renderer import DocxRenderer

            docx_path = output_dir / f"{safe_name}.docx"
            with console.status("[bold blue]Generating DOCX..."):
                docx_renderer = DocxRenderer(branding, git_info, mkdocs_cfg)
                docx_renderer.render(
                    html_pages,
                    docx_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                    local_time=local_time,
                )
            generated_files.append(docx_path)
            console.print(f"  [bold green]DOCX:[/bold green] {docx_path}")

        if format in ("html", "all"):
            from leafpress.html.renderer import HtmlRenderer

            html_path = output_dir / f"{safe_name}.html"
            with console.status("[bold blue]Generating HTML..."):
                html_renderer = HtmlRenderer(branding, git_info, mkdocs_cfg)
                html_renderer.render(
                    html_pages,
                    html_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                    local_time=local_time,
                )
            generated_files.append(html_path)
            console.print(f"  [bold green]HTML:[/bold green] {html_path}")

        if format in ("odt", "all"):
            from leafpress.odt.renderer import OdtRenderer

            odt_path = output_dir / f"{safe_name}.odt"
            with console.status("[bold blue]Generating ODT..."):
                odt_renderer = OdtRenderer(branding, git_info, mkdocs_cfg)
                odt_renderer.render(
                    html_pages,
                    odt_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                    local_time=local_time,
                )
            generated_files.append(odt_path)
            console.print(f"  [bold green]ODT:[/bold green] {odt_path}")

        if format in ("epub", "all"):
            from leafpress.epub.renderer import EpubRenderer

            epub_path = output_dir / f"{safe_name}.epub"
            with console.status("[bold blue]Generating EPUB..."):
                epub_renderer = EpubRenderer(branding, git_info, mkdocs_cfg)
                epub_renderer.render(
                    html_pages,
                    epub_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                    local_time=local_time,
                )
            generated_files.append(epub_path)
            console.print(f"  [bold green]EPUB:[/bold green] {epub_path}")

    return generated_files


def _find_mkdocs_config(project_dir: Path) -> Path:
    """Locate mkdocs.yml or mkdocs.yaml in the project directory."""
    for name in ("mkdocs.yml", "mkdocs.yaml"):
        config_path = project_dir / name
        if config_path.exists():
            return config_path
    raise LeafpressError(f"No mkdocs.yml or mkdocs.yaml found in {project_dir}")


def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()


def _collect_monorepo_pages(
    projects: list[ProjectEntry],
    config_dir: Path,
    mermaid_output_dir: Path,
    branding: BrandingConfig,
    con: Console,
) -> tuple[list[tuple[NavItem, str]], int]:
    """Parse and render pages from multiple MkDocs projects.

    Supports both local paths and git URL entries. Git repos are cloned
    to temporary directories and cleaned up after all pages are collected.

    Returns (combined html_pages, total page count).
    """
    all_pages: list[tuple[NavItem, str]] = []
    total_pages = 0

    with contextlib.ExitStack() as stack:
        for entry in projects:
            # Resolve project directory (local path or git clone)
            if entry.url:
                resolved = stack.enter_context(
                    resolve_source(entry.url, entry.branch)
                )
                project_dir = resolved
                source_label = entry.url
            else:
                project_dir = (config_dir / entry.path).resolve()
                if not project_dir.is_dir():
                    raise SourceError(
                        f"Monorepo project directory not found: {project_dir}"
                    )
                source_label = entry.path

            mkdocs_file = _find_mkdocs_config(project_dir)
            mkdocs_cfg = parse_mkdocs_config(mkdocs_file)

            con.print(
                f"  [green]Chapter:[/green] {mkdocs_cfg.site_name} ({source_label})"
            )

            # Chapter heading
            chapter = NavItem(title=mkdocs_cfg.site_name, path=None, level=0)
            all_pages.append((chapter, ""))

            # Per-project metadata as HTML
            meta_html = _build_chapter_meta(entry, branding)
            if meta_html:
                meta_item = NavItem(title="", path=None, level=0)
                all_pages.append((meta_item, meta_html))

            # Render pages with project-specific docs_dir
            renderer = MarkdownRenderer(
                extensions=mkdocs_cfg.markdown_extensions,
                docs_dir=mkdocs_cfg.docs_dir,
                mermaid_output_dir=mermaid_output_dir,
            )
            flat_nav = flatten_nav(mkdocs_cfg.nav_items)
            bumped = bump_nav_levels(flat_nav)

            for item in bumped:
                if item.path is None:
                    all_pages.append((item, ""))
                    continue
                md_file = mkdocs_cfg.docs_dir / item.path
                if not md_file.exists():
                    con.print(
                        f"  [yellow]Warning:[/yellow] File not found: {item.path}"
                    )
                    continue
                md_content = md_file.read_text(encoding="utf-8")
                html = renderer.render(md_content, md_file)
                all_pages.append((item, html))
                total_pages += 1

    return all_pages, total_pages


def _build_chapter_meta(entry: ProjectEntry, branding: BrandingConfig) -> str:
    """Build HTML metadata block for a monorepo chapter heading.

    Uses per-project overrides, falling back to top-level branding values.
    Returns empty string if no metadata to display.
    """
    lines: list[str] = []

    author = entry.author or branding.author
    author_email = entry.author_email or branding.author_email
    if author or author_email:
        if author and author_email:
            lines.append(f"<p><em>Author: {author} &lt;{author_email}&gt;</em></p>")
        elif author:
            lines.append(f"<p><em>Author: {author}</em></p>")
        else:
            lines.append(f"<p><em>Author: {author_email}</em></p>")

    owner = entry.document_owner or branding.document_owner
    if owner:
        lines.append(f"<p><em>Document Owner: {owner}</em></p>")

    review = entry.review_cycle or branding.review_cycle
    if review:
        lines.append(f"<p><em>Review Cycle: {review}</em></p>")

    subtitle = entry.subtitle or branding.subtitle
    if subtitle:
        lines.append(f"<p><em>{subtitle}</em></p>")

    return "\n".join(lines)
