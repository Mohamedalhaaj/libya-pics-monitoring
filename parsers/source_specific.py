from __future__ import annotations

from copy import deepcopy

from parsers.generic import GenericListParser


class SelectorOverrideParser(GenericListParser):
    parser_name = "selector_override"
    selector_overrides: dict[str, str] = {}

    def __init__(self, source, keywords, collection_url=None) -> None:
        super().__init__(source, keywords, collection_url)
        self.source = deepcopy(source)
        selectors = self.source.setdefault("selectors", {})
        selectors.update(self.selector_overrides)


class AlWasatParser(SelectorOverrideParser):
    parser_name = "al_wasat"
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


class LibyaHeraldParser(EanLibyaParser):
    parser_name = "libya_herald"


class AlShahedParser(EanLibyaParser):
    parser_name = "al_shahed"
