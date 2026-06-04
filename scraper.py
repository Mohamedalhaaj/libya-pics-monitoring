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
from utils.config import load_sources
from utils.dates import in_date_range, parse_cli_date, parse_date_from_url
from utils.exports import ensure_output_dir, write_articles_csv, write_date_uncertain_csv, write_verification_csv
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
    "brega",
    "sebha",
    "zuwara",
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
]

async def scrape_source(
    source: dict,
    fetcher: BrowserFetcher,
    keywords: list[str],
    start_date: datetime | None,
    end_date: datetime | None,
    max_pages: int,
) -> tuple[list[Article], list[Article], SourceVerification]:
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
    accepted: list[Article] = []
    uncertain: list[Article] = []
    rejected_date_count = 0
    rejected_relevance_count = 0
    date_parsed_count = 0

    for article in parsed_candidates:
        enrich_article(article, start_date)
        relevance_ok, relevance_reason = check_libya_relevance(article, source)
        article.relevance_reason = relevance_reason
        if not relevance_ok:
            article.notes = "not_libya_related"
            rejected_relevance_count += 1
            continue

        date_status = classify_date(article, start_date, end_date)
        article.date_status = date_status
        if article.published_at:
            date_parsed_count += 1
        if date_status == "in_range":
            article.include_candidate = True
            accepted.append(article)
        elif date_status in {"missing_date", "ambiguous_date"}:
            article.notes = date_status
            uncertain.append(article)
        else:
            article.notes = "outside_date_window"
            rejected_date_count += 1

    verification = SourceVerification(
        source_name=source["name"],
        source_url=" | ".join(fetched_urls[:3]) or source["url"],
        fetch_status="failed_fetch" if not fetched_urls and errors else "ok",
        candidate_links_found=len(parsed_candidates),
        article_pages_opened=0,
        date_parsed_count=date_parsed_count,
        accepted_count=len(accepted),
        rejected_date_count=rejected_date_count,
        rejected_relevance_count=rejected_relevance_count,
        uncertain_date_count=len(uncertain),
        failed_count=len(errors),
        zero_result_reason=determine_zero_reason(
            fetched_pages=len(fetched_urls),
            candidate_count=len(parsed_candidates),
            date_parsed_count=date_parsed_count,
            accepted_count=len(accepted),
            rejected_date_count=rejected_date_count,
            rejected_relevance_count=rejected_relevance_count,
            uncertain_date_count=len(uncertain),
            errors=errors,
        ),
        error=" | ".join(errors[:3]),
    )

    if verification.zero_result_reason:
        logger.info(
            "Zero-result diagnostic source=%s reason=%s candidates=%s accepted=%s rejected_date=%s rejected_relevance=%s uncertain=%s errors=%s",
            source["id"],
            verification.zero_result_reason,
            len(parsed_candidates),
            len(accepted),
            rejected_date_count,
            rejected_relevance_count,
            len(uncertain),
            " | ".join(errors),
        )

    return accepted, uncertain, verification


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
    all_articles: list[Article] = []
    date_uncertain_articles: list[Article] = []
    verifications: list[SourceVerification] = []

    async with BrowserFetcher(
        timeout_ms=args.timeout * 1000,
        retries=args.retries,
        retry_delay_seconds=args.retry_delay,
        headless=not args.show_browser,
    ) as fetcher:
        for source in sources:
            articles, uncertain_articles, verification = await scrape_source(
                source=source,
                fetcher=fetcher,
                keywords=keywords,
                start_date=start_date,
                end_date=end_date,
                max_pages=args.max_pages_per_source,
            )
            all_articles.extend(articles)
            date_uncertain_articles.extend(uncertain_articles)
            verifications.append(verification)

    all_articles = deduplicate_articles(all_articles)
    date_uncertain_articles = deduplicate_articles(date_uncertain_articles)
    all_articles.sort(key=lambda article: article.published_at or datetime.min, reverse=True)

    articles_csv = output_dir / "libya_media_headlines.csv"
    verification_csv = output_dir / "source_verification_table.csv"
    uncertain_csv = output_dir / "date_uncertain_items.csv"

    write_articles_csv(all_articles, articles_csv)
    write_verification_csv(verifications, verification_csv)
    write_date_uncertain_csv(date_uncertain_articles, uncertain_csv)

    logger.info("Wrote %s accepted articles to %s", len(all_articles), articles_csv)
    logger.info("Wrote verification table to %s", verification_csv)
    logger.info("Wrote %s date-uncertain candidates to %s", len(date_uncertain_articles), uncertain_csv)
    print_terminal_summary(verifications)


def enrich_article(article: Article, start_date: datetime | None) -> None:
    if article.published_at is None:
        url_date = parse_date_from_url(article.url)
        if url_date:
            if start_date and is_month_only_url(article.url) and same_month(url_date, start_date):
                url_date = start_date
            article.published_at = url_date
            article.date_source = "url"
    if article.published_at:
        article.date_status = "parsed"
    article.section_guess = guess_section(article)


def classify_date(article: Article, start_date: datetime | None, end_date: datetime | None) -> str:
    if article.published_at is None:
        return "missing_date"
    if start_date is None and end_date is None:
        return "in_range"
    if in_date_range(article.published_at, start_date, end_date, keep_undated=False):
        return "in_range"
    return "outside_date_window"


def check_libya_relevance(article: Article, source: dict) -> tuple[bool, str]:
    url_path = unquote(urlparse(article.url).path)
    text = f"{article.title} {article.summary} {url_path} {article.section}".casefold()
    matched = [keyword for keyword in LIBYA_KEYWORDS if keyword.casefold() in text]
    if matched:
        return True, f"keyword_match:{matched[0]}"
    return False, "not_libya_related"


def looks_like_article_url(url: str) -> bool:
    lowered = url.casefold()
    blocked = ("/category/", "/tag/", "/tags/", "/section/", "/author/", ".pdf")
    if any(marker in lowered for marker in blocked):
        return False
    return bool(re.search(r"/(?:20\d{2}/)?[^/?#]{12,}", lowered))


def is_month_only_url(url: str) -> bool:
    return bool(re.search(r"/20\d{2}/[01]?\d(?:/|$)", url)) and not bool(
        re.search(r"/20\d{2}/[01]?\d/[0-3]?\d(?:/|[-_])", url)
    )


def same_month(left: datetime, right: datetime) -> bool:
    return left.year == right.year and left.month == right.month


def guess_section(article: Article) -> str:
    text = f"{article.section} {article.title} {article.summary}".casefold()
    sections = [
        ("United Nations", ["unsmil", "united nations", "srsg", "dsrsg", "الأمم المتحدة", "البعثة الأممية"]),
        ("Politics", ["election", "government", "parliament", "dialogue", "roadmap", "حكومة", "انتخابات", "مجلس", "خارطة"]),
        ("Military & Security", ["security", "armed", "clashes", "army", "crime", "أمني", "اشتباك", "مسلح", "جريمة"]),
        ("Human Rights & Rule of Law", ["human rights", "court", "justice", "prison", "migrant", "refugee", "حقوق", "محكمة", "عدل", "سجن", "مهاجر", "لاجئ"]),
        ("Economy", ["central bank", "economy", "oil", "fuel", "bank", "مصرف", "اقتصاد", "نفط", "وقود"]),
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
    date_parsed_count: int,
    accepted_count: int,
    rejected_date_count: int,
    rejected_relevance_count: int,
    uncertain_date_count: int,
    errors: list[str],
) -> str:
    if accepted_count:
        return ""
    if fetched_pages == 0 and errors:
        return "fetch_failed"
    if candidate_count == 0:
        return "no_links_found"
    if date_parsed_count == 0 and uncertain_date_count:
        return "date_parsing_failed"
    if rejected_date_count and rejected_date_count >= candidate_count - rejected_relevance_count:
        return "all_items_outside_date_window"
    if rejected_relevance_count and rejected_relevance_count >= candidate_count - uncertain_date_count:
        return "all_items_failed_relevance_filter"
    return "unknown"


def print_terminal_summary(verifications: list[SourceVerification]) -> None:
    failed = [verification for verification in verifications if verification.fetch_status == "failed_fetch"]
    succeeded = [verification for verification in verifications if verification.fetch_status != "failed_fetch"]
    top_sources = Counter({verification.source_name: verification.accepted_count for verification in verifications})

    print("\nScraper summary")
    print(f"- total sources checked: {len(verifications)}")
    print(f"- sources succeeded: {len(succeeded)}")
    print(f"- sources failed: {len(failed)}")
    print(f"- total candidate links found: {sum(v.candidate_links_found for v in verifications)}")
    print(f"- total article pages opened: {sum(v.article_pages_opened for v in verifications)}")
    print(f"- total accepted items: {sum(v.accepted_count for v in verifications)}")
    print(f"- total date-uncertain items: {sum(v.uncertain_date_count for v in verifications)}")
    print(f"- total rejected outside date window: {sum(v.rejected_date_count for v in verifications)}")
    print(f"- total rejected non-Libya items: {sum(v.rejected_relevance_count for v in verifications)}")

    print("\nTop sources by accepted item count:")
    for source_name, count in top_sources.most_common(10):
        print(f"- {source_name}: {count}")

    print("\nFailed sources list:")
    if failed:
        for verification in failed:
            print(f"- {verification.source_name}: {verification.error or verification.zero_result_reason}")
    else:
        print("- None")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Libya-related headlines for UNSMIL/PICS media monitoring.")
    parser.add_argument("--sources", default="sources.json", help="Path to source configuration JSON.")
    parser.add_argument("--output-dir", default="output", help="Directory for CSV outputs.")
    parser.add_argument("--start-date", help="Inclusive start date, for example 2026-06-01.")
    parser.add_argument("--end-date", help="Inclusive end date, for example 2026-06-02.")
    parser.add_argument("--keyword", action="append", default=[], help="Additional Arabic or English keyword filter.")
    parser.add_argument("--source-id", action="append", default=[], help="Limit run to one or more source IDs.")
    parser.add_argument("--timeout", type=int, default=30, help="Browser timeout per page in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Fetch retry attempts per source.")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Base retry delay in seconds.")
    parser.add_argument("--max-pages-per-source", type=int, default=8, help="Maximum primary/search/archive URLs to fetch per source.")
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
