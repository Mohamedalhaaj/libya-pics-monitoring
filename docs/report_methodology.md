# UNSMIL/PICS Libya News Headlines — Report Methodology

> **Authoritative rules:** the full, current conversion rules live in
> [`samples/PICS_headlines_conversion_SOP.md`](../samples/PICS_headlines_conversion_SOP.md)
> — benchmark subsections (§8), political-title tags (§9), exact formatting and
> English-only source names (§7), and the QC checklist (§10). This file is a
> condensed overview; the SOP wins where they differ.

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
