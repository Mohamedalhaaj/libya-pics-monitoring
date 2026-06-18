# Libya PICS Monitoring

Python editorial intelligence system for collecting Libya-related media items from approved Arabic and English sources, filtering them with UNSMIL/PICS-style editorial judgement, clustering related coverage into stories, and exporting a final daily monitoring report.

## Features

- Playwright-based page collection for static and JavaScript-rendered sites
- BeautifulSoup parsing with modular parser classes
- Source configuration in `sources.json`
- Arabic and English keyword support
- Date filtering with optional handling for undated source items
- CSV outputs for raw candidates, editorial review, and approved headlines
- CSV verification table for source checks
- Source-by-source debug report for extraction and zero-result diagnosis
- Search/archive fallback collection using source-specific URL plans
- Article-page fallback extraction when listing pages do not expose dates or summaries
- Date-uncertain candidate export for editorial review
- Editorial relevance scoring from 0-100 with configurable threshold
- HIGH/MEDIUM/LOW PICS priority assignment
- Anti-noise filtering for sports, entertainment, weather, market tables, and routine low-value items
- Story clustering across sources so the final report presents developments, not duplicate headlines
- Contextual coverage expansion for major stories: reactions, support, opposition, analysis, commentary, opinion, podcasts, and interviews
- Coverage-completeness audit for each major theme and expansion dimension
- Source trust tiers used as a confidence signal
- Automated editorial QA checks before final report generation
- Word report generation from approved story clusters
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
│   ├── common.py
│   ├── generic.py
│   └── source_specific.py
└── utils/
    ├── config.py
    ├── dates.py
    ├── editorial.py
    ├── exports.py
    ├── fetcher.py
    ├── logger.py
    ├── models.py
    └── source_plan.py
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
python scraper.py --start-date 2026-06-01 --end-date 2026-06-02
```

Equivalent production report command:

```bash
python scraper.py --start-date 2026-06-01 --end-date 2026-06-01 --output-dir output
```

The scraper always writes the CSV audit package. `final_pics_report.docx` is generated only when the production trust gates pass.

Adjust the editorial approval threshold, if needed:

```bash
python scraper.py --start-date 2026-06-01 --end-date 2026-06-02 --relevance-threshold 70
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

Run extraction diagnostics for one source:

```bash
python scraper.py --debug-source "Al Wasat" --start-date 2026-06-01 --end-date 2026-06-02
```

Outputs are written to `output/`:

- `libya_media_headlines.csv`
- `raw_candidates.csv`
- `review_queue.csv`
- `rejected_items.csv`
- `approved_headlines.csv`
- `story_clusters.csv`
- `source_verification_table.csv`
- `date_uncertain_items.csv`
- `source_debug_report.csv`
- `editorial_qa_report.csv`
- `final_pics_report.docx`
- `source_audit.csv`
- `discovery_evidence.csv`
- `source_contribution.csv`
- `missed_story_audit.csv`
- `contextual_coverage_audit.csv`
- `source_recovery_report.csv`

Logs are written to `logs/scraper.log`.

The terminal summary shows source collection statistics, editorially approved articles, story clusters, review queue size, zero-article source reasons, and automated editorial QA status.

## Editorial Intelligence Pipeline

The system follows a broad-collection, strict-publication model:

1. Collect broadly from approved source homepages, categories, search pages, archive pages, and date pages.
2. Detect primary themes from the first-pass collection, such as Structured Dialogue, Elections, Migration, UNSMIL, Central Bank, NOC, Zawiya clashes, constitutional issues, and executive-authority proposals.
3. Run a contextual expansion pass for each primary theme, searching source-specific search URLs for reactions, statements, support, opposition, criticism, analysis, commentary, opinion, podcasts, interviews, and long-form discussion.
4. Reject non-article URLs from final outputs, including search, tag, category, author, page, and archive URLs.
5. Validate that each approved item has an article URL, headline, body or snippet, publication date, and Libya relevance.
6. Score each article from 0-100 using Libya relevance, UNSMIL/PICS topic importance, section signals, and source trust tier.
7. Reject items below the configured threshold, default `60`.
8. Assign each approved item a `HIGH`, `MEDIUM`, or `LOW` priority.
9. Cluster same-event coverage across sources into story-level entries, while preserving separate reaction/commentary/analysis items where they add editorial context.
10. Run automated QA checks before producing `final_pics_report.docx`.

The final DOCX is the human-facing product. CSV files are diagnostics and audit trails.

## Contextual Expansion

The contextual expansion pass is enabled by default. It asks whether each major story has coverage beyond the initial event and searches across the mandatory PICS context-source universe, not just the source that first found the event.

- Event
- Reaction or statement
- Support
- Opposition or criticism
- Analysis or opinion
- Commentary, interview, podcast, or long-form discussion

The pass uses source-specific search templates from `utils/source_plan.py`, including Arabic equivalents such as `رد`, `تعليق`, `انتقاد`, `رفض`, `دعم`, `موقف`, `تصريح`, `رأي`, `تحليل`, `مقال`, `مقابلة`, `بودكاست`, `نقاش`, and `بيان`.

Useful controls:

```bash
python scraper.py --start-date 2026-06-10 --end-date 2026-06-11 \
  --max-contextual-pages-per-source 6 \
  --max-contextual-article-pages-per-source 20
```

Disable the pass for source-debugging only:

```bash
python scraper.py --start-date 2026-06-10 --end-date 2026-06-11 --no-contextual-expansion
```

Review `output/contextual_coverage_audit.csv` before publication. Incomplete statuses show where a major theme still lacks reaction, opposition, support, analysis, commentary, source breadth, or actor breadth from the live source set.

The context-source universe includes the main domestic sources (`Libya Observer`, `Al Wasat`, `Ean Libya`, `Libya Al Ahrar`, `Al Menassa`, `Libya Review`, `Libya Update`, `Address Libya`, `Libya 24`, `LANA`, `Al Sabaah`) and regional/international context sources (`Asharq Al Awsat`, `New Arab`, `Al Jazeera`, `Anadolu`, `Reuters`, `AP`, `BBC`).

The audit generates one row per major theme with:

- counts for event, reaction, support, opposition, analysis, and commentary coverage
- sources checked and sources used
- actor categories checked/found
- `coverage_score`
- status such as `complete`, `event_only_incomplete`, `insufficient_source_or_actor_breadth`, or `analysis_sources_not_checked`

## Evidence Package

Every run also produces an evidence package proving that the final report was built from collected source material rather than a reference report:

- `source_audit.csv`: source-level fetch status, discovery URLs, collection timestamps, and extraction counts.
- `discovery_evidence.csv`: one row per final story source URL, with publication date, discovery source, parser, and collection timestamp.
- `source_contribution.csv`: source contribution counts across final stories, approved articles, review items, and rejected items.
- `missed_story_audit.csv`: collected items excluded from the final report, with rejection or review reasons.
- `contextual_coverage_audit.csv`: major-theme completeness check for event, reaction, support, opposition, analysis, and commentary coverage.

Reference reports may be used as formatting benchmarks only; they are not used as factual inputs.

## Source Configuration

Sources are managed in `sources.json`. Each enabled source defines:

- `id`: stable source identifier
- `name`: report-friendly source name
- `language`: `ar` or `en`
- `url`: collection URL
- `parser`: parser implementation, for example `generic_list`, `al_wasat`, `ean_libya`, or `libya_review`
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

## Keyword And Category Maintenance

Editorial keyword lists live in `utils/keywords.py`, not inside the scraper logic.

Update these lists when adding new Libya-specific monitoring vocabulary:

- `LIBYA_ENTITIES`: cities, regions, and place names.
- `LIBYA_INSTITUTIONS`: state bodies, ministries, UN entities, and public institutions.
- `LIBYA_FIGURES`: prominent political, security, economic, and UN actors.
- `LIBYA_ISSUES`: elections, governance, economy, security, migration, human rights, public services, and other PICS issues.
- `PICS_SECTION_KEYWORDS`: section classifiers for United Nations, Politics, Military & Security, Human Rights & Rule of Law, Migration, Economy, Banking, Energy, Municipalities & Public Services, Reconstruction & Infrastructure, Environment, Regional & International, Varieties, and Other.
- `SUBSECTION_KEYWORDS`: more specific grouping labels such as UNSMIL, Governance, Elections, Security, Migration, Oil & Energy, Banking, Municipal Services, Health, Foreign Relations, and anti-migrant sentiment.

The relevance filter uses weighted positive and noise signals. Noise terms such as Gaza, Iran, Ukraine, or Sudan do not automatically reject a story when Libya-specific entities and PICS issue terms are stronger.

## Adding Sources

Add sources in `sources.json`. Prefer a source-specific parser when the site has stable article structures; otherwise use `generic_list` with source-specific selectors and search/archive URLs. For each new source, verify:

- article-level URLs are discovered, not only search/category/tag pages
- publication dates are extracted from article metadata or visible timestamps
- source search URLs work for Libya, Arabic, and section-specific terms
- zero-result diagnostics explain whether failures are fetch, selector, date, relevance, or stale-story related

## Narrative Report Generation

The DOCX report is generated from story clusters after date validation, raw-candidate review, deduplication, section classification, and QA. Clusters preserve source links so a report item can cite multiple outlets. Arabic headline translation is exposed through `translate_headline_stub` in `utils/editorial.py`; configure that hook before enabling external translation APIs.

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
- For strict daily products, run with `--start-date` and `--end-date`.
- Human review should focus on exceptional edge cases in `review_queue.csv`; the final DOCX is generated from editorially approved story clusters only.
