from __future__ import annotations

import re
from datetime import date, datetime, time, timezone

from dateutil import parser as date_parser

# Matches dates embedded in article URLs, e.g. /2026/06/20/ or /2026/6/18.
_URL_DATE_RE = re.compile(r"/(20\d{2})/(\d{1,2})(?:/(\d{1,2}))?(?:/|$|[?#])")


def parse_cli_date(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    parsed = date_parser.parse(value)
    if isinstance(parsed, datetime):
        if parsed.time() == time.min and end_of_day:
            parsed = datetime.combine(parsed.date(), time.max)
        return parsed
    if isinstance(parsed, date):
        return datetime.combine(parsed, time.max if end_of_day else time.min)
    return None


def parse_article_date(value: str | None) -> datetime | None:
    if not value:
        return None
    # Fuzzy parsing happily turns arbitrary text (e.g. a category label that
    # landed in the date selector) into "today". Require at least one digit so
    # we only attempt to parse strings that plausibly contain a date.
    if not any(char.isdigit() for char in value):
        return None
    try:
        parsed = date_parser.parse(value, fuzzy=True)
    except (TypeError, ValueError, OverflowError):
        return None
    # Normalise to naive UTC so article dates compare consistently against the
    # naive CLI date bounds (see parse_cli_date).
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def parse_date_from_url(url: str | None) -> datetime | None:
    """Best-effort date from a date-stamped article URL.

    Only trusted when the URL carries a full year/month/day. Month-only URLs
    (e.g. WordPress /2026/06/slug) are treated as undated rather than guessing
    the 1st — guessing produced confidently-wrong dates that wrongly excluded
    in-window articles. Use the article-page resolver to date those precisely.
    """
    if not url:
        return None
    match = _URL_DATE_RE.search(url)
    if not match or not match.group(3):
        return None
    year, month, day = match.group(1), match.group(2), match.group(3)
    try:
        return datetime(int(year), int(month), int(day))
    except ValueError:
        return None


def in_date_range(
    published_at: datetime | None,
    start_date: datetime | None,
    end_date: datetime | None,
    keep_undated: bool,
) -> bool:
    if published_at is None:
        return keep_undated
    if start_date and published_at < start_date:
        return False
    if end_date and published_at > end_date:
        return False
    return True
