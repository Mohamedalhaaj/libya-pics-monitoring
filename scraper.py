from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from datetime import date, datetime

from parsers import get_parser
from parsers.feed import discover_feed_url
from utils.config import load_sources
from utils.dates import in_date_range, parse_cli_date
from utils.enrich import EnrichmentUnavailable, enrich_report
from utils.exports import (
    build_fallback_report,
    ensure_output_dir,
    write_articles_csv,
    write_verification_csv,
    write_word_report,
)
from utils.fetcher import BrowserFetcher
from utils.logger import setup_logging
from utils.models import Article, SourceVerification, StructuredReport
from utils.resolver import resolve_articles

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
    discover_feeds: bool = False,
) -> tuple[list[Article], SourceVerification]:
    """Collect articles for one source. Date filtering happens later, after the
    article-page resolver fills in reliable dates."""
    source_id = source["id"]
    logger.info("Collecting source=%s url=%s", source_id, source["url"])
    try:
        if source["parser"] == "feed":
            feed_url = source.get("feed_url") or source["url"]
            result = await fetcher.fetch(feed_url, settle=False)
            articles = get_parser("feed")(source, keywords).parse(result.html)
            final_url = result.final_url
        else:
            # Only wait on an explicit, specific selector. Passing the generic
            # article selector (which matches dozens of `li` elements) made
            # Playwright log floods and could crash the driver, so rely on the
            # fetcher's networkidle settle for JS-rendered lists instead.
            result = await fetcher.fetch(source["url"], wait_for_selector=source.get("wait_for_selector"))
            final_url = result.final_url
            articles = get_parser(source["parser"])(source, keywords).parse(result.html)
            if discover_feeds:
                articles = await _augment_with_feed(source, keywords, fetcher, result.html, final_url, articles)

        return articles, SourceVerification(
            source_id=source_id,
            source_name=source["name"],
            url=final_url,
            status="ok",
            articles_found=len(articles),
        )
    except Exception as exc:
        logger.exception("Source failed: %s", source_id)
        return [], SourceVerification(
            source_id=source_id,
            source_name=source["name"],
            url=source["url"],
            status="failed",
            error=str(exc),
        )


async def _augment_with_feed(source, keywords, fetcher, html, base, html_articles):
    """If the page advertises an RSS/Atom feed, fold its items (which carry
    reliable dates) into the HTML-scraped set, deduped by URL/title."""
    feed_url = discover_feed_url(html, base)
    if not feed_url:
        return html_articles
    try:
        feed_result = await fetcher.fetch(feed_url, settle=False)
        feed_articles = get_parser("feed")(source, keywords).parse(feed_result.html)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Feed discovery failed for %s: %s", source["id"], exc)
        return html_articles

    by_key: dict[str, Article] = {}
    for article in html_articles + feed_articles:
        key = article.url or article.title
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = article
        elif existing.published_at is None and article.published_at is not None:
            by_key[key] = article  # prefer the copy that has a date
    logger.info("Source %s: merged feed %s (+%s items)", source["id"], feed_url, len(feed_articles))
    return list(by_key.values())


async def run(args: argparse.Namespace) -> None:
    setup_logging(args.log_file, args.verbose)
    output_dir = ensure_output_dir(args.output_dir)
    start_date = parse_cli_date(args.start_date)
    end_date = parse_cli_date(args.end_date, end_of_day=True)
    sources = load_sources(args.sources)
    keywords = DEFAULT_KEYWORDS + args.keyword

    logger.info("Loaded %s enabled sources", len(sources))
    all_articles: list[Article] = []
    verifications: list[SourceVerification] = []

    # CDP drives the user's real browser; keep concurrency low there to avoid a
    # storm of tabs. Headless can fan out freely.
    concurrency = args.concurrency if args.concurrency else (2 if args.cdp_url else 6)
    # A date window is only trustworthy with resolved per-article dates.
    resolve_dates = args.resolve_dates or bool(start_date or end_date)

    async with BrowserFetcher(
        timeout_ms=args.timeout * 1000,
        retries=args.retries,
        retry_delay_seconds=args.retry_delay,
        headless=not args.show_browser,
        cdp_url=args.cdp_url,
    ) as fetcher:
        semaphore = asyncio.Semaphore(concurrency)

        async def collect(source):
            async with semaphore:
                return await scrape_source(source, fetcher, keywords, discover_feeds=args.discover_feeds)

        results = await asyncio.gather(*(collect(source) for source in sources))
        for articles, verification in results:
            all_articles.extend(articles)
            verifications.append(verification)

        if resolve_dates:
            undated = [a for a in all_articles if a.published_at is None and a.url]
            if undated:
                await resolve_articles(fetcher, undated, concurrency=concurrency)

    # Apply the date window now that dates are as reliable as we can make them.
    all_articles = [
        a for a in all_articles
        if in_date_range(a.published_at, start_date, end_date, args.keep_undated)
    ]
    all_articles.sort(key=lambda article: article.published_at or datetime.min, reverse=True)

    report_date = format_report_date(args.report_date, end_date)
    report = build_report(all_articles, report_date, enrich=not args.no_enrich, model=args.model)

    articles_csv = output_dir / "libya_media_headlines.csv"
    verification_csv = output_dir / "source_verification_table.csv"
    report_docx = output_dir / "unsmil_pics_daily_media_report.docx"

    write_articles_csv(all_articles, articles_csv)
    write_verification_csv(verifications, verification_csv)
    write_word_report(report, verifications, report_docx)

    logger.info("Wrote %s articles to %s", len(all_articles), articles_csv)
    logger.info("Wrote verification table to %s", verification_csv)
    logger.info("Wrote Word report (%s headlines) to %s", report.total_headlines(), report_docx)


def build_report(
    articles: list[Article],
    report_date: str,
    enrich: bool,
    model: str,
) -> StructuredReport:
    """Produce the editorial report, preferring Claude enrichment.

    Falls back to a mechanical source-grouped layout when enrichment is
    disabled or unavailable (no API key, missing SDK, or a failed call).
    """
    if enrich:
        try:
            return enrich_report(articles, report_date, model=model)
        except EnrichmentUnavailable as exc:
            logger.warning("Enrichment unavailable, using mechanical fallback: %s", exc)
    else:
        logger.info("Enrichment disabled; using mechanical fallback layout")
    return build_fallback_report(articles, report_date)


def format_report_date(explicit: str | None, end_date: datetime | None) -> str:
    """Title-friendly coverage date, e.g. '3 June'."""
    if explicit:
        return explicit
    day: date = end_date.date() if end_date else date.today()
    return f"{day.day} {day.strftime('%B')}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Libya-related headlines for UNSMIL/PICS media monitoring.")
    parser.add_argument("--sources", default="sources.json", help="Path to source configuration JSON.")
    parser.add_argument("--output-dir", default="output", help="Directory for CSV and Word report outputs.")
    parser.add_argument("--start-date", help="Inclusive start date, for example 2026-06-01.")
    parser.add_argument("--end-date", help="Inclusive end date, for example 2026-06-03.")
    parser.add_argument(
        "--report-date",
        help="Title date for the report, e.g. '3 June'. Defaults to the end date (or today).",
    )
    parser.add_argument(
        "--model",
        default="claude-opus-4-8",
        help="Claude model used for editorial enrichment.",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip Claude enrichment and use the mechanical source-grouped layout.",
    )
    parser.add_argument("--keyword", action="append", default=[], help="Additional Arabic or English keyword filter.")
    parser.add_argument("--keep-undated", action="store_true", help="Keep articles where the source does not expose a date.")
    parser.add_argument("--timeout", type=int, default=30, help="Browser timeout per page in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Fetch retry attempts per source.")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=0,
        help="Parallel fetches (0 = auto: 6 headless, 2 over CDP).",
    )
    parser.add_argument(
        "--resolve-dates",
        action="store_true",
        help="Fetch article pages to read precise publish dates (auto-on with a date window).",
    )
    parser.add_argument(
        "--discover-feeds",
        action="store_true",
        help="Also pull each source's advertised RSS/Atom feed (reliable dates, bypasses bot/JS).",
    )
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Base retry delay in seconds.")
    parser.add_argument("--show-browser", action="store_true", help="Run Playwright with a visible browser.")
    parser.add_argument(
        "--cdp-url",
        help=(
            "Fetch through an already-running Chrome via DevTools, e.g. "
            "http://localhost:9222. Uses the real browser's identity/cookies to "
            "reach bot-protected, JS-rendered sources. Launch Chrome with "
            "--remote-debugging-port=9222 first."
        ),
    )
    parser.add_argument("--log-file", default="logs/scraper.log", help="Path to scraper log file.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
