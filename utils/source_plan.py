from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote_plus


PRIORITY_SOURCE_IDS = [
    "al_wasat",
    "ean_libya",
    "rna_reportage",
    "libya_observer",
    "libya_review",
    "lana",
    "al_marsad",
    "al_shahed",
    "libya_24",
    "al_saaa_24",
    "address_libya",
]


SOURCE_URLS: dict[str, dict[str, list[str]]] = {
    "al_wasat": {
        "collection_urls": [
            "https://alwasat.ly/section/libya",
            "https://alwasat.ly/section/all",
            "https://alwasat.ly/",
        ],
        "search_url_templates": ["https://alwasat.ly/search?search={query}"],
    },
    "ean_libya": {
        "collection_urls": ["https://www.eanlibya.com/", "https://www.eanlibya.com/category/news/"],
        "search_url_templates": ["https://www.eanlibya.com/?s={query}"],
    },
    "rna_reportage": {
        "collection_urls": ["https://reportage.ly/", "https://reportage.ly/category/news/"],
        "search_url_templates": ["https://reportage.ly/?s={query}"],
    },
    "libya_observer": {
        "collection_urls": ["https://libyaobserver.ly/news", "https://libyaobserver.ly/"],
        "search_url_templates": ["https://libyaobserver.ly/search?search={query}"],
    },
    "libya_review": {
        "collection_urls": ["https://libyareview.com/category/libya/", "https://libyareview.com/"],
        "search_url_templates": ["https://libyareview.com/?s={query}"],
    },
    "lana": {
        "collection_urls": [
            "https://lana.gov.ly/category.php?lang=ar&id=8",
            "https://lana.gov.ly/",
        ],
        "search_url_templates": [
            "https://lana.gov.ly/search.php?lang=ar&q={query}",
            "https://lana.gov.ly/?s={query}",
        ],
    },
    "al_marsad": {
        "collection_urls": ["https://almarsad.co/category/libya/", "https://almarsad.co/"],
        "search_url_templates": ["https://almarsad.co/?s={query}"],
    },
    "al_shahed": {
        "collection_urls": ["https://lywitness.com/category/libya/", "https://lywitness.com/"],
        "search_url_templates": ["https://lywitness.com/?s={query}"],
    },
    "libya_24": {
        "collection_urls": ["https://libya24.tv/category/news/", "https://libya24.tv/"],
        "search_url_templates": ["https://libya24.tv/?s={query}"],
    },
    "al_saaa_24": {
        "collection_urls": ["https://alsaaa24.net/category/libya/", "https://alsaaa24.net/"],
        "search_url_templates": ["https://alsaaa24.net/?s={query}"],
    },
    "address_libya": {
        "collection_urls": ["https://www.addresslibya.com/category/libya/", "https://www.addresslibya.com/"],
        "search_url_templates": ["https://www.addresslibya.com/?s={query}"],
    },
    "asharq_al_awsat": {
        "collection_urls": ["https://aawsat.com/tags/%D9%84%D9%8A%D8%A8%D9%8A%D8%A7"],
        "search_url_templates": ["https://aawsat.com/search?search={query}"],
    },
    "fawasel_media": {
        "collection_urls": ["https://fawaselmedia.com/category/news/", "https://fawaselmedia.com/"],
        "search_url_templates": ["https://fawaselmedia.com/?s={query}"],
    },
    "tanasuh": {
        "collection_urls": ["https://tanasuh.tv/category/news/", "https://tanasuh.tv/"],
        "search_url_templates": ["https://tanasuh.tv/?s={query}"],
    },
    "libya_herald": {
        "collection_urls": ["https://libyaherald.com/category/libya/", "https://libyaherald.com/"],
        "search_url_templates": ["https://libyaherald.com/?s={query}"],
    },
    "al_menassa": {
        "collection_urls": ["https://almenassa.ly/wide-web-1/", "https://almenassa.ly/"],
        "search_url_templates": ["https://almenassa.ly/?s={query}"],
    },
    "al_mashhad": {
        "collection_urls": ["https://www.almashhad.com/latest/", "https://www.almashhad.com/"],
        "search_url_templates": ["https://www.almashhad.com/search?keyword={query}"],
    },
    "libya_al_ahrar": {
        "collection_urls": ["https://libyaalahrar.tv/category/news/", "https://libyaalahrar.tv/"],
        "search_url_templates": ["https://libyaalahrar.tv/?s={query}"],
    },
    "libya_update": {
        "collection_urls": ["https://libyaupdate.com/category/news/", "https://libyaupdate.com/"],
        "search_url_templates": ["https://libyaupdate.com/?s={query}"],
    },
    "akhbar_libya_24": {
        "collection_urls": ["https://akhbarlibya24.net/category/libya-news/", "https://akhbarlibya24.net/"],
        "search_url_templates": ["https://akhbarlibya24.net/?s={query}"],
    },
    "al_sabaah": {
        "collection_urls": ["https://alsabaah.ly/category/libya/", "https://alsabaah.ly/"],
        "search_url_templates": ["https://alsabaah.ly/?s={query}"],
    },
    "al_jazeera_ar_libya": {
        "collection_urls": ["https://www.aljazeera.net/where/mideast/arab/libya/"],
        "search_url_templates": ["https://www.aljazeera.net/search/{query}"],
    },
    "al_ain": {
        "collection_urls": ["https://al-ain.com/tag/libya", "https://al-ain.com/"],
        "search_url_templates": ["https://al-ain.com/search?query={query}"],
    },
    "arabi21": {
        "collection_urls": ["https://arabi21.com/stories/t/49474/0/%D9%84%D9%8A%D8%A8%D9%8A%D8%A7"],
        "search_url_templates": ["https://arabi21.com/Search?searchText={query}"],
    },
    "new_arab": {
        "collection_urls": ["https://www.newarab.com/tag/libya"],
        "search_url_templates": ["https://www.newarab.com/search?search_api_fulltext={query}"],
    },
    "ansa": {
        "collection_urls": ["https://www.ansa.it/english/", "https://www.ansa.it/english/news/world/"],
        "search_url_templates": ["https://www.ansa.it/english/search.html?query={query}"],
    },
    "anadolu_agency": {
        "collection_urls": ["https://www.aa.com.tr/en/africa", "https://www.aa.com.tr/en"],
        "search_url_templates": ["https://www.aa.com.tr/en/search/?s={query}"],
    },
    "the_guardian": {
        "collection_urls": ["https://www.theguardian.com/world/libya"],
        "search_url_templates": ["https://www.theguardian.com/search?q={query}"],
    },
    "bss_news": {
        "collection_urls": ["https://www.bssnews.net/international", "https://www.bssnews.net/"],
        "search_url_templates": ["https://www.bssnews.net/search?q={query}"],
    },
    "gazettengr": {
        "collection_urls": ["https://gazettengr.com/category/world/", "https://gazettengr.com/"],
        "search_url_templates": ["https://gazettengr.com/?s={query}"],
    },
    "ch_aviation": {
        "collection_urls": ["https://www.ch-aviation.com/news"],
        "search_url_templates": ["https://www.ch-aviation.com/news?query={query}"],
    },
    "volcanodiscovery": {
        "collection_urls": ["https://www.volcanodiscovery.com/earthquakes/libya.html"],
        "search_url_templates": ["https://www.volcanodiscovery.com/search.html?q={query}"],
    },
    "reuters": {
        "collection_urls": ["https://www.reuters.com/world/africa/"],
        "search_url_templates": ["https://www.reuters.com/site-search/?query={query}"],
    },
}


def sort_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {source_id: index for index, source_id in enumerate(PRIORITY_SOURCE_IDS)}
    return sorted(sources, key=lambda source: priority.get(source["id"], len(priority)))


def build_collection_urls(source: dict[str, Any], keywords: list[str], start_date: datetime | None) -> list[str]:
    configured = SOURCE_URLS.get(source["id"], {})
    urls = list(source.get("collection_urls", []))
    urls.extend(configured.get("collection_urls", []))
    urls.append(source["url"])

    search_keywords = source.get("search_keywords") or default_search_keywords(source, keywords)
    date_tokens = date_search_tokens(start_date)
    for template in [*source.get("search_url_templates", []), *configured.get("search_url_templates", [])]:
        for keyword in [*date_tokens, *search_keywords]:
            urls.append(template.format(query=quote_plus(keyword), raw_query=keyword))

    return dedupe(urls)


def default_search_keywords(source: dict[str, Any], keywords: list[str]) -> list[str]:
    if source["language"] == "ar":
        defaults = ["ليبيا", "البعثة الأممية", "طرابلس", "بنغازي"]
    else:
        defaults = ["Libya", "UNSMIL", "Tripoli", "Benghazi"]
    extras = [keyword for keyword in keywords if keyword not in defaults]
    return [*defaults, *extras[:3]]


def date_search_tokens(start_date: datetime | None) -> list[str]:
    if not start_date:
        return []
    return [
        start_date.strftime("%Y/%m"),
        start_date.strftime("%Y-%m-%d"),
    ]


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
