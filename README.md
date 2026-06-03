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
- Word report generation utilities for later editorial workflows
- Search/archive fallback collection using source-specific URL plans
- Date-uncertain candidate export for editorial review
- Logging and retry handling

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
│   └── generic.py
└── utils/
    ├── config.py
    ├── dates.py
    ├── exports.py
    ├── fetcher.py
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

## Usage

Run the monitor for a specific date range:

```bash
python scraper.py --start-date 2026-06-01 --end-date 2026-06-03
```

Add custom keywords:

```bash
python scraper.py --keyword "elections" --keyword "انتخابات"
```

Review source items that do not expose a machine-readable date:

```bash
python scraper.py --start-date 2026-06-03 --end-date 2026-06-03
```

Then inspect `output/date_uncertain_items.csv`.

Run a focused maintenance check for one source:

```bash
python scraper.py --source-id al_wasat --start-date 2026-06-03 --end-date 2026-06-03
```

Outputs are written to `output/`:

- `libya_media_headlines.csv`
- `source_verification_table.csv`
- `date_uncertain_items.csv`

Logs are written to `logs/scraper.log`.

The scraper also prints a terminal summary showing articles collected per source, failed sources, zero-article sources, and the reason each source returned no dated articles.

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
- For strict daily products, run with `--start-date` and `--end-date`, then review `date_uncertain_items.csv`.
- The scraper intentionally does not generate a Word report automatically from raw collection output. Use the CSVs for editorial verification before producing a narrative report.
