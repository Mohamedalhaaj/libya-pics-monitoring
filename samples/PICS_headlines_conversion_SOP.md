# UNSMIL/PICS Libya News Headlines — Report Methodology

This document captures the format and editorial rules that the daily
**Libya News Headlines** report must follow. It is the in-repo, diffable
version of the original methodology brief
(`docs/report_methodology_source.docx`). The reference output products that
match this format live in [`samples/`](../samples).

The mechanical scraper (`scraper.py`) only **collects** candidate headlines.
Turning that raw collection into a report shaped like the samples — Arabic
headlines translated to English, the same story merged across outlets,
everything sorted into the fixed taxonomy below — is an editorial step. In
this project that step is performed by the Claude API enrichment layer
(`utils/enrich.py`); without an API key the report falls back to a simpler
source-grouped layout.

## 1. Core objective

A professional daily Libya media monitoring report covering all relevant
Libya-related news published during the coverage dates, organised by theme,
written as concise English headline-style bullets. Include only items
published within the coverage window.

## 2. Report structure

Title line: `Libya News Headlines – <DATE>` (e.g. `Libya News Headlines – 3 June`).

Use this **exact** main section order. Omit a section only if it has no items.

1. United Nations
2. Politics
3. Military & Security
4. Human Rights & Rule of Law
5. Economy
6. Environment
7. Regional & International
8. Varieties

Create subsections where useful (do not create empty ones). Suggested
subsections:

| Main section | Suggested subsections |
|---|---|
| United Nations | UNSMIL and political process; UN agencies and international support; Security Council and international mediation; Other UN news |
| Politics | Political institutions and governance; Elections and constitutional process; Government and municipal affairs; Other political news |
| Military & Security | Security and crime; Border and military affairs; Armed groups and ceasefire/security arrangements; Other security news |
| Human Rights & Rule of Law | Migration and human trafficking; Justice and accountability; Health, children and vulnerable groups; Civil liberties and human rights; Other human rights and rule-of-law news |
| Economy | Banking and currency; Energy and fuel; Markets, labour and services; Infrastructure and reconstruction; Other economic news |
| Environment | Weather, climate and agriculture; Water and environmental resources; Other environment news |
| Regional & International | Diplomacy and foreign relations; Regional security; Gaza/convoy-related Libya news; Other regional and international news |
| Varieties | Culture, heritage and society; Sports; Other varieties |

## 3. Writing style

- Concise professional headline-monitoring style; one clear sentence per bullet.
- The bullet begins with the **news fact**, not the source name.
- End each bullet with the linked source name(s). For Arabic sources, append
  `(Arabic)` after the source name.
- Translate Arabic headlines into polished English; do not leave raw Arabic in
  the final report. If an Arabic article is unclear, exclude it rather than guess.
- No opinions or conclusions unless the source explicitly reports them.

Example bullets:

- Tetteh briefed the Presidential Council on progress in the political process and roadmap consultations. – Al Wasat (Arabic)
- The Central Bank said new dollar cash supplies were intended to reduce pressure on the parallel market. – Libya Herald

## 4. Deduplication rules

- **Non-UN news:** remove exact duplicates and syndicated repeats. If several
  sources report the same story, keep the clearest/most authoritative version.
  When a story is reported by multiple outlets, render it as one bullet and
  list all sources after it, joined by ` / `.
- **UN-related news (mandatory repetition rule):** all UN-related items are
  included even if repeated across sources. If different sources add different
  wording/detail, keep separate bullets; if identical, combine into one bullet
  listing every source. The duplicate-removal rule must never suppress
  UN-related coverage. "UN-related" covers UNSMIL, SRSG/DSRSG, UN agencies,
  UN-supported initiatives, Security Council activity, international mediation,
  humanitarian agencies, and UN partnerships.

## 5. Inclusion / exclusion

Include only items that are from an approved source, about or directly
affecting Libya, published in the coverage window, with a verifiable
article-level URL, and accurately summarisable in English. Exclude non-Libya
regional items, undated pages, broken links, unclear aggregator items, and
duplicate non-UN syndicated items.

## 6. Mandatory disclaimer

The Word report must end with:

> DISCLAIMER: The Media Monitoring Reviews are compiled by the Public
> Information & Communications Section (PICS) of UNSMIL. These Reports do not
> reflect the views or official positions of UNSMIL, nor does UNSMIL vouch for
> the accuracy of the information contained therein. If you have any
> questions/suggestions, please contact: unsmil-info-libya@un.org

## 7. Exact PICS formatting benchmark

When converting an existing Libya News Headlines report into final PICS
format, use the approved June 2026 benchmark files in [`samples/`](../samples)
as the master reference. The task is formatting, structure, organization,
title standardization, and editorial consistency. Do not add stories, remove
valid stories, shorten the report, summarize sections, or change factual
content unless needed for consistency.

The final Word report must look as if it was produced by the same person who
produced the benchmark reports:

- Page setup: US Letter, 1 inch margins.
- Title: centered, bold Calibri 12, exact form
  `Libya News Headlines – <DATE RANGE>`, e.g.
  `Libya News Headlines – 18-21 June 2026`.
- No subtitle, explanatory note, footer, numbering, or bullets.
- Body: Calibri 12, approximately 1.15 line spacing.
- Main section headings: Impact 14, black, left aligned.
- Subsections: bold Calibri 12, black, left aligned.
- Source names must be Word-native hyperlinks.
- Source format is always `Headline – Source (Arabic)` or
  `Headline – Source (English)` with an en dash. When multiple sources carry
  the same story, join them with ` / `.
- Visible source display names must be in English only. Do not leave Arabic,
  Chinese, or other non-English source labels visible in the final DOCX. Keep
  the `(Arabic)` language label after translated Arabic-source names and
  preserve the original URL/hyperlink.
- Examples: `سكاي نيوز عربية` -> `Sky News Arabia`; `الشرق الأوسط` ->
  `Asharq Al-Awsat`; `العربي الجديد` -> `The New Arab`; `بوابة الوسط` ->
  `Al Wasat`; `新华网` -> `Xinhua`.

Use this exact main section order unless a section has no items:

1. United Nations
2. Politics
3. Military & Security
4. Human Rights & Rule of Law
5. Economy
6. Environment
7. Regional & International
8. Varieties

## 8. Benchmark subsection conventions

Use benchmark-style thematic clusters rather than generic catch-all headings.
Create subsections where they help the reader scan the report, but avoid
unnecessary or empty subsections except where the benchmark explicitly expects
fixed economic headings.

### United Nations

Group UN-related stories into logical PICS subsections such as:

- Political Process
- Structured Dialogue
- SRSG Meetings
- DSRSG Meetings
- Migration
- Other UN News

Keep substantive UN developments. Do not suppress UN stories simply because
similar language appears elsewhere; merge only clearly identical coverage of
the same event.

### Politics

Use thematic groups such as:

- Political Process
- Structured Dialogue
- Three Presidencies Agreement
- US Initiative
- Central Region
- Migration Debate
- Other political news

### Military & Security

Use whichever of these are appropriate:

- Security Developments
- Officials' Meetings
- Border Security
- Combating crime
- Migration Security
- Other security news

### Human Rights & Rule of Law

Use whichever of these are appropriate:

- Migration
- Rule of Law
- Human Rights
- Health
- Social Affairs
- Other Human Rights
- Other human rights and rule of law news

### Economy

Always split the Economy section into these benchmark headings, even if one
contains only one item or has no item in a converted draft:

- Banking
- Energy
- Reconstruction and infrastructure
- Transport
- Telecommunications
- Other economic news

### Environment

Use whichever of these are appropriate:

- Climate
- Environment
- Water Resources
- Other environmental news

### Regional & International

Create thematic clusters where possible, for example:

- Libya-Tunisia relations
- Libya-Greece relations
- Cairo talks on Libya and regional files
- International Relations
- Migration
- Other regional and international news

### Varieties

The Varieties section follows the benchmark feature format and should not be
left as headline-only entries. Use:

`Analysis | Title – Source`

`Feature | Title – Source`

`Opinion | Title – Source`

`Think Tank | Title – Source`

Then add a short paragraph summary below each Varieties item.

## 9. Political title standardization

Preserve and standardize institutional positions throughout the report. Use
bracketed tags where roles are known, including:

- `[SRSG]`
- `[DSRSG]`
- `[HoR Speaker]`
- `[HoR Member]`
- `[HCS President]`
- `[HCS Member]`
- `[Prime Minister]`
- `[HoR-appointed PM]`
- `[PC President]`
- `[PC Member]`
- `[AFM]`
- `[CoS]`
- `[LNA Commander]`
- `[LNA Deputy Commander-in-Chief]`
- `[CBL Governor]`
- `[Mufti]`

Never reduce a political figure to a surname only when the role is known.

## 10. Final conversion quality control

Before exporting a final PICS-format DOCX:

- Verify the title exactly matches the benchmark format.
- Verify the fonts, spacing, margins, and hierarchy match the sample reports.
- Confirm the section order and benchmark-style subsections.
- Confirm political titles are standardized.
- Confirm all source names are clickable Word-native hyperlinks.
- Confirm all visible source names are English-only, with Arabic-language
  items marked using `(Arabic)`.
- Confirm every headline uses an en dash before sources.
- Confirm there are no bullets, numbering, subtitle, or footer.
- Confirm the benchmark disclaimer appears at the end.
- Render the DOCX to page images and visually inspect every page for clipping,
  overlap, missing glyphs, awkward spacing, or broken hyperlinks.
