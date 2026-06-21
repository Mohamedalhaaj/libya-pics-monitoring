# Libya PICS Monitoring

Python media monitoring system for collecting Libya-related headlines from approved Arabic and English sources and exporting structured products suitable for UNSMIL/PICS daily media monitoring.

## Features

- Playwright-based page collection for static and JavaScript-rendered sites
- BeautifulSoup parsing with modular parser classes
- Source configuration in `sources.json`
- Arabic and English keyword support
- Date filtering with optional handling for undated source items
- CSV output for collected headlines
- CSV verification table for source checks
- Claude-powered editorial enrichment (translation, thematic categorisation,
  cross-source deduplication) producing a Word report in the UNSMIL/PICS
  `Libya News Headlines` format
- Logging and retry handling

## How it works

The pipeline has three stages:

1. **Collection** (concurrent) — for each source the scraper fetches the listing
   page (Playwright + BeautifulSoup) and, with `--discover-feeds`, also folds in
   the source's advertised RSS/Atom feed. Feeds are the most reliable path: they
   carry clean titles, links and dates, and bypass both bot protection and
   client-side rendering. Sources can also be configured with `"parser": "feed"`
   and a `feed_url` to use a feed directly.
2. **Date resolution** — listing pages rarely expose a trustworthy date, so when
   a date window is requested (or `--resolve-dates` is passed) the scraper opens
   each kept article's page and reads its real `article:published_time` /
   JSON-LD date (`utils/resolver.py`). Only then is the date window applied — so
   the report can be limited to exactly the requested dates without a manual
   link-check.
3. **Editorial enrichment** — the collected articles are sent to the Claude API
   (`utils/enrich.py`), which translates Arabic headlines to English, sorts them
   into the fixed 8-section taxonomy, and merges the same story reported by
   multiple outlets into one bullet citing every source. The result is rendered
   as the Word report.

The enrichment step needs an API key in `ANTHROPIC_API_KEY`. If the key (or the
`anthropic` package) is missing, or you pass `--no-enrich`, the report falls
back to a mechanical source-grouped layout that has the correct structure but
leaves headlines in their original wording.

See [`docs/report_methodology.md`](docs/report_methodology.md) for the editorial
rules and [`samples/`](samples) for reference output products.

## Repository Structure

```text
.
├── scraper.py
├── sources.json
├── requirements.txt
├── README.md
├── parsers/
│   ├── __init__.py
│   ├── base.py
│   ├── feed.py
│   └── generic.py
└── utils/
    ├── config.py
    ├── dates.py
    ├── enrich.py
    ├── exports.py
    ├── fetcher.py
    ├── resolver.py
    ├── taxonomy.py
    ├── logger.py
    └── models.py
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

Recommended full run (feeds for reliability + precise per-article dates; a date
window auto-enables date resolution):

```bash
python scraper.py --start-date 2026-06-18 --end-date 2026-06-21 \
  --discover-feeds --report-date "18–21 June 2026"
```

Tuning knobs: `--concurrency N` (parallel fetches; auto = 6 headless / 2 over
CDP), `--resolve-dates` (force per-article date lookup even without a window),
`--discover-feeds` (also pull each source's RSS/Atom feed).

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

## Source Configuration

Sources are managed in `sources.json`. Each enabled source defines:

- `id`: stable source identifier
- `name`: report-friendly source name
- `language`: `ar` or `en`
- `url`: collection URL
- `parser`: parser implementation, currently `generic_list`
- `selectors`: CSS selectors for article cards, titles, URLs, summaries, dates, and sections
- `require_keyword_match`: whether to filter items by Libya/PICS keywords

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
