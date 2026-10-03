"""Cover-page fields and footer text shared by every output format.

Each renderer used to assemble these itself, and they drifted: PDF and DOCX
honored ``footer.include_*`` and ``repo_url`` while HTML, EPUB, and ODT
ignored them. Building them here keeps all formats in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from leafpress.config import BrandingConfig
from leafpress.git_info import GitVersion

# Joins footer parts in every format (the credit itself contains a "·")
FOOTER_SEPARATOR = " - "
CREDIT = "Made with LeafPress · leafpress.dev"


def render_time(local_time: bool) -> datetime:
    """The "now" for cover and footer dates: UTC unless ``local_time``."""
    return datetime.now() if local_time else datetime.now(UTC)


def footer_parts(
    branding: BrandingConfig | None, git_info: GitVersion | None, now: datetime
) -> list[str]:
    """The footer's pieces, in order, as plain (unescaped) text.

    1. ``footer.custom_text``
    2. ``footer.repo_url``
    3. The version field: the enabled parts of tag, commit, commit date, and
       branch, joined by `` | ``
    4. ``Generated YYYY-MM-DD`` (if ``footer.include_render_date``)
    5. The leafpress credit

    Without a branding config, tag, commit, commit date, and render date are
    shown. Callers join the parts with :data:`FOOTER_SEPARATOR`, escaping each
    one for their format (custom text may come from an untrusted repo).
    """
    footer = branding.footer if branding else None
    parts: list[str] = []
    if footer and footer.custom_text:
        parts.append(footer.custom_text)
    if footer and footer.repo_url:
        parts.append(footer.repo_url)
    if git_info:
        version: list[str] = []
        if (footer is None or footer.include_tag) and git_info.tag:
            distance = git_info.tag_distance
            version.append(f"{git_info.tag}+{distance}" if distance else git_info.tag)
        if footer is None or footer.include_commit:
            version.append(git_info.commit_hash)
        if footer is None or footer.include_date:
            version.append(git_info.commit_date.strftime("%Y-%m-%d"))
        if footer and footer.include_branch:
            version.append(git_info.branch)
        if version:
            parts.append(" | ".join(version))
    if footer is None or footer.include_render_date:
        parts.append(f"Generated {now.strftime('%Y-%m-%d')}")
    parts.append(CREDIT)
    return parts


@dataclass(frozen=True)
class CoverFields:
    """Text shown on the cover page, with branding fallbacks applied."""

    company_name: str
    project_name: str
    subtitle: str
    author: str
    author_email: str
    document_owner: str
    review_cycle: str
    date: str  # e.g. "October 03, 2026"

    @classmethod
    def build(cls, branding: BrandingConfig | None, site_name: str, now: datetime) -> CoverFields:
        """Cover text from branding; the title falls back to the MkDocs site name."""
        b = branding
        return cls(
            company_name=b.company_name if b else "",
            project_name=b.project_name if b else site_name,
            subtitle=(b.subtitle or "") if b else "",
            author=(b.author or "") if b else "",
            author_email=(b.author_email or "") if b else "",
            document_owner=(b.document_owner or "") if b else "",
            review_cycle=(b.review_cycle or "") if b else "",
            date=now.strftime("%B %d, %Y"),
        )

    def template_context(self) -> dict[str, str]:
        """Keyword arguments for the ``cover.html.j2`` templates."""
        return {
            "company_name": self.company_name,
            "project_name": self.project_name,
            "subtitle": self.subtitle,
            "author": self.author,
            "author_email": self.author_email,
            "document_owner": self.document_owner,
            "review_cycle": self.review_cycle,
            "date": self.date,
        }
