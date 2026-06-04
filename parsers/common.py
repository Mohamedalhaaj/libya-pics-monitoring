from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from utils.dates import parse_article_date
from utils.models import Article


NOISE_TEXT = {
    "home",
    "الرئيسية",
    "about",
    "about us",
    "من نحن",
    "contact",
    "contact us",
    "اتصل بنا",
    "privacy policy",
    "terms",
    "advertise",
    "login",
    "subscribe",
}

NOISE_URL_PARTS = (
    "facebook.com",
    "twitter.com",
    "x.com/",
    "instagram.com",
    "youtube.com",
    "whatsapp",
    "mailto:",
    "javascript:",
    "/tag/",
    "/tags/",
    "/category/",
    "/section/",
    "/author/",
    "/about",
    "/contact",
    "/privacy",
    "/terms",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
)


def clean_text(value: str) -> str:
    return " ".join(value.replace("\u200f", " ").replace("\u200e", " ").split())


def normalize_url(base_url: str, href: str, source_id: str = "") -> str:
    href = (href or "").strip()
    if not href:
        return base_url
    if href.startswith("ly.reportage://https"):
        href = "https://reportage.ly/"
    if href.startswith("reportage.ly://https") or href.startswith("https://reportage.ly://"):
        href = "https://reportage.ly/"
    normalized = urljoin(base_url, href)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return ""
    normalized = urlunparse(parsed._replace(fragment=""))
    if source_id == "rna_reportage" and not normalized.startswith("https://reportage.ly/"):
        reportage_path = parsed.path.lstrip("/")
        if reportage_path:
            normalized = urljoin("https://reportage.ly/", reportage_path)
    return normalized


def is_noise_link(title: str, url: str) -> bool:
    cleaned = clean_text(title).casefold()
    if len(cleaned) < 12 or cleaned in NOISE_TEXT:
        return True
    lowered_url = url.casefold()
    return any(part in lowered_url for part in NOISE_URL_PARTS)


def extract_date(item: Tag, selectors: dict[str, str]) -> tuple[object, str, str]:
    candidates: list[str] = []
    if selectors.get("date"):
        for node in item.select(selectors["date"]):
            candidates.extend(
                [
                    node.get("datetime") or "",
                    node.get("content") or "",
                    node.get_text(" ", strip=True),
                ]
            )
    for attr in ("datetime", "data-date", "data-time", "data-published", "title"):
        value = item.get(attr)
        if value:
            candidates.append(str(value))
    item_text = item.get_text(" ", strip=True)
    candidates.extend(find_date_like_text(item_text))
    for candidate in candidates:
        candidate = clean_text(candidate)
        parsed = parse_article_date(candidate)
        if parsed:
            return parsed, candidate, "markup"
    return None, "", ""


def find_date_like_text(text: str) -> list[str]:
    patterns = [
        r"\d{4}-\d{1,2}-\d{1,2}(?:T\d{1,2}:\d{2}:\d{2}Z?)?",
        r"\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر)\s+\d{4}",
        r"(?:منذ|قبل)\s+\d+\s+(?:دقيقة|دقائق|ساعة|ساعات|يوم|أيام)",
        r"\d+\s+(?:minute|minutes|hour|hours|day|days)\s+ago",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return matches


def build_article(
    source: dict,
    collection_url: str,
    parser_used: str,
    title: str,
    url: str,
    summary: str = "",
    section: str = "",
    published_at=None,
    raw_date: str = "",
    date_source: str = "",
    matched_keywords: list[str] | None = None,
) -> Article:
    return Article(
        source_id=source["id"],
        source_name=source["name"],
        language=source["language"],
        country_focus=source.get("country_focus", "Libya"),
        title=clean_text(title),
        url=url,
        published_at=published_at,
        summary=clean_text(summary),
        section=clean_text(section),
        raw_date=raw_date,
        date_source=date_source,
        collection_url=collection_url,
        parser_used=parser_used,
        matched_keywords=matched_keywords or [],
    )


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    normalized = text.casefold()
    return [keyword for keyword in keywords if keyword.casefold() in normalized]


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    seen: set[tuple[str, str]] = set()
    unique: list[Article] = []
    for article in articles:
        key = (article.source_id, article.url or article.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")
