"""RSS/Atom feed parser.

Feeds are the most reliable collection path: they return clean titles, links,
summaries and — crucially — publication dates, and they bypass both bot
protection and client-side rendering that defeat HTML scraping. Most of the
domestic WordPress sources expose `/feed/`. The scraper tries the feed first
(when a `feed_url` is configured or auto-discovered) and falls back to HTML.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from parsers.generic import deduplicate_articles, match_keywords
from utils.dates import parse_article_date
from utils.models import Article


class FeedParser(BaseParser):
    def parse(self, xml: str) -> list[Article]:
        # `xml` parser keeps RSS/Atom structure intact (html.parser mangles it).
        soup = BeautifulSoup(xml, "xml")
        base = self.source.get("feed_url") or self.source["url"]
        items = soup.find_all("item") or soup.find_all("entry")  # RSS or Atom
        articles: list[Article] = []

        for item in items:
            title = (item.title.get_text(strip=True) if item.title else "").strip()
            if not title:
                continue
            url = _entry_link(item, base)
            summary = _entry_summary(item)
            published_at = parse_article_date(_entry_date(item))

            # Aggregator feeds (e.g. Google News) carry the real outlet in a
            # <source> element and append " - Outlet" to the title. Surface the
            # real outlet so the report cites it, not the aggregator.
            outlet = item.find("source")
            source_name = self.source["name"]
            if outlet and outlet.get_text(strip=True):
                source_name = outlet.get_text(strip=True)
                suffix = f" - {source_name}"
                if title.endswith(suffix):
                    title = title[: -len(suffix)].strip()

            matched = match_keywords(f"{title} {summary}", self.keywords)
            if self.source.get("require_keyword_match", True) and not matched:
                continue

            articles.append(
                Article(
                    source_id=self.source["id"],
                    source_name=source_name,
                    language=self.source["language"],
                    country_focus=self.source.get("country_focus", "Libya"),
                    title=title,
                    url=url,
                    published_at=published_at,
                    summary=summary,
                    section="",
                    matched_keywords=matched,
                )
            )

        return deduplicate_articles(articles)


def discover_feed_url(html: str, base: str) -> str | None:
    """Find an RSS/Atom feed advertised in a page's <head>, if any."""
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link", attrs={"rel": "alternate"}):
        feed_type = (link.get("type") or "").lower()
        if ("rss" in feed_type or "atom" in feed_type) and link.get("href"):
            return urljoin(base, link["href"])
    return None


def _entry_link(item, base: str) -> str:
    link = item.find("link")
    if link is None:
        guid = item.find("guid")
        href = guid.get_text(strip=True) if guid else ""
    elif link.get("href"):  # Atom: <link href="...">
        href = link["href"]
    else:  # RSS: <link>text</link>
        href = link.get_text(strip=True)
    return urljoin(base, href) if href else ""


def _entry_summary(item) -> str:
    node = item.find("description") or item.find("summary") or item.find("content")
    if not node:
        return ""
    text = node.get_text(" ", strip=True)
    # Strip any HTML the summary smuggles in as escaped markup.
    return " ".join(BeautifulSoup(text, "html.parser").get_text(" ", strip=True).split())


def _entry_date(item) -> str:
    for tag in ("pubDate", "published", "updated", "dc:date", "date"):
        node = item.find(tag)
        if node and node.get_text(strip=True):
            return node.get_text(strip=True)
    return ""
