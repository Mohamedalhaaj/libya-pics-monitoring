from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from utils.source_plan import CATEGORY_SEARCH_TERMS, SOURCE_TIERS


DISCOVERY_PRECISION_FIELDS = [
    "source",
    "candidate_links",
    "article_links",
    "non_article_links",
    "inside_window",
    "outside_window",
    "precision_rate",
    "top_failure_reason",
]

SOURCE_BALANCE_FIELDS = [
    "source",
    "tier",
    "candidate_links_found",
    "article_pages_opened",
    "verified_articles",
    "accepted_articles",
    "review_queue_items",
    "rejected_articles",
    "top_rejection_reason",
    "status",
    "notes",
]

MISSED_STORY_FIELDS = [
    "category",
    "expected",
    "found",
    "number_of_items",
    "sources_checked",
    "specific_search_terms_used",
    "status",
    "notes",
]

SOURCE_FAILURE_FIELDS = [
    "source",
    "error",
    "failure_count",
    "last_successful_fetch",
    "retry_attempts",
    "recovery_recommendation",
]

REPORT_STATUS_FIELDS = [
    "check",
    "status",
    "value",
    "threshold",
    "result",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def generate_evidence_package(output_dir: str | Path) -> None:
    output = Path(output_dir)
    approved = read_csv(output / "approved_headlines.csv")
    raw = read_csv(output / "raw_candidates.csv")
    review = read_csv(output / "review_queue.csv")
    rejected = read_csv(output / "rejected_items.csv")
    clusters = read_csv(output / "story_clusters.csv")
    verification = read_csv(output / "source_verification_table.csv")

    verification_by_source = {row.get("source_name", ""): row for row in verification}
    approved_by_url = {row.get("article_url", ""): row for row in approved}
    raw_by_url = {row.get("article_url", ""): row for row in raw}
    cluster_by_url: dict[str, dict[str, str]] = {}
    for cluster in clusters:
        for url in split_multi(cluster.get("article_urls", "")):
            cluster_by_url[url] = cluster

    source_audit_rows = []
    for row in verification:
        source_audit_rows.append(
            {
                "source_name": row.get("source_name", ""),
                "fetch_status": row.get("fetch_status", ""),
                "discovery_sources": row.get("source_url", ""),
                "collection_timestamp": row.get("checked_at", ""),
                "candidate_links_found": row.get("candidate_links_found", ""),
                "article_pages_opened": row.get("article_pages_opened", ""),
                "date_parsed_count": row.get("date_parsed_count", ""),
                "accepted_count": row.get("accepted_count", ""),
                "review_count": row.get("uncertain_date_count", ""),
                "rejected_date_count": row.get("rejected_date_count", ""),
                "rejected_relevance_count": row.get("rejected_relevance_count", ""),
                "zero_result_reason": row.get("zero_result_reason", ""),
                "error": row.get("error", ""),
            }
        )

    discovery_rows = []
    for cluster in clusters:
        for url in split_multi(cluster.get("article_urls", "")):
            article = approved_by_url.get(url) or raw_by_url.get(url, {})
            source_name = article.get("source_name", infer_source_for_url(url, approved))
            source_verification = verification_by_source.get(source_name, {})
            discovery_rows.append(
                {
                    "story_id": cluster.get("story_id", ""),
                    "story_headline": cluster.get("canonical_headline", ""),
                    "section": cluster.get("section", ""),
                    "priority": cluster.get("priority", ""),
                    "source_name": source_name,
                    "source_url": url,
                    "publication_date": article.get("publication_date", cluster.get("publication_date", "")),
                    "discovery_source": article.get("discovery_source") or source_verification.get("source_url", ""),
                    "collection_timestamp": source_verification.get("checked_at", ""),
                    "parser_used": article.get("parser_used", ""),
                    "evidence_status": evidence_status(article, source_verification),
                    "qa_status": article.get("qa_status", ""),
                    "date_status": article.get("date_status", ""),
                }
            )

    contribution = defaultdict(lambda: Counter())
    for article in approved:
        source = article.get("source_name", "")
        contribution[source]["approved_articles"] += 1
        if article.get("story_id"):
            contribution[source][f"story::{article['story_id']}"] += 1
    for cluster in clusters:
        for source in split_multi(cluster.get("sources", "")):
            contribution[source]["story_clusters"] += 1
    for article in review:
        contribution[article.get("source_name", "")]["review_items"] += 1
    for article in rejected:
        contribution[article.get("source_name", "")]["rejected_items"] += 1

    source_contribution_rows = []
    for source, counts in sorted(contribution.items()):
        if not source:
            continue
        source_contribution_rows.append(
            {
                "source_name": source,
                "story_clusters": str(counts["story_clusters"]),
                "approved_articles": str(counts["approved_articles"]),
                "review_items": str(counts["review_items"]),
                "rejected_items": str(counts["rejected_items"]),
                "collection_timestamp": verification_by_source.get(source, {}).get("checked_at", ""),
            }
        )

    final_urls = set(cluster_by_url)
    missed_rows = []
    for article in [*review, *rejected]:
        url = article.get("article_url", "")
        if not url or url in final_urls:
            continue
        source_name = article.get("source_name", "")
        source_verification = verification_by_source.get(source_name, {})
        missed_rows.append(
            {
                "source_name": source_name,
                "headline": article.get("headline_original", ""),
                "article_url": url,
                "publication_date": article.get("publication_date", ""),
                "discovery_source": article.get("discovery_source") or source_verification.get("source_url", ""),
                "collection_timestamp": source_verification.get("checked_at", ""),
                "audit_status": "not_in_final_report",
                "reason": article.get("rejection_reason")
                or article.get("editorial_reason")
                or article.get("date_status")
                or article.get("relevance_reason")
                or article.get("notes", ""),
                "qa_status": article.get("qa_status", ""),
                "date_status": article.get("date_status", ""),
            }
        )

    write_csv(
        output / "source_audit.csv",
        source_audit_rows,
        [
            "source_name",
            "fetch_status",
            "discovery_sources",
            "collection_timestamp",
            "candidate_links_found",
            "article_pages_opened",
            "date_parsed_count",
            "accepted_count",
            "review_count",
            "rejected_date_count",
            "rejected_relevance_count",
            "zero_result_reason",
            "error",
        ],
    )
    write_csv(
        output / "discovery_evidence.csv",
        discovery_rows,
        [
            "story_id",
            "story_headline",
            "section",
            "priority",
            "source_name",
            "source_url",
            "publication_date",
            "discovery_source",
            "collection_timestamp",
            "parser_used",
            "evidence_status",
            "qa_status",
            "date_status",
        ],
    )
    write_csv(
        output / "source_contribution.csv",
        source_contribution_rows,
        ["source_name", "story_clusters", "approved_articles", "review_items", "rejected_items", "collection_timestamp"],
    )
    write_csv(
        output / "excluded_item_audit.csv",
        missed_rows,
        [
            "source_name",
            "headline",
            "article_url",
            "publication_date",
            "discovery_source",
            "collection_timestamp",
            "audit_status",
            "reason",
            "qa_status",
            "date_status",
        ],
    )


def generate_source_balance_report(output_dir: str | Path, sources: list[dict[str, str]]) -> None:
    output = Path(output_dir)
    verification = read_csv(output / "source_verification_table.csv")
    raw = read_csv(output / "raw_candidates.csv")
    approved = read_csv(output / "accepted_articles.csv")
    if not approved:
        approved = read_csv(output / "approved_headlines.csv")
    review = read_csv(output / "review_queue.csv")
    rejected = read_csv(output / "rejected_items.csv")

    source_meta = {source["name"]: source for source in sources}
    verified_by_source = Counter(row.get("source_name", "") for row in raw if is_verified_article_row(row))
    accepted_by_source = Counter(row.get("source_name", "") for row in approved)
    review_by_source = Counter(row.get("source_name", "") for row in review)
    rejected_by_source = Counter(row.get("source_name", "") for row in rejected)
    rejection_reasons: dict[str, Counter] = defaultdict(Counter)
    for row in rejected:
        reason = (
            row.get("rejection_reason")
            or row.get("editorial_reason")
            or row.get("relevance_reason")
            or row.get("date_status")
            or row.get("qa_notes")
            or "unknown"
        )
        rejection_reasons[row.get("source_name", "")][reason] += 1

    rows = []
    verification_sources = {row.get("source_name", "") for row in verification}
    all_sources = sorted(verification_sources | set(source_meta))
    for source_name in all_sources:
        source = source_meta.get(source_name, {})
        source_id = source.get("id", "")
        tier = SOURCE_TIERS.get(source_id, source.get("tier", "Tier 3" if source_name else ""))
        verification_row = next((row for row in verification if row.get("source_name") == source_name), {})
        candidates = int_or_zero(verification_row.get("candidate_links_found", ""))
        opened = int_or_zero(verification_row.get("article_pages_opened", ""))
        verified_count = verified_by_source[source_name]
        accepted_count = accepted_by_source[source_name]
        review_count = review_by_source[source_name]
        rejected_count = rejected_by_source[source_name]
        top_reason = rejection_reasons[source_name].most_common(1)[0][0] if rejection_reasons[source_name] else ""
        status, notes = source_balance_status(
            tier=tier,
            fetch_status=verification_row.get("fetch_status", ""),
            zero_result_reason=verification_row.get("zero_result_reason", ""),
            candidates=candidates,
            opened=opened,
            verified=verified_count,
            accepted=accepted_count,
            review=review_count,
            rejected=rejected_count,
            failed=int_or_zero(verification_row.get("failed_count", "")),
        )
        rows.append(
            {
                "source": source_name,
                "tier": tier,
                "candidate_links_found": str(candidates),
                "article_pages_opened": str(opened),
                "verified_articles": str(verified_count),
                "accepted_articles": str(accepted_count),
                "review_queue_items": str(review_count),
                "rejected_articles": str(rejected_count),
                "top_rejection_reason": top_reason,
                "status": status,
                "notes": notes,
            }
        )

    write_csv(output / "source_balance_report.csv", rows, SOURCE_BALANCE_FIELDS)


def generate_category_missed_story_audit(output_dir: str | Path, sources: list[dict[str, str]]) -> None:
    output = Path(output_dir)
    approved = read_csv(output / "accepted_articles.csv")
    if not approved:
        approved = read_csv(output / "approved_headlines.csv")
    review = read_csv(output / "review_queue.csv")
    raw = read_csv(output / "raw_candidates.csv")
    verification = read_csv(output / "source_verification_table.csv")

    source_names = {source["name"] for source in sources}
    checked_sources = [
        row.get("source_name", "")
        for row in verification
        if row.get("source_name") in source_names and row.get("fetch_status") in {"ok", "success", ""}
    ]
    failed_tier1 = [
        row.get("source_name", "")
        for row in verification
        if row.get("fetch_status") != "ok"
        and SOURCE_TIERS.get(next((source["id"] for source in sources if source["name"] == row.get("source_name")), ""), "") == "Tier 1"
    ]

    audit_rows = []
    for category, terms in CATEGORY_SEARCH_TERMS.items():
        approved_matches = matching_rows(approved, terms, category)
        review_matches = matching_rows(review, terms, category)
        raw_matches = matching_rows(raw, terms, category)
        found_count = len(approved_matches)
        if found_count:
            found = "yes"
            status = "found"
            notes = f"{found_count} accepted item(s) matched category terms or section."
        elif review_matches:
            found = "partial"
            status = "review_only"
            notes = f"{len(review_matches)} item(s) were collected but require date/editorial review."
        elif raw_matches:
            found = "partial"
            status = "collected_not_accepted"
            notes = f"{len(raw_matches)} candidate item(s) were collected but not accepted."
        else:
            found = "no"
            status = "not_found_but_searched"
            notes = "No collected item matched this category in the configured live source set."
        if failed_tier1:
            notes = f"{notes} Tier 1 fetch risk: {', '.join(failed_tier1[:4])}."

        audit_rows.append(
            {
                "category": category,
                "expected": "yes",
                "found": found,
                "number_of_items": str(found_count or len(review_matches) or len(raw_matches)),
                "sources_checked": "; ".join(checked_sources),
                "specific_search_terms_used": "; ".join(terms),
                "status": status,
                "notes": notes,
            }
        )

    write_csv(output / "missed_story_audit.csv", audit_rows, MISSED_STORY_FIELDS)
    write_csv(output / "missing_story_audit.csv", audit_rows, MISSED_STORY_FIELDS)


def generate_source_failure_report(
    output_dir: str | Path,
    sources: list[dict[str, str]],
    retry_attempts: int,
) -> None:
    output = Path(output_dir)
    verification = read_csv(output / "source_verification_table.csv")
    rows = []
    for row in verification:
        failed = row.get("fetch_status") == "failed_fetch" or row.get("zero_result_reason") == "fetch_failed"
        if not failed:
            continue
        source_name = row.get("source_name", "")
        rows.append(
            {
                "source": source_name,
                "error": row.get("error", ""),
                "failure_count": row.get("failed_count", "0"),
                "last_successful_fetch": last_successful_fetch(source_name, verification),
                "retry_attempts": str(retry_attempts),
                "recovery_recommendation": recovery_recommendation(row, sources),
            }
        )
    write_csv(output / "source_failure_report.csv", rows, SOURCE_FAILURE_FIELDS)


def generate_report_generation_status(output_dir: str | Path, rows: list[dict[str, str]]) -> None:
    write_csv(Path(output_dir) / "report_generation_status.csv", rows, REPORT_STATUS_FIELDS)


def generate_discovery_precision_audit(output_dir: str | Path, priority_sources: list[str] | None = None) -> None:
    output = Path(output_dir)
    raw = read_csv(output / "raw_candidates.csv")
    rejected = read_csv(output / "rejected_items.csv")
    rejected_by_url = {(row.get("source_name", ""), row.get("article_url", "")): row for row in rejected}

    rows_by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in raw:
        merged = dict(row)
        merged.update(rejected_by_url.get((row.get("source_name", ""), row.get("article_url", "")), {}))
        source = merged.get("source_name", "")
        if priority_sources and source not in priority_sources:
            continue
        rows_by_source[source].append(merged)

    audit_rows = []
    for source in priority_sources or sorted(rows_by_source):
        rows = rows_by_source.get(source, [])
        candidate_links = len(rows)
        article_links = sum(1 for row in rows if classify_discovery_candidate(row) == "article")
        non_article_links = candidate_links - article_links
        inside_window = sum(1 for row in rows if row.get("date_status") == "in_range")
        outside_window = sum(1 for row in rows if row.get("date_status") == "outside_date_window")
        failures = Counter(discovery_failure_reason(row) for row in rows)
        failures.pop("valid_article_candidate", None)
        top_failure_reason = failures.most_common(1)[0][0] if failures else ""
        audit_rows.append(
            {
                "source": source,
                "candidate_links": str(candidate_links),
                "article_links": str(article_links),
                "non_article_links": str(non_article_links),
                "inside_window": str(inside_window),
                "outside_window": str(outside_window),
                "precision_rate": f"{(article_links / candidate_links):.1%}" if candidate_links else "0.0%",
                "top_failure_reason": top_failure_reason,
            }
        )

    write_csv(output / "discovery_precision_audit.csv", audit_rows, DISCOVERY_PRECISION_FIELDS)


def classify_discovery_candidate(row: dict[str, str]) -> str:
    reason = discovery_failure_reason(row)
    if reason in {"category_page", "search_page", "tag_page"}:
        return reason
    return "article"


def discovery_failure_reason(row: dict[str, str]) -> str:
    url = row.get("article_url", "")
    title = row.get("headline_original", "").casefold()
    parsed = urlparse(url)
    path = parsed.path.casefold().rstrip("/")
    lowered_url = url.casefold()
    if any(marker in lowered_url for marker in ("?s=", "/search", "keyword=", "search=")) or title.startswith(
        "you searched for"
    ):
        return "search_page"
    if any(marker in path for marker in ("/tag/", "/tags/")):
        return "tag_page"
    if (
        any(marker in path for marker in ("/category/", "/section/"))
        or path in {"", "/latest", "/live", "/timeline", "/ads", "/frequency"}
        or row.get("rejection_reason") == "non_article_url"
    ):
        return "category_page"
    if row.get("date_status") == "outside_date_window":
        return "old_article"
    if row.get("date_status") in {"missing_date", "ambiguous_date", "date_conflict"}:
        return "date_uncertain_article"
    if row.get("relevance_status") == "rejected" or row.get("rejection_reason") == "not_libya_related":
        return "non_libya_article"
    return "valid_article_candidate"


def split_multi(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def infer_source_for_url(url: str, approved: list[dict[str, str]]) -> str:
    for article in approved:
        if article.get("article_url") == url:
            return article.get("source_name", "")
    return ""


def evidence_status(article: dict[str, str], source_verification: dict[str, str]) -> str:
    if not article:
        return "article_not_found_in_approved_csv"
    if not article.get("article_url"):
        return "missing_article_url"
    if not article.get("publication_date"):
        return "missing_publication_date"
    if not source_verification.get("checked_at"):
        return "missing_collection_timestamp"
    return "collected_from_source"


def last_successful_fetch(source_name: str, verification: list[dict[str, str]]) -> str:
    for row in verification:
        if row.get("source_name") == source_name and row.get("fetch_status") in {"ok", "success"}:
            return row.get("checked_at", "")
    return ""


def recovery_recommendation(row: dict[str, str], sources: list[dict[str, str]]) -> str:
    error = row.get("error", "").casefold()
    source_name = row.get("source_name", "")
    source = next((candidate for candidate in sources if candidate.get("name") == source_name), {})
    tier = SOURCE_TIERS.get(source.get("id", ""), "Tier 3")
    if "err_internet_disconnected" in error or "network is unreachable" in error:
        return f"{tier}: restore network connectivity and rerun full collection before publication"
    if "name_not_resolved" in error or "failed to resolve" in error:
        return f"{tier}: verify DNS/site availability, retry from stable network, and consider source mirror/RSS"
    if "403" in error or "cloudflare" in error or "captcha" in error or "access denied" in error:
        return f"{tier}: inspect browser access, headers, rate limits, and approved alternate feed"
    if "timeout" in error:
        return f"{tier}: increase timeout/retries and test homepage/category/search/article URLs manually"
    return f"{tier}: run debug_source and verify homepage, category, search, archive, pagination, RSS, and article selectors"


def is_verified_article_row(row: dict[str, str]) -> bool:
    if not row.get("article_url") or not row.get("headline_original"):
        return False
    if discovery_failure_reason(row) in {"category_page", "search_page", "tag_page"}:
        return False
    if row.get("qa_status") == "rejected" and row.get("relevance_reason") == "non_article_url":
        return False
    return True


def matching_rows(rows: list[dict[str, str]], terms: list[str], category: str) -> list[dict[str, str]]:
    matches = []
    lowered_terms = [term.casefold() for term in terms]
    for row in rows:
        haystack = " ".join(
            [
                row.get("headline_original", ""),
                row.get("article_snippet", ""),
                row.get("section_guess", ""),
                row.get("subsection_guess", ""),
                row.get("article_url", ""),
            ]
        ).casefold()
        if category.casefold() in haystack or any(term in haystack for term in lowered_terms):
            matches.append(row)
    return matches


def source_balance_status(
    *,
    tier: str,
    fetch_status: str,
    zero_result_reason: str,
    candidates: int,
    opened: int,
    verified: int,
    accepted: int,
    review: int,
    rejected: int,
    failed: int,
) -> tuple[str, str]:
    notes = []
    if fetch_status and fetch_status not in {"ok", "success"}:
        notes.append(f"fetch_status={fetch_status}")
    if zero_result_reason:
        notes.append(f"zero_result_reason={zero_result_reason}")
    if failed:
        notes.append(f"failed_fetches={failed}")
    if candidates and opened == 0:
        notes.append("candidate links found but no article pages opened")
    if candidates and verified == 0:
        notes.append("no verified article-level pages")
    if tier == "Tier 1" and accepted == 0:
        notes.append("Tier 1 source produced no accepted articles")
    if accepted:
        return "healthy", "; ".join(notes) or "accepted live items"
    if review:
        return "review_needed", "; ".join(notes) or "items collected but not auto-approved"
    if verified:
        return "verified_not_accepted", "; ".join(notes) or "article pages verified but rejected by date/relevance/editorial logic"
    if candidates:
        return "low_precision", "; ".join(notes) or "candidate discovery did not produce verified articles"
    return "no_output", "; ".join(notes) or "no candidates discovered"


def int_or_zero(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
