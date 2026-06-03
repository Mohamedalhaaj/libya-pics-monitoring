from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from utils.models import Article, SourceVerification


ARTICLE_FIELDS = [
    "source_id",
    "source_name",
    "language",
    "country_focus",
    "title",
    "url",
    "published_at",
    "summary",
    "section",
    "section_guess",
    "raw_date",
    "date_source",
    "collection_url",
    "matched_keywords",
]

VERIFICATION_FIELDS = [
    "source_id",
    "source_name",
    "url",
    "status",
    "articles_found",
    "pages_checked",
    "links_found",
    "candidates_found",
    "date_uncertain_items",
    "zero_reason",
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


def write_word_report(articles: list[Article], verifications: list[SourceVerification], path: str | Path) -> None:
    document = Document()
    title = document.add_heading("UNSMIL/PICS Daily Libya Media Monitoring Report", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_paragraph(f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z")
    document.add_paragraph(f"Total relevant items: {len(articles)}")

    document.add_heading("Headlines", level=1)
    if not articles:
        document.add_paragraph("No matching Libya-related articles were collected for the selected date range.")
    for article in articles:
        heading = document.add_heading(article.title, level=2)
        if article.language == "ar":
            heading.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        metadata = document.add_paragraph()
        metadata.add_run("Source: ").bold = True
        metadata.add_run(article.source_name)
        metadata.add_run(" | Language: ").bold = True
        metadata.add_run(article.language)
        metadata.add_run(" | Published: ").bold = True
        metadata.add_run(article.published_at.isoformat() if article.published_at else "Unknown")
        document.add_paragraph(article.summary or "No summary available.")
        document.add_paragraph(article.url)

    document.add_heading("Source Verification", level=1)
    table = document.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    headers = ["Source", "URL", "Status", "Articles", "Error"]
    for index, header in enumerate(headers):
        table.rows[0].cells[index].text = header
    for verification in verifications:
        cells = table.add_row().cells
        cells[0].text = verification.source_name
        cells[1].text = verification.url
        cells[2].text = verification.status
        cells[3].text = str(verification.articles_found)
        cells[4].text = verification.error

    document.save(path)
