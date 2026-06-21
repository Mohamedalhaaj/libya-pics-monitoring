from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_SOURCE_FIELDS = {"id", "name", "language", "url", "parser", "selectors"}


def load_sources(path: str | Path) -> list[dict[str, Any]]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources.json must contain a top-level 'sources' list")

    for source in sources:
        missing = REQUIRED_SOURCE_FIELDS - source.keys()
        if missing:
            raise ValueError(f"Source {source.get('id', '<unknown>')} missing: {sorted(missing)}")
        if not source.get("enabled", True):
            continue
        # Feed sources read RSS/Atom and don't use CSS selectors.
        if source["parser"] == "feed":
            if not (source.get("feed_url") or source.get("url")):
                raise ValueError(f"Feed source {source['id']} requires feed_url or url")
            continue
        selectors = source["selectors"]
        if "article" not in selectors or "title" not in selectors:
            raise ValueError(f"Source {source['id']} requires selectors.article and selectors.title")

    return [source for source in sources if source.get("enabled", True)]
