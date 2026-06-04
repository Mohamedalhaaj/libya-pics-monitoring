from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    section_guess: str = ""
    relevance_reason: str = ""
    date_status: str = "missing_date"
    include_candidate: bool = False
    duplicate_key: str = ""
    parser_used: str = ""
    notes: str = ""
    raw_date: str = ""
    date_source: str = ""
    collection_url: str = ""
    matched_keywords: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.duplicate_key:
            self.duplicate_key = make_duplicate_key(self.source_id, self.url, self.title)

    def to_row(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_language": self.language,
            "headline_original": self.title,
            "headline_english_placeholder": "",
            "article_url": self.url,
            "publication_date": self.published_at.date().isoformat() if self.published_at else "",
            "article_snippet": self.summary,
            "section_guess": self.section_guess,
            "relevance_reason": self.relevance_reason,
            "date_status": self.date_status,
            "include_candidate": "yes" if self.include_candidate else "no",
            "duplicate_key": self.duplicate_key,
            "parser_used": self.parser_used,
            "notes": self.notes,
        }


@dataclass(slots=True)
class SourceVerification:
    source_name: str
    source_url: str
    fetch_status: str
    candidate_links_found: int = 0
    article_pages_opened: int = 0
    date_parsed_count: int = 0
    accepted_count: int = 0
    rejected_date_count: int = 0
    rejected_relevance_count: int = 0
    uncertain_date_count: int = 0
    failed_count: int = 0
    zero_result_reason: str = ""
    error: str = ""
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_row(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "fetch_status": self.fetch_status,
            "candidate_links_found": self.candidate_links_found,
            "article_pages_opened": self.article_pages_opened,
            "date_parsed_count": self.date_parsed_count,
            "accepted_count": self.accepted_count,
            "rejected_date_count": self.rejected_date_count,
            "rejected_relevance_count": self.rejected_relevance_count,
            "uncertain_date_count": self.uncertain_date_count,
            "failed_count": self.failed_count,
            "zero_result_reason": self.zero_result_reason,
            "error": self.error,
            "checked_at": self.checked_at.isoformat(timespec="seconds") + "Z",
        }


def make_duplicate_key(source_id: str, url: str, title: str) -> str:
    key_source = url or title
    return f"{source_id}:{key_source.strip().casefold()}"
