from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.editorial import run_editorial_pipeline
from utils.models import Article


def make_article(
    title: str,
    source_id: str = "al_wasat",
    source_name: str = "Al Wasat",
    summary: str = "ليبيا وطرابلس وتطورات سياسية ذات صلة.",
    url: str = "https://example.com/news/libya/123",
) -> Article:
    return Article(
        source_id=source_id,
        source_name=source_name,
        language="ar",
        country_focus="Libya",
        title=title,
        url=url,
        published_at=datetime(2026, 6, 9),
        summary=summary,
        content_text=summary,
        date_status="in_range",
        relevance_status="accepted",
        include_candidate=True,
    )


def test_unsmil_article_gets_high_priority_and_score() -> None:
    article = make_article("البعثة الأممية تعلن إحاطة جديدة بشأن العملية السياسية في ليبيا")
    result = run_editorial_pipeline([article], [], threshold=60)
    assert len(result.approved_articles) == 1
    assert result.approved_articles[0].priority == "HIGH"
    assert result.approved_articles[0].relevance_score >= 95
    assert result.clusters[0].section == "United Nations"


def test_sports_noise_goes_to_review() -> None:
    article = make_article("الأهلي طرابلس يفوز في مباراة الدوري الليبي لكرة القدم")
    result = run_editorial_pipeline([article], [], threshold=60)
    assert not result.approved_articles
    assert result.rejected_articles[0].rejection_reason == "sports_or_entertainment"


def test_cross_source_same_story_is_clustered_not_removed() -> None:
    left = make_article(
        "توصيات الحوار المنظم تعتمد مسارا سياسيا جديدا",
        source_id="al_wasat",
        source_name="Al Wasat",
        summary="توصيات الحوار المنظم في ليبيا تعتمد مسارا سياسيا جديدا بمشاركة مؤسسات وطنية.",
        url="https://alwasat.ly/news/libya/1",
    )
    right = make_article(
        "اعتماد توصيات الحوار المنظم بشأن المسار السياسي في ليبيا",
        source_id="libya_24",
        source_name="Libya 24",
        summary="اعتماد توصيات الحوار المنظم بشأن المسار السياسي في ليبيا بمشاركة المؤسسات الوطنية.",
        url="https://libya24.tv/news/2",
    )
    result = run_editorial_pipeline([left, right], [], threshold=60)
    assert len(result.approved_articles) == 2
    assert len(result.clusters) == 1
    assert result.clusters[0].article_count == 2


def test_stale_story_is_rejected_before_report_generation() -> None:
    article = make_article(
        "تقرير قديم عن الحوار المنظم في ليبيا دون تطور جديد",
        summary="الحوار المنظم في ليبيا وتفاصيل سياسية منشورة قبل فترة الرصد.",
        url="https://alwasat.ly/news/libya/old-story",
    )
    article.published_at = datetime(2026, 6, 7)
    article.date_status = "in_range"
    article.date_source = "article_publication"
    result = run_editorial_pipeline(
        [article],
        [],
        threshold=60,
        start_date=datetime(2026, 6, 9),
        end_date=datetime(2026, 6, 10, 23, 59, 59),
    )
    assert not result.approved_articles
    assert result.stale_story_rows
    assert result.stale_story_rows[0]["reason"] == "stale_story"


def test_raw_candidate_local_prosecution_item_is_promoted() -> None:
    article = make_article(
        "النائب العام يأمر بحبس متهم في قضية تزوير أموال عامة بطرابلس",
        summary="أعلن مكتب النائب العام في ليبيا حبس متهم احتياطيا على ذمة قضية تزوير ومال عام في طرابلس.",
        url="https://alwasat.ly/news/libya/2026/06/09/prosecution-case",
    )
    article.editorial_status = "unreviewed"
    article.qa_status = "rejected"
    article.relevance_status = "rejected"
    result = run_editorial_pipeline(
        [],
        [],
        raw_articles=[article],
        threshold=60,
        start_date=datetime(2026, 6, 9),
        end_date=datetime(2026, 6, 10, 23, 59, 59),
    )
    assert len(result.approved_articles) == 1
    assert result.approved_articles[0].section_guess == "Human Rights & Rule of Law"
    assert result.raw_candidate_promotion_rows[0]["new_status"] == "promoted"


if __name__ == "__main__":
    test_unsmil_article_gets_high_priority_and_score()
    test_sports_noise_goes_to_review()
    test_cross_source_same_story_is_clustered_not_removed()
    test_stale_story_is_rejected_before_report_generation()
    test_raw_candidate_local_prosecution_item_is_promoted()
    print("Editorial intelligence tests passed")
