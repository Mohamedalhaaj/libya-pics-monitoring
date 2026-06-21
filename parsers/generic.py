from __future__ import annotations

import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from utils.dates import parse_article_date, parse_date_from_url
from utils.models import Article


class GenericListParser(BaseParser):
    def parse(self, html: str) -> list[Article]:
        soup = BeautifulSoup(html, "html.parser")
        selectors = self.source["selectors"]
        articles: list[Article] = []

        for item in soup.select(selectors["article"]):
            title_node = item.select_one(selectors["title"])
            if not title_node:
                continue
            title = " ".join(title_node.get_text(" ", strip=True).split())
            if not title:
                continue

            # Resolve the link. Three card shapes: the title is itself a link,
            # the card element is itself a link (common on Next.js/Tailwind
            # sites where the whole card is one <a>), or a separate url selector.
            if title_node.name == "a":
                link_node = title_node
            elif item.name == "a":
                link_node = item
            else:
                link_node = item.select_one(selectors.get("url", "a[href]"))
            href = link_node.get("href") if link_node else ""
            # Leave the URL empty when the item exposes no real link, rather than
            # pointing every link-less item at the listing page. Otherwise dedup
            # (keyed on source_id + url) would collapse unrelated items together.
            url = urljoin(self.source["url"], href) if href else ""

            summary = ""
            if selectors.get("summary"):
                summary_node = item.select_one(selectors["summary"])
                if summary_node:
                    summary = " ".join(summary_node.get_text(" ", strip=True).split())

            date_value = ""
            if selectors.get("date"):
                date_node = item.select_one(selectors["date"])
                if date_node:
                    date_value = date_node.get("datetime") or date_node.get_text(" ", strip=True)

            section = ""
            if selectors.get("section"):
                section_node = item.select_one(selectors["section"])
                if section_node:
                    section = section_node.get_text(" ", strip=True)

            if _is_noise(title, url):
                continue

            matched_keywords = match_keywords(f"{title} {summary}", self.keywords)
            if self.source.get("require_keyword_match", True) and not matched_keywords:
                continue

            articles.append(
                Article(
                    source_id=self.source["id"],
                    source_name=self.source["name"],
                    language=self.source["language"],
                    country_focus=self.source.get("country_focus", "Libya"),
                    title=title,
                    url=url,
                    published_at=parse_article_date(date_value) or parse_date_from_url(url),
                    summary=summary,
                    section=section,
                    matched_keywords=matched_keywords,
                )
            )

        return deduplicate_articles(articles)


# Common chrome/navigation labels that the broad `li`/`a` selectors pick up.
_NAV_LABELS = {
    "terms & conditions", "privacy policy", "fact-checking policy", "about us",
    "contact us", "newsletter", "subscribe", "sign in", "log in", "read more",
    "entertainment", "sports", "politics", "economy", "home", "menu",
    "صحافة المواطن", "الرئيسية", "اتصل بنا", "من نحن", "سياسة الخصوصية",
    "شروط الاستخدام", "اقتصاد", "رياضة", "سياسة", "منوعات", "أخبار ليبيا",
    "فيديو", "مقالات", "عربى", "عربي ودولي", "الأخبار الاقتصادية",
}


def _is_noise(title: str, url: str) -> bool:
    """Filter out navigation/boilerplate cards the broad selectors capture."""
    stripped = title.strip()
    if _normalize(stripped) in _NAV_LABELS:
        return True
    # A real headline either links somewhere or is a full sentence; a short,
    # link-less fragment is almost always chrome.
    if not url and len(stripped) < 25:
        return True
    return False


def _normalize(text: str) -> str:
    # NFKC unifies presentation/compatibility Arabic codepoints so the same
    # word matches regardless of how the source encoded it.
    return unicodedata.normalize("NFKC", text).casefold()


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    normalized = _normalize(text)
    return [keyword for keyword in keywords if _normalize(keyword) in normalized]


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
