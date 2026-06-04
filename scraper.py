from __future__ import annotations

import argparse
import asyncio
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from parsers import get_parser
from parsers.common import clean_text, extract_article_page_details, is_noise_link, is_probable_article_url, normalize_url, page_metadata_flags, soup_from_html
from utils.config import load_sources
from utils.dates import has_exact_date_in_url, in_date_range, parse_cli_date, parse_date_from_url
from utils.exports import (
    ensure_output_dir,
    write_articles_csv,
    write_date_uncertain_csv,
    write_debug_report_csv,
    write_verification_csv,
)
from utils.fetcher import BrowserFetcher
from utils.logger import setup_logging
from utils.models import Article, SourceVerification
from utils.source_plan import build_collection_urls, sort_sources

logger = logging.getLogger(__name__)

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
) -> tuple[list[Article], list[Article], list[Article], SourceVerification]:
    collection_urls = build_collection_urls(source, keywords, start_date)[:max_pages]
    collection_urls.extend(source.get("fallback_urls", []))
    collection_urls = dedupe_values(collection_urls)
    parser_cls = get_parser(source["parser"])
    fetched_urls: list[str] = []
    errors: list[str] = []
    parsed_candidates: list[Article] = []

    logger.info("Collecting source=%s parser=%s planned_urls=%s", source["id"], source["parser"], len(collection_urls))
    for collection_url in collection_urls:
        try:
            result = await fetcher.fetch(collection_url)
            fetched_urls.append(result.final_url)
            parser = parser_cls(source, keywords, collection_url=result.final_url)
            page_candidates = parser.parse(result.html)
            logger.info(
                "Parsed source=%s url=%s candidates=%s",
                source["id"],
                result.final_url,
                len(page_candidates),
            )
            parsed_candidates.extend(page_candidates)
        except Exception as exc:
            message = f"{collection_url}: {exc}"
            errors.append(message)
            logger.warning("Fetch failed for source=%s %s", source["id"], message)

    parsed_candidates = deduplicate_articles(parsed_candidates)
    candidate_count = len(parsed_candidates)
    article_pages_opened = 0
    article_fetch_errors: list[str] = []
    enriched_candidates: list[Article] = []
    for article in parsed_candidates[:max_article_pages]:
        try:
            result = await asyncio.to_thread(fetcher.fetch_with_requests, article.url)
            article_pages_opened += 1
            enriched_candidates.append(extract_article_page_details(result.html, article))
        except Exception as requests_exc:
            try:
                result = await fetcher.fetch(article.url)
                article_pages_opened += 1
                enriched_candidates.append(extract_article_page_details(result.html, article))
            except Exception as exc:
                article_fetch_errors.append(f"{article.url}: requests={requests_exc}; playwright={exc}")
                logger.warning(
                    "Article fetch failed for source=%s url=%s requests=%s playwright=%s",
                    source["id"],
                    article.url,
                    requests_exc,
                    exc,
                )
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
            f"article_fetch_errors={len(article_fetch_errors)}"
        ),
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

    return raw_candidates, accepted, review_queue, verification


async def run(args: argparse.Namespace) -> None:
    setup_logging(args.log_file, args.verbose)
    output_dir = ensure_output_dir(args.output_dir)
    start_date = parse_cli_date(args.start_date)
    end_date = parse_cli_date(args.end_date, end_of_day=True)
    sources = sort_sources(load_sources(args.sources))
    if args.source_id:
        requested = set(args.source_id)
        sources = [source for source in sources if source["id"] in requested]
    keywords = DEFAULT_KEYWORDS + args.keyword

    logger.info("Loaded %s enabled sources", len(sources))
    raw_candidates: list[Article] = []
    approved_articles: list[Article] = []
    review_queue_articles: list[Article] = []
    verifications: list[SourceVerification] = []

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
            source_raw, source_approved, source_review, verification = await scrape_source(
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

    raw_candidates = deduplicate_articles(raw_candidates)
    approved_articles = deduplicate_articles(approved_articles)
    review_queue_articles = deduplicate_articles(review_queue_articles)
    approved_articles, duplicate_articles = deduplicate_cross_source_stories(approved_articles)
    approved_articles.sort(key=lambda article: article.published_at or datetime.min, reverse=True)

    raw_csv = output_dir / "raw_candidates.csv"
    approved_csv = output_dir / "approved_headlines.csv"
    legacy_articles_csv = output_dir / "libya_media_headlines.csv"
    review_queue_csv = output_dir / "review_queue.csv"
    verification_csv = output_dir / "source_verification_table.csv"
    uncertain_csv = output_dir / "date_uncertain_items.csv"
    debug_csv = output_dir / "source_debug_report.csv"

    write_articles_csv(raw_candidates, raw_csv)
    write_articles_csv(approved_articles, approved_csv)
    write_articles_csv(approved_articles, legacy_articles_csv)
    write_articles_csv(review_queue_articles, review_queue_csv)
    write_verification_csv(verifications, verification_csv)
    write_date_uncertain_csv(review_queue_articles, uncertain_csv)
    write_debug_report_csv(verifications, debug_csv)

    logger.info("Wrote %s raw candidates to %s", len(raw_candidates), raw_csv)
    logger.info("Wrote %s approved articles to %s", len(approved_articles), approved_csv)
    logger.info("Wrote %s review queue articles to %s", len(review_queue_articles), review_queue_csv)
    logger.info("Wrote verification table to %s", verification_csv)
    logger.info("Wrote %s date-uncertain candidates to %s", len(review_queue_articles), uncertain_csv)
    logger.info("Wrote source debug report to %s", debug_csv)
    logger.info("Removed %s cross-source duplicate approved articles", len(duplicate_articles))
    print_terminal_summary(verifications, approved_articles, review_queue_articles, len(duplicate_articles))


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
                article.date_status = "ambiguous_date"
                article.raw_date = article.raw_date or article.url
                article.date_source = "url_month_only"
            else:
                article.published_at = url_date
                article.date_source = "url"
    if article.published_at and article.date_status != "date_conflict":
        article.date_status = "parsed"
    article.section_guess = guess_section(article)
    article.subsection_guess = guess_subsection(article)


def classify_date(article: Article, start_date: datetime | None, end_date: datetime | None) -> str:
    if article.date_status == "date_conflict":
        return "date_conflict"
    if article.date_source == "url_month_only":
        return "ambiguous_date"
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
    matched = [keyword for keyword in EXPLICIT_LIBYA_KEYWORDS if keyword.casefold() in text]
    if matched:
        return True, f"keyword_match:{matched[0]}"
    noise_match = next((keyword for keyword in INTERNATIONAL_NOISE_KEYWORDS if keyword.casefold() in text), "")
    if noise_match:
        return False, f"global_news_without_libya_angle:{noise_match}"
    if source["id"] == "lana":
        return False, "lana_requires_explicit_libya_angle"
    topical_match = next((keyword for keyword in PUBLIC_AFFAIRS_KEYWORDS if keyword.casefold() in text), "")
    if source["id"] in LIBYA_SOURCE_IDS and topical_match:
        return True, f"libya_source_topic:{topical_match}"
    if source["id"] in LIBYA_SOURCE_IDS:
        return False, "libya_source_without_article_level_evidence"
    return False, "not_libya_related"


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
    text = f"{article.section} {article.title} {article.summary}".casefold()
    markers = [
        ("UNSMIL", ["unsmil", "البعثة الأممية"]),
        ("Government", ["government", "حكومة", "وزارة", "وزير"]),
        ("Elections", ["election", "انتخابات"]),
        ("Security", ["security", "armed", "clashes", "أمن", "اشتباك", "مسلح"]),
        ("Migration", ["migration", "migrant", "refugee", "هجرة", "مهاجر", "لاجئ"]),
        ("Oil & Energy", ["oil", "fuel", "noc", "brega", "نفط", "وقود", "البريقة"]),
        ("Banking", ["central bank", "currency", "مصرف", "عملة"]),
        ("Municipal Services", ["municipality", "public services", "بلدية", "خدمات"]),
        ("Health", ["health", "hospital", "صحة", "مستشفى"]),
        ("Foreign Relations", ["italy", "tunisia", "egypt", "إيطاليا", "تونس", "مصر"]),
    ]
    for subsection, words in markers:
        if any(word in text for word in words):
            return subsection
    return article.section_guess or "General"


def guess_section(article: Article) -> str:
    text = f"{article.section} {article.title} {article.summary}".casefold()
    sections = [
        ("United Nations", ["unsmil", "united nations", "srsg", "dsrsg", "الأمم المتحدة", "البعثة الأممية"]),
        ("Governance", ["government", "ministry", "minister", "cabinet", "governance", "حكومة", "وزارة", "وزير", "حوكمة"]),
        ("Politics", ["election", "parliament", "dialogue", "roadmap", "مجلس", "انتخابات", "حوار", "خارطة"]),
        ("Military & Security", ["security", "armed", "clashes", "army", "crime", "أمني", "اشتباك", "مسلح", "جريمة"]),
        ("Migration", ["migration", "migrant", "refugee", "هجرة", "مهاجر", "لاجئ"]),
        ("Human Rights", ["human rights", "court", "justice", "prison", "حقوق", "محكمة", "عدل", "سجن"]),
        ("Economy", ["central bank", "economy", "oil", "fuel", "bank", "مصرف", "اقتصاد", "نفط", "وقود"]),
        ("Municipalities & Public Services", ["municipality", "municipal", "public services", "electricity", "water", "education", "بلدية", "البلديات", "خدمات", "كهرباء", "مياه", "تعليم"]),
        ("Reconstruction", ["reconstruction", "rebuild", "infrastructure", "إعمار", "إعادة الإعمار", "بنية تحتية"]),
        ("Health", ["health", "hospital", "medical", "صحة", "مستشفى", "طبي"]),
        ("Environment", ["weather", "flood", "earthquake", "climate", "طقس", "فيضانات", "زلزال", "مناخ"]),
        ("Regional & International", ["italy", "tunisia", "turkey", "egypt", "chad", "إيطاليا", "تونس", "تركيا", "مصر", "تشاد"]),
        ("Varieties", ["sport", "football", "culture", "heritage", "رياضة", "كرة", "ثقافة", "تراث"]),
    ]
    for section, markers in sections:
        if any(marker in text for marker in markers):
            return section
    return "Politics"


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
        if union_size == 0:
            continue
        similarity = len(token_key & existing_tokens) / union_size
        if similarity >= 0.48:
            return existing_article
    return None


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
    return {token for token in text.split() if token not in STORY_STOPWORDS and len(token) > 1}


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
    print(f"- approved items after dedupe: {len(approved_articles)}")
    print(f"- review queue items: {len(review_queue_articles)}")
    print(f"- duplicates removed from approved output: {duplicates_removed}")
    print(f"- total rejected outside date window: {sum(v.rejected_date_count for v in verifications)}")
    print(f"- total rejected non-Libya items: {sum(v.rejected_relevance_count for v in verifications)}")

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
    parser.add_argument("--max-pages-per-source", type=int, default=8, help="Maximum primary/search/archive URLs to fetch per source.")
    parser.add_argument("--max-article-pages-per-source", type=int, default=35, help="Maximum candidate article pages to open per source.")
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
