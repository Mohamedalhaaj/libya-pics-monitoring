"""Resolve precise article metadata from article pages.

Listing pages rarely expose a reliable publication date — a card may show a
relative time ("2h ago") or even a date that belongs to the story (e.g. a
future election date), which is how wrong dates slipped into reports. Article
pages, by contrast, almost always carry a machine-readable
`article:published_time` / JSON-LD `datePublished`. This module fetches the
article pages (concurrently) and fills in the real date, so date-window
filtering can be trusted without a manual link-check.
"""

from __future__ import annotations

import asyncio
import json
import logging

from bs4 import BeautifulSoup

from utils.dates import parse_article_date
from utils.fetcher import BrowserFetcher
from utils.models import Article

logger = logging.getLogger(__name__)

# Meta tags (property or name) that carry a publication timestamp, best first.
_DATE_META = (
    "article:published_time",
    "article:modified_time",
    "og:article:published_time",
    "datePublished",
    "publish-date",
    "pubdate",
    "date",
)


def _meta(soup: BeautifulSoup, key: str) -> str | None:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    if tag and tag.get("content"):
        return tag["content"]
    tag = soup.find("meta", attrs={"itemprop": key})
    if tag and tag.get("content"):
        return tag["content"]
    return None


def _jsonld_date(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.text or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _iter_ld_nodes(data):
            if isinstance(node, dict) and node.get("datePublished"):
                return node["datePublished"]
    return None


def _iter_ld_nodes(data):
    if isinstance(data, list):
        for item in data:
            yield from _iter_ld_nodes(item)
    elif isinstance(data, dict):
        yield data
        if "@graph" in data:
            yield from _iter_ld_nodes(data["@graph"])


def extract_published_date(html: str):
    """Pull a publication datetime from an article page's HTML, or None."""
    soup = BeautifulSoup(html, "html.parser")
    for key in _DATE_META:
        value = _meta(soup, key)
        parsed = parse_article_date(value)
        if parsed:
            return parsed
    parsed = parse_article_date(_jsonld_date(soup))
    if parsed:
        return parsed
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        return parse_article_date(time_tag["datetime"])
    return None


async def resolve_articles(
    fetcher: BrowserFetcher,
    articles: list[Article],
    concurrency: int = 6,
) -> int:
    """Fill `published_at` for each article from its own page, concurrently.

    Updates articles in place; returns how many gained or corrected a date.
    Articles without a URL are skipped. Failures are logged and left as-is.
    """
    targets = [a for a in articles if a.url]
    if not targets:
        return 0

    semaphore = asyncio.Semaphore(max(1, concurrency))
    resolved = 0

    async def resolve_one(article: Article) -> None:
        nonlocal resolved
        async with semaphore:
            try:
                result = await fetcher.fetch(article.url, settle=False)
            except Exception as exc:  # noqa: BLE001 - per-article best effort
                logger.debug("Could not resolve %s: %s", article.url, exc)
                return
            published = extract_published_date(result.html)
            if published:
                article.published_at = published
                resolved += 1

    logger.info("Resolving article dates for %s items (concurrency=%s)", len(targets), concurrency)
    await asyncio.gather(*(resolve_one(article) for article in targets))
    logger.info("Resolved precise dates for %s/%s articles", resolved, len(targets))
    return resolved
