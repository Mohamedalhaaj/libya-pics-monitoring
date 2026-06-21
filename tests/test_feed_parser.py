"""Tests for parsers.feed.FeedListParser against a synthetic RSS feed.

Runnable directly (`python tests/test_feed_parser.py`) or under pytest.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsers.feed import FeedListParser  # noqa: E402

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <item>
    <title>Libya's three councils agree to hold elections before February 2027</title>
    <link>https://example.com/2026/06/20/elections</link>
    <description>&lt;p&gt;The three councils reached an &lt;b&gt;agreement&lt;/b&gt;.&lt;/p&gt;</description>
    <pubDate>Fri, 20 Jun 2026 09:30:00 +0000</pubDate>
    <category>Politics</category>
  </item>
  <item>
    <title>Egypt and Saudi Arabia discuss regional economy</title>
    <link>https://example.com/2026/06/20/economy</link>
    <description>No mention of the target country here.</description>
    <pubDate>Fri, 20 Jun 2026 08:00:00 +0000</pubDate>
  </item>
  <item>
    <title>Tripoli port resumes operations after maintenance</title>
    <link>https://example.com/2026/06/19/port</link>
    <pubDate>Thu, 19 Jun 2026 18:00:00 +0000</pubDate>
  </item>
</channel></rss>
"""

BASE_SOURCE = {
    "id": "test_feed",
    "name": "Test Feed",
    "language": "en",
    "country_focus": "Libya",
}

KEYWORDS = ["Libya", "Libyan", "Tripoli"]


def test_feed_parses_titles_dates_summaries():
    source = {**BASE_SOURCE, "require_keyword_match": False}
    articles = FeedListParser(source, KEYWORDS).parse(RSS)
    assert len(articles) == 3
    first = articles[0]
    assert first.title == "Libya's three councils agree to hold elections before February 2027"
    assert first.url == "https://example.com/2026/06/20/elections"
    # HTML stripped from the description (feedparser may leave cosmetic spaces).
    assert "<" not in first.summary and ">" not in first.summary
    assert "three councils reached an agreement" in first.summary
    assert first.section == "Politics"
    # pubDate parsed to a real datetime (naive UTC).
    assert isinstance(first.published_at, datetime)
    assert (first.published_at.year, first.published_at.month, first.published_at.day) == (2026, 6, 20)


GNEWS_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Google News</title>
  <item>
    <title>At least 15 migrant bodies wash ashore in eastern Libya - Reuters</title>
    <link>https://news.google.com/rss/articles/abc123</link>
    <pubDate>Fri, 20 Jun 2026 09:30:00 +0000</pubDate>
    <source url="https://www.reuters.com">Reuters</source>
  </item>
  <item>
    <title>A boat with migrants capsized north off Libya - ABC News</title>
    <link>https://news.google.com/rss/articles/def456</link>
    <pubDate>Fri, 20 Jun 2026 08:00:00 +0000</pubDate>
    <source url="https://abcnews.go.com">ABC News - Breaking News, Latest News and Videos</source>
  </item>
</channel></rss>
"""


def test_per_item_source_uses_real_outlet():
    # Aggregator feed (Google News): cite the originating outlet, not "Google News".
    source = {**BASE_SOURCE, "name": "Google News", "require_keyword_match": True,
              "per_item_source": True}
    articles = FeedListParser(source, KEYWORDS).parse(GNEWS_RSS)
    assert {a.source_name for a in articles} == {"Reuters", "ABC News"}
    # The trailing " - Publisher" is stripped from the headline.
    assert articles[0].title == "At least 15 migrant bodies wash ashore in eastern Libya"
    # Long publisher boilerplate is shortened to the outlet name.
    assert articles[1].source_name == "ABC News"


def test_keyword_filter_drops_offtopic_items():
    # Broad/site-wide feeds set require_keyword_match to filter to Libya items.
    source = {**BASE_SOURCE, "require_keyword_match": True}
    articles = FeedListParser(source, KEYWORDS).parse(RSS)
    titles = {a.title for a in articles}
    assert "Egypt and Saudi Arabia discuss regional economy" not in titles  # no keyword
    assert "Tripoli port resumes operations after maintenance" in titles  # Tripoli
    assert len(articles) == 2


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} feed-parser tests passed.")
