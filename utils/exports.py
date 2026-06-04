from __future__ import annotations

import csv
from pathlib import Path

from utils.models import Article, SourceVerification


ARTICLE_FIELDS = [
    "source_name",
    "source_language",
    "headline_original",
    "headline_english_placeholder",
    "article_url",
    "publication_date",
    "article_snippet",
    "section_guess",
    "relevance_reason",
    "date_status",
    "include_candidate",
    "duplicate_key",
    "parser_used",
    "notes",
]

VERIFICATION_FIELDS = [
    "source_name",
    "source_url",
    "fetch_status",
    "candidate_links_found",
    "article_pages_opened",
    "date_parsed_count",
    "accepted_count",
    "rejected_date_count",
    "rejected_relevance_count",
    "uncertain_date_count",
    "failed_count",
    "zero_result_reason",
    "error",
    "checked_at",
]


def ensure_output_dir(path: str | Path) -> Path:
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def write_articles_csv(articles: list[Article], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ARTICLE_FIELDS)
        writer.writeheader()
        for article in articles:
            writer.writerow(article.to_row())


def write_verification_csv(verifications: list[SourceVerification], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=VERIFICATION_FIELDS)
        writer.writeheader()
        for verification in verifications:
            writer.writerow(verification.to_row())


def write_date_uncertain_csv(articles: list[Article], path: str | Path) -> None:
    write_articles_csv(articles, path)
