from __future__ import annotations

from parsers.base import BaseParser
from parsers.common import (
    build_article,
    clean_text,
    deduplicate_articles,
    extract_date,
    is_noise_link,
    match_keywords,
    normalize_url,
    soup_from_html,
)
from utils.models import Article


class GenericListParser(BaseParser):
    parser_name = "generic_list"

    def parse(self, html: str) -> list[Article]:
        soup = soup_from_html(html)
        selectors = self.source["selectors"]
        nodes = soup.select(selectors["article"]) or soup.select("article, a[href], h1, h2, h3, h4")
        articles: list[Article] = []

        for item in nodes:
            title_node = item.select_one(selectors["title"])
            if not title_node and item.name == "a":
                title_node = item
            if not title_node:
                continue
            title = clean_text(title_node.get_text(" ", strip=True))
            link_node = title_node if title_node.name == "a" else item.select_one(selectors.get("url", "a[href]"))
            href = link_node.get("href") if link_node else ""
            url = normalize_url(self.collection_url, href, self.source["id"])
            if not url or is_noise_link(title, url):
                continue

            summary = ""
            if selectors.get("summary"):
                summary_node = item.select_one(selectors["summary"])
                if summary_node:
                    summary = clean_text(summary_node.get_text(" ", strip=True))

            section = ""
            if selectors.get("section"):
                section_node = item.select_one(selectors["section"])
                if section_node:
                    section = clean_text(section_node.get_text(" ", strip=True))

            published_at, raw_date, date_source = extract_date(item, selectors)
            matched_keywords = match_keywords(f"{title} {summary} {url}", self.keywords)

            articles.append(
                build_article(
                    source=self.source,
                    collection_url=self.collection_url,
                    parser_used=self.parser_name,
                    title=title,
                    url=url,
                    summary=summary,
                    section=section,
                    published_at=published_at,
                    raw_date=raw_date,
                    date_source=date_source,
                    matched_keywords=matched_keywords,
                )
            )

        return deduplicate_articles(articles)
