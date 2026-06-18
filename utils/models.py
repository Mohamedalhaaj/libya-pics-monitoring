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
    subsection_guess: str = ""
    relevance_status: str = "unchecked"
    relevance_reason: str = ""
    date_status: str = "missing_date"
    duplicate_status: str = "unique"
    qa_status: str = "needs_review"
    qa_notes: str = ""
    include_candidate: bool = False
    duplicate_key: str = ""
    parser_used: str = ""
    notes: str = ""
    raw_date: str = ""
    date_source: str = ""
    collection_url: str = ""
    content_text: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    relevance_score: int = 0
    priority: str = ""
    source_tier: str = ""
    editorial_status: str = "unreviewed"
    editorial_reason: str = ""
    rejection_reason: str = ""
    story_id: str = ""

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
            "discovery_source": self.collection_url,
            "article_snippet": self.summary,
            "section_guess": self.section_guess,
            "subsection_guess": self.subsection_guess,
            "date_status": self.date_status,
            "relevance_status": self.relevance_status,
            "relevance_reason": self.relevance_reason,
            "relevance_score": self.relevance_score,
            "priority": self.priority,
            "source_tier": self.source_tier,
            "duplicate_status": self.duplicate_status,
            "story_id": self.story_id,
            "editorial_status": self.editorial_status,
            "editorial_reason": self.editorial_reason,
            "rejection_reason": self.rejection_reason,
            "qa_status": self.qa_status,
            "qa_notes": self.qa_notes,
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
    notes: str = ""
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
            "notes": self.notes,
            "checked_at": self.checked_at.isoformat(timespec="seconds") + "Z",
        }


@dataclass(slots=True)
class StoryCluster:
    story_id: str
    canonical_headline: str
    summary: str
    section: str
    priority: str
    relevance_score: int
    publication_date: str
    sources: list[str] = field(default_factory=list)
    article_urls: list[str] = field(default_factory=list)
    article_count: int = 0
    confidence: int = 0
    reason_for_inclusion: str = ""
    qa_status: str = "approved"
    qa_notes: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "story_id": self.story_id,
            "canonical_headline": self.canonical_headline,
            "summary": self.summary,
            "section": self.section,
            "priority": self.priority,
            "relevance_score": self.relevance_score,
            "publication_date": self.publication_date,
            "sources": "; ".join(self.sources),
            "article_urls": "; ".join(self.article_urls),
            "article_count": self.article_count,
            "confidence": self.confidence,
            "reason_for_inclusion": self.reason_for_inclusion,
            "qa_status": self.qa_status,
            "qa_notes": self.qa_notes,
        }


def make_duplicate_key(source_id: str, url: str, title: str) -> str:
    key_source = url or title
    return f"{source_id}:{key_source.strip().casefold()}"
