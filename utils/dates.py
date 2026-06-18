from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser

TRIPOLI_TZ = ZoneInfo("Africa/Tripoli")

ARABIC_MONTHS = {
    "يناير": 1,
    "كانون الثاني": 1,
    "فبراير": 2,
    "شباط": 2,
    "مارس": 3,
    "آذار": 3,
    "ابريل": 4,
    "أبريل": 4,
    "نيسان": 4,
    "مايو": 5,
    "أيار": 5,
    "يونيو": 6,
    "حزيران": 6,
    "يوليو": 7,
    "تموز": 7,
    "اغسطس": 8,
    "أغسطس": 8,
    "آب": 8,
    "سبتمبر": 9,
    "ايلول": 9,
    "أيلول": 9,
    "اكتوبر": 10,
    "أكتوبر": 10,
    "تشرين الأول": 10,
    "نوفمبر": 11,
    "تشرين الثاني": 11,
    "ديسمبر": 12,
    "كانون الأول": 12,
}

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def parse_cli_date(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    parsed = date_parser.parse(value)
    if isinstance(parsed, datetime):
        if parsed.time() == time.min and end_of_day:
            parsed = datetime.combine(parsed.date(), time.max)
        return to_tripoli_naive(parsed)
    if isinstance(parsed, date):
        return datetime.combine(parsed, time.max if end_of_day else time.min)
    return None


def parse_article_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = normalize_digits(value)
    relative_date = parse_relative_date(value)
    if relative_date:
        return relative_date
    arabic_date = parse_arabic_date(value)
    if arabic_date:
        return arabic_date
    day_first_date = parse_day_first_numeric_date(value)
    if day_first_date:
        return day_first_date
    try:
        parsed = date_parser.parse(value, fuzzy=True)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo:
        return to_tripoli_naive(parsed)
    return to_tripoli_naive(parsed)


def parse_day_first_numeric_date(value: str) -> datetime | None:
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", value)
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    if day > 12 or month <= 12:
        return safe_datetime(year, month, day)
    return None


def normalize_digits(value: str) -> str:
    return value.translate(ARABIC_DIGITS)


def parse_arabic_date(value: str) -> datetime | None:
    normalized = " ".join(
        value.replace("،", " ")
        .replace(":", " ")
        .replace("تاريخ النشر", " ")
        .replace("نشر في", " ")
        .replace("آخر تحديث", " ")
        .split()
    )
    for month_name, month_number in ARABIC_MONTHS.items():
        if month_name not in normalized:
            continue
        pattern = rf"(\d{{1,2}})\s+{re.escape(month_name)}(?:\s+(\d{{4}}))?"
        match = re.search(pattern, normalized)
        if match:
            day = int(match.group(1))
            year = int(match.group(2)) if match.group(2) else datetime.utcnow().year
            return safe_datetime(year, month_number, day)
        pattern = rf"{re.escape(month_name)}\s+(\d{{1,2}})(?:\s+(\d{{4}}))?"
        match = re.search(pattern, normalized)
        if match:
            day = int(match.group(1))
            year = int(match.group(2)) if match.group(2) else datetime.utcnow().year
            return safe_datetime(year, month_number, day)
    return None


def has_exact_date_in_url(url: str) -> bool:
    patterns = [
        r"/20\d{2}/[01]?\d/[0-3]?\d(?:/|[-_])",
        r"[-_/]20\d{2}[-_/][01]?\d[-_/][0-3]?\d(?:[-_/]|$)",
    ]
    return any(re.search(pattern, url) for pattern in patterns)


def parse_relative_date(value: str) -> datetime | None:
    normalized = value.casefold()
    today = datetime.now(TRIPOLI_TZ).replace(tzinfo=None, microsecond=0)
    if "أمس" in normalized or "امس" in normalized or "yesterday" in normalized:
        return today - timedelta(days=1)
    if "اليوم" in normalized or "today" in normalized:
        return today
    relative_markers = [
        "ago",
        "hour",
        "minute",
        "منذ",
        "ساعة",
        "ساعات",
        "دقيقة",
        "دقائق",
    ]
    if any(marker in normalized for marker in relative_markers):
        return today
    return None


def safe_datetime(year: int, month: int, day: int) -> datetime | None:
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def parse_date_from_url(url: str) -> datetime | None:
    patterns = [
        r"/(20\d{2})/([01]?\d)/([0-3]?\d)(?:/|[-_])",
        r"/(20\d{2})/([01]?\d)(?:/|$)",
        r"[-_/](20\d{2})[-_/]([01]?\d)[-_/]([0-3]?\d)(?:[-_/]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if not match:
            continue
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3)) if len(match.groups()) >= 3 and match.group(3) else monthrange(year, month)[1]
        parsed = safe_datetime(year, month, day)
        if parsed:
            return parsed
    return None


def to_tripoli_naive(value: datetime) -> datetime:
    if value.tzinfo:
        return value.astimezone(TRIPOLI_TZ).replace(tzinfo=None)
    return value.replace(tzinfo=TRIPOLI_TZ).astimezone(TRIPOLI_TZ).replace(tzinfo=None)


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
