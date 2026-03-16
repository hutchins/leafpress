"""Conversion pipeline orchestrator."""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, PackageLoader
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from leafpress.config import BrandingConfig, ProjectEntry, config_from_env, load_config
from leafpress.exceptions import LeafpressError, RenderError, SourceError
from leafpress.git_info import extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import (
    MkDocsConfig,
    NavItem,
    bump_nav_levels,
    flatten_nav,
    parse_mkdocs_config,
)
from leafpress.source import resolve_source

console = Console()


class _ConsoleWarningHandler(logging.Handler):
    """Route WARNING+ log records to Rich console output.

    Attached temporarily during ``convert()`` so that logger.warning()
    calls inside renderers (SVG logo skips, extension failures, etc.)
    are surfaced to the user automatically.
    """

    def __init__(self, con: Console) -> None:
        super().__init__(level=logging.WARNING)
        self._console = con

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self._console.print(f"  [yellow]⚠ {msg}[/yellow]")


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
    footer_render_date: bool | None = None,
    verbose: bool = False,
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
        footer_render_date: Override include_render_date in footer config.
        verbose: Enable verbose output (surfaces DEBUG-level log messages).

    Returns:
        List of generated output file paths.
    """
    generated_files: list[Path] = []

    # Attach a handler that routes leafpress logger warnings to the console.
    # This surfaces logger.warning() calls from renderers (SVG logo skip,
    # extension failures, etc.) that would otherwise be invisible.
    _log_handler = _ConsoleWarningHandler(console)
    if verbose:
        _log_handler.setLevel(logging.DEBUG)
    _pkg_logger = logging.getLogger("leafpress")
    _prev_log_level = _pkg_logger.level
    _pkg_logger.addHandler(_log_handler)
    _pkg_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)

    with resolve_source(source, branch) as project_dir:
        # Load .env from project dir (shell env takes priority via override=False)
        load_dotenv(project_dir / ".env", override=False)

        # Load branding config (before mkdocs.yml so monorepo mode can skip it)
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

        # Parse mkdocs.yml (not required in monorepo mode)
        is_monorepo = branding is not None and bool(branding.projects)
        mkdocs_cfg = None
        if not is_monorepo:
            with console.status("[bold blue]Parsing MkDocs configuration..."):
                config_file = mkdocs_config_path or _find_mkdocs_config(project_dir)
                mkdocs_cfg = parse_mkdocs_config(config_file)
            console.print(f"  [green]Site:[/green] {mkdocs_cfg.site_name}")
        elif mkdocs_config_path:
            # Monorepo mode but an explicit mkdocs config was given
            mkdocs_cfg = parse_mkdocs_config(mkdocs_config_path)
            console.print(f"  [green]Site:[/green] {mkdocs_cfg.site_name}")
        else:
            # Monorepo mode without top-level mkdocs.yml — synthesize a minimal config
            mkdocs_cfg = MkDocsConfig(
                site_name=branding.project_name,
                docs_dir=project_dir,
                nav_items=[],
                markdown_extensions=[],
                theme_name=None,
                extra_css=[],
                config_path=project_dir / "mkdocs.yml",
            )
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

        # CLI --footer-date flag overrides config
        if footer_render_date is not None and branding:
            branding = branding.model_copy(
                update={
                    "footer": branding.footer.model_copy(
                        update={"include_render_date": footer_render_date}
                    )
                }
            )

        if branding:
            console.print(
                f"  [green]Branding:[/green] {branding.company_name} / {branding.project_name}"
            )
            if branding.logo_path:
                logo = branding.logo_path
                if logo.startswith(("http://", "https://")) or Path(logo).exists():
                    console.print(f"  [green]✓[/green] Logo: {logo}")
                else:
                    console.print(f"  [yellow]⚠[/yellow] Logo not found: {logo}")
            if branding.watermark.text:
                console.print(f'  [green]Watermark:[/green] "{branding.watermark.text}"')

        # Extract git info and package version
        git_info = extract_git_info(project_dir)
        from leafpress.package_version import detect_package_version

        pkg_ver = detect_package_version(project_dir)
        if git_info and pkg_ver:
            git_info = dataclasses.replace(git_info, package_version=pkg_ver)
        if git_info:
            console.print(f"  [green]Version:[/green] {git_info.format_version_string()}")
        elif pkg_ver:
            console.print(f"  [green]Version:[/green] {pkg_ver}")

        # Initialize temp dir for mermaid images
        mermaid_dir = Path(tempfile.mkdtemp(prefix="leafpress-mermaid-"))

        # Monorepo mode: collect pages from multiple projects
        if branding and branding.projects:
            config_dir = (config_path or project_dir).parent if config_path else project_dir
            html_pages, page_count = _collect_monorepo_pages(
                branding.projects,
                config_dir,
                mermaid_dir,
                branding,
                console,
            )
            console.print(
                f"  [green]Projects:[/green] {len(branding.projects)} ({page_count} documents)\n"
            )
        else:
            # Single-project mode (unchanged)
            renderer = MarkdownRenderer(
                extensions=mkdocs_cfg.markdown_extensions,
                docs_dir=mkdocs_cfg.docs_dir,
                mermaid_output_dir=mermaid_dir,
            )
            for ext, ok in renderer.extension_load_results:
                if ok:
                    console.print(f"  [green]✓[/green] Extension: {ext}")
                else:
                    console.print(f"  [yellow]⚠[/yellow] Skipping unavailable extension: {ext}")

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
                    html, render_warnings = renderer.render(md_content, md_file)
                    for w in render_warnings:
                        if "failed" in w:
                            console.print(f"  [yellow]⚠ {w}[/yellow]")
                        else:
                            console.print(f"  [green]✓ {w}[/green]")
                    html_pages.append((item, html))
                    progress.update(task, advance=1)

        # Generate outputs
        output_dir.mkdir(parents=True, exist_ok=True)
        if mkdocs_cfg:
            site_name = mkdocs_cfg.site_name
        elif branding:
            site_name = branding.project_name
        else:
            site_name = "output"
        safe_name = _safe_filename(site_name)

        if format in ("pdf", "both", "all"):
            try:
                from leafpress.pdf.renderer import PdfRenderer
            except ImportError as e:
                raise LeafpressError(
                    "PDF output requires WeasyPrint. Install it with:\n"
                    "  uv tool install 'leafpress[pdf]'  (or pip install 'leafpress[pdf]')\n"
                    "  Run 'leafpress doctor' to diagnose your environment."
                ) from e
            except OSError as e:
                raise LeafpressError(
                    "WeasyPrint is installed but its system libraries could not be loaded.\n"
                    "  This usually means cairo/pango/gdk-pixbuf are missing or not on the path.\n"
                    "  macOS:  brew install cairo pango gdk-pixbuf libffi\n"
                    "          (NOTE: 'brew install weasyprint' is a different package)\n"
                    "  Apple Silicon: "
                    "export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH\n"
                    "  Linux:  sudo apt install libcairo2-dev libpango1.0-dev "
                    "libgdk-pixbuf2.0-dev libffi-dev\n"
                    "  Run 'leafpress doctor' for a full diagnosis.\n"
                    f"  Original error: {e}"
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
                try:
                    docx_renderer.render(
                        html_pages,
                        docx_path,
                        cover_page=cover_page,
                        include_toc=include_toc,
                        local_time=local_time,
                    )
                except LeafpressError:
                    raise
                except Exception as exc:
                    raise RenderError(
                        f"DOCX rendering failed: {type(exc).__name__}: {exc}\n"
                        f"  Check that all images are in a supported format (PNG, JPEG).\n"
                        f"  SVG images are not supported in DOCX output."
                    ) from exc
            generated_files.append(docx_path)
            console.print(f"  [bold green]DOCX:[/bold green] {docx_path}")

        if format in ("html", "all"):
            from leafpress.html.renderer import HtmlRenderer

            html_path = output_dir / f"{safe_name}.html"
            with console.status("[bold blue]Generating HTML..."):
                html_renderer = HtmlRenderer(branding, git_info, mkdocs_cfg)
                try:
                    html_renderer.render(
                        html_pages,
                        html_path,
                        cover_page=cover_page,
                        include_toc=include_toc,
                        local_time=local_time,
                    )
                except LeafpressError:
                    raise
                except Exception as exc:
                    raise RenderError(
                        f"HTML rendering failed: {type(exc).__name__}: {exc}"
                    ) from exc
            generated_files.append(html_path)
            console.print(f"  [bold green]HTML:[/bold green] {html_path}")

        if format in ("odt", "all"):
            from leafpress.odt.renderer import OdtRenderer

            odt_path = output_dir / f"{safe_name}.odt"
            with console.status("[bold blue]Generating ODT..."):
                odt_renderer = OdtRenderer(branding, git_info, mkdocs_cfg)
                try:
                    odt_renderer.render(
                        html_pages,
                        odt_path,
                        cover_page=cover_page,
                        include_toc=include_toc,
                        local_time=local_time,
                    )
                except LeafpressError:
                    raise
                except Exception as exc:
                    raise RenderError(
                        f"ODT rendering failed: {type(exc).__name__}: {exc}\n"
                        f"  Check that all images are in a supported format (PNG, JPEG).\n"
                        f"  SVG images are not supported in ODT output."
                    ) from exc
            generated_files.append(odt_path)
            console.print(f"  [bold green]ODT:[/bold green] {odt_path}")

        if format in ("epub", "all"):
            from leafpress.epub.renderer import EpubRenderer

            epub_path = output_dir / f"{safe_name}.epub"
            with console.status("[bold blue]Generating EPUB..."):
                epub_renderer = EpubRenderer(branding, git_info, mkdocs_cfg)
                try:
                    epub_renderer.render(
                        html_pages,
                        epub_path,
                        cover_page=cover_page,
                        include_toc=include_toc,
                        local_time=local_time,
                    )
                except LeafpressError:
                    raise
                except Exception as exc:
                    raise RenderError(
                        f"EPUB rendering failed: {type(exc).__name__}: {exc}"
                    ) from exc
            generated_files.append(epub_path)
            console.print(f"  [bold green]EPUB:[/bold green] {epub_path}")

        if format in ("markdown", "all"):
            from leafpress.markdown_export.renderer import MarkdownExportRenderer

            md_export_path = output_dir / f"{safe_name}.md"
            with console.status("[bold blue]Generating Markdown..."):
                md_export = MarkdownExportRenderer(branding, git_info, mkdocs_cfg)
                md_export.render(
                    html_pages,
                    md_export_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                    local_time=local_time,
                )
            generated_files.append(md_export_path)
            console.print(f"  [bold green]Markdown:[/bold green] {md_export_path}")

    # Detach the console warning handler
    _pkg_logger.removeHandler(_log_handler)
    _pkg_logger.setLevel(_prev_log_level)

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
                resolved = stack.enter_context(resolve_source(entry.url, entry.branch))
                project_dir = resolved
                source_label = entry.url
            else:
                project_dir = (config_dir / entry.path).resolve()
                if not project_dir.is_dir():
                    raise SourceError(f"Monorepo project directory not found: {project_dir}")
                source_label = entry.path

            mkdocs_file = _find_mkdocs_config(project_dir)
            mkdocs_cfg = parse_mkdocs_config(mkdocs_file)

            con.print(f"  [green]Chapter:[/green] {mkdocs_cfg.site_name} ({source_label})")

            # Chapter cover page with metadata
            chapter_html = _build_chapter_cover(entry, branding, mkdocs_cfg.site_name, source_label)
            chapter = NavItem(title=mkdocs_cfg.site_name, path=None, level=0)
            all_pages.append((chapter, chapter_html))

            # Render pages with project-specific docs_dir
            renderer = MarkdownRenderer(
                extensions=mkdocs_cfg.markdown_extensions,
                docs_dir=mkdocs_cfg.docs_dir,
                mermaid_output_dir=mermaid_output_dir,
            )
            for ext, ok in renderer.extension_load_results:
                if ok:
                    con.print(f"  [green]✓[/green] Extension: {ext}")
                else:
                    con.print(f"  [yellow]⚠[/yellow] Skipping unavailable extension: {ext}")
            flat_nav = flatten_nav(mkdocs_cfg.nav_items)
            bumped = bump_nav_levels(flat_nav)

            for item in bumped:
                if item.path is None:
                    all_pages.append((item, ""))
                    continue
                md_file = mkdocs_cfg.docs_dir / item.path
                if not md_file.exists():
                    con.print(
                        f"  [yellow]Warning:[/yellow] File not found:"
                        f" {item.path} (in {mkdocs_cfg.site_name})"
                    )
                    continue
                md_content = md_file.read_text(encoding="utf-8")
                html, render_warnings = renderer.render(md_content, md_file)
                for w in render_warnings:
                    if "failed" in w:
                        con.print(f"  [yellow]⚠ {w}[/yellow]")
                    else:
                        con.print(f"  [green]✓ {w}[/green]")
                all_pages.append((item, html))
                total_pages += 1

    return all_pages, total_pages


def _build_chapter_cover(
    entry: ProjectEntry,
    branding: BrandingConfig,
    site_name: str,
    source_label: str,
) -> str:
    """Build a chapter cover page using the Jinja template.

    Uses per-project overrides, falling back to top-level branding values.
    The PDF and HTML renderers share the same template variable contract;
    the PDF template is used here as the canonical source (renderers that
    need a different template, e.g. HTML, re-render from the same data
    via their own template in the page loop).
    """
    jinja = Environment(
        loader=PackageLoader("leafpress.pdf", "templates"),
        autoescape=True,
    )
    tmpl = jinja.get_template("chapter_cover.html.j2")

    return tmpl.render(
        title=site_name,
        subtitle=entry.subtitle or branding.subtitle or "",
        source_label=source_label,
        author=entry.author or branding.author or "",
        author_email=entry.author_email or branding.author_email or "",
        document_owner=entry.document_owner or branding.document_owner or "",
        review_cycle=entry.review_cycle or branding.review_cycle or "",
    )
