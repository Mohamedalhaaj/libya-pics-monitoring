"""Canonical outlet names for aggregator (Google News) attribution.

Google News reports each item's publisher in its own language and house spelling
("بوابة الوسط", "Anadolu Ajansı", "allAfrica.com"). The PICS gold reports cite
those outlets by a consistent English label ("Al Wasat", "Anadolu Agency",
"all Africa"). Mapping the raw publisher to the gold label keeps attribution
consistent, lets the same story from a direct feed and from Google News
deduplicate, and makes coverage compare correctly against the gold report.

Only outlets that matter (appear in the gold reports or correspond to a monitored
source) are mapped; unmapped publishers pass through unchanged.
"""

from __future__ import annotations

# raw publisher (any script) -> canonical English label used in the gold reports
OUTLET_ALIASES: dict[str, str] = {
    # Arabic outlets
    "عين ليبيا": "Ean Libya",
    "بوابة الوسط": "Al Wasat",
    "الوسط": "Al Wasat",
    "العين الإخبارية": "Al Ain",
    "سكاي نيوز عربية": "Sky News Arabia",
    "الشرق الأوسط": "Asharq Al-Awsat",
    "العربي الجديد": "New Arab",
    "اندبندنت عربية": "Independent Arabia",
    "العربية": "Al Arabiya",
    "صحيفة الساعة 24": "Alsaaa 24",
    "الساعة 24": "Alsaaa 24",
    "القدس العربي": "Al Quds Al Arabi",
    "الجزيرة نت": "Al Jazeera",
    "الجزيرة": "Al Jazeera",
    "الشرق للأخبار": "Asharq News",
    "الشرق مع بلومبرغ": "Asharq News",
    "شفق نيوز": "Shafaq",
    "سانا": "SANA",
    "إرم نيوز": "Erem News",
    "المصري اليوم": "Al-Masry Al-Youm",
    # English / Latin variants -> gold spelling
    "the libya observer": "Libya Observer",
    "libyaupdate.com": "Libya Update",
    "libyaobserver.ly": "Libya Observer",
    "the new arab": "New Arab",
    "anadolu ajansı": "Anadolu Agency",
    "anadolu ajansi": "Anadolu Agency",
    "allafrica.com": "all Africa",
    "allafrica": "all Africa",
    "middle-east-online.com": "Middle East Online",
    "annahar.com": "Annahar",
    "news.cgtn.com": "CGTN",
    "dw.com": "DW",
    "cbc": "CBC News",
    "新华网": "Xinhua",
    "fana news": "Fana",
}

# Normalised lookup (casefolded). Arabic casefolds to itself, so this is safe.
_ALIASES_CF = {key.casefold(): value for key, value in OUTLET_ALIASES.items()}


def canonicalize_outlet(name: str) -> str:
    """Map a raw publisher name to its canonical label; pass through if unknown."""
    cleaned = (name or "").strip().strip("-|–—").strip()
    return _ALIASES_CF.get(cleaned.casefold(), cleaned)
