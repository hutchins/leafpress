"""Conversion pipeline orchestrator."""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import dotenv_values
from jinja2 import Environment, PackageLoader
from rich.console import Console
from rich.markup import escape
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from leafpress.asset_policy import AssetPolicy, is_public_host, is_within
from leafpress.base_renderer import build_asset_policy
from leafpress.config import (
    BrandingConfig,
    MermaidConfig,
    ProjectEntry,
    WatermarkConfig,
    config_from_env,
    env_bool,
    load_config,
    resolve_mermaid_config,
)
from leafpress.exceptions import LeafpressError, RenderError, SourceError
from leafpress.git_info import GitVersion, extract_git_info
from leafpress.markdown_renderer import MarkdownRenderer
from leafpress.mkdocs_parser import (
    MkDocsConfig,
    NavItem,
    bump_nav_levels,
    find_site_config,
    flatten_nav,
    is_zensical_config,
    parse_mkdocs_config,
    resolve_page_path,
)
from leafpress.render_errors import format_render_error
from leafpress.sanitize import sanitize_html as sanitize
from leafpress.sanitize import should_sanitize
from leafpress.source import redact_url, resolve_source

# Used when convert() is not given a console (the CLI's case)
_default_console = Console()


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
        msg = escape(self.format(record))
        if record.levelno >= logging.ERROR:
            self._console.print(f"  [red]✗ {msg}[/red]")
        elif record.levelno >= logging.WARNING:
            self._console.print(f"  [yellow]⚠ {msg}[/yellow]")
        elif record.levelno >= logging.INFO:
            self._console.print(f"  {msg}")
        else:
            self._console.print(f"  [dim]{msg}[/dim]")


_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _resolve_log_level(verbose: bool, con: Console) -> int:
    """Pick the console log level: ``--verbose``, then ``LEAFPRESS_LOG_LEVEL``, then WARNING.

    ``LEAFPRESS_LOG_LEVEL`` accepts DEBUG, INFO, WARNING, ERROR, or CRITICAL
    (case-insensitive) and is handy in CI where adding ``--verbose`` isn't.
    """
    if verbose:
        return logging.DEBUG
    raw = os.environ.get("LEAFPRESS_LOG_LEVEL", "").strip().upper()
    if not raw:
        return logging.WARNING
    if raw not in _LOG_LEVELS:
        con.print(
            f"  [yellow]⚠ Ignoring invalid LEAFPRESS_LOG_LEVEL={escape(raw)!s}; "
            f"expected one of {', '.join(sorted(_LOG_LEVELS))}[/yellow]"
        )
        return logging.WARNING
    return _LOG_LEVELS[raw]


@dataclass(frozen=True)
class _OutputFormat:
    """One output format and the ``--format`` values that produce it."""

    label: str  # shown in progress messages and error text, e.g. "PDF"
    extension: str
    selected_by: frozenset[str]
    load_renderer: Callable[[], Any]  # imported lazily: some need optional extras
    takes_asset_policy: bool = True


def _load_pdf_renderer() -> Any:
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
    return PdfRenderer


def _load_docx_renderer() -> Any:
    from leafpress.docx.renderer import DocxRenderer

    return DocxRenderer


def _load_html_renderer() -> Any:
    from leafpress.html.renderer import HtmlRenderer

    return HtmlRenderer


def _load_odt_renderer() -> Any:
    from leafpress.odt.renderer import OdtRenderer

    return OdtRenderer


def _load_epub_renderer() -> Any:
    from leafpress.epub.renderer import EpubRenderer

    return EpubRenderer


def _load_markdown_renderer() -> Any:
    from leafpress.markdown_export.renderer import MarkdownExportRenderer

    return MarkdownExportRenderer


# Generated in this order; "both" is the legacy PDF + DOCX choice
_OUTPUT_FORMATS: tuple[_OutputFormat, ...] = (
    _OutputFormat("PDF", "pdf", frozenset({"pdf", "both", "all"}), _load_pdf_renderer),
    _OutputFormat("DOCX", "docx", frozenset({"docx", "both", "all"}), _load_docx_renderer),
    _OutputFormat("HTML", "html", frozenset({"html", "all"}), _load_html_renderer),
    _OutputFormat("ODT", "odt", frozenset({"odt", "all"}), _load_odt_renderer),
    _OutputFormat("EPUB", "epub", frozenset({"epub", "all"}), _load_epub_renderer),
    _OutputFormat(
        "Markdown",
        "md",
        frozenset({"markdown", "all"}),
        _load_markdown_renderer,
        takes_asset_policy=False,
    ),
)


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
    mermaid: bool | None = None,
    sanitize_html: bool | None = None,
    verbose: bool = False,
    console: Console | None = None,
) -> list[Path]:
    """Main conversion pipeline.

    Args:
        source: Local path or git URL to an MkDocs project.
        output_dir: Directory for generated output files.
        format: Output format - "pdf", "docx", "html", "odt", "epub",
            "markdown", "both" (PDF + DOCX), or "all".
        config_path: Optional path to leafpress branding config YAML.
        mkdocs_config_path: Optional override path to mkdocs.yml.
        branch: Git branch to clone (only for git URL sources).
        cover_page: Include a cover page.
        include_toc: Include a table of contents.
        local_time: Use local time instead of UTC for dates (also
            ``LEAFPRESS_LOCAL_TIME``).
        watermark: Override the watermark text.
        footer_render_date: Override include_render_date in footer config.
        mermaid: Override whether mermaid diagrams are rendered (None = use config).
        sanitize_html: Override HTML sanitizing (None = on for git URL sources,
            else ``LEAFPRESS_SANITIZE_HTML`` / leafpress.yml ``sanitize_html``).
        verbose: Enable verbose output (surfaces DEBUG-level log messages).
        console: Where progress and warnings are printed (default: stdout).
            The desktop app passes one that writes to its log panel.

    Returns:
        List of generated output file paths.
    """
    con = console or _default_console
    # --local-time wins; otherwise LEAFPRESS_LOCAL_TIME=true turns it on
    local_time = local_time or env_bool("LEAFPRESS_LOCAL_TIME") is True

    # Attach a handler that routes leafpress logger warnings to the console.
    # This surfaces logger.warning() calls from renderers (SVG logo skip,
    # extension failures, etc.) that would otherwise be invisible.
    log_level = _resolve_log_level(verbose, con)
    _log_handler = _ConsoleWarningHandler(con)
    _log_handler.setLevel(log_level)
    _pkg_logger = logging.getLogger("leafpress")
    _prev_log_level = _pkg_logger.level
    _pkg_logger.addHandler(_log_handler)
    _pkg_logger.setLevel(log_level)

    # Cleanup (log handler, cloned repos, mermaid temp dir) runs on success
    # and on error, in reverse order of registration. The handler callbacks
    # are registered first so a failed clone still detaches it.
    with contextlib.ExitStack() as cleanup:
        cleanup.callback(_pkg_logger.setLevel, _prev_log_level)
        cleanup.callback(_pkg_logger.removeHandler, _log_handler)
        resolved_source = resolve_source(source, branch)
        # A cloned repo is someone else's content: don't trust its .env or let
        # its leafpress.yml point monorepo projects at local directories outside it.
        untrusted_source = resolved_source.is_temporary
        project_dir = cleanup.enter_context(resolved_source)
        if not untrusted_source:
            # Removed again when this run ends, so a long-lived process (the
            # desktop UI) doesn't carry one project's settings into the next
            loaded_env = _load_project_env(project_dir / ".env")
            cleanup.callback(_unset_env, loaded_env)

        # Branding is loaded before mkdocs.yml so monorepo mode can skip it
        branding = _load_branding(config_path, project_dir, con)
        # A leafpress.yml auto-detected inside a cloned repo is untrusted; an
        # explicit -c file and LEAFPRESS_* env vars come from the operator.
        repo_config_untrusted = untrusted_source and config_path is None
        if branding is not None and repo_config_untrusted:
            branding = _confine_untrusted_paths(branding, project_dir, con)

        monorepo = branding if branding is not None and branding.projects else None
        mkdocs_cfg = _load_site_config(project_dir, mkdocs_config_path, monorepo, con)
        branding = _apply_cli_overrides(branding, mkdocs_cfg, watermark, footer_render_date)
        _report_branding(branding, con)
        git_info = _detect_version(project_dir, con)

        # Initialize temp dir for mermaid images
        mermaid_dir = Path(tempfile.mkdtemp(prefix="leafpress-mermaid-"))
        cleanup.callback(shutil.rmtree, mermaid_dir, ignore_errors=True)
        mermaid_cfg = resolve_mermaid_config(branding, enabled_override=mermaid)
        # An untrusted repo config can't aim rendering at internal hosts; an
        # operator-set LEAFPRESS_MERMAID_SERVER (e.g. self-hosted) is trusted.
        mermaid_public_only = repo_config_untrusted and not os.environ.get(
            "LEAFPRESS_MERMAID_SERVER"
        )
        config_sanitize = bool(branding and branding.sanitize_html)
        sanitize_pages = should_sanitize(
            cli_override=sanitize_html,
            untrusted_source=untrusted_source,
            config_value=config_sanitize,
        )
        if sanitize_pages:
            con.print("  [dim]Sanitizing page HTML (scripts and event handlers removed)[/dim]")
        if not mermaid_cfg.enabled:
            con.print("  [dim]Mermaid rendering disabled; diagrams kept as code[/dim]")
        # Local files that document content may embed (monorepo projects are
        # added as they are resolved)
        asset_policy = build_asset_policy(
            mkdocs_cfg, branding, extra_roots=[project_dir, mermaid_dir]
        )

        if monorepo is not None:
            config_dir = config_path.parent if config_path else project_dir
            html_pages, page_count = _collect_monorepo_pages(
                monorepo.projects,
                config_dir,
                mermaid_dir,
                monorepo,
                con,
                mermaid_cfg=mermaid_cfg,
                sanitize_override=sanitize_html,
                config_sanitize=config_sanitize,
                asset_policy=asset_policy,
                untrusted_source=untrusted_source,
                resources=cleanup,
                mermaid_public_only=mermaid_public_only,
                source_root=project_dir,
            )
            con.print(
                f"  [green]Projects:[/green] {len(monorepo.projects)} ({page_count} documents)\n"
            )
        else:
            renderer = _make_md_renderer(
                mkdocs_cfg,
                mermaid_dir,
                mermaid_cfg,
                mermaid_public_only=mermaid_public_only,
                asset_roots=[project_dir],
                con=con,
            )
            html_pages = _render_single_project(mkdocs_cfg, renderer, sanitize_pages, con)

        return _write_outputs(
            html_pages,
            format,
            output_dir,
            _safe_filename(mkdocs_cfg.site_name),
            branding=branding,
            git_info=git_info,
            mkdocs_cfg=mkdocs_cfg,
            asset_policy=asset_policy,
            cover_page=cover_page,
            include_toc=include_toc,
            local_time=local_time,
            con=con,
        )


def _load_branding(
    config_path: Path | None, project_dir: Path, con: Console
) -> BrandingConfig | None:
    """Load ``-c`` config, else an auto-detected leafpress.yml, else ``LEAFPRESS_*`` env vars."""
    if config_path:
        return load_config(config_path)
    for name in ("leafpress.yml", "leafpress.yaml"):
        candidate = project_dir / name
        if candidate.exists():
            con.print(f"  [green]Config:[/green] Auto-detected {candidate.name}")
            return load_config(candidate)
    return config_from_env()


def _load_site_config(
    project_dir: Path,
    explicit_path: Path | None,
    monorepo: BrandingConfig | None,
    con: Console,
) -> MkDocsConfig:
    """Parse the site config (mkdocs.yml or zensical.toml).

    A monorepo needs no top-level site config; without an explicit one, a
    minimal config named after the branding project is synthesized.
    """
    if monorepo is not None and explicit_path is None:
        return MkDocsConfig(
            site_name=monorepo.project_name,
            docs_dir=project_dir,
            nav_items=[],
            markdown_extensions=[],
            theme_name=None,
            extra_css=[],
            config_path=project_dir / "mkdocs.yml",
        )
    with con.status("[bold blue]Parsing MkDocs configuration..."):
        config_file = explicit_path or _find_mkdocs_config(project_dir, con)
        mkdocs_cfg = parse_mkdocs_config(config_file)
    con.print(f"  [green]Site:[/green] {mkdocs_cfg.site_name}")
    return mkdocs_cfg


def _apply_cli_overrides(
    branding: BrandingConfig | None,
    mkdocs_cfg: MkDocsConfig,
    watermark: str | None,
    footer_render_date: bool | None,
) -> BrandingConfig | None:
    """Apply ``--watermark`` and ``--footer-date``, which win over any config."""
    if watermark and branding:
        branding = branding.model_copy(
            update={"watermark": branding.watermark.model_copy(update={"text": watermark})}
        )
    elif watermark:
        # No branding config at all: a watermark alone still needs one
        branding = BrandingConfig(
            company_name=mkdocs_cfg.site_name,
            project_name=mkdocs_cfg.site_name,
            watermark=WatermarkConfig(text=watermark),
        )
    if footer_render_date is not None and branding:
        branding = branding.model_copy(
            update={
                "footer": branding.footer.model_copy(
                    update={"include_render_date": footer_render_date}
                )
            }
        )
    return branding


def _report_branding(branding: BrandingConfig | None, con: Console) -> None:
    """Print the branding summary (names, logo status, watermark)."""
    if not branding:
        return
    con.print(f"  [green]Branding:[/green] {branding.company_name} / {branding.project_name}")
    if branding.logo_path:
        logo = branding.logo_path
        if logo.startswith(("http://", "https://")) or Path(logo).exists():
            con.print(f"  [green]✓[/green] Logo: {logo}")
        else:
            con.print(f"  [yellow]⚠[/yellow] Logo not found: {logo}")
    if branding.watermark.text:
        con.print(f'  [green]Watermark:[/green] "{branding.watermark.text}"')


def _detect_version(project_dir: Path, con: Console) -> GitVersion | None:
    """Git info for the cover and footer, with the package version folded in."""
    from leafpress.package_version import detect_package_version

    git_info = extract_git_info(project_dir)
    pkg_ver = detect_package_version(project_dir)
    if git_info and pkg_ver:
        git_info = dataclasses.replace(git_info, package_version=pkg_ver)
    if git_info:
        con.print(f"  [green]Version:[/green] {git_info.format_version_string()}")
    elif pkg_ver:
        con.print(f"  [green]Version:[/green] {pkg_ver}")
    return git_info


def _make_md_renderer(
    mkdocs_cfg: MkDocsConfig,
    mermaid_dir: Path,
    mermaid_cfg: MermaidConfig,
    *,
    mermaid_public_only: bool,
    asset_roots: list[Path],
    con: Console,
) -> MarkdownRenderer:
    """Build the Markdown renderer for one project and report its extensions."""
    renderer = MarkdownRenderer(
        extensions=mkdocs_cfg.markdown_extensions,
        docs_dir=mkdocs_cfg.docs_dir,
        mermaid_output_dir=mermaid_dir if mermaid_cfg.enabled else None,
        mermaid_server=mermaid_cfg.server,
        mermaid_public_only=mermaid_public_only,
        project_root=mkdocs_cfg.config_path.parent,
        asset_roots=asset_roots,
    )
    for ext, ok, err_msg in renderer.extension_load_results:
        if ok:
            con.print(f"  [green]✓[/green] Extension: {ext}")
        else:
            hint = ""
            if "No module named" in err_msg:
                pkg = _pip_package_for(ext)
                hint = f"\n    Tip: pip install {pkg}  (or uv pip install {pkg})"
            con.print(
                f"  [yellow]⚠[/yellow] Skipping unavailable extension: {ext}"
                f"\n    Error: {err_msg}{hint}"
            )
    for warning in renderer.config_warnings:
        con.print(f"  [yellow]⚠[/yellow] {warning}")
    return renderer


def _render_single_project(
    mkdocs_cfg: MkDocsConfig,
    renderer: MarkdownRenderer,
    sanitize_pages: bool,
    con: Console,
) -> list[tuple[NavItem, str]]:
    """Render a single project's nav to HTML with a progress bar."""
    items = flatten_nav(mkdocs_cfg.nav_items)
    page_count = sum(1 for p in items if p.path is not None)
    con.print(f"  [green]Pages:[/green] {page_count} documents to convert\n")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=con,
    ) as progress:
        task = progress.add_task("Converting Markdown to HTML", total=page_count)
        html_pages, _ = _render_nav_pages(
            items,
            renderer,
            mkdocs_cfg.docs_dir,
            sanitize_pages=sanitize_pages,
            con=con,
            on_page=lambda: progress.update(task, advance=1),
        )
    return html_pages


def _render_nav_pages(
    items: list[NavItem],
    renderer: MarkdownRenderer,
    docs_dir: Path,
    *,
    sanitize_pages: bool,
    con: Console,
    site_label: str | None = None,
    on_page: Callable[[], None] | None = None,
) -> tuple[list[tuple[NavItem, str]], int]:
    """Render flattened nav items to HTML, shared by single-project and monorepo mode.

    Section headers (no path) are kept with an empty body. Pages outside
    ``docs_dir`` or missing on disk are skipped with a warning. Missing
    images and other assets are summarized at the end.

    Args:
        site_label: Project name added to warnings (monorepo chapters).
        on_page: Called once per nav page, rendered or skipped (progress bar).

    Returns:
        (rendered pages, number of pages actually rendered).
    """
    where = f" (in {site_label})" if site_label else ""
    html_pages: list[tuple[NavItem, str]] = []
    unresolved: list[tuple[str, str]] = []
    rendered = 0
    for item in items:
        if item.path is None:
            html_pages.append((item, ""))
            continue
        md_file = resolve_page_path(docs_dir, item.path)
        if md_file is None:
            con.print(
                f"  [yellow]Warning:[/yellow] Skipping page outside docs_dir: {item.path}{where}"
            )
        elif not md_file.exists():
            con.print(f"  [yellow]Warning:[/yellow] File not found: {item.path}{where}")
        else:
            html, render_warnings = renderer.render(md_file.read_text(encoding="utf-8"), md_file)
            if sanitize_pages:
                html = sanitize(html)
            for w in render_warnings:
                if "failed" in w:
                    con.print(f"  [yellow]⚠ {w}[/yellow]")
                else:
                    con.print(f"  [green]✓ {w}[/green]")
            unresolved.extend(renderer.unresolved_assets)
            html_pages.append((dataclasses.replace(item, source_file=md_file), html))
            rendered += 1
        if on_page is not None:
            on_page()

    if unresolved:
        scope = f"in {site_label}" if site_label else "found"
        con.print(f"  [yellow]⚠[/yellow] {len(unresolved)} missing asset(s) {scope}:")
        for page, ref in unresolved:
            con.print(f"    [yellow]•[/yellow] {Path(page).name}: {ref}")
    return html_pages, rendered


def _write_outputs(
    html_pages: list[tuple[NavItem, str]],
    format: str,
    output_dir: Path,
    base_name: str,
    *,
    branding: BrandingConfig | None,
    git_info: GitVersion | None,
    mkdocs_cfg: MkDocsConfig,
    asset_policy: AssetPolicy,
    cover_page: bool,
    include_toc: bool,
    local_time: bool,
    con: Console,
) -> list[Path]:
    """Run every output renderer selected by ``format``; return the files written.

    Unexpected renderer exceptions become a :class:`RenderError` with a
    format-specific explanation; leafpress's own errors pass through.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for spec in _OUTPUT_FORMATS:
        if format not in spec.selected_by:
            continue
        renderer_cls = spec.load_renderer()
        out_path = output_dir / f"{base_name}.{spec.extension}"
        extra = {"asset_policy": asset_policy} if spec.takes_asset_policy else {}
        with con.status(f"[bold blue]Generating {spec.label}..."):
            try:
                renderer_cls(branding, git_info, mkdocs_cfg, **extra).render(
                    html_pages,
                    out_path,
                    cover_page=cover_page,
                    include_toc=include_toc,
                    local_time=local_time,
                )
            except LeafpressError:
                raise
            except Exception as exc:
                raise RenderError(format_render_error(spec.label, exc)) from exc
        generated.append(out_path)
        con.print(f"  [bold green]{spec.label}:[/bold green] {out_path}")
    return generated


def _find_mkdocs_config(project_dir: Path, con: Console | None = None) -> Path:
    """Locate mkdocs.yml/mkdocs.yaml, or (experimentally) zensical.toml."""
    config_path = find_site_config(project_dir)
    if config_path is None:
        raise LeafpressError(f"No mkdocs.yml, mkdocs.yaml, or zensical.toml found in {project_dir}")
    out = con or _default_console
    if is_zensical_config(config_path):
        out.print(f"  [dim]Using {config_path.name} (experimental Zensical support)[/dim]")
    elif (project_dir / "zensical.toml").is_file():
        out.print(
            f"  [dim]Both {config_path.name} and zensical.toml found; using {config_path.name}. "
            "Pass --mkdocs-config zensical.toml to use the Zensical config.[/dim]"
        )
    return config_path


def _safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()


def _confine_untrusted_paths(
    branding: BrandingConfig, project_dir: Path, con: Console
) -> BrandingConfig:
    """Drop local files named by an untrusted repo config that lie outside the repo.

    Otherwise a cloned repo could pull any readable local file into the
    output: a key or ``/proc/self/environ`` as its ``logo_path``, or one of
    your own Word documents as ``docx.template_path`` (a template's body is
    kept). A logo set via ``LEAFPRESS_LOGO_PATH`` comes from the operator and
    is kept.
    """
    logo = branding.logo_path
    if (
        logo
        and not logo.startswith(("http://", "https://"))
        and not os.environ.get("LEAFPRESS_LOGO_PATH")
        and not is_within(Path(logo), project_dir)
    ):
        con.print(
            f"  [yellow]⚠[/yellow] Ignoring logo_path outside the cloned repository: {escape(logo)}"
        )
        branding = branding.model_copy(update={"logo_path": None})
    template = branding.docx.template_path
    if template and not is_within(Path(template), project_dir):
        con.print(
            "  [yellow]⚠[/yellow] Ignoring docx.template_path outside the cloned repository: "
            f"{escape(str(template))}"
        )
        branding = branding.model_copy(
            update={"docx": branding.docx.model_copy(update={"template_path": None})}
        )
    return branding


# Module prefix -> PyPI package, where they differ
_EXTENSION_PACKAGES = {
    "pymdownx": "pymdown-extensions",
    "material": "mkdocs-material",
    "mdx_truly_sane_lists": "mdx-truly-sane-lists",
    "markdown_include": "markdown-include",
    "plantuml_markdown": "plantuml-markdown",
    "zensical": "zensical",
}


def _pip_package_for(extension: str) -> str:
    """Best guess at the PyPI package providing a Markdown extension module."""
    module = extension.split(":", 1)[0].split(".")[0]
    return _EXTENSION_PACKAGES.get(module, module.replace("_", "-"))


def _git_url_host(url: str) -> str:
    """Host of a git URL: ``https://h/...``, ``ssh://u@h:p/...``, or scp-style ``git@h:path``."""
    if "://" in url:
        return urlsplit(url).hostname or ""
    match = re.match(r"^[^@/\s]+@([^:/\s]+):", url)
    return match.group(1) if match else ""


def _load_project_env(env_file: Path) -> list[str]:
    """Load ``LEAFPRESS_*`` settings from a project's ``.env`` file.

    Only leafpress settings are read, so a ``.env`` can't set variables such as
    ``GIT_SSH_COMMAND`` that change how git or other tools behave. Values
    already set in the shell take priority.

    Returns:
        The variable names that were set, so the caller can remove them.
    """
    if not env_file.is_file():
        return []
    loaded: list[str] = []
    for key, value in dotenv_values(env_file).items():
        if key.startswith("LEAFPRESS_") and value is not None and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def _unset_env(keys: list[str]) -> None:
    """Remove environment variables set by :func:`_load_project_env`."""
    for key in keys:
        os.environ.pop(key, None)


def _collect_monorepo_pages(
    projects: list[ProjectEntry],
    config_dir: Path,
    mermaid_output_dir: Path,
    branding: BrandingConfig,
    con: Console,
    mermaid_cfg: MermaidConfig | None = None,
    asset_policy: AssetPolicy | None = None,
    untrusted_source: bool = False,
    sanitize_override: bool | None = None,
    config_sanitize: bool = False,
    resources: contextlib.ExitStack | None = None,
    mermaid_public_only: bool = False,
    source_root: Path | None = None,
) -> tuple[list[tuple[NavItem, str]], int]:
    """Parse and render pages from multiple MkDocs projects.

    Supports both local paths and git URL entries. Git repos are cloned to
    temporary directories registered on ``resources`` (the caller's cleanup
    stack), so their images still exist when the output is rendered.

    Returns (combined html_pages, total page count).
    """
    all_pages: list[tuple[NavItem, str]] = []
    total_pages = 0
    mermaid_cfg = mermaid_cfg or MermaidConfig()

    with contextlib.ExitStack() as local_stack:
        stack = resources if resources is not None else local_stack
        for entry in projects:
            # Resolve project directory (local path or git clone)
            if entry.url:
                if untrusted_source and not is_public_host(_git_url_host(entry.url)):
                    raise SourceError(
                        "Monorepo project url in a cloned repository must point to a "
                        f"public host: {redact_url(entry.url)}"
                    )
                resolved = stack.enter_context(resolve_source(entry.url, entry.branch))
                project_dir = resolved
                # Shown in the console and on the chapter cover page
                source_label = redact_url(entry.url)
            else:
                project_dir = (config_dir / entry.path).resolve()
                if untrusted_source and not is_within(project_dir, config_dir):
                    raise SourceError(
                        f"Monorepo project path escapes the cloned repository: {entry.path}"
                    )
                if not project_dir.is_dir():
                    raise SourceError(f"Monorepo project directory not found: {project_dir}")
                source_label = entry.path

            mkdocs_file = _find_mkdocs_config(project_dir, con)
            mkdocs_cfg = parse_mkdocs_config(mkdocs_file)
            # Projects cloned from a URL are untrusted even if the top-level
            # source is local
            sanitize_project = should_sanitize(
                cli_override=sanitize_override,
                untrusted_source=untrusted_source or bool(entry.url),
                config_value=config_sanitize,
            )
            if asset_policy is not None:
                asset_policy.add_root(project_dir)

            # Detect per-project version (no walk-up to avoid parent manifests)
            from leafpress.package_version import detect_package_version

            package_root = (config_dir / entry.root).resolve() if entry.root else project_dir
            if untrusted_source and not is_within(package_root, config_dir):
                raise SourceError(
                    f"Monorepo project root escapes the cloned repository: {entry.root}"
                )
            project_version = detect_package_version(package_root, walk_up=False)

            version_suffix = f" v{project_version}" if project_version else ""
            con.print(
                f"  [green]Chapter:[/green] {mkdocs_cfg.site_name}{version_suffix} ({source_label})"
            )

            # Chapter cover page with metadata
            chapter_html = _build_chapter_cover(
                entry, branding, mkdocs_cfg.site_name, source_label, project_version
            )
            chapter = NavItem(title=mkdocs_cfg.site_name, path=None, level=0)
            all_pages.append((chapter, chapter_html))

            renderer = _make_md_renderer(
                mkdocs_cfg,
                mermaid_output_dir,
                mermaid_cfg,
                mermaid_public_only=mermaid_public_only,
                asset_roots=[source_root] if source_root and not entry.url else [],
                con=con,
            )
            pages, rendered = _render_nav_pages(
                bump_nav_levels(flatten_nav(mkdocs_cfg.nav_items)),
                renderer,
                mkdocs_cfg.docs_dir,
                sanitize_pages=sanitize_project,
                con=con,
                site_label=mkdocs_cfg.site_name,
            )
            all_pages.extend(pages)
            total_pages += rendered

    return all_pages, total_pages


def _build_chapter_cover(
    entry: ProjectEntry,
    branding: BrandingConfig,
    site_name: str,
    source_label: str,
    version: str | None = None,
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
        version=version or "",
        author=entry.author or branding.author or "",
        author_email=entry.author_email or branding.author_email or "",
        document_owner=entry.document_owner or branding.document_owner or "",
        review_cycle=entry.review_cycle or branding.review_cycle or "",
    )
