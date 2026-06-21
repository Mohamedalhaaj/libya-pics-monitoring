"""Outlet display-name normalisation.

Aggregator feeds (Google News) return outlet names in their native script
(Arabic, Chinese, …). The PICS SOP requires visible source names in the final
report to be English-only (e.g. بوابة الوسط -> "Al Wasat", 新华网 -> "Xinhua").
This map covers the outlets seen in collection; unknown names pass through
unchanged for the enrichment/editor to handle.
"""

from __future__ import annotations

# Native outlet name -> English display name.
OUTLET_NAMES: dict[str, str] = {
    "بوابة الوسط": "Al Wasat",
    "الوسط": "Al Wasat",
    "العين الإخبارية": "Al Ain News",
    "العربي الجديد": "The New Arab",
    "الشرق الأوسط": "Asharq Al-Awsat",
    "الشرق للأخبار": "Asharq News",
    "سكاي نيوز عربية": "Sky News Arabia",
    "اليوم السابع": "Youm7",
    "الاتحاد": "Al Ittihad",
    "صدى البلد": "Sada El-Balad",
    "بوابة الأهرام": "Ahram Gate",
    "الجزيرة نت": "Al Jazeera",
    "العربية": "Al Arabiya",
    "سبوتنيك عربي": "Sputnik Arabic",
    "أخبار الغد": "Akhbar Al-Ghad",
    "النهار المصرية": "Egyptian Al-Nahar",
    "جريدة النهار المصرية": "Egyptian Al-Nahar",
    "حفريات": "Hafryat",
    "المنصة": "Al Manassa",
    "إرم نيوز": "Erem News",
    "عربي21": "Arabi21",
    "الميادين": "Al Mayadeen",
    "أخبار ليبيا": "Akhbar Libya",
    "新华网": "Xinhua",
    "新华社": "Xinhua",
    "人民网": "People's Daily",
}


def english_outlet_name(name: str) -> str:
    """Return the English display name for an outlet, or the name unchanged."""
    cleaned = (name or "").strip()
    return OUTLET_NAMES.get(cleaned, cleaned)
