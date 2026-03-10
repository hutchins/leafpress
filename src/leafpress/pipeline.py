"""Conversion pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from dotenv import load_dotenv

from leafpress.config import BrandingConfig, config_from_env, load_config
from leafpress.docx.renderer import DocxRenderer
from leafpress.exceptions import LeafpressError
from leafpress.git_info import GitVersion, extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import (
    MkDocsConfig,
    NavItem,
    flatten_nav,
    parse_mkdocs_config,
)
from leafpress.pdf.renderer import PdfRenderer
from leafpress.source import resolve_source

console = Console()


def convert(
    source: str,
    output_dir: Path,
    format: str = "pdf",
    config_path: Optional[Path] = None,
    mkdocs_config_path: Optional[Path] = None,
    branch: Optional[str] = None,
    cover_page: bool = True,
    include_toc: bool = True,
) -> list[Path]:
    """Main conversion pipeline.

    Args:
        source: Local path or git URL to an MkDocs project.
        output_dir: Directory for generated output files.
        format: Output format - "pdf", "docx", or "both".
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
        branding: Optional[BrandingConfig] = None
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
        if branding:
            console.print(
                f"  [green]Branding:[/green] {branding.company_name} / {branding.project_name}"
            )

        # Extract git info
        git_info = extract_git_info(project_dir)
        if git_info:
            console.print(f"  [green]Version:[/green] {git_info.format_version_string()}")

        # Initialize markdown renderer
        renderer = MarkdownRenderer(
            extensions=mkdocs_cfg.markdown_extensions,
            docs_dir=mkdocs_cfg.docs_dir,
        )

        # Flatten nav
        pages = flatten_nav(mkdocs_cfg.nav_items)
        page_count = sum(1 for p in pages if p.path is not None)
        console.print(f"  [green]Pages:[/green] {page_count} documents to convert\n")

        # Convert Markdown -> HTML
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

        if format in ("pdf", "both"):
            pdf_path = output_dir / f"{safe_name}.pdf"
            with console.status("[bold blue]Generating PDF..."):
                pdf_renderer = PdfRenderer(branding, git_info, mkdocs_cfg)
                pdf_renderer.render(
                    html_pages,
                    pdf_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                )
            generated_files.append(pdf_path)
            console.print(f"  [bold green]PDF:[/bold green] {pdf_path}")

        if format in ("docx", "both"):
            docx_path = output_dir / f"{safe_name}.docx"
            with console.status("[bold blue]Generating DOCX..."):
                docx_renderer = DocxRenderer(branding, git_info, mkdocs_cfg)
                docx_renderer.render(
                    html_pages,
                    docx_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                )
            generated_files.append(docx_path)
            console.print(f"  [bold green]DOCX:[/bold green] {docx_path}")

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
