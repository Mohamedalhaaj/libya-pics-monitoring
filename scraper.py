from __future__ import annotations

import argparse
import asyncio
import logging
import re
from pathlib import Path

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
    "UNSMIL",
    "ليبيا",
    "الليبي",
    "طرابلس",
    "بنغازي",
    "مصراتة",
    "درنة",
    "البعثة الأممية",
]


async def scrape_source(
    source: dict,
    fetcher: BrowserFetcher,
    keywords: list[str],
    start_date,
    end_date,
    max_pages: int,
) -> tuple[list[Article], list[Article], SourceVerification]:
    source_id = source["id"]
    collection_urls = build_collection_urls(source, keywords, start_date)[:max_pages]
    parser_cls = get_parser(source["parser"])
    fetched_urls: list[str] = []
    errors: list[str] = []
    parsed_candidates: list[Article] = []

    logger.info("Collecting source=%s planned_urls=%s", source_id, len(collection_urls))
    for collection_url in collection_urls:
        try:
            result = await fetcher.fetch(collection_url)
            fetched_urls.append(result.final_url)
            parser = parser_cls(source, keywords, collection_url=result.final_url)
            page_candidates = parser.parse(result.html)
            logger.info(
                "Parsed source=%s url=%s candidates=%s",
                source_id,
                result.final_url,
                len(page_candidates),
            )
            parsed_candidates.extend(page_candidates)
        except Exception as exc:
            message = f"{collection_url}: {exc}"
            errors.append(message)
            logger.warning("Fetch failed for source=%s %s", source_id, message)

    parsed_candidates = deduplicate_articles(parsed_candidates)
    relevant_candidates = [candidate for candidate in parsed_candidates if is_relevant(candidate, source)]
    final_articles: list[Article] = []
    uncertain_articles: list[Article] = []

    for article in relevant_candidates:
        enrich_article(article, start_date)
        if article.published_at is None:
            uncertain_articles.append(article)
            continue
        if in_date_range(article.published_at, start_date, end_date, keep_undated=False):
            final_articles.append(article)

    zero_reason = determine_zero_reason(
        fetched_pages=len(fetched_urls),
        parsed_candidates=len(parsed_candidates),
        relevant_candidates=len(relevant_candidates),
        final_articles=len(final_articles),
        uncertain_articles=len(uncertain_articles),
        errors=errors,
        start_date=start_date,
        end_date=end_date,
    )
    if zero_reason:
        logger.info(
            "Zero/low-result diagnostic source=%s reason=%s parsed=%s relevant=%s uncertain=%s errors=%s",
            source_id,
            zero_reason,
            len(parsed_candidates),
            len(relevant_candidates),
            len(uncertain_articles),
            " | ".join(errors),
        )

    status = "failed" if not fetched_urls and errors else "ok"
    verification = SourceVerification(
        source_id=source_id,
        source_name=source["name"],
        url=" | ".join(fetched_urls[:3]) or source["url"],
        status=status,
        articles_found=len(final_articles),
        pages_checked=len(fetched_urls),
        links_found=len(parsed_candidates),
        candidates_found=len(relevant_candidates),
        date_uncertain_items=len(uncertain_articles),
        zero_reason=zero_reason,
        error=" | ".join(errors[:3]),
    )
    return final_articles, uncertain_articles, verification


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
    all_articles.sort(key=lambda article: article.published_at or source_sort_floor(), reverse=True)

    articles_csv = output_dir / "libya_media_headlines.csv"
    verification_csv = output_dir / "source_verification_table.csv"
    uncertain_csv = output_dir / "date_uncertain_items.csv"

    write_articles_csv(all_articles, articles_csv)
    write_verification_csv(verifications, verification_csv)
    write_date_uncertain_csv(date_uncertain_articles, uncertain_csv)

    logger.info("Wrote %s articles to %s", len(all_articles), articles_csv)
    logger.info("Wrote verification table to %s", verification_csv)
    logger.info("Wrote %s date-uncertain candidates to %s", len(date_uncertain_articles), uncertain_csv)
    print_terminal_summary(verifications)


def source_sort_floor():
    from datetime import datetime

    return datetime.min


def is_relevant(article: Article, source: dict) -> bool:
    text = f"{article.title} {article.summary} {article.url}".casefold()
    if article.matched_keywords:
        return is_article_like(article)
    if source.get("require_keyword_match", True):
        return False
    return is_article_like(article) and (
        source.get("country_focus") == "Libya"
        or "libya" in text
        or "ليبيا" in text
    )


def is_article_like(article: Article) -> bool:
    title = article.title.strip()
    if len(title) < 12:
        return False
    url = article.url.casefold()
    blocked_url_markers = [
        "facebook.com",
        "twitter.com",
        "x.com/",
        "instagram.com",
        "youtube.com",
        "whatsapp",
        "mailto:",
        "javascript:",
        "/terms",
        "/privacy",
        "/contact",
        "/about",
    ]
    if any(marker in url for marker in blocked_url_markers):
        return False
    structural_url_markers = [
        "/section/",
        "/category/",
        "/tag/",
        "/tags/",
        "/archive",
        ".pdf",
    ]
    if any(marker in url for marker in structural_url_markers) and not parse_date_from_url(article.url):
        return False
    blocked_titles = {
        "home",
        "الرئيسية",
        "اتصل بنا",
        "contact us",
        "privacy policy",
        "من نحن",
        "about us",
    }
    return title.casefold() not in blocked_titles


def enrich_article(article: Article, start_date) -> None:
    if article.published_at is None:
        url_date = parse_date_from_url(article.url)
        if url_date:
            if start_date and is_month_only_url(article.url) and same_month(url_date, start_date):
                url_date = start_date
            article.published_at = url_date
            article.date_source = "url"
    article.section_guess = guess_section(article)


def is_month_only_url(url: str) -> bool:
    return bool(re.search(r"/20\d{2}/[01]?\d(?:/|$)", url)) and not bool(
        re.search(r"/20\d{2}/[01]?\d/[0-3]?\d(?:/|[-_])", url)
    )


def same_month(left, right) -> bool:
    return left.year == right.year and left.month == right.month


def guess_section(article: Article) -> str:
    text = f"{article.section} {article.title} {article.summary}".casefold()
    sections = [
        ("united_nations", ["unsmil", "united nations", "srsg", "dsrsg", "الأمم المتحدة", "البعثة الأممية"]),
        ("politics", ["election", "government", "parliament", "dialogue", "roadmap", "حكومة", "انتخابات", "مجلس", "خارطة"]),
        ("military_security", ["security", "armed", "clashes", "army", "crime", "أمني", "اشتباك", "مسلح", "جريمة"]),
        ("migration", ["migrant", "migration", "refugee", "iom", "unhcr", "مهاجر", "هجرة", "لاجئ"]),
        ("economy", ["central bank", "economy", "oil", "fuel", "bank", "مصرف", "اقتصاد", "نفط", "وقود"]),
        ("environment", ["weather", "flood", "earthquake", "climate", "طقس", "فيضانات", "زلزال", "مناخ"]),
        ("regional_international", ["italy", "tunisia", "turkey", "egypt", "chad", "إيطاليا", "تونس", "تركيا", "مصر", "تشاد"]),
        ("culture_sports", ["sport", "football", "culture", "heritage", "رياضة", "كرة", "ثقافة", "تراث"]),
    ]
    for section, markers in sections:
        if any(marker in text for marker in markers):
            return section
    return "general"


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


def determine_zero_reason(
    fetched_pages: int,
    parsed_candidates: int,
    relevant_candidates: int,
    final_articles: int,
    uncertain_articles: int,
    errors: list[str],
    start_date,
    end_date,
) -> str:
    if final_articles:
        return ""
    if fetched_pages == 0 and errors:
        return "fetch_failed"
    if parsed_candidates == 0:
        return "no_links_found"
    if relevant_candidates == 0:
        return "keyword_filtering_removed_items"
    if uncertain_articles and (start_date or end_date):
        return "date_parsing_failed"
    if start_date or end_date:
        return "date_filtering_removed_items"
    return "no_articles_collected"


def print_terminal_summary(verifications: list[SourceVerification]) -> None:
    print("\nScraper summary")
    print("Articles collected per source:")
    for verification in verifications:
        print(f"- {verification.source_name}: {verification.articles_found}")

    failed = [verification for verification in verifications if verification.status == "failed"]
    zero = [verification for verification in verifications if verification.articles_found == 0]

    print("\nFailed sources:")
    if failed:
        for verification in failed:
            print(f"- {verification.source_name}: {verification.error or verification.zero_reason}")
    else:
        print("- None")

    print("\nSources with zero articles:")
    if zero:
        for verification in zero:
            print(f"- {verification.source_name}: {verification.zero_reason or 'unknown'}")
    else:
        print("- None")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Libya-related headlines for UNSMIL/PICS media monitoring.")
    parser.add_argument("--sources", default="sources.json", help="Path to source configuration JSON.")
    parser.add_argument("--output-dir", default="output", help="Directory for CSV and Word report outputs.")
    parser.add_argument("--start-date", help="Inclusive start date, for example 2026-06-01.")
    parser.add_argument("--end-date", help="Inclusive end date, for example 2026-06-03.")
    parser.add_argument("--keyword", action="append", default=[], help="Additional Arabic or English keyword filter.")
    parser.add_argument("--source-id", action="append", default=[], help="Limit run to one or more source IDs.")
    parser.add_argument("--timeout", type=int, default=30, help="Browser timeout per page in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Fetch retry attempts per source.")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Base retry delay in seconds.")
    parser.add_argument("--max-pages-per-source", type=int, default=6, help="Maximum primary/search/archive URLs to fetch per source.")
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
