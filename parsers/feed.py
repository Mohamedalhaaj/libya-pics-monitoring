from __future__ import annotations

import html as html_lib
import re
from calendar import timegm
from datetime import datetime, timezone

import feedparser

from parsers.base import BaseParser
from parsers.generic import deduplicate_articles, match_keywords
from utils.models import Article

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    """Strip HTML tags/entities and collapse whitespace from a feed field."""
    return " ".join(_TAG_RE.sub(" ", html_lib.unescape(text or "")).split())


def _entry_datetime(entry) -> datetime | None:
    # feedparser normalises feed dates to a UTC struct_time. Convert to the
    # naive-UTC convention the rest of the pipeline compares against.
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if struct:
            return datetime.fromtimestamp(timegm(struct), tz=timezone.utc).replace(tzinfo=None)
    return None


def _entry_section(entry) -> str:
    tags = entry.get("tags")
    if tags:
        return _clean(tags[0].get("term", ""))
    return _clean(entry.get("category", ""))


def _entry_source_title(entry) -> str:
    """The originating outlet, for aggregator feeds (e.g. Google News)."""
    source = entry.get("source")
    if not source:
        return ""
    title = source.get("title") if isinstance(source, dict) else getattr(source, "title", "")
    # "ABC News - Breaking News, Latest News and Videos" -> "ABC News".
    name = _clean(title or "")
    for separator in (" - ", " | ", " — "):
        if separator in name:
            name = name.split(separator, 1)[0]
    return name.strip()


def _strip_trailing_source(title: str, source_name: str) -> str:
    """Google News appends ' - Publisher' to each headline; drop it."""
    parts = title.rsplit(" - ", 1)
    if len(parts) == 2 and len(parts[1]) <= 40:
        return parts[0].strip()
    return title


class FeedListParser(BaseParser):
    """Parse an RSS/Atom feed body into Article records.

    Feeds are already article lists, so there is no boilerplate to strip; we
    only apply the same keyword gate as the HTML parser (broad, site-wide feeds
    such as Asharq Al-Awsat or New Arab set ``require_keyword_match`` to filter
    down to Libya items).
    """

    def parse(self, feed_text: str) -> list[Article]:
        parsed = feedparser.parse(feed_text)
        require_keyword = self.source.get("require_keyword_match", True)
        # Aggregator feeds (Google News) carry the real outlet per item; use it
        # so the report cites "Reuters"/"ABC News", not the aggregator name.
        per_item_source = self.source.get("per_item_source", False)
        articles: list[Article] = []

        for entry in parsed.entries:
            title = _clean(entry.get("title", ""))
            if not title:
                continue
            url = (entry.get("link") or "").strip()
            summary = _clean(entry.get("summary", entry.get("description", "")))

            source_name = self.source["name"]
            if per_item_source:
                outlet = _entry_source_title(entry)
                if outlet:
                    source_name = outlet
                    title = _strip_trailing_source(title, outlet)

            matched_keywords = match_keywords(f"{title} {summary}", self.keywords)
            if require_keyword and not matched_keywords:
                continue

            articles.append(
                Article(
                    source_id=self.source["id"],
                    source_name=source_name,
                    language=self.source["language"],
                    country_focus=self.source.get("country_focus", "Libya"),
                    title=title,
                    url=url,
                    published_at=_entry_datetime(entry),
                    summary=summary,
                    section=_entry_section(entry),
                    matched_keywords=matched_keywords,
                )
            )

        return deduplicate_articles(articles)
