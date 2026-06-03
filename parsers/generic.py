from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from parsers.base import BaseParser
from utils.dates import parse_article_date
from utils.models import Article


class GenericListParser(BaseParser):
    def parse(self, html: str) -> list[Article]:
        soup = BeautifulSoup(html, "html.parser")
        selectors = self.source["selectors"]
        articles: list[Article] = []
        nodes = soup.select(selectors["article"])
        if not nodes:
            nodes = soup.select("article, a[href], h1, h2, h3, h4")

        for item in nodes:
            title_node = item.select_one(selectors["title"])
            if not title_node and item.name == "a":
                title_node = item
            if not title_node:
                continue
            title = " ".join(title_node.get_text(" ", strip=True).split())
            if not title:
                continue

            link_node = title_node if title_node.name == "a" else item.select_one(selectors.get("url", "a[href]"))
            href = link_node.get("href") if link_node else ""
            url = urljoin(self.collection_url, href) if href else self.collection_url

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

            matched_keywords = match_keywords(f"{title} {summary}", self.keywords)

            articles.append(
                Article(
                    source_id=self.source["id"],
                    source_name=self.source["name"],
                    language=self.source["language"],
                    country_focus=self.source.get("country_focus", "Libya"),
                    title=title,
                    url=url,
                    published_at=parse_article_date(date_value),
                    summary=summary,
                    section=section,
                    raw_date=date_value,
                    date_source="markup" if date_value else "",
                    collection_url=self.collection_url,
                    matched_keywords=matched_keywords,
                )
            )

        return deduplicate_articles(articles)


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
