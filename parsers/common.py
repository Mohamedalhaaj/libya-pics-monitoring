from __future__ import annotations

import re
import json
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


def is_probable_article_url(url: str, include_patterns: tuple[str, ...] = ()) -> bool:
    parsed = urlparse(url)
    path = parsed.path.casefold()
    if any(part in url.casefold() for part in NOISE_URL_PARTS):
        return False
    if include_patterns and any(pattern in path for pattern in include_patterns):
        return True
    if re.search(r"/20\d{2}/", path):
        return True
    path_parts = [part for part in path.split("/") if part]
    if len(path_parts) >= 1 and len(path_parts[-1]) >= 14:
        return True
    return False


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
        r"\d{4}/\d{1,2}/\d{1,2}",
        r"\d{1,2}[/-]\d{1,2}[/-]20\d{2}",
        r"(?:السبت|الأحد|الاحد|الإثنين|الاثنين|الثلاثاء|الأربعاء|الاربعاء|الخميس|الجمعة)\s+\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر)\s+\d{4}",
        r"\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر)\s+\d{4}",
        r"(?:تاريخ النشر|نشر في|آخر تحديث|آخر تحديث:)\s*[:：]?\s*[^|،\n]{0,60}\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر)\s+\d{4}",
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


def extract_article_page_details(html: str, article: Article) -> Article:
    soup = soup_from_html(html)
    title = first_text(
        soup,
        [
            "meta[property='og:title']",
            "meta[name='twitter:title']",
            "h1",
            ".entry-title",
            ".post-title",
            "title",
        ],
    )
    if title and len(title) > len(article.title):
        article.title = title

    summary = first_text(
        soup,
        [
            "meta[property='og:description']",
            "meta[name='description']",
            "meta[name='twitter:description']",
            ".entry-summary",
            ".post-excerpt",
            "article p",
            ".article-content p",
            ".content p",
        ],
    )
    if summary:
        article.summary = summary

    raw_dates = []
    raw_dates.extend(extract_json_ld_dates(soup))
    for selector in [
        "meta[property='article:published_time']",
        "meta[name='article:published_time']",
        "meta[name='date']",
        "meta[itemprop='datePublished']",
        "time",
        ".date",
        ".entry-date",
        ".post-date",
        ".article-date",
        ".news-date",
        ".date-display-single",
        ".published",
        ".timestamp",
        ".created",
        ".created-at",
        ".article-info",
        ".post-info",
        ".meta",
        ".metadata",
        "span[class*='date']",
        "div[class*='date']",
        "span[class*='time']",
        "div[class*='time']",
    ]:
        for node in soup.select(selector):
            raw_dates.extend(
                [
                    node.get("datetime") or "",
                    node.get("content") or "",
                    node.get_text(" ", strip=True),
                ]
            )
    raw_dates.extend(find_date_like_text(soup.get_text(" ", strip=True)[:15000]))
    for raw_date in raw_dates:
        raw_date = clean_text(raw_date)
        parsed = parse_article_date(raw_date)
        if parsed:
            article.published_at = parsed
            article.raw_date = raw_date
            article.date_source = "article_page"
            break
    return article


def extract_json_ld_dates(soup: BeautifulSoup) -> list[str]:
    dates: list[str] = []
    for node in soup.select("script[type='application/ld+json']"):
        raw = node.string or node.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in flatten_json_ld(payload):
            if not isinstance(item, dict):
                continue
            for key in ("datePublished", "dateCreated", "dateModified", "uploadDate"):
                value = item.get(key)
                if isinstance(value, str):
                    dates.append(value)
    return dates


def flatten_json_ld(payload):
    if isinstance(payload, list):
        for item in payload:
            yield from flatten_json_ld(item)
    elif isinstance(payload, dict):
        yield payload
        graph = payload.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                yield from flatten_json_ld(item)


def page_metadata_flags(html: str) -> tuple[bool, bool, list[str]]:
    soup = soup_from_html(html)
    has_json_ld = bool(soup.select("script[type='application/ld+json']"))
    has_open_graph = bool(soup.select("meta[property^='og:'], meta[property^='article:']"))
    dates = extract_json_ld_dates(soup)
    dates.extend(find_date_like_text(soup.get_text(" ", strip=True)[:3000]))
    return has_json_ld, has_open_graph, [clean_text(date) for date in dates if clean_text(date)]


def extract_structured_links(soup: BeautifulSoup, base_url: str, source_id: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for selector in ["link[rel='canonical']", "meta[property='og:url']", "meta[name='twitter:url']"]:
        for node in soup.select(selector):
            href = node.get("href") or node.get("content") or ""
            url = normalize_url(base_url, href, source_id)
            if url:
                title = first_text(soup, ["meta[property='og:title']", "meta[name='twitter:title']", "title"])
                links.append((title or url, url))

    for node in soup.select("script[type='application/ld+json']"):
        raw = node.string or node.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in flatten_json_ld(payload):
            if not isinstance(item, dict):
                continue
            title = str(item.get("headline") or item.get("name") or "")
            value = item.get("url") or item.get("mainEntityOfPage")
            if isinstance(value, dict):
                value = value.get("@id")
            if isinstance(value, str):
                url = normalize_url(base_url, value, source_id)
                if url:
                    links.append((title or url, url))
    return links


def first_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
        value = clean_text(value or "")
        if value:
            return value
    return ""


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
