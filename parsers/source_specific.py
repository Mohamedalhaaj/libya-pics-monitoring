from __future__ import annotations

from copy import deepcopy

from parsers.common import (
    build_article,
    clean_text,
    deduplicate_articles,
    extract_date,
    extract_structured_links,
    is_noise_link,
    is_probable_article_url,
    match_keywords,
    normalize_url,
    soup_from_html,
)
from parsers.generic import GenericListParser


class SelectorOverrideParser(GenericListParser):
    parser_name = "selector_override"
    selector_overrides: dict[str, str] = {}
    article_url_patterns: tuple[str, ...] = ()

    def __init__(self, source, keywords, collection_url=None) -> None:
        super().__init__(source, keywords, collection_url)
        self.source = deepcopy(source)
        selectors = self.source.setdefault("selectors", {})
        selectors.update(self.selector_overrides)

    def parse(self, html: str):
        if not self.article_url_patterns:
            return super().parse(html)

        soup = soup_from_html(html)
        selectors = self.source["selectors"]
        articles = []
        link_candidates = [
            (clean_text(link.get_text(" ", strip=True)), normalize_url(self.collection_url, link.get("href") or "", self.source["id"]), link)
            for link in soup.select("a[href]")
        ]
        link_candidates.extend((title, url, None) for title, url in extract_structured_links(soup, self.collection_url, self.source["id"]))

        for title, url, link in link_candidates:
            if not url or is_noise_link(title, url):
                continue
            if not is_probable_article_url(url, self.article_url_patterns):
                continue
            container = link.find_parent(["article", "li", "div", "tr"]) if link else None
            container = container or link or soup
            published_at, raw_date, date_source = extract_date(container, selectors)
            summary = ""
            summary_node = container.select_one(selectors.get("summary", "p"))
            if summary_node:
                summary = clean_text(summary_node.get_text(" ", strip=True))
            section = ""
            section_node = container.select_one(selectors.get("section", ".category"))
            if section_node:
                section = clean_text(section_node.get_text(" ", strip=True))
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
                    matched_keywords=match_keywords(f"{title} {summary} {url}", self.keywords),
                )
            )
        return deduplicate_articles(articles)


class AlWasatParser(SelectorOverrideParser):
    parser_name = "al_wasat"
    article_url_patterns = ("/news/",)
    selector_overrides = {
        "article": "article, .news-item, .item, .media, .views-row",
        "title": "h1 a, h2 a, h3 a, h4 a, .title a, a[href*='/news/']",
        "url": "h1 a, h2 a, h3 a, h4 a, .title a, a[href*='/news/']",
        "summary": "p, .summary, .introtext, .description",
        "date": "time, .date, .created, .time, span[class*='date']",
        "section": ".section, .category, .breadcrumb",
    }


class LanaParser(SelectorOverrideParser):
    parser_name = "lana"
    selector_overrides = {
        "article": "article, .post, .news, .row, tr, li",
        "title": "a[href*='post.php'], h1 a, h2 a, h3 a, h4 a",
        "url": "a[href*='post.php'], h1 a, h2 a, h3 a, h4 a",
        "summary": "p, td, .summary",
        "date": "time, .date, .created, td, span",
        "section": ".category, .breadcrumb",
    }


class RNAReportageParser(SelectorOverrideParser):
    parser_name = "rna_reportage"
    article_url_patterns = ("/20",)
    selector_overrides = {
        "article": "article, .post, .jeg_post, .td_module_wrap, .elementor-post, .news-item",
        "title": "h1 a, h2 a, h3 a, h4 a, .entry-title a, .jeg_post_title a, a[href*='reportage.ly']",
        "url": "h1 a, h2 a, h3 a, h4 a, .entry-title a, .jeg_post_title a, a[href*='reportage.ly']",
        "summary": ".entry-summary, .excerpt, .post-excerpt, p",
        "date": "time, .date, .entry-date, span[class*='date']",
        "section": ".category, .cat-links, .jeg_meta_category",
    }


class EanLibyaParser(SelectorOverrideParser):
    parser_name = "ean_libya"
    article_url_patterns = ("/20",)
    selector_overrides = {
        "article": "article, .post, .td_module_wrap, .jeg_post, .elementor-post",
        "title": "h1 a, h2 a, h3 a, h4 a, .entry-title a, .post-title a, .td-module-title a",
        "url": "h1 a, h2 a, h3 a, h4 a, .entry-title a, .post-title a, .td-module-title a",
        "summary": ".entry-summary, .td-excerpt, .excerpt, p",
        "date": "time, .entry-date, .date, span[class*='date']",
        "section": ".category, .cat-links, .td-post-category",
    }


class AddressLibyaParser(EanLibyaParser):
    parser_name = "address_libya"


class LibyaObserverParser(SelectorOverrideParser):
    parser_name = "libya_observer"
    article_url_patterns = ("/news/", "/economy/", "/inbrief/")
    selector_overrides = {
        "article": "article, .views-row, .node, .card, .news-item",
        "title": "h1 a, h2 a, h3 a, .field-content a, a[href*='/news/'], a[href*='/economy/'], a[href*='/inbrief/']",
        "url": "h1 a, h2 a, h3 a, .field-content a, a[href*='/news/'], a[href*='/economy/'], a[href*='/inbrief/']",
        "summary": ".field--name-body, .views-field-body, .summary, p",
        "date": "time, .date, .created, span[class*='date']",
        "section": ".category, .field--name-field-category",
    }


class LibyaReviewParser(EanLibyaParser):
    parser_name = "libya_review"
    article_url_patterns = ("/20",)


class LibyaHeraldParser(EanLibyaParser):
    parser_name = "libya_herald"
    article_url_patterns = ("/20",)


class AlShahedParser(EanLibyaParser):
    parser_name = "al_shahed"
    article_url_patterns = ("/20",)


class AlMenassaParser(EanLibyaParser):
    parser_name = "al_menassa"
    article_url_patterns = ("/20",)


class AsharqAlAwsatParser(EanLibyaParser):
    parser_name = "asharq_al_awsat"
    article_url_patterns = ("/العالم-العربي/", "/arab-world/", "/%")


class Libya24Parser(EanLibyaParser):
    parser_name = "libya_24"
    article_url_patterns = ("/20",)


class AlSaaa24Parser(EanLibyaParser):
    parser_name = "al_saaa_24"
    article_url_patterns = ("/20",)
