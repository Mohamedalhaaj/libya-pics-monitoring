# Codex enrichment brief — build the PICS report from the raw CSV

Use this with the raw data in `output/libya_media_headlines.csv` to produce the
UNSMIL/PICS **“Libya News Headlines”** report. This is the editorial step the
pipeline normally hands to the Claude API (`utils/enrich.py`); the brief lets
another model do the same job. Reference the gold human reports in `samples/*.docx`
for tone and layout.

## Input

`output/libya_media_headlines.csv` (UTF-8, columns):

| column | meaning |
|---|---|
| `source_name` | report-friendly outlet name (cite this verbatim) |
| `language` | `ar` or `en` — Arabic items must be translated |
| `title` | headline as published (Arabic or English) |
| `summary` | short dek / publish line, if any |
| `url` | article link |
| `published_at` | ISO timestamp (all rows are dated) |
| `section` | publisher's own category, if any (a hint, not authoritative) |

Coverage date = the span of `published_at` (current data: **18–21 June 2026**).
Title the report `Libya News Headlines – 18-21 June` (collapse a multi-day window
to a `D-D Month` range; a single day is just `D Month`).

## Editorial rules

1. **Relevance.** Keep only items about or directly affecting Libya. Drop generic
   regional/international items with no Libya link, and anything you cannot
   summarise accurately in English.
2. **Translate.** Render every Arabic headline as one clear, concise English
   sentence stating the news fact. Never start a bullet with the outlet name. No
   opinion or editorialising. Preserve proper nouns / transliterations of Libyan
   names (Tetteh, Boulos, Haftar, Dbeibeh, Menfi, Takala, Saleh…).
3. **Deduplicate (non-UN).** When several outlets report the same story, produce
   ONE bullet and cite every reporting outlet. Split into separate bullets only
   when an outlet adds materially different information.
4. **Never drop UN coverage as a duplicate.** UN items (UNSMIL, SRSG/DSRSG
   Tetteh/Koury, Security Council, UN agencies, international mediation,
   humanitarian agencies) are combined when identical but kept even if repeated.
5. **Attribution format.** End each bullet with ` – ` then the outlets joined by
   ` / `. Append ` (Arabic)` **only** to Arabic-language outlets (the `language`
   column is `ar`); **never tag English outlets** — write `Reuters`, not
   `Reuters (English)`. English outlets first where natural. Example:
   `At least 15 migrant bodies wash ashore in eastern Libya – Reuters / New Arab / Shafaq (Arabic)`
6. **Role/title prefixes.** When a bullet reports a named person's statement,
   prefix their role in square brackets, e.g.
   `[HoR Member] Jehani: the General Command's support gives the US initiative momentum`,
   `[Mufti] Gharyani issues a fatwa calling on Libyans to reject the outcomes`.
7. **One sentence per bullet.** Factual, present tense where natural.

## Structure

Use this exact main section order; omit a section only if it has no items. **Each
main section appears at most once** — group all of its bullets and subsections
under a single heading; never emit the same section heading twice.

1. United Nations
2. Politics
3. Military & Security
4. Human Rights & Rule of Law
5. Economy
6. Environment
7. Regional & International
8. Varieties

Group bullets under concise subsections. You MAY also add a short **event-specific
sub-header** to cluster a major running story, e.g.
`Libyan governing institutions agree to hold elections before February 2027`,
`HoR members show support for US proposal`, `Cairo hosts talks between USA, Türkiye, Egypt and Saudi Arabia`.

Suggested subsections (use what fits; add an "Other …" bucket as needed):

- **United Nations:** UNSMIL and political process; UN agencies and international support; Security Council and international mediation; Other UN news
- **Politics:** Political institutions and governance; Elections and constitutional process; Government and municipal affairs; Other political news
- **Military & Security:** Security and crime; Border and military affairs; Armed groups and security arrangements; Other security news
- **Human Rights & Rule of Law:** Migration and human trafficking; Justice and accountability; Health, children and vulnerable groups; Civil liberties and human rights; Other
- **Economy:** Banking and currency; Energy and fuel; Markets, labour and services; Infrastructure and reconstruction; Other economic news
- **Environment:** Weather, climate and agriculture; Water and environmental resources; Other
- **Regional & International:** Diplomacy and foreign relations; Regional security; Gaza/convoy-related Libya news; Other
- **Varieties:** Culture, heritage and society; Sports; Analysis/Opinion; Other

## Output

A Word-style document:

- Centred bold title `Libya News Headlines – 18-21 June`.
- Bold section headings (the 8 above), bold sub-headings, bulleted headlines
  with linked source names.
- End with the mandatory disclaimer:

> DISCLAIMER: The Media Monitoring Reviews are compiled by the Public Information
> & Communications Section (PICS) of UNSMIL. These Reports do not reflect the
> views or official positions of UNSMIL, nor does UNSMIL vouch for the accuracy
> of the information contained therein. If you have any questions/suggestions,
> please contact: unsmil-info-libya@un.org

## Self-check

Score the result with `python evaluate.py <your_report>.docx --gold samples/<a_gold>.docx`
(or against `~/Downloads/20260621_headlines.docx`, the human 18–21 June report).
Targets to match the gold corpus: ~100% English bullets, sections in canonical
order, every bullet attributed, zero boilerplate, dedup rate ≈ 0.24.
