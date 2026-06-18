from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper import (
    check_libya_relevance,
    classify_date,
    deduplicate_cross_source_stories,
    determine_zero_reason,
    enrich_article,
    looks_like_article_url,
    guess_section,
    guess_subsection,
)
from utils.dates import parse_date_from_url, parse_relative_date
from utils.models import Article


LIBYA_SOURCE = {
    "id": "ean_libya",
    "name": "Ean Libya",
    "require_keyword_match": False,
}


def make_article(title: str, source_name: str = "Ean Libya", url: str = "https://example.com/article/one") -> Article:
    return Article(
        source_id=source_name.casefold().replace(" ", "_"),
        source_name=source_name,
        language="ar",
        country_focus="Libya",
        title=title,
        url=url,
        published_at=datetime(2026, 6, 2),
    )


def test_libya_source_identity_is_not_enough() -> None:
    article = make_article("ترامب يبحث وقف إطلاق النار في الشرق الأوسط")
    ok, reason = check_libya_relevance(article, LIBYA_SOURCE)
    assert not ok
    assert reason.startswith("global_news_without_libya_angle")


def test_libya_topic_evidence_passes() -> None:
    article = make_article("اجتماع حكومي في طرابلس يبحث ملف الهجرة")
    ok, reason = check_libya_relevance(article, LIBYA_SOURCE)
    assert ok
    assert "weighted" in reason or reason.startswith("libya_source_topic")


def test_lana_is_not_blanket_rejected() -> None:
    article = make_article("رئيس الحكومة يبحث في طرابلس ملف الخدمات البلدية", "LANA")
    source = {"id": "lana", "name": "LANA", "require_keyword_match": False}
    ok, reason = check_libya_relevance(article, source)
    assert ok
    assert "lana_requires_explicit_libya_angle" not in reason


def test_noise_keyword_does_not_override_libya_context() -> None:
    article = make_article("طرابلس تبحث أوضاع قافلة غزة المحتجزة في ليبيا")
    ok, reason = check_libya_relevance(article, LIBYA_SOURCE)
    assert ok
    assert "noise_context_overridden" in reason


def test_expanded_section_and_subsection_detection() -> None:
    banking = make_article("مصرف ليبيا المركزي يناقش السيولة وسعر الصرف")
    assert guess_section(banking) == "Economy"
    assert guess_subsection(banking) == "Banking"
    energy = make_article("المؤسسة الوطنية للنفط تبحث إنتاج النفط والغاز")
    assert guess_subsection(energy) == "Oil & Energy"


def test_non_article_urls_are_rejected() -> None:
    assert not looks_like_article_url("https://example.com/search?q=libya")
    assert not looks_like_article_url("https://example.com/category/libya/")
    assert looks_like_article_url("https://lana.gov.ly/article.php?lang=ar&id=12345")


def test_url_date_conflict_goes_to_review() -> None:
    article = make_article(
        "Libya migration meeting",
        url="https://example.com/2026/06/01/libya-migration-meeting",
    )
    article.published_at = datetime(2026, 6, 2)
    enrich_article(article, datetime(2026, 6, 1))
    assert classify_date(article, datetime(2026, 6, 1), datetime(2026, 6, 2, 23, 59, 59)) == "date_conflict"


def test_zero_result_reasons_are_specific() -> None:
    assert determine_zero_reason(1, 0, 0, 0, 0, 0, 0, 0, []) == "no_article_links_found"
    assert determine_zero_reason(1, 10, 10, 0, 0, 0, 10, 0, [], non_article_count=10) == "selector_failed"
    assert determine_zero_reason(1, 10, 10, 0, 0, 10, 0, 0, []) == "date_parsing_failed"


def test_cross_source_duplicate_detection() -> None:
    primary = make_article("طرابلس.. اجتماع سيادي رفيع لبحث ملف الهجرة ومخاطر التوطين", "Ean Libya")
    duplicate = make_article("ناقش اجتماع سيادي رفيع بطرابلس ملف الهجرة غير الشرعية ومخاطر التوطين", "Address Libya")
    unique, duplicates = deduplicate_cross_source_stories([primary, duplicate])
    assert len(unique) == 1
    assert len(duplicates) == 1
    assert duplicates[0].duplicate_status == "duplicate_cross_source"
    assert "also_reported_by:Address Libya" in unique[0].notes


def test_tripoli_relative_and_month_only_url_dates() -> None:
    assert parse_relative_date("أمس") is not None
    parsed = parse_date_from_url("https://example.com/2026/06/")
    assert parsed is not None
    assert parsed.day == 30


if __name__ == "__main__":
    test_libya_source_identity_is_not_enough()
    test_libya_topic_evidence_passes()
    test_lana_is_not_blanket_rejected()
    test_noise_keyword_does_not_override_libya_context()
    test_expanded_section_and_subsection_detection()
    test_non_article_urls_are_rejected()
    test_url_date_conflict_goes_to_review()
    test_zero_result_reasons_are_specific()
    test_cross_source_duplicate_detection()
    test_tripoli_relative_and_month_only_url_dates()
    print("Scraper quality tests passed")
