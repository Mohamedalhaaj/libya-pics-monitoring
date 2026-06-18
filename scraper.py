from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from parsers import get_parser
from parsers.common import clean_text, extract_article_page_details, is_noise_link, is_probable_article_url, normalize_url, page_metadata_flags, soup_from_html
from utils.config import load_sources
from utils.audit import (
    generate_category_missed_story_audit,
    generate_discovery_precision_audit,
    generate_evidence_package,
    generate_report_generation_status,
    generate_source_failure_report,
    generate_source_balance_report,
)
from utils.dates import has_exact_date_in_url, in_date_range, parse_cli_date, parse_date_from_url
from utils.editorial import (
    DEFAULT_RELEVANCE_THRESHOLD,
    run_editorial_pipeline,
    write_classification_qa_report_csv,
    write_editorial_qa_report_csv,
    write_final_pics_report_docx,
    write_raw_candidate_promotion_report_csv,
    write_review_queue_recovery_report_csv,
    write_stale_story_report_csv,
    write_story_clusters_csv,
)
from utils.exports import (
    ensure_output_dir,
    write_articles_csv,
    write_date_uncertain_csv,
    write_debug_report_csv,
    write_verification_csv,
)
from utils.fetcher import BrowserFetcher
from utils.logger import setup_logging
from utils.keywords import (
    INTERNATIONAL_NOISE,
    LIBYA_ENTITIES,
    LIBYA_INSTITUTIONS,
    PICS_SECTION_KEYWORDS,
    SECTION_ORDER,
    SUBSECTION_KEYWORDS,
    all_libya_positive_keywords,
)
from utils.models import Article, SourceVerification
from utils.source_plan import (
    ACTOR_DISCOVERY_TERMS,
    ANALYSIS_CONTEXT_SOURCE_IDS,
    CONTEXTUAL_EXPANSION_DIMENSIONS,
    MANDATORY_CONTEXT_SOURCE_IDS,
    MANDATORY_PICS_SECTIONS,
    PRIMARY_THEME_SEARCH_TERMS,
    SOURCE_TIERS,
    build_collection_urls,
    build_contextual_expansion_urls,
    build_section_coverage_urls,
    sort_sources,
)

logger = logging.getLogger(__name__)

MAX_PRIMARY_FETCH_FAILURES_PER_SOURCE = 5
MAX_RECOVERY_FETCH_FAILURES_PER_SOURCE = 5

DEFAULT_KEYWORDS = [
    "Libya",
    "Libyan",
    "Tripoli",
    "Benghazi",
    "Misrata",
    "Derna",
    "Sebha",
    "Zuwara",
    "Zawiya",
    "Brega",
    "UNSMIL",
    "United Nations",
    "migration",
    "migrant",
    "security",
    "governance",
    "municipality",
    "municipal",
    "public services",
    "reconstruction",
    "health",
    "human rights",
    "ليبيا",
    "الليبي",
    "الليبية",
    "طرابلس",
    "بنغازي",
    "مصراتة",
    "درنة",
    "سبها",
    "زوارة",
    "الزاوية",
    "البريقة",
    "البعثة الأممية",
    "الأمم المتحدة",
    "هجرة",
    "مهاجر",
    "أمن",
    "حوكمة",
    "بلدية",
    "البلديات",
    "خدمات",
    "إعمار",
    "إعادة الإعمار",
    "صحة",
    "مستشفى",
    "حقوق الإنسان",
]

LIBYA_KEYWORDS = [
    "libya",
    "libyan",
    "tripoli",
    "benghazi",
    "misrata",
    "derna",
    "zawiya",
    "unsmil",
    "united nations",
    "srsg",
    "brega",
    "sebha",
    "zuwara",
    "election",
    "government",
    "parliament",
    "security",
    "migration",
    "migrant",
    "economy",
    "central bank",
    "oil",
    "governance",
    "municipality",
    "municipal",
    "public services",
    "reconstruction",
    "health",
    "hospital",
    "human rights",
    "ليبيا",
    "ليبي",
    "الليبي",
    "الليبية",
    "طرابلس",
    "بنغازي",
    "مصراتة",
    "درنة",
    "الزاوية",
    "سبها",
    "زوارة",
    "البريقة",
    "الخليج العربي للنفط",
    "البعثة الأممية",
    "الأمم المتحدة",
    "المبعوث",
    "انتخابات",
    "حكومة",
    "مجلس",
    "أمن",
    "هجرة",
    "مهاجر",
    "اقتصاد",
    "مصرف",
    "نفط",
    "حوكمة",
    "بلدية",
    "البلديات",
    "خدمات",
    "إعمار",
    "إعادة الإعمار",
    "صحة",
    "مستشفى",
    "حقوق الإنسان",
]

EXPLICIT_LIBYA_KEYWORDS = [
    "libya",
    "libyan",
    "tripoli",
    "benghazi",
    "misrata",
    "derna",
    "zawiya",
    "brega",
    "sebha",
    "zuwara",
    "unsmil",
    "ليبيا",
    "ليبي",
    "الليبي",
    "الليبية",
    "طرابلس",
    "بنغازي",
    "مصراتة",
    "درنة",
    "الزاوية",
    "سبها",
    "زوارة",
    "البريقة",
    "الخليج العربي للنفط",
    "البعثة الأممية",
    "رئاسة الوزراء",
    "حكومة الوحدة",
    "حكومة الاستقرار",
    "مجلس النواب",
    "المجلس الأعلى للدولة",
    "المفوضية الوطنية العليا للانتخابات",
    "مصرف ليبيا المركزي",
    "المؤسسة الوطنية للنفط",
    "المنفي",
    "الدبيبة",
    "الدبيبه",
    "حفتر",
    "عقيلة صالح",
    "تكالة",
    "باتيلي",
    "تيتيه",
    "وليامز",
    "الكبير",
    "طرابلسي",
    "حماد",
    "باشاغا",
    "الدبيبة",
]

LIBYA_SOURCE_IDS = {
    "al_wasat",
    "ean_libya",
    "rna_reportage",
    "libya_observer",
    "libya_review",
    "libya_herald",
    "al_menassa",
    "al_shahed",
    "al_marsad",
    "libya_24",
    "al_saaa_24",
    "address_libya",
    "lana",
    "fawasel_media",
    "tanasuh",
    "libya_al_ahrar",
    "libya_update",
    "akhbar_libya_24",
    "al_sabaah",
}

PUBLIC_AFFAIRS_KEYWORDS = [
    "unsmil",
    "united nations",
    "politic",
    "government",
    "parliament",
    "election",
    "security",
    "migration",
    "migrant",
    "economy",
    "central bank",
    "oil",
    "governance",
    "municipal",
    "municipality",
    "public service",
    "reconstruction",
    "health",
    "hospital",
    "human rights",
    "الأمم المتحدة",
    "البعثة الأممية",
    "سياس",
    "حكومة",
    "مجلس",
    "انتخاب",
    "أمن",
    "هجرة",
    "مهاجر",
    "اقتصاد",
    "مصرف",
    "نفط",
    "حوكمة",
    "بلدية",
    "البلديات",
    "خدمات",
    "إعمار",
    "صحة",
    "مستشفى",
    "حقوق الإنسان",
]

INTERNATIONAL_NOISE_KEYWORDS = [
    "iran",
    "israel",
    "gaza",
    "ukraine",
    "russia",
    "china",
    "syria",
    "lebanon",
    "iraq",
    "sudan",
    "trump",
    "إيران",
    "إسرائيل",
    "غزة",
    "أوكرانيا",
    "روسيا",
    "الصين",
    "سوريا",
    "لبنان",
    "العراق",
    "السودان",
    "ترامب",
]

async def scrape_source(
    source: dict,
    fetcher: BrowserFetcher,
    keywords: list[str],
    start_date: datetime | None,
    end_date: datetime | None,
    max_pages: int,
    max_article_pages: int,
    collection_urls_override: list[str] | None = None,
    pass_label: str = "primary",
) -> tuple[list[Article], list[Article], list[Article], SourceVerification, dict[str, str]]:
    if collection_urls_override is None:
        all_collection_urls = build_collection_urls(source, keywords, start_date, end_date)
        collection_urls = all_collection_urls[:max_pages]
        recovery_urls = all_collection_urls[max_pages : max_pages + 24]
        collection_urls.extend(source.get("fallback_urls", []))
    else:
        all_collection_urls = collection_urls_override
        collection_urls = collection_urls_override[:max_pages]
        recovery_urls = []
    collection_urls = dedupe_values(collection_urls)
    recovery_urls = dedupe_values([url for url in recovery_urls if url not in collection_urls])
    parser_cls = get_parser(source["parser"])
    fetched_urls: list[str] = []
    errors: list[str] = []
    parsed_candidates: list[Article] = []
    attempted_recovery_methods: list[str] = []
    successful_recovery_methods: list[str] = []

    logger.info(
        "Collecting source=%s parser=%s pass=%s planned_urls=%s",
        source["id"],
        source["parser"],
        pass_label,
        len(collection_urls),
    )
    primary_fetch_failures = 0
    for collection_url in collection_urls:
        try:
            result, attempted_methods, successful_method = await fetch_url_with_recovery(
                fetcher,
                collection_url,
                discovery_method=url_discovery_method(collection_url, source, collection_urls),
            )
            attempted_recovery_methods.extend(attempted_methods)
            if successful_method != "playwright_default":
                successful_recovery_methods.append(successful_method)
            fetched_urls.append(result.final_url)
            parser = parser_cls(source, keywords, collection_url=result.final_url)
            page_candidates = parser.parse(result.html)
            page_candidates = filter_discovery_candidates(source, page_candidates, start_date, end_date)
            logger.info(
                "Parsed source=%s pass=%s url=%s candidates=%s",
                source["id"],
                pass_label,
                result.final_url,
                len(page_candidates),
            )
            parsed_candidates.extend(page_candidates)
            primary_fetch_failures = 0
        except Exception as exc:
            message = f"{collection_url}: {exc}"
            errors.append(message)
            primary_fetch_failures += 1
            logger.warning("Fetch failed for source=%s %s", source["id"], message)
            if primary_fetch_failures >= MAX_PRIMARY_FETCH_FAILURES_PER_SOURCE and not fetched_urls:
                logger.warning(
                    "Primary fetch failure budget reached for source=%s failures=%s",
                    source["id"],
                    primary_fetch_failures,
                )
                break

    if not parsed_candidates and recovery_urls:
        logger.info("Starting recovery discovery source=%s recovery_urls=%s", source["id"], len(recovery_urls))
        recovery_fetch_failures = 0
        for recovery_url in recovery_urls:
            try:
                discovery_method = url_discovery_method(recovery_url, source, collection_urls)
                result, attempted_methods, successful_method = await fetch_url_with_recovery(
                    fetcher,
                    recovery_url,
                    discovery_method=discovery_method,
                )
                attempted_recovery_methods.extend([discovery_method, *attempted_methods])
                successful_recovery_methods.append(f"{successful_method}:{discovery_method}")
                fetched_urls.append(result.final_url)
                parser = parser_cls(source, keywords, collection_url=result.final_url)
                page_candidates = parser.parse(result.html)
                page_candidates = filter_discovery_candidates(source, page_candidates, start_date, end_date)
                logger.info(
                    "Recovered parse source=%s method=%s url=%s candidates=%s",
                    source["id"],
                    discovery_method,
                    result.final_url,
                    len(page_candidates),
                )
                parsed_candidates.extend(page_candidates)
                recovery_fetch_failures = 0
                if parsed_candidates:
                    break
            except Exception as exc:
                message = f"{recovery_url}: {exc}"
                errors.append(message)
                recovery_fetch_failures += 1
                logger.warning("Recovery fetch failed for source=%s %s", source["id"], message)
                if recovery_fetch_failures >= MAX_RECOVERY_FETCH_FAILURES_PER_SOURCE:
                    logger.warning(
                        "Recovery fetch failure budget reached for source=%s failures=%s",
                        source["id"],
                        recovery_fetch_failures,
                    )
                    break

    parsed_candidates = deduplicate_articles(parsed_candidates)
    candidate_count = len(parsed_candidates)
    article_pages_opened = 0
    article_fetch_errors: list[str] = []
    enriched_candidates: list[Article] = []
    for article in parsed_candidates[:max_article_pages]:
        try:
            result, attempted_methods, successful_method = await fetch_url_with_recovery(
                fetcher,
                article.url,
                discovery_method="article_page_verification",
            )
            attempted_recovery_methods.extend(attempted_methods)
            if successful_method != "playwright_default":
                successful_recovery_methods.append(f"{successful_method}:article_page_verification")
            article_pages_opened += 1
            enriched_candidates.append(extract_article_page_details(result.html, article))
        except Exception as exc:
            article_fetch_errors.append(f"{article.url}: {exc}")
            logger.warning("Article fetch failed for source=%s url=%s error=%s", source["id"], article.url, exc)
            enriched_candidates.append(article)

    if len(parsed_candidates) > max_article_pages:
        logger.info(
            "Article page cap reached source=%s candidates=%s opened=%s",
            source["id"],
            len(parsed_candidates),
            max_article_pages,
        )
        enriched_candidates.extend(parsed_candidates[max_article_pages:])

    parsed_candidates = deduplicate_articles(enriched_candidates)
    accepted: list[Article] = []
    review_queue: list[Article] = []
    raw_candidates: list[Article] = []
    rejected_date_count = 0
    rejected_relevance_count = 0
    rejected_non_article_count = 0
    date_parsed_count = 0

    for article in parsed_candidates:
        article.source_tier = SOURCE_TIERS.get(source["id"], "")
        enrich_article(article, start_date)
        if article.published_at:
            date_parsed_count += 1
        if not looks_like_article_url(article.url):
            article.notes = append_note(article.notes, "non_article_url")
            article.relevance_status = "rejected"
            article.relevance_reason = "non_article_url"
            article.qa_status = "rejected"
            article.qa_notes = "Rejected because URL is a listing, search, tag, category, or other non-article page"
            rejected_relevance_count += 1
            rejected_non_article_count += 1
            raw_candidates.append(article)
            continue
        relevance_ok, relevance_reason = check_libya_relevance(article, source)
        article.relevance_reason = relevance_reason
        article.relevance_status = "accepted" if relevance_ok else "rejected"
        if not relevance_ok:
            article.notes = "not_libya_related"
            article.qa_status = "rejected"
            article.qa_notes = "Rejected by Libya relevance filter"
            rejected_relevance_count += 1
            raw_candidates.append(article)
            continue

        date_status = classify_date(article, start_date, end_date)
        article.date_status = date_status
        if date_status == "in_range":
            article.include_candidate = True
            article.qa_status = "approved"
            article.qa_notes = "Reliable date inside target window and Libya-relevant"
            accepted.append(article)
        elif date_status in {"missing_date", "ambiguous_date", "date_conflict"}:
            article.notes = append_note(article.notes, date_status)
            article.qa_status = "needs_review"
            if date_status == "date_conflict":
                article.qa_notes = append_note(
                    article.qa_notes,
                    "URL date conflicts with article metadata; needs editorial verification",
                )
            else:
                article.qa_notes = append_note(article.qa_notes, "Date missing or uncertain; not approved automatically")
            review_queue.append(article)
        else:
            article.notes = "outside_date_window"
            article.qa_status = "rejected"
            article.qa_notes = "Publication date outside target window"
            rejected_date_count += 1
        raw_candidates.append(article)

    verification = SourceVerification(
        source_name=source["name"],
        source_url=" | ".join(fetched_urls[:3]) or source["url"],
        fetch_status="failed_fetch" if not fetched_urls and errors else "ok",
        candidate_links_found=candidate_count,
        article_pages_opened=article_pages_opened,
        date_parsed_count=date_parsed_count,
        accepted_count=len(accepted),
        rejected_date_count=rejected_date_count,
        rejected_relevance_count=rejected_relevance_count,
        uncertain_date_count=len(review_queue),
        failed_count=len(errors) + len(article_fetch_errors),
        zero_result_reason=determine_zero_reason(
            fetched_pages=len(fetched_urls),
            candidate_count=candidate_count,
            article_pages_opened=article_pages_opened,
            date_parsed_count=date_parsed_count,
            accepted_count=len(accepted),
            rejected_date_count=rejected_date_count,
            rejected_relevance_count=rejected_relevance_count,
            uncertain_date_count=len(review_queue),
            errors=[*errors, *article_fetch_errors],
            non_article_count=rejected_non_article_count,
        ),
        error=" | ".join([*errors, *article_fetch_errors][:3]),
        notes=(
            f"rejected_non_article={rejected_non_article_count}; "
            f"article_fetch_errors={len(article_fetch_errors)}; "
            f"successful_recovery_methods={dedupe_values(successful_recovery_methods)}"
        ),
    )
    if pass_label != "primary":
        verification.notes = append_note(verification.notes, f"contextual_pass={pass_label}")
        for article in [*raw_candidates, *accepted, *review_queue]:
            article.notes = append_note(article.notes, f"contextual_pass={pass_label}")

    recovery_report = build_source_recovery_report(
        source=source,
        errors=errors,
        attempted_methods=attempted_recovery_methods,
        successful_methods=successful_recovery_methods,
        recovered_articles=len(accepted) + len(review_queue),
        verification=verification,
    )

    if verification.zero_result_reason:
        logger.info(
            "Zero-result diagnostic source=%s reason=%s candidates=%s opened=%s dates=%s accepted=%s rejected_date=%s rejected_relevance=%s uncertain=%s errors=%s",
            source["id"],
            verification.zero_result_reason,
            candidate_count,
            article_pages_opened,
            date_parsed_count,
            len(accepted),
            rejected_date_count,
            rejected_relevance_count,
            len(review_queue),
            " | ".join(errors),
        )

    return raw_candidates, accepted, review_queue, verification, recovery_report


def filter_discovery_candidates(
    source: dict,
    articles: list[Article],
    start_date: datetime | None,
    end_date: datetime | None,
) -> list[Article]:
    if not source.get("filter_discovery_to_date_window"):
        return articles
    filtered = [
        article
        for article in articles
        if not article.published_at or in_date_range(article.published_at, start_date, end_date, keep_undated=True)
    ]
    dropped = len(articles) - len(filtered)
    if dropped:
        logger.info("Discovery date filter source=%s dropped_old_candidates=%s", source["id"], dropped)
    return filtered


async def fetch_url_with_recovery(
    fetcher: BrowserFetcher,
    url: str,
    discovery_method: str,
) -> tuple[object, list[str], str]:
    attempted: list[str] = [discovery_method]
    failures: list[str] = []
    strategies = [
        ("requests", lambda: asyncio.to_thread(fetcher.fetch_with_plain_requests, url)),
        ("requests_with_browser_headers", lambda: asyncio.to_thread(fetcher.fetch_with_requests, url)),
        ("session_reuse", lambda: asyncio.to_thread(fetcher.fetch_with_session, url)),
        ("playwright_default", lambda: fetcher.fetch_with_playwright(url)),
    ]
    for strategy_name, strategy in strategies:
        attempted.append(strategy_name)
        try:
            result = await strategy()
            return result, attempted, strategy_name
        except Exception as exc:
            failures.append(f"{strategy_name}={exc}")
    raise RuntimeError("; ".join(failures))


def url_discovery_method(url: str, source: dict, primary_urls: list[str]) -> str:
    lowered = url.casefold()
    if any(marker in lowered for marker in ("rss", "feed")):
        return "rss_feeds"
    if "sitemap" in lowered:
        return "sitemap_discovery"
    if any(marker in lowered for marker in ("/archive", "/archives", "/20")):
        return "archive_pages"
    if any(marker in lowered for marker in ("?s=", "/search", "keyword=", "query=")):
        return "article_search_fallback"
    if any(marker in lowered for marker in ("/category/", "/section/", "/news", "/latest", "/libya")):
        return "category_pages"
    if url in primary_urls:
        return "homepage"
    if source.get("recovery_logic"):
        return "source_specific_recovery_logic"
    return "alternative_source_urls"


def build_source_recovery_report(
    source: dict,
    errors: list[str],
    attempted_methods: list[str],
    successful_methods: list[str],
    recovered_articles: int,
    verification: SourceVerification,
) -> dict[str, str]:
    failure_type = classify_failure_type(" ".join(errors))
    remaining_issue = ""
    if verification.fetch_status == "failed_fetch":
        remaining_issue = verification.zero_result_reason or failure_type or "fetch_failed"
    elif verification.accepted_count == 0 and verification.uncertain_date_count == 0:
        remaining_issue = verification.zero_result_reason or "no_accepted_articles_after_recovery"
    return {
        "source": source["name"],
        "failure_type": failure_type,
        "attempted_recovery_methods": "; ".join(dedupe_values(attempted_methods)),
        "successful_method": "; ".join(dedupe_values(successful_methods)),
        "articles_recovered": str(recovered_articles),
        "remaining_issue": remaining_issue,
    }


def classify_failure_type(error_text: str) -> str:
    lowered = error_text.casefold()
    if not lowered:
        return ""
    if "err_internet_disconnected" in lowered or "network is unreachable" in lowered:
        return "network_unavailable"
    if "name_not_resolved" in lowered or "failed to resolve" in lowered:
        return "dns_resolution_failed"
    if "403" in lowered or "access denied" in lowered:
        return "access_denied"
    if "cloudflare" in lowered or "captcha" in lowered:
        return "bot_protection"
    if "timeout" in lowered:
        return "timeout"
    return "fetch_failed"


def write_source_recovery_report_csv(rows: list[dict[str, str]], path: str | Path) -> None:
    fields = [
        "source",
        "failure_type",
        "attempted_recovery_methods",
        "successful_method",
        "articles_recovered",
        "remaining_issue",
    ]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def contextual_expansion_sources(all_sources: list[dict], primary_sources: list[dict]) -> list[dict]:
    by_id = {source["id"]: source for source in all_sources}
    selected: list[dict] = []
    for source_id in MANDATORY_CONTEXT_SOURCE_IDS:
        source = by_id.get(source_id)
        if source and source.get("enabled", True):
            selected.append(source)
    for source in primary_sources:
        if source.get("enabled", True) and source not in selected:
            selected.append(source)
    return selected


def detect_primary_themes(articles: list[Article]) -> list[str]:
    text = "\n".join(f"{article.title} {article.summary} {article.content_text}" for article in articles).casefold()
    theme_rules: list[tuple[str, list[str]]] = [
        ("Structured Dialogue", ["structured dialogue", "الحوار المهيكل", "حوار منظم", "مخرجات الحوار"]),
        ("Elections", ["election", "hnec", "انتخابات", "المفوضية", "القوانين الانتخابية"]),
        ("Central Region", ["central region", "إقليم الوسطى", "الإقليم الأوسط", "المنطقة الوسطى"]),
        ("Migration", ["migration", "migrant", "deport", "settlement", "هجرة", "مهاجر", "ترحيل", "توطين"]),
        ("UNSMIL", ["unsmil", "tetteh", "united nations", "البعثة الأممية", "تيتيه", "الأمم المتحدة"]),
        ("Central Bank", ["central bank", "cbl", "مصرف ليبيا المركزي", "السيولة", "سعر الصرف"]),
        ("NOC", ["national oil corporation", "noc", "oil", "fuel", "المؤسسة الوطنية للنفط", "النفط", "الوقود"]),
        ("Zawiya Clashes", ["zawiya", "الزاوية", "clashes", "اشتباكات"]),
        ("Constitutional Issues", ["constitutional", "الدستوري", "القاعدة الدستورية"]),
        ("Executive Authority", ["executive authority", "new government", "parallel government", "السلطة التنفيذية", "حكومة جديدة", "حكومة موازية"]),
    ]
    themes = [theme for theme, markers in theme_rules if any(marker in text for marker in markers)]
    return dedupe_values(themes)


def build_contextual_coverage_audit(
    themes: list[str],
    sources: list[dict],
    approved: list[Article],
    review: list[Article],
    raw: list[Article],
    searched_by_source: dict[str, list[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    searched_source_names = {
        source["name"]
        for source in sources
        if searched_by_source.get(source["id"])
    }
    searched_source_count = len(searched_source_names)
    all_items = [*approved, *review, *raw]
    for theme in themes:
        theme_terms = PRIMARY_THEME_SEARCH_TERMS.get(theme, [theme])
        dimension_counts = {
            dimension: count_theme_dimension_matches(all_items, theme_terms, dimension_terms)
            for dimension, dimension_terms in CONTEXTUAL_EXPANSION_DIMENSIONS.items()
        }
        matched_sources = theme_sources_used(all_items, theme_terms)
        if matched_sources and not dimension_counts.get("event", 0):
            dimension_counts["event"] = count_theme_matches(all_items, theme_terms)
        actor_categories_found = theme_actor_categories_found(all_items, theme_terms)
        actor_categories_checked = "; ".join(ACTOR_DISCOVERY_TERMS)
        non_event_dimensions = sum(1 for dimension, count in dimension_counts.items() if dimension != "event" and count > 0)
        analysis_checked = analysis_sources_checked(searched_by_source, sources)
        coverage_score = contextual_coverage_score(
            searched_source_count=searched_source_count,
            matched_source_count=len(matched_sources),
            actor_category_count=len(actor_categories_found),
            non_event_dimensions=non_event_dimensions,
            analysis_found=dimension_counts.get("analysis", 0) > 0,
            analysis_checked=analysis_checked,
        )
        rows.append(
            {
                "theme": theme,
                "events_found": str(dimension_counts.get("event", 0)),
                "reactions_found": str(dimension_counts.get("reaction", 0)),
                "support_found": str(dimension_counts.get("support", 0)),
                "opposition_found": str(dimension_counts.get("opposition", 0)),
                "analysis_found": str(dimension_counts.get("analysis", 0)),
                "commentary_found": str(dimension_counts.get("commentary", 0)),
                "sources_used": "; ".join(sorted(matched_sources)),
                "sources_checked": "; ".join(sorted(searched_source_names)),
                "sources_checked_count": str(searched_source_count),
                "actor_categories_checked": actor_categories_checked,
                "actor_categories_found": "; ".join(actor_categories_found),
                "coverage_score": str(coverage_score),
                "status": contextual_theme_status(
                    dimension_counts=dimension_counts,
                    searched_source_count=searched_source_count,
                    actor_category_count=len(actor_categories_found),
                    analysis_checked=analysis_checked,
                ),
            }
        )
    return rows


def count_theme_dimension_matches(
    articles: list[Article],
    theme_terms: list[str],
    dimension_terms: list[str],
) -> int:
    count = 0
    theme_markers = [term.casefold() for term in theme_terms]
    dimension_markers = [term.casefold() for term in dimension_terms]
    for article in articles:
        text = f"{article.title} {article.summary} {article.content_text} {article.notes}".casefold()
        if any(term in text for term in theme_markers) and any(term in text for term in dimension_markers):
            count += 1
    return count


def count_theme_matches(articles: list[Article], theme_terms: list[str]) -> int:
    theme_markers = [term.casefold() for term in theme_terms]
    count = 0
    for article in articles:
        text = f"{article.title} {article.summary} {article.content_text} {article.notes}".casefold()
        if any(term in text for term in theme_markers):
            count += 1
    return count


def contextual_status(approved_count: int, review_count: int, raw_count: int) -> str:
    if approved_count:
        return "found"
    if review_count:
        return "review_only"
    if raw_count:
        return "collected_not_accepted"
    return "searched_not_found"


def theme_sources_used(articles: list[Article], theme_terms: list[str]) -> set[str]:
    theme_markers = [term.casefold() for term in theme_terms]
    sources: set[str] = set()
    for article in articles:
        text = f"{article.title} {article.summary} {article.content_text}".casefold()
        if any(term in text for term in theme_markers):
            sources.add(article.source_name)
    return sources


def theme_actor_categories_found(articles: list[Article], theme_terms: list[str]) -> list[str]:
    theme_markers = [term.casefold() for term in theme_terms]
    found: list[str] = []
    for category, markers in ACTOR_DISCOVERY_TERMS.items():
        lowered_markers = [marker.casefold() for marker in markers]
        if any(
            any(theme_term in f"{article.title} {article.summary} {article.content_text}".casefold() for theme_term in theme_markers)
            and any(marker in f"{article.title} {article.summary} {article.content_text}".casefold() for marker in lowered_markers)
            for article in articles
        ):
            found.append(category)
    return found


def analysis_sources_checked(searched_by_source: dict[str, list[str]], sources: list[dict]) -> bool:
    checked = {source["id"] for source in sources if searched_by_source.get(source["id"])}
    return bool({"asharq_al_awsat", "new_arab"} <= checked and (checked & ANALYSIS_CONTEXT_SOURCE_IDS))


def contextual_coverage_score(
    searched_source_count: int,
    matched_source_count: int,
    actor_category_count: int,
    non_event_dimensions: int,
    analysis_found: bool,
    analysis_checked: bool,
) -> int:
    score = 0
    score += min(30, searched_source_count * 5)
    score += min(25, matched_source_count * 8)
    score += min(20, actor_category_count * 7)
    score += min(20, non_event_dimensions * 5)
    if analysis_found:
        score += 5
    elif analysis_checked:
        score += 2
    return min(score, 100)


def contextual_theme_status(
    dimension_counts: dict[str, int],
    searched_source_count: int,
    actor_category_count: int,
    analysis_checked: bool,
) -> str:
    non_event_found = any(count for dimension, count in dimension_counts.items() if dimension != "event")
    minimum_breadth = searched_source_count >= 3 or actor_category_count >= 3
    if not dimension_counts.get("event", 0):
        return "event_not_found"
    if not non_event_found:
        return "event_only_incomplete"
    if not minimum_breadth:
        return "insufficient_source_or_actor_breadth"
    if not dimension_counts.get("analysis", 0) and not analysis_checked:
        return "analysis_sources_not_checked"
    return "complete"


def write_contextual_coverage_audit_csv(rows: list[dict[str, str]], path: str | Path) -> None:
    fields = [
        "theme",
        "events_found",
        "reactions_found",
        "support_found",
        "opposition_found",
        "analysis_found",
        "commentary_found",
        "sources_used",
        "sources_checked",
        "sources_checked_count",
        "actor_categories_checked",
        "actor_categories_found",
        "coverage_score",
        "status",
    ]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_section_coverage_audit(
    sections: list[str],
    searched_by_section: dict[str, dict[str, list[str]]],
    approved_articles: list[Article],
    clusters: list,
) -> list[dict[str, str]]:
    approved_by_section = Counter(article.section_guess for article in approved_articles)
    clusters_by_section = Counter(cluster.section for cluster in clusters)
    rows: list[dict[str, str]] = []
    for section in sections:
        searched_sources = sorted(
            source_id
            for source_id, urls in searched_by_section.get(section, {}).items()
            if urls
        )
        cluster_count = clusters_by_section.get(section, 0)
        approved_count = approved_by_section.get(section, 0)
        status = "complete"
        if not searched_sources:
            status = "not_searched"
        elif cluster_count == 0:
            status = "empty_after_targeted_search"
        elif cluster_count < section_story_floor(section):
            status = "weak_after_targeted_search"
        rows.append(
            {
                "section": section,
                "sources_checked": "; ".join(searched_sources),
                "sources_checked_count": str(len(searched_sources)),
                "approved_articles": str(approved_count),
                "story_clusters": str(cluster_count),
                "targeted_recovery_run": "yes" if searched_sources else "no",
                "status": status,
            }
        )
    return rows


def section_story_floor(section: str) -> int:
    return {
        "United Nations": 1,
        "Politics": 6,
        "Military & Security": 4,
        "Human Rights & Rule of Law": 2,
        "Economy & Energy": 6,
        "Environment": 1,
        "Regional & International": 2,
        "Varieties": 1,
    }.get(section, 1)


def write_section_coverage_audit_csv(rows: list[dict[str, str]], path: str | Path) -> None:
    fields = [
        "section",
        "sources_checked",
        "sources_checked_count",
        "approved_articles",
        "story_clusters",
        "targeted_recovery_run",
        "status",
    ]
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_story_source_map_csv(clusters: list, articles: list[Article], path: str | Path) -> None:
    fields = [
        "story_id",
        "canonical_headline",
        "source_count",
        "source_names",
        "source_urls",
        "language_markers",
        "consolidation_status",
    ]
    article_counts = Counter(article.story_id for article in articles if article.story_id)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for cluster in sorted(clusters, key=lambda item: item.story_id):
            source_count = len(cluster.sources)
            language_markers = ["(Arabic)" if source_looks_arabic_for_map(source) else "" for source in cluster.sources]
            consolidation_status = "ok"
            if source_count == 1 and article_counts.get(cluster.story_id, 0) > 1:
                consolidation_status = "needs_source_consolidation"
            writer.writerow(
                {
                    "story_id": cluster.story_id,
                    "canonical_headline": cluster.canonical_headline,
                    "source_count": str(source_count),
                    "source_names": "; ".join(cluster.sources),
                    "source_urls": "; ".join(cluster.article_urls),
                    "language_markers": "; ".join(language_markers),
                    "consolidation_status": consolidation_status,
                }
            )


def source_looks_arabic_for_map(source_name: str) -> bool:
    english_only = {"Libya Herald", "Libya Observer", "Libya Review", "Reuters", "ANSA", "The Guardian", "New Arab", "AP", "BBC", "CH Aviation", "BSS News"}
    return source_name not in english_only


def merge_source_verification(base: SourceVerification, extra: SourceVerification) -> None:
    base.source_url = " | ".join(dedupe_values([*base.source_url.split(" | "), *extra.source_url.split(" | ")]))[:1200]
    base.fetch_status = "failed_fetch" if base.fetch_status == "failed_fetch" and extra.fetch_status == "failed_fetch" else "ok"
    base.candidate_links_found += extra.candidate_links_found
    base.article_pages_opened += extra.article_pages_opened
    base.date_parsed_count += extra.date_parsed_count
    base.accepted_count += extra.accepted_count
    base.rejected_date_count += extra.rejected_date_count
    base.rejected_relevance_count += extra.rejected_relevance_count
    base.uncertain_date_count += extra.uncertain_date_count
    base.failed_count += extra.failed_count
    if base.zero_result_reason and extra.accepted_count:
        base.zero_result_reason = ""
    elif not base.zero_result_reason:
        base.zero_result_reason = extra.zero_result_reason
    base.error = " | ".join(filter(None, [base.error, extra.error]))[:1200]
    base.notes = append_note(base.notes, extra.notes)


async def run(args: argparse.Namespace) -> None:
    setup_logging(args.log_file, args.verbose)
    output_dir = ensure_output_dir(args.output_dir)
    start_date = parse_cli_date(args.start_date)
    end_date = parse_cli_date(args.end_date, end_of_day=True)
    all_sources = sort_sources(load_sources(args.sources))
    sources = list(all_sources)
    if args.source_id:
        requested = set(args.source_id)
        sources = [source for source in sources if source["id"] in requested]
    keywords = DEFAULT_KEYWORDS + args.keyword

    logger.info("Loaded %s enabled sources", len(sources))
    raw_candidates: list[Article] = []
    approved_articles: list[Article] = []
    review_queue_articles: list[Article] = []
    verifications: list[SourceVerification] = []
    recovery_reports: list[dict[str, str]] = []
    contextual_coverage_rows: list[dict[str, str]] = []
    searched_by_section: dict[str, dict[str, list[str]]] = {}

    async with BrowserFetcher(
        timeout_ms=args.timeout * 1000,
        retries=args.retries,
        retry_delay_seconds=args.retry_delay,
        headless=not args.show_browser,
    ) as fetcher:
        if args.debug_source:
            await debug_source(
                args.debug_source,
                sources,
                fetcher,
                keywords,
                start_date,
                args.max_pages_per_source,
            )
            return

        for source in sources:
            source_raw, source_approved, source_review, verification, recovery_report = await scrape_source(
                source=source,
                fetcher=fetcher,
                keywords=keywords,
                start_date=start_date,
                end_date=end_date,
                max_pages=args.max_pages_per_source,
                max_article_pages=args.max_article_pages_per_source,
            )
            raw_candidates.extend(source_raw)
            approved_articles.extend(source_approved)
            review_queue_articles.extend(source_review)
            verifications.append(verification)
            recovery_reports.append(recovery_report)

        if not args.no_contextual_expansion:
            primary_themes = detect_primary_themes([*approved_articles, *review_queue_articles])
            logger.info("Detected contextual primary themes: %s", primary_themes or ["Analysis"])
            contextual_themes = primary_themes or ["Analysis"]
            verification_by_source = {verification.source_name: verification for verification in verifications}
            searched_by_source: dict[str, list[str]] = {}
            expansion_sources = contextual_expansion_sources(all_sources, sources)
            logger.info(
                "Contextual expansion source universe: %s",
                [source["id"] for source in expansion_sources],
            )
            for source in expansion_sources:
                contextual_url_cap = args.max_contextual_pages_per_source
                expansion_urls = build_contextual_expansion_urls(
                    source,
                    contextual_themes,
                    max_urls=contextual_url_cap,
                )
                if not expansion_urls:
                    continue
                searched_by_source[source["id"]] = expansion_urls
                source_raw, source_approved, source_review, verification, recovery_report = await scrape_source(
                    source=source,
                    fetcher=fetcher,
                    keywords=keywords,
                    start_date=start_date,
                    end_date=end_date,
                    max_pages=contextual_url_cap,
                    max_article_pages=args.max_contextual_article_pages_per_source,
                    collection_urls_override=expansion_urls,
                    pass_label="contextual_expansion",
                )
                raw_candidates.extend(source_raw)
                approved_articles.extend(source_approved)
                review_queue_articles.extend(source_review)
                existing = verification_by_source.get(verification.source_name)
                if existing:
                    merge_source_verification(existing, verification)
                else:
                    verifications.append(verification)
                    verification_by_source[verification.source_name] = verification
                recovery_reports.append(recovery_report)

            contextual_coverage_rows = build_contextual_coverage_audit(
                contextual_themes,
                expansion_sources,
                approved_articles,
                review_queue_articles,
                raw_candidates,
                searched_by_source,
            )

        if not args.no_section_coverage_expansion:
            verification_by_source = {verification.source_name: verification for verification in verifications}
            expansion_sources = contextual_expansion_sources(all_sources, sources)
            for section_name in MANDATORY_PICS_SECTIONS:
                searched_by_section.setdefault(section_name, {})
                for source in expansion_sources:
                    section_urls = build_section_coverage_urls(
                        source,
                        section_name,
                        max_urls=args.max_section_pages_per_source,
                    )
                    if not section_urls:
                        continue
                    searched_by_section[section_name][source["id"]] = section_urls
                    source_raw, source_approved, source_review, verification, recovery_report = await scrape_source(
                        source=source,
                        fetcher=fetcher,
                        keywords=keywords,
                        start_date=start_date,
                        end_date=end_date,
                        max_pages=args.max_section_pages_per_source,
                        max_article_pages=args.max_section_article_pages_per_source,
                        collection_urls_override=section_urls,
                        pass_label=f"section_coverage:{section_name}",
                    )
                    raw_candidates.extend(source_raw)
                    approved_articles.extend(source_approved)
                    review_queue_articles.extend(source_review)
                    existing = verification_by_source.get(verification.source_name)
                    if existing:
                        merge_source_verification(existing, verification)
                    else:
                        verifications.append(verification)
                        verification_by_source[verification.source_name] = verification
                    recovery_reports.append(recovery_report)

    raw_candidates = deduplicate_articles(raw_candidates)
    approved_articles = deduplicate_articles(approved_articles)
    review_queue_articles = deduplicate_articles(review_queue_articles)
    editorial_result = run_editorial_pipeline(
        approved_articles,
        review_queue_articles,
        raw_candidates,
        threshold=args.relevance_threshold,
        start_date=start_date,
        end_date=end_date,
    )
    approved_articles = editorial_result.approved_articles
    review_queue_articles = editorial_result.review_articles

    raw_csv = output_dir / "raw_candidates.csv"
    verified_articles_csv = output_dir / "verified_articles.csv"
    approved_csv = output_dir / "approved_headlines.csv"
    accepted_articles_csv = output_dir / "accepted_articles.csv"
    legacy_articles_csv = output_dir / "libya_media_headlines.csv"
    review_queue_csv = output_dir / "review_queue.csv"
    rejected_items_csv = output_dir / "rejected_items.csv"
    verification_csv = output_dir / "source_verification_table.csv"
    uncertain_csv = output_dir / "date_uncertain_items.csv"
    debug_csv = output_dir / "source_debug_report.csv"
    recovery_csv = output_dir / "source_recovery_report.csv"
    contextual_coverage_csv = output_dir / "contextual_coverage_audit.csv"
    story_clusters_csv = output_dir / "story_clusters.csv"
    editorial_qa_csv = output_dir / "editorial_qa_report.csv"
    review_recovery_csv = output_dir / "review_queue_recovery_report.csv"
    raw_promotion_csv = output_dir / "raw_candidate_promotion_report.csv"
    classification_qa_csv = output_dir / "classification_qa_report.csv"
    stale_story_csv = output_dir / "stale_story_report.csv"
    section_coverage_csv = output_dir / "section_coverage_audit.csv"
    story_source_map_csv = output_dir / "story_source_map.csv"
    final_report_docx = output_dir / "final_pics_report.docx"
    blocked_report_txt = output_dir / "final_pics_report_NOT_GENERATED.txt"

    verified_articles = [article for article in raw_candidates if is_verified_article(article)]
    write_articles_csv(raw_candidates, raw_csv)
    write_articles_csv(verified_articles, verified_articles_csv)
    write_articles_csv(approved_articles, approved_csv)
    write_articles_csv(approved_articles, accepted_articles_csv)
    write_articles_csv(approved_articles, legacy_articles_csv)
    write_articles_csv(review_queue_articles, review_queue_csv)
    write_articles_csv(editorial_result.rejected_articles, rejected_items_csv)
    write_verification_csv(verifications, verification_csv)
    write_source_recovery_report_csv(recovery_reports, recovery_csv)
    write_contextual_coverage_audit_csv(contextual_coverage_rows, contextual_coverage_csv)
    write_date_uncertain_csv(review_queue_articles, uncertain_csv)
    write_debug_report_csv(verifications, debug_csv)
    write_story_clusters_csv(editorial_result.clusters, story_clusters_csv)
    write_editorial_qa_report_csv(editorial_result.qa_rows, editorial_qa_csv)
    write_review_queue_recovery_report_csv(editorial_result.review_recovery_rows, review_recovery_csv)
    write_raw_candidate_promotion_report_csv(editorial_result.raw_candidate_promotion_rows, raw_promotion_csv)
    write_classification_qa_report_csv(editorial_result.classification_qa_rows, classification_qa_csv)
    write_stale_story_report_csv(editorial_result.stale_story_rows, stale_story_csv)
    section_coverage_rows = build_section_coverage_audit(
        MANDATORY_PICS_SECTIONS,
        searched_by_section,
        approved_articles,
        editorial_result.clusters,
    )
    write_section_coverage_audit_csv(section_coverage_rows, section_coverage_csv)
    write_story_source_map_csv(editorial_result.clusters, approved_articles, story_source_map_csv)
    generate_evidence_package(output_dir)
    generate_source_failure_report(output_dir, sources, args.retries)
    generate_source_balance_report(output_dir, sources)
    generate_category_missed_story_audit(output_dir, sources)
    generate_discovery_precision_audit(
        output_dir,
        ["Libya Observer", "Libya Al Ahrar", "Al Wasat", "Al Mashhad"],
    )
    trust_gate_rows = evaluate_publication_readiness(
        sources=sources,
        verifications=verifications,
        approved_articles=approved_articles,
        story_cluster_count=len(editorial_result.clusters),
        qa_rows=editorial_result.qa_rows,
        section_coverage_rows=section_coverage_rows,
        stale_story_rows=editorial_result.stale_story_rows,
    )
    generate_report_generation_status(output_dir, trust_gate_rows)
    blocking_rows = [row for row in trust_gate_rows if row["result"] == "block"]
    if blocking_rows:
        if final_report_docx.exists():
            stale_name = f"final_pics_report_STALE_PREVIOUS_RUN_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.docx"
            final_report_docx.replace(output_dir / stale_name)
        blocked_report_txt.write_text(
            build_blocked_report_message(blocking_rows, start_date, end_date),
            encoding="utf-8",
        )
        logger.error(
            "Report generation blocked: %s",
            " | ".join(f"{row['check']}={row['status']}" for row in blocking_rows),
        )
    else:
        if blocked_report_txt.exists():
            blocked_report_txt.unlink()
        write_final_pics_report_docx(
            editorial_result.clusters,
            editorial_result.qa_rows,
            final_report_docx,
            start_date,
            end_date,
        )

    logger.info("Wrote %s raw candidates to %s", len(raw_candidates), raw_csv)
    logger.info("Wrote %s verified article-stage rows to %s", len(verified_articles), verified_articles_csv)
    logger.info("Wrote %s editorially approved articles to %s", len(approved_articles), approved_csv)
    logger.info("Wrote %s accepted article-stage rows to %s", len(approved_articles), accepted_articles_csv)
    logger.info("Wrote %s review queue articles to %s", len(review_queue_articles), review_queue_csv)
    logger.info("Wrote %s rejected items to %s", len(editorial_result.rejected_articles), rejected_items_csv)
    logger.info("Wrote verification table to %s", verification_csv)
    logger.info("Wrote source recovery report to %s", recovery_csv)
    logger.info("Wrote contextual coverage audit to %s", contextual_coverage_csv)
    logger.info("Wrote %s date-uncertain candidates to %s", len(review_queue_articles), uncertain_csv)
    logger.info("Wrote source debug report to %s", debug_csv)
    logger.info("Wrote %s story clusters to %s", len(editorial_result.clusters), story_clusters_csv)
    logger.info("Wrote editorial QA report to %s", editorial_qa_csv)
    logger.info("Wrote raw candidate promotion report to %s", raw_promotion_csv)
    logger.info("Wrote classification QA report to %s", classification_qa_csv)
    logger.info("Wrote stale story report to %s", stale_story_csv)
    logger.info("Wrote section coverage audit to %s", section_coverage_csv)
    logger.info("Wrote story source map to %s", story_source_map_csv)
    if blocking_rows:
        logger.info("Did not generate final PICS report; wrote blocked marker to %s", blocked_report_txt)
    else:
        logger.info("Wrote final PICS report to %s", final_report_docx)
    logger.info("Wrote evidence package to %s", output_dir)
    logger.info("Wrote source failure report to %s", output_dir / "source_failure_report.csv")
    logger.info("Wrote source balance report to %s", output_dir / "source_balance_report.csv")
    logger.info("Wrote category missed-story audit to %s", output_dir / "missed_story_audit.csv")
    logger.info("Wrote category missing-story audit to %s", output_dir / "missing_story_audit.csv")
    logger.info("Wrote report generation status to %s", output_dir / "report_generation_status.csv")
    logger.info("Wrote discovery precision audit to %s", output_dir / "discovery_precision_audit.csv")
    logger.info("Removed %s same-source duplicate approved articles", editorial_result.duplicates_removed)
    print_terminal_summary(
        verifications,
        approved_articles,
        review_queue_articles,
        editorial_result.duplicates_removed,
        len(editorial_result.clusters),
        editorial_result.qa_rows,
        len(editorial_result.rejected_articles),
    )
    if blocking_rows:
        print("\nREPORT GENERATION BLOCKED")
        for row in blocking_rows:
            print(f"- {row['check']}: {row['status']} ({row['value']} vs {row['threshold']})")


def evaluate_publication_readiness(
    sources: list[dict],
    verifications: list[SourceVerification],
    approved_articles: list[Article],
    story_cluster_count: int,
    qa_rows: list[dict[str, str]],
    section_coverage_rows: list[dict[str, str]] | None = None,
    stale_story_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    verification_by_source = {verification.source_name: verification for verification in verifications}
    tier1_sources = [source for source in sources if SOURCE_TIERS.get(source["id"]) == "Tier 1"]
    tier2_sources = [source for source in sources if SOURCE_TIERS.get(source["id"]) == "Tier 2"]
    tier1_failed = [
        source
        for source in tier1_sources
        if verification_by_source.get(source["name"])
        and verification_by_source[source["name"]].fetch_status == "failed_fetch"
    ]
    tier2_failed = [
        source
        for source in tier2_sources
        if verification_by_source.get(source["name"])
        and verification_by_source[source["name"]].fetch_status == "failed_fetch"
    ]
    tier1_rate = len(tier1_failed) / len(tier1_sources) if tier1_sources else 0.0
    tier2_rate = len(tier2_failed) / len(tier2_sources) if tier2_sources else 0.0
    qa_failures = [row for row in qa_rows if row["status"] != "pass"]
    section_coverage_rows = section_coverage_rows or []
    stale_story_rows = stale_story_rows or []
    unsearched_sections = [row for row in section_coverage_rows if row["status"] == "not_searched"]
    weak_sections = [
        row
        for row in section_coverage_rows
        if row["status"] in {"empty_after_targeted_search", "weak_after_targeted_search"}
    ]
    rows = [
        readiness_row(
            "tier1_failure_rate",
            tier1_rate,
            "max 20%",
            "block" if tier1_rate > 0.20 else "pass",
            f"{len(tier1_failed)}/{len(tier1_sources)} Tier 1 sources failed: {', '.join(source['name'] for source in tier1_failed[:8])}",
        ),
        readiness_row(
            "tier2_failure_rate",
            tier2_rate,
            "max 20%",
            "block" if tier2_rate > 0.20 else "pass",
            f"{len(tier2_failed)}/{len(tier2_sources)} Tier 2 sources failed: {', '.join(source['name'] for source in tier2_failed[:8])}",
        ),
        readiness_row(
            "accepted_article_floor",
            len(approved_articles),
            ">= 40",
            "block" if len(approved_articles) < 40 else "pass",
            "Accepted articles below floor; secondary discovery pass is required before publication."
            if len(approved_articles) < 40
            else "Accepted article volume meets production floor.",
        ),
        readiness_row(
            "cluster_floor",
            story_cluster_count,
            ">= 20",
            "block" if story_cluster_count < 20 else "pass",
            "Story cluster count below floor; run cluster_integrity_audit and split unrelated developments."
            if story_cluster_count < 20
            else "Story cluster count meets production floor.",
        ),
        readiness_row(
            "editorial_qa",
            len(qa_failures),
            "0 failures",
            "block" if qa_failures else "pass",
            "; ".join(f"{row['check']}={row['details']}" for row in qa_failures[:5]) or "All editorial QA checks passed.",
        ),
        readiness_row(
            "temporal_validation",
            len(stale_story_rows),
            "0 stale stories",
            "block" if stale_story_rows else "pass",
            "; ".join(f"{row['source']}: {row['headline'][:80]}" for row in stale_story_rows[:5])
            or "Every final item has a publication date or material update inside the monitoring window.",
        ),
        readiness_row(
            "mandatory_section_search",
            len(unsearched_sections),
            "0 unsearched sections",
            "block" if unsearched_sections else "pass",
            "; ".join(row["section"] for row in unsearched_sections)
            or "All mandatory PICS sections were actively searched.",
        ),
        readiness_row(
            "section_coverage_strength",
            len(weak_sections),
            "audit weak/empty sections",
            "pass",
            "; ".join(f"{row['section']}={row['status']}" for row in weak_sections)
            or "All searched sections met the configured story floor.",
        ),
    ]
    return rows


def readiness_row(check: str, value: float | int, threshold: str, result: str, notes: str) -> dict[str, str]:
    if isinstance(value, float):
        status = f"{value:.1%}"
    else:
        status = str(value)
    return {
        "check": check,
        "status": status,
        "value": status,
        "threshold": threshold,
        "result": result,
        "notes": notes,
    }


def build_blocked_report_message(
    blocking_rows: list[dict[str, str]],
    start_date: datetime | None,
    end_date: datetime | None,
) -> str:
    period = ""
    if start_date and end_date:
        period = f"{start_date.date().isoformat()} to {end_date.date().isoformat()}"
    elif start_date:
        period = start_date.date().isoformat()
    lines = [
        "FINAL PICS REPORT NOT GENERATED",
        "",
        f"Coverage period: {period or 'unspecified'}",
        "",
        "The collection run failed production trust gates. A final UNSMIL/PICS report cannot be trusted until the issues below are resolved and the collection is rerun.",
        "",
    ]
    for row in blocking_rows:
        lines.append(f"- {row['check']}: {row['status']} (threshold: {row['threshold']})")
        if row.get("notes"):
            lines.append(f"  {row['notes']}")
    lines.extend(
        [
            "",
            "Required next actions:",
            "- Review source_failure_report.csv for failed source diagnostics.",
            "- Restore source/network access and rerun collection.",
            "- If accepted_article_floor remains below 40, run a secondary discovery pass.",
            "- If cluster_floor remains below 20, run cluster integrity review and split unrelated developments.",
        ]
    )
    return "\n".join(lines) + "\n"


def enrich_article(article: Article, start_date: datetime | None) -> None:
    url_date = parse_date_from_url(article.url)
    if article.published_at and url_date and has_exact_date_in_url(article.url):
        if article.published_at.date() != url_date.date():
            article.date_status = "date_conflict"
            article.notes = append_note(article.notes, f"url_date_conflict:{url_date.date().isoformat()}")
            article.qa_notes = append_note(article.qa_notes, "URL date differs from article metadata date")
    if article.published_at is None:
        if url_date:
            if is_month_only_url(article.url):
                article.published_at = url_date
                article.date_status = "parsed"
                article.raw_date = article.raw_date or article.url
                article.date_source = "url_month_latest_day"
            else:
                article.published_at = url_date
                article.date_source = "url"
    if article.published_at and article.date_status != "date_conflict":
        article.date_status = "parsed"
    article.section_guess = guess_section(article)
    article.subsection_guess = guess_subsection(article)


def is_verified_article(article: Article) -> bool:
    if not article.url or not article.title.strip():
        return False
    if not looks_like_article_url(article.url):
        return False
    if article.relevance_reason == "non_article_url":
        return False
    return bool(article.published_at or article.summary.strip() or article.content_text.strip())


def classify_date(article: Article, start_date: datetime | None, end_date: datetime | None) -> str:
    if article.date_status == "date_conflict":
        return "date_conflict"
    if article.published_at is None:
        return "missing_date"
    if start_date is None and end_date is None:
        return "in_range"
    if in_date_range(article.published_at, start_date, end_date, keep_undated=False):
        return "in_range"
    return "outside_date_window"


def check_libya_relevance(article: Article, source: dict) -> tuple[bool, str]:
    url_path = unquote(urlparse(article.url).path)
    text = f"{article.title} {article.summary} {article.content_text} {url_path} {article.section}".casefold()
    positive_matches = keyword_matches(text, all_libya_positive_keywords())
    entity_matches = keyword_matches(text, [*LIBYA_ENTITIES, *LIBYA_INSTITUTIONS])
    section_matches = [
        f"{section}:{match}"
        for section, markers in PICS_SECTION_KEYWORDS.items()
        for match in keyword_matches(text, markers)
    ]
    noise_matches = keyword_matches(text, INTERNATIONAL_NOISE)
    score = relevance_score(
        source_id=source["id"],
        positive_matches=positive_matches,
        entity_matches=entity_matches,
        section_matches=section_matches,
        noise_matches=noise_matches,
    )
    if score >= 6 and (entity_matches or (source["id"] in LIBYA_SOURCE_IDS and section_matches)):
        reason = f"weighted_libya_score:{score}"
        if positive_matches:
            reason += f"; keyword_match:{positive_matches[0]}"
        if noise_matches:
            reason += f"; noise_context_overridden:{noise_matches[0]}"
        return True, reason
    if noise_matches and not entity_matches:
        return False, f"global_news_without_libya_angle:{noise_matches[0]}; weighted_score:{score}"
    if source["id"] in LIBYA_SOURCE_IDS and section_matches:
        return True, f"libya_source_topic_weighted:{section_matches[0]}; score:{score}"
    if source["id"] in LIBYA_SOURCE_IDS:
        return False, f"libya_source_without_article_level_evidence; weighted_score:{score}"
    return False, f"not_libya_related; weighted_score:{score}"


def keyword_matches(text: str, keywords: list[str]) -> list[str]:
    matches: list[str] = []
    for keyword in keywords:
        lowered = keyword.casefold()
        if not lowered:
            continue
        if re.fullmatch(r"[a-z0-9_-]+", lowered):
            found = re.search(rf"(?<![a-z0-9_-]){re.escape(lowered)}(?![a-z0-9_-])", text) is not None
        else:
            found = lowered in text
        if found and keyword not in matches:
            matches.append(keyword)
    return matches


def relevance_score(
    source_id: str,
    positive_matches: list[str],
    entity_matches: list[str],
    section_matches: list[str],
    noise_matches: list[str],
) -> int:
    score = 0
    score += min(12, len(positive_matches) * 2)
    score += min(12, len(entity_matches) * 4)
    score += min(8, len(section_matches))
    if source_id in LIBYA_SOURCE_IDS:
        score += 3
    score -= min(8, len(noise_matches) * 2)
    return score


def looks_like_article_url(url: str) -> bool:
    lowered = url.casefold()
    if re.search(r"/(?:article|news|details|story)\.php\?", lowered) and re.search(r"[?&](?:id|news_id|nid)=", lowered):
        return True
    blocked = (
        "/category/",
        "/tag/",
        "/tags/",
        "/section/",
        "/author/",
        "/search",
        "search?",
        "site-search",
        "?s=",
        "&s=",
        ".pdf",
    )
    if any(marker in lowered for marker in blocked):
        return False
    path = urlparse(url).path.strip("/")
    if not path:
        return False
    if path.casefold() in {"news", "latest", "libya", "world", "international", "africa"}:
        return False
    return True


def is_month_only_url(url: str) -> bool:
    return bool(re.search(r"/20\d{2}/[01]?\d(?:/|$)", url)) and not bool(
        re.search(r"/20\d{2}/[01]?\d/[0-3]?\d(?:/|[-_])", url)
    )


def same_month(left: datetime, right: datetime) -> bool:
    return left.year == right.year and left.month == right.month


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}; {note}"


def guess_subsection(article: Article) -> str:
    text = f"{article.section} {article.title} {article.summary} {article.content_text[:1000]}".casefold()
    matches = [
        (subsection, len(keyword_matches(text, markers)))
        for subsection, markers in SUBSECTION_KEYWORDS.items()
        if keyword_matches(text, markers)
    ]
    if not matches:
        return f"Other {article.section_guess or guess_section(article)} news"
    matches.sort(key=lambda item: (-item[1], list(SUBSECTION_KEYWORDS).index(item[0])))
    return matches[0][0]


def guess_section(article: Article) -> str:
    text = f"{article.section} {article.title} {article.summary} {article.content_text[:1000]}".casefold()
    section_scores = []
    for section in SECTION_ORDER:
        markers = PICS_SECTION_KEYWORDS.get(section, [])
        matches = keyword_matches(text, markers)
        if matches:
            section_scores.append((section, len(matches)))
    if not section_scores:
        return "Other"
    section_scores.sort(key=lambda item: (-item[1], SECTION_ORDER.index(item[0])))
    section = section_scores[0][0]
    if section in {"Banking", "Energy"}:
        return "Economy"
    return section


def deduplicate_articles(articles: list[Article]) -> list[Article]:
    seen: set[str] = set()
    unique: list[Article] = []
    for article in articles:
        if article.duplicate_key in seen:
            continue
        seen.add(article.duplicate_key)
        unique.append(article)
    return unique


def deduplicate_cross_source_stories(articles: list[Article]) -> tuple[list[Article], list[Article]]:
    seen: dict[tuple[str, str], Article] = {}
    seen_by_date: dict[str, list[tuple[set[str], Article]]] = {}
    unique: list[Article] = []
    duplicates: list[Article] = []

    for article in articles:
        key = story_duplicate_key(article)
        if key is None:
            unique.append(article)
            continue
        primary = seen.get(key)
        token_key = normalized_story_tokens(article.title)
        fuzzy_primary = find_similar_story(article, token_key, seen_by_date)
        if primary is None and fuzzy_primary is None:
            seen[key] = article
            seen_by_date.setdefault(article.published_at.date().isoformat(), []).append((token_key, article))
            unique.append(article)
            continue
        primary = primary or fuzzy_primary
        article.duplicate_status = "duplicate_cross_source"
        article.include_candidate = False
        article.qa_status = "duplicate"
        article.qa_notes = append_note(
            article.qa_notes,
            f"Duplicate story removed from approved output; primary source: {primary.source_name}",
        )
        article.notes = append_note(article.notes, f"duplicate_of:{primary.source_name}")
        primary.notes = append_note(primary.notes, f"also_reported_by:{article.source_name}<{article.url}>")
        primary.qa_notes = append_note(primary.qa_notes, f"cross_source_duplicate_retained:{article.source_name}")
        duplicates.append(article)

    return unique, duplicates


def find_similar_story(
    article: Article,
    token_key: set[str],
    seen_by_date: dict[str, list[tuple[set[str], Article]]],
) -> Article | None:
    if not article.published_at or len(token_key) < 4:
        return None
    date_key = article.published_at.date().isoformat()
    for existing_tokens, existing_article in seen_by_date.get(date_key, []):
        if existing_article.source_name == article.source_name:
            continue
        union_size = len(token_key | existing_tokens)
        token_similarity = len(token_key & existing_tokens) / union_size if union_size else 0.0
        semantic_similarity = multilingual_title_similarity(article.title, existing_article.title)
        if max(token_similarity, semantic_similarity) >= 0.52:
            return existing_article
    return None


def multilingual_title_similarity(left: str, right: str) -> float:
    """Lightweight multilingual title similarity used when transformer embeddings are unavailable."""
    left_norm = normalize_for_semantic_similarity(left)
    right_norm = normalize_for_semantic_similarity(right)
    if not left_norm or not right_norm:
        return 0.0
    left_ngrams = char_ngrams(left_norm)
    right_ngrams = char_ngrams(right_norm)
    ngram_union = len(left_ngrams | right_ngrams)
    ngram_score = len(left_ngrams & right_ngrams) / ngram_union if ngram_union else 0.0
    left_tokens = normalized_story_tokens(left_norm)
    right_tokens = normalized_story_tokens(right_norm)
    token_union = len(left_tokens | right_tokens)
    token_score = len(left_tokens & right_tokens) / token_union if token_union else 0.0
    return max(token_score, (token_score * 0.45) + (ngram_score * 0.55))


def normalize_for_semantic_similarity(value: str) -> str:
    text = value.casefold()
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    text = text.translate(
        str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"})
    )
    return re.sub(r"\s+", " ", re.sub(r"[^\w\u0600-\u06ff]+", " ", text)).strip()


def char_ngrams(value: str, size: int = 4) -> set[str]:
    compact = value.replace(" ", "")
    if len(compact) <= size:
        return {compact}
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def story_duplicate_key(article: Article) -> tuple[str, str] | None:
    if not article.published_at:
        return None
    title_key = normalize_story_title(article.title)
    if len(title_key) < 18:
        return None
    return article.published_at.date().isoformat(), title_key


def normalize_story_title(title: str) -> str:
    return " ".join(sorted(normalized_story_tokens(title)))


def normalized_story_tokens(title: str) -> set[str]:
    text = title.casefold()
    text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
    replacements = str.maketrans(
        {
            "أ": "ا",
            "إ": "ا",
            "آ": "ا",
            "ٱ": "ا",
            "ى": "ي",
            "ؤ": "و",
            "ئ": "ي",
            "ة": "ه",
        }
    )
    text = text.translate(replacements)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^\w\u0600-\u06ff]+", " ", text)
    return {normalize_arabic_token(token) for token in text.split() if token not in STORY_STOPWORDS and len(token) > 1}


def normalize_arabic_token(token: str) -> str:
    if re.search(r"[\u0600-\u06ff]", token) and len(token) > 4:
        for prefix in ("وال", "بال", "لل", "ال", "و", "ب", "ل"):
            if token.startswith(prefix) and len(token) - len(prefix) >= 3:
                return token[len(prefix) :]
    return token


STORY_STOPWORDS = {
    "في",
    "من",
    "عن",
    "على",
    "الى",
    "إلى",
    "مع",
    "بعد",
    "قبل",
    "هذا",
    "هذه",
    "ذلك",
    "تلك",
    "التي",
    "الذي",
    "انه",
    "انها",
    "and",
    "the",
    "for",
    "from",
    "with",
    "after",
    "before",
    "this",
    "that",
    "says",
    "over",
}


def dedupe_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def determine_zero_reason(
    fetched_pages: int,
    candidate_count: int,
    article_pages_opened: int,
    date_parsed_count: int,
    accepted_count: int,
    rejected_date_count: int,
    rejected_relevance_count: int,
    uncertain_date_count: int,
    errors: list[str],
    non_article_count: int = 0,
) -> str:
    if accepted_count:
        return ""
    if fetched_pages == 0 and errors:
        error_text = " ".join(errors).casefold()
        if any(marker in error_text for marker in ("403", "cloudflare", "captcha", "access denied")):
            return "blocked_by_site"
        return "fetch_failed"
    if candidate_count == 0:
        return "no_article_links_found"
    if non_article_count and non_article_count >= max(candidate_count - 1, 1):
        return "selector_failed"
    if article_pages_opened and date_parsed_count == 0 and (uncertain_date_count or rejected_date_count):
        return "date_parsing_failed"
    relevant_candidate_count = candidate_count - rejected_relevance_count
    if rejected_date_count and relevant_candidate_count > 0 and rejected_date_count >= relevant_candidate_count - uncertain_date_count:
        return "all_items_outside_date_window"
    if rejected_relevance_count and rejected_relevance_count >= candidate_count - rejected_date_count - uncertain_date_count:
        return "all_items_failed_relevance_filter"
    if uncertain_date_count and uncertain_date_count >= candidate_count - rejected_relevance_count - rejected_date_count:
        return "date_uncertain_review_required"
    return "unknown"


def print_terminal_summary(
    verifications: list[SourceVerification],
    approved_articles: list[Article],
    review_queue_articles: list[Article],
    duplicates_removed: int,
    story_cluster_count: int = 0,
    qa_rows: list[dict[str, str]] | None = None,
    rejected_count: int = 0,
) -> None:
    failed = [verification for verification in verifications if verification.fetch_status == "failed_fetch"]
    succeeded = [verification for verification in verifications if verification.fetch_status != "failed_fetch"]
    approved_by_source = Counter(article.source_name for article in approved_articles)
    review_by_source = Counter(article.source_name for article in review_queue_articles)

    print("\nScraper summary")
    print(f"- total sources checked: {len(verifications)}")
    print(f"- sources succeeded: {len(succeeded)}")
    print(f"- sources failed: {len(failed)}")
    print(f"- total candidate links found: {sum(v.candidate_links_found for v in verifications)}")
    print(f"- total article pages opened: {sum(v.article_pages_opened for v in verifications)}")
    print(f"- editorially approved articles: {len(approved_articles)}")
    print(f"- story clusters: {story_cluster_count}")
    print(f"- review queue items: {len(review_queue_articles)}")
    print(f"- rejected items: {rejected_count}")
    print(f"- same-source duplicates removed from approved output: {duplicates_removed}")
    print(f"- total rejected outside date window: {sum(v.rejected_date_count for v in verifications)}")
    print(f"- total rejected non-Libya items: {sum(v.rejected_relevance_count for v in verifications)}")
    if qa_rows is not None:
        passed = sum(1 for row in qa_rows if row["status"] == "pass")
        print(f"- editorial QA checks passed: {passed}/{len(qa_rows)}")

    print("\nSource contribution table:")
    print("source,approved,review")
    contribution_sources = sorted(
        set(approved_by_source) | set(review_by_source),
        key=lambda source_name: (-approved_by_source[source_name], -review_by_source[source_name], source_name),
    )
    if contribution_sources:
        for source_name in contribution_sources:
            print(f"{source_name},{approved_by_source[source_name]},{review_by_source[source_name]}")
    else:
        print("None,0,0")

    print("\nFailed sources list:")
    if failed:
        for verification in failed:
            print(f"- {verification.source_name}: {verification.error or verification.zero_result_reason}")
    else:
        print("- None")

    print("\nSources with zero accepted articles:")
    zero_sources = [verification for verification in verifications if verification.accepted_count == 0]
    if zero_sources:
        for verification in zero_sources:
            print(
                f"- {verification.source_name}: {verification.zero_result_reason} "
                f"(links={verification.candidate_links_found}, opened={verification.article_pages_opened}, "
                f"dates={verification.date_parsed_count}, rejected_date={verification.rejected_date_count}, "
                f"rejected_relevance={verification.rejected_relevance_count}, uncertain={verification.uncertain_date_count})"
            )
    else:
        print("- None")


async def debug_source(
    requested_source: str,
    sources: list[dict],
    fetcher: BrowserFetcher,
    keywords: list[str],
    start_date: datetime | None,
    max_pages: int,
) -> None:
    source = find_source(requested_source, sources)
    if not source:
        available = ", ".join(source["name"] for source in sources)
        raise SystemExit(f"Debug source not found: {requested_source}. Available: {available}")

    parser_cls = get_parser(source["parser"])
    parser_patterns = getattr(parser_cls, "article_url_patterns", ())
    collection_urls = build_collection_urls(source, keywords, start_date)[:max_pages]
    collection_urls.extend(source.get("fallback_urls", []))
    collection_urls = dedupe_values(collection_urls)

    print(f"\nDebug source: {source['name']} ({source['id']})")
    print(f"- parser: {source['parser']}")
    print(f"- selectors used: {source.get('selectors', {})}")
    print(f"- planned URLs: {len(collection_urls)}")

    for collection_url in collection_urls:
        print(f"\nURL: {collection_url}")
        try:
            result = await fetcher.fetch(collection_url)
        except Exception as exc:
            print(f"- fetch failed: {exc}")
            continue

        soup = soup_from_html(result.html)
        links = []
        detected = []
        rejected = []
        for link in soup.select("a[href]"):
            title = clean_text(link.get_text(" ", strip=True))
            url = normalize_url(result.final_url, link.get("href") or "", source["id"])
            if not url:
                rejected.append(("", "empty_or_invalid_url"))
                continue
            links.append((title, url))
            if is_noise_link(title, url):
                rejected.append((url, "noise_link"))
                continue
            if not is_probable_article_url(url, parser_patterns):
                rejected.append((url, "not_probable_article_url"))
                continue
            detected.append((title, url))

        has_json_ld, has_open_graph, date_candidates = page_metadata_flags(result.html)
        page_title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""

        print(f"- page title: {page_title}")
        print(f"- response status: {result.status_code or ''}")
        print(f"- final URL: {result.final_url}")
        print(f"- number of links found: {len(links)}")
        print(f"- article links detected: {len(detected)}")
        print(f"- article links rejected: {len(rejected)}")
        print(f"- JSON-LD found: {'yes' if has_json_ld else 'no'}")
        print(f"- OpenGraph metadata found: {'yes' if has_open_graph else 'no'}")
        print(f"- date candidates found: {date_candidates[:20]}")

        print("- first 100 discovered links:")
        for title, url in links[:100]:
            print(f"  - {title[:90]} | {url}")

        print("- first 50 detected article links:")
        for title, url in detected[:50]:
            print(f"  - {title[:90]} | {url}")

        print("- first 50 rejected links:")
        for url, reason in rejected[:50]:
            print(f"  - {reason}: {url}")


def find_source(requested_source: str, sources: list[dict]) -> dict | None:
    needle = requested_source.casefold().strip()
    for source in sources:
        if needle in {source["id"].casefold(), source["name"].casefold()}:
            return source
    for source in sources:
        if needle in source["name"].casefold():
            return source
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Libya-related headlines for UNSMIL/PICS media monitoring.")
    parser.add_argument("--sources", default="sources.json", help="Path to source configuration JSON.")
    parser.add_argument("--output-dir", default="output", help="Directory for CSV outputs.")
    parser.add_argument("--start-date", help="Inclusive start date, for example 2026-06-01.")
    parser.add_argument("--end-date", help="Inclusive end date, for example 2026-06-02.")
    parser.add_argument("--keyword", action="append", default=[], help="Additional Arabic or English keyword filter.")
    parser.add_argument("--source-id", action="append", default=[], help="Limit run to one or more source IDs.")
    parser.add_argument("--debug-source", help="Print detailed extraction diagnostics for a source name or ID.")
    parser.add_argument("--timeout", type=int, default=20, help="Browser timeout per page in seconds.")
    parser.add_argument("--retries", type=int, default=1, help="Fetch retry attempts per source.")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Base retry delay in seconds.")
    parser.add_argument("--max-pages-per-source", type=int, default=10, help="Maximum primary/search/archive URLs to fetch per source.")
    parser.add_argument("--max-article-pages-per-source", type=int, default=50, help="Maximum candidate article pages to open per source.")
    parser.add_argument("--no-contextual-expansion", action="store_true", help="Disable the PICS contextual expansion pass.")
    parser.add_argument("--max-contextual-pages-per-source", type=int, default=4, help="Maximum reaction/analysis/opinion search URLs to fetch per source.")
    parser.add_argument("--max-contextual-article-pages-per-source", type=int, default=12, help="Maximum contextual candidate article pages to verify per source.")
    parser.add_argument("--no-section-coverage-expansion", action="store_true", help="Disable mandatory PICS section coverage searches.")
    parser.add_argument("--max-section-pages-per-source", type=int, default=3, help="Maximum targeted section URLs to fetch per source.")
    parser.add_argument("--max-section-article-pages-per-source", type=int, default=8, help="Maximum targeted section candidate article pages to verify per source.")
    parser.add_argument("--relevance-threshold", type=int, default=DEFAULT_RELEVANCE_THRESHOLD, help="Minimum editorial relevance score for final approval.")
    parser.add_argument("--show-browser", action="store_true", help="Run Playwright with a visible browser.")
    parser.add_argument("--log-file", default="logs/scraper.log", help="Path to scraper log file.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
