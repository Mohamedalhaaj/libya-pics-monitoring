"""Claude-powered editorial enrichment of scraped headlines.

The scraper collects raw, mostly-Arabic headlines. The UNSMIL/PICS report
(see docs/report_methodology.md) needs those translated to English, sorted
into a fixed thematic taxonomy, and de-duplicated across outlets so the same
story becomes one bullet citing every source. That editorial judgement is the
job of this module: it sends the collected articles to the Claude API and
returns a StructuredReport ready to render.

Enrichment is optional. When the `anthropic` package or an API key is missing
(or `enrich_report` raises), the caller falls back to a mechanical
source-grouped layout — see utils/exports.build_fallback_report.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from utils import taxonomy
from utils.models import (
    Article,
    HeadlineSource,
    ReportHeadline,
    ReportSection,
    ReportSubsection,
    StructuredReport,
)

logger = logging.getLogger(__name__)

# Default model for enrichment. Opus 4.8 is the most capable model and this is a
# translation + classification + clustering task where quality matters most.
DEFAULT_MODEL = "claude-opus-4-8"

# Output token ceiling. Reports can be long, so stream the response.
MAX_TOKENS = 32000


class EnrichmentUnavailable(RuntimeError):
    """Raised when enrichment cannot run (missing SDK, key, or API failure)."""


def _build_system_prompt() -> str:
    sections = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(taxonomy.SECTION_ORDER))
    subsection_lines = []
    for section, subs in taxonomy.SUGGESTED_SUBSECTIONS.items():
        subsection_lines.append(f"- {section}: " + "; ".join(subs))
    subsections = "\n".join(subsection_lines)
    return (
        "You are a media-monitoring editor producing the UNSMIL/PICS daily "
        "\"Libya News Headlines\" report from a list of collected articles. Follow "
        "the PICS conversion SOP (samples/PICS_headlines_conversion_SOP.md).\n\n"
        "Rules:\n"
        "1. COVERAGE FIRST: include every distinct Libya-related story in the "
        "input. Do not shorten, summarise away, or skip valid stories — the goal "
        "is an exhaustive report, not a digest. Drop only items with no Libya "
        "connection or that cannot be summarised accurately in English.\n"
        "2. Translate Arabic headlines into clear, concise English. Each bullet is "
        "one sentence stating the news fact; never start with the source name. No "
        "opinions.\n"
        "3. Exact main section order (omit a section only if it has no items):\n"
        f"{sections}\n\n"
        "4. Use benchmark-style thematic subsections (not generic catch-alls), "
        "e.g. Politics: Three Presidencies Agreement / US Initiative / Structured "
        "Dialogue / Central Region / Migration Debate / Other political news. "
        "Suggested subsections per section:\n"
        f"{subsections}\n"
        "Always split Economy into: Banking; Energy; Reconstruction and "
        "infrastructure; Transport; Telecommunications; Other economic news.\n\n"
        "5. Deduplicate non-UN news: when several sources report the same story, "
        "produce ONE headline listing every reporting source. A source adding "
        "materially different information may be a separate headline.\n"
        "6. UN-related news (UNSMIL, SRSG/DSRSG, UN agencies, Security Council, "
        "international mediation, humanitarian agencies, UN partnerships) is kept "
        "even when repeated. Never drop UN coverage as a duplicate.\n"
        "7. Each headline ends with its sources. Use English-only outlet display "
        "names (e.g. بوابة الوسط -> 'Al Wasat'); keep the (Arabic) language label "
        "for Arabic sources; preserve each article URL.\n"
        "8. Standardise known political roles with bracketed tags: [SRSG], "
        "[DSRSG], [HoR Speaker], [HoR Member], [HCS President], [HCS Member], "
        "[Prime Minister], [PC President], [LNA Commander], [CBL Governor], "
        "[Mufti], etc. Never reduce a figure to a surname when the role is known.\n"
        "9. Varieties items use the feature format 'Analysis | Title', "
        "'Feature | Title', 'Opinion | Title', 'Think Tank | Title', each followed "
        "by a short summary sentence.\n\n"
        "Return the report via the provided JSON schema only."
    )


def _report_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "enum": taxonomy.SECTION_ORDER},
                        "subsections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "headlines": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "text": {"type": "string"},
                                                "sources": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "additionalProperties": False,
                                                        "properties": {
                                                            "name": {"type": "string"},
                                                            "language": {
                                                                "type": "string",
                                                                "enum": ["ar", "en"],
                                                            },
                                                            "url": {"type": "string"},
                                                        },
                                                        "required": ["name", "language", "url"],
                                                    },
                                                },
                                            },
                                            "required": ["text", "sources"],
                                        },
                                    },
                                },
                                "required": ["name", "headlines"],
                            },
                        },
                    },
                    "required": ["name", "subsections"],
                },
            }
        },
        "required": ["sections"],
    }


def _articles_payload(articles: list[Article]) -> str:
    rows = [
        {
            "source_name": article.source_name,
            "language": article.language,
            "title": article.title,
            "summary": article.summary,
            "url": article.url,
            "published_at": article.published_at.isoformat() if article.published_at else "",
            "scraped_section": article.section,
        }
        for article in articles
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2)


def _parse_report(data: dict[str, Any], report_date: str) -> StructuredReport:
    sections: list[ReportSection] = []
    for raw_section in data.get("sections", []):
        subsections: list[ReportSubsection] = []
        for raw_sub in raw_section.get("subsections", []):
            headlines = [
                ReportHeadline(
                    text=raw_headline["text"],
                    sources=[
                        HeadlineSource(
                            name=source["name"],
                            language=source.get("language", "en"),
                            url=source.get("url", ""),
                        )
                        for source in raw_headline.get("sources", [])
                    ],
                )
                for raw_headline in raw_sub.get("headlines", [])
                if raw_headline.get("text")
            ]
            if headlines:
                subsections.append(ReportSubsection(name=raw_sub.get("name", ""), headlines=headlines))
        if subsections:
            sections.append(ReportSection(name=raw_section["name"], subsections=subsections))

    sections.sort(key=lambda section: taxonomy.section_sort_key(section.name))
    return StructuredReport(report_date=report_date, sections=sections)


def enrich_report(
    articles: list[Article],
    report_date: str,
    model: str = DEFAULT_MODEL,
) -> StructuredReport:
    """Turn scraped articles into an editorial StructuredReport via Claude.

    Raises EnrichmentUnavailable when the SDK/key is missing or the call fails,
    so the caller can fall back to the mechanical layout.
    """
    if not articles:
        return StructuredReport(report_date=report_date, sections=[])

    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise EnrichmentUnavailable(
            "The 'anthropic' package is not installed; run `pip install anthropic`."
        ) from exc

    try:
        client = anthropic.Anthropic()
    except Exception as exc:  # missing/invalid credentials surface here
        raise EnrichmentUnavailable(f"Could not initialise Anthropic client: {exc}") from exc

    system_prompt = _build_system_prompt()
    user_content = (
        f"Coverage date: {report_date}.\n"
        "Here are the collected articles as JSON. Produce the report.\n\n"
        f"{_articles_payload(articles)}"
    )

    logger.info("Enriching %s articles with %s", len(articles), model)
    try:
        # Stream because reports can be long enough to risk a non-streaming
        # HTTP timeout at this max_tokens.
        with client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            output_config={"format": {"type": "json_schema", "schema": _report_schema()}},
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        raise EnrichmentUnavailable(f"Enrichment request failed: {exc}") from exc

    if message.stop_reason == "refusal":
        raise EnrichmentUnavailable("Model declined the enrichment request (refusal).")

    text = next((block.text for block in message.content if block.type == "text"), "")
    if not text:
        raise EnrichmentUnavailable("Model returned no text content.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EnrichmentUnavailable(f"Could not parse model output as JSON: {exc}") from exc

    return _parse_report(data, report_date)
