from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow() -> datetime:
    # Naive UTC (datetime.utcnow() is deprecated in Python 3.12+).
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(slots=True)
class Article:
    source_id: str
    source_name: str
    language: str
    country_focus: str
    title: str
    url: str
    published_at: datetime | None = None
    summary: str = ""
    section: str = ""
    matched_keywords: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "language": self.language,
            "country_focus": self.country_focus,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else "",
            "summary": self.summary,
            "section": self.section,
            "matched_keywords": "; ".join(self.matched_keywords),
        }


@dataclass(slots=True)
class HeadlineSource:
    """A single outlet that reported a headline, as cited in the report."""

    name: str
    language: str = "en"
    url: str = ""

    def render(self) -> str:
        """`Source Name (Arabic)` style citation used in the Word report."""
        label = self.name
        if self.language == "ar":
            label = f"{label} (Arabic)"
        return label


@dataclass(slots=True)
class ReportHeadline:
    """One editorial bullet: an English headline plus its cited sources.

    `summary` is the short paragraph that follows Varieties feature items
    (Analysis | … / Feature | …) per the PICS SOP; empty for normal headlines.
    """

    text: str
    sources: list[HeadlineSource] = field(default_factory=list)
    summary: str = ""

    def render_sources(self) -> str:
        return " / ".join(source.render() for source in self.sources)


@dataclass(slots=True)
class ReportSubsection:
    name: str
    headlines: list[ReportHeadline] = field(default_factory=list)


@dataclass(slots=True)
class ReportSection:
    name: str
    subsections: list[ReportSubsection] = field(default_factory=list)


@dataclass(slots=True)
class StructuredReport:
    """A full editorial report ready to render in the PICS Word format."""

    report_date: str
    sections: list[ReportSection] = field(default_factory=list)

    def total_headlines(self) -> int:
        return sum(
            len(subsection.headlines)
            for section in self.sections
            for subsection in section.subsections
        )


@dataclass(slots=True)
class SourceVerification:
    source_id: str
    source_name: str
    url: str
    status: str
    articles_found: int = 0
    error: str = ""
    checked_at: datetime = field(default_factory=_utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "url": self.url,
            "status": self.status,
            "articles_found": self.articles_found,
            "error": self.error,
            "checked_at": self.checked_at.isoformat(timespec="seconds") + "Z",
        }
