# Libya PICS Monitoring

Python media monitoring system for collecting Libya-related headlines from approved Arabic and English sources and exporting structured products suitable for UNSMIL/PICS daily media monitoring.

## Features

- **Feed-first collection**: sources with an RSS/Atom feed are read straight
  from the feed (clean titles, real publication dates, and it reaches several
  bot-protected outlets the headless browser could not). Falls back to HTML
  automatically when a feed is missing, empty, or fails.
- **Wire recovery via Google News**: `per_item_source` meta-feeds pull in the
  one-off wires the gold reports cite (Reuters, AP, ABC, Anadolu, allAfrica, …),
  attributing each item to its originating outlet rather than the aggregator.
- Playwright-based page collection for static and JavaScript-rendered sites
- **Structural noise filtering**: navigation, headers, footers, sidebars,
  social bars, category chips and pagination are stripped before parsing so
  menu/footer links never surface as headlines (removed ~80% of raw scrape
  noise in testing)
- BeautifulSoup parsing with modular parser classes
- Source configuration in `sources.json`
- Arabic and English keyword support
- Date filtering with optional handling for undated source items
- CSV output for collected headlines
- CSV verification table for source checks
- Claude-powered editorial enrichment (translation, thematic categorisation,
  cross-source deduplication) producing a Word report in the UNSMIL/PICS
  `Libya News Headlines` format
- **Quality evaluation** (`evaluate.py`): scores any generated report 0-100
  against a profile learned from the gold `samples/` reports (structure, style
  conformance, and source-coverage recall), so "did it get better?" is a number
- Logging and retry handling

## How it works

The pipeline has two stages:

1. **Collection** — for each source the collector prefers its RSS/Atom feed
   (`feed` in `sources.json`); otherwise Playwright + BeautifulSoup scrape the
   page, with boilerplate regions stripped and a structural filter dropping
   non-article chrome. Results are written to `libya_media_headlines.csv` and
   the source verification table (status `ok` / `empty` / `failed`).
2. **Editorial enrichment** — the collected articles are sent to the Claude API
   (`utils/enrich.py`), which translates Arabic headlines to English, sorts them
   into the fixed 8-section taxonomy, and merges the same story reported by
   multiple outlets into one bullet citing every source. The result is rendered
   as the Word report.

The enrichment step needs an API key in `ANTHROPIC_API_KEY`. If the key (or the
`anthropic` package) is missing, or you pass `--no-enrich`, the report falls
back to a mechanical source-grouped layout that has the correct structure but
leaves headlines in their original wording. The fallback report is stamped
**DRAFT** so an untranslated, mechanically-deduplicated product is never mistaken
for the final report.

See [`docs/report_methodology.md`](docs/report_methodology.md) for the editorial
rules and [`samples/`](samples) for reference output products.

## Repository Structure

```text
.
├── scraper.py
├── evaluate.py
├── sources.json
├── requirements.txt
├── README.md
├── parsers/
│   ├── __init__.py
│   ├── base.py
│   ├── feed.py
│   └── generic.py
├── tests/
│   ├── test_cleaning.py
│   ├── test_dates.py
│   ├── test_feed_parser.py
│   └── test_report_eval.py
└── utils/
    ├── cleaning.py
    ├── config.py
    ├── dates.py
    ├── enrich.py
    ├── exports.py
    ├── feeds.py
    ├── fetcher.py
    ├── logger.py
    ├── models.py
    ├── report_eval.py
    └── taxonomy.py
```

Run the tests (no extra deps; they self-run):

```bash
python tests/test_cleaning.py
python tests/test_dates.py
python tests/test_feed_parser.py
python tests/test_report_eval.py
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Set an API key for editorial enrichment (optional but recommended):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Usage

Run the monitor for a specific date range:

```bash
python scraper.py --start-date 2026-06-01 --end-date 2026-06-03
```

Set the report title date, choose a model, or skip enrichment entirely:

```bash
python scraper.py --start-date 2026-06-03 --end-date 2026-06-03 --report-date "3 June"
python scraper.py --no-enrich          # mechanical layout, no API calls
python scraper.py --model claude-opus-4-8
```

Add custom keywords:

```bash
python scraper.py --keyword "elections" --keyword "انتخابات"
```

### Bot-protected / JS-rendered sources (real-browser fetch)

A few sources (e.g. Akhbar Libya 24, New Arab, Reuters) block the headless
browser or only render via heavy client-side JS. Fetch those through a real
Chrome over the DevTools protocol:

```bash
# 1. Launch Chrome with a debugging port (a separate profile avoids disturbing
#    your normal session):
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-scraper-profile about:blank

# 2. Point the scraper at it:
python scraper.py --cdp-url http://localhost:9222 --start-date 2026-06-20 --end-date 2026-06-20
```

The headless default is faster; use `--cdp-url` for maximum source coverage.

Keep source items that do not expose a machine-readable date:

```bash
python scraper.py --start-date 2026-06-03 --end-date 2026-06-03 --keep-undated
```

Outputs are written to `output/`:

- `libya_media_headlines.csv`
- `source_verification_table.csv`
- `unsmil_pics_daily_media_report.docx`

Logs are written to `logs/scraper.log`.

## Quality evaluation

`evaluate.py` turns report quality into a tracked number. It learns a profile
from the gold human reports in `samples/` (bullets per report, % English, dedup
rate, role-prefix usage, source vocabulary) and scores a target report against
it:

```bash
# Score the latest generated report against the gold profile
python evaluate.py output/unsmil_pics_daily_media_report.docx

# Add source-coverage recall against a date-matched gold report
python evaluate.py output/unsmil_pics_daily_media_report.docx \
  --gold ~/Downloads/20260621_headlines.docx

# Inspect the gold corpus profile
python evaluate.py --profile
```

The 0-100 total combines three components:

- **structure** — title format, canonical section order, every bullet
  attributed, zero boilerplate noise.
- **style conformance** — English ratio, cross-source dedup rate, role-prefix
  usage and bullet volume, measured against the gold profile.
- **coverage** *(only with `--gold`)* — **ceiling recall**: of the gold report's
  outlets that are *also* in the monitored source list (`--sources`, default
  `sources.json`), how many the target cites. This excludes gold's one-off wires
  outside the source list from the denominator, so the score reflects report
  quality rather than the source roster. Raw recall and the list of
  monitored-but-missed outlets are still shown, to point at real coverage gaps.

A gold sample scores ~100; an untranslated DRAFT scores high on structure but
low on style until Claude enrichment runs. Pass `--llm-judge` (needs an API key
with credit) to add qualitative translation-quality and story-recall scores.

## Source Configuration

Sources are managed in `sources.json`. Each enabled source defines:

- `id`: stable source identifier
- `name`: report-friendly source name
- `language`: `ar` or `en`
- `url`: collection URL (HTML listing page)
- `feed` *(optional)*: RSS/Atom feed URL. When set it is used in preference to
  the HTML page; the collector falls back to `url` if the feed is empty/fails.
- `autodiscover_feed` *(optional, default `true`)*: when no `feed` is set, look
  for a feed advertised by the page's `<link rel="alternate">` and use it.
- `per_item_source` *(optional, default `false`)*: for aggregator feeds (Google
  News), cite each item's originating outlet (from the feed's `<source>` tag)
  instead of the configured source name, and strip the trailing `- Publisher`
  from the headline.
- `min_title_words` *(optional, default `4`)*: HTML items whose title has fewer
  words are treated as navigation chrome and dropped.
- `parser`: parser implementation, currently `generic_list` (HTML) or
  `feed_list` (RSS/Atom)
- `selectors`: CSS selectors for article cards, titles, URLs, summaries, dates, and sections
- `require_keyword_match`: whether to filter items by Libya/PICS keywords. Set
  `true` for broad, site-wide feeds (e.g. Asharq Al-Awsat, New Arab) so only
  Libya items are kept.

Example:

```json
{
  "id": "example_source",
  "name": "Example Source",
  "language": "en",
  "country_focus": "Libya",
  "url": "https://example.com/libya",
  "parser": "generic_list",
  "enabled": true,
  "require_keyword_match": true,
  "selectors": {
    "article": "article",
    "title": "h2 a",
    "url": "h2 a",
    "summary": "p",
    "date": "time",
    "section": ".category"
  }
}
```

## Adding Parsers

Create a parser in `parsers/` that subclasses `BaseParser`, then register it in `parsers/__init__.py`.

```python
from parsers.base import BaseParser


class CustomParser(BaseParser):
    def parse(self, html):
        ...
```

Use custom parsers when a source needs special handling beyond config-driven CSS selectors.

## Operational Notes

- Review and approve all sources before adding them to `sources.json`.
- CSS selectors may need maintenance when publishers redesign pages.
- For strict daily products, run with `--start-date`, `--end-date`, and without `--keep-undated`.
- Generated Word reports are intended as first-draft monitoring products and should be editorially reviewed before distribution.
