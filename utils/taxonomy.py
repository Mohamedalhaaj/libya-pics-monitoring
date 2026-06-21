"""Canonical UNSMIL/PICS report taxonomy.

Defines the fixed section order, suggested subsections, and the mandatory
disclaimer used by the daily Libya News Headlines report. See
docs/report_methodology.md for the editorial rules behind these values.
"""

from __future__ import annotations

# Exact main section order required by the report. Sections with no items are
# omitted at render time, but their relative order never changes.
SECTION_ORDER: list[str] = [
    "United Nations",
    "Politics",
    "Military & Security",
    "Human Rights & Rule of Law",
    "Economy",
    "Environment",
    "Regional & International",
    "Varieties",
]

# Benchmark subsections per section, matching the PICS conversion SOP
# (samples/PICS_headlines_conversion_SOP.md §8). Used to steer the enrichment
# model and to order subsections within a section.
SUGGESTED_SUBSECTIONS: dict[str, list[str]] = {
    "United Nations": [
        "Political Process",
        "Structured Dialogue",
        "SRSG Meetings",
        "DSRSG Meetings",
        "Migration",
        "Other UN News",
    ],
    "Politics": [
        "Political Process",
        "Structured Dialogue",
        "Three Presidencies Agreement",
        "US Initiative",
        "Central Region",
        "Migration Debate",
        "Other political news",
    ],
    "Military & Security": [
        "Security Developments",
        "Officials' Meetings",
        "Border Security",
        "Combating crime",
        "Migration Security",
        "Other security news",
    ],
    "Human Rights & Rule of Law": [
        "Migration",
        "Rule of Law",
        "Human Rights",
        "Health",
        "Social Affairs",
        "Other Human Rights",
    ],
    # Economy is always split into these fixed headings (SOP §8).
    "Economy": [
        "Banking",
        "Energy",
        "Reconstruction and infrastructure",
        "Transport",
        "Telecommunications",
        "Other economic news",
    ],
    "Environment": [
        "Climate",
        "Environment",
        "Water Resources",
        "Other environmental news",
    ],
    "Regional & International": [
        "Cairo talks on Libya and regional files",
        "Libya-Tunisia relations",
        "Libya-Greece relations",
        "International Relations",
        "Migration",
        "Other regional and international news",
    ],
    "Varieties": [
        "Analysis",
        "Feature",
        "Opinion",
        "Think Tank",
    ],
}

DISCLAIMER = (
    "DISCLAIMER: The Media Monitoring Reviews are compiled by the Public "
    "Information & Communications Section (PICS) of UNSMIL. These Reports do not "
    "reflect the views or official positions of UNSMIL, nor does UNSMIL vouch "
    "for the accuracy of the information contained therein. If you have any "
    "questions/suggestions, please contact: unsmil-info-libya@un.org"
)


def section_sort_key(section_name: str) -> int:
    """Sort key placing sections in canonical order; unknown names go last."""
    try:
        return SECTION_ORDER.index(section_name)
    except ValueError:
        return len(SECTION_ORDER)
