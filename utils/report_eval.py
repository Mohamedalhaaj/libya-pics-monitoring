"""Quality evaluation for generated PICS reports.

Turns "did the report get better?" into a number. The approach has two parts:

1. A **gold profile** learned from the human reports in ``samples/`` (bullets
   per report, % English bullets, multi-source/dedup rate, role-prefix usage,
   source vocabulary). These reports define what a correct PICS product looks
   like.
2. A **scorecard** for any report, parsed from its .docx: hard structural
   checks (title, canonical section order, every bullet attributed, zero
   boilerplate noise), conformance to the gold profile (English ratio, dedup,
   bullet volume), and — when a date-matched gold report is supplied —
   source-coverage recall against it.

Everything here is deterministic and offline. ``llm_judge`` adds an optional
qualitative pass (translation quality / story recall) when an API key with
credit is available, degrading gracefully exactly like utils.enrich.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document

from utils import taxonomy
from utils.cleaning import is_boilerplate_title, normalize

_SECTION_SET = {normalize(name) for name in taxonomy.SECTION_ORDER}
_ARABIC_RE = re.compile(r"[؀-ۿ]")
_PAREN_RE = re.compile(r"\([^)]*\)")
_LANG_TAG_RE = re.compile(r"\((?:arabic|english|عربي|عربى)\)", re.IGNORECASE)


def canonical_source(name: str) -> str:
    """Match-key for an outlet name: drop parentheticals (e.g. '(English)'),
    unify hyphens/apostrophes and a leading 'the', collapse whitespace.

    Lets 'Asharq Al-Awsat', 'Asharq Al Awsat' and 'The New Arab (English)'
    compare equal across reports that label outlets slightly differently.
    """
    text = normalize(name)
    text = _PAREN_RE.sub(" ", text).replace("-", " ").replace("’", "'").replace("`", "'")
    text = re.sub(r"^the\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()
_ROLE_PREFIX_RE = re.compile(r"^\s*\[[^\]]+\]")
# Source citations are joined by " / "; the source block follows the last
# en/em dash. e.g. "Headline text – Source A / Source B (Arabic)".
_DASH_SPLIT_RE = re.compile(r"\s[–—-]\s")
_TITLE_RE = re.compile(r"libya news headlines", re.IGNORECASE)
_STOP_HEADINGS = {"source verification", "disclaimer"}


@dataclass(slots=True)
class Bullet:
    text: str
    sources: list[tuple[str, str]]  # (name, language)
    section: str
    subsection: str

    @property
    def is_english(self) -> bool:
        if not self.text:
            return False
        arabic = len(_ARABIC_RE.findall(self.text))
        return arabic / max(len(self.text), 1) < 0.15

    @property
    def has_role_prefix(self) -> bool:
        return bool(_ROLE_PREFIX_RE.match(self.text))


@dataclass(slots=True)
class ParsedReport:
    path: str
    title: str
    bullets: list[Bullet] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)  # in document order

    def source_names(self) -> set[str]:
        return {canonical_source(name) for bullet in self.bullets for name, _ in bullet.sources}


def _split_sources(source_blob: str) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for piece in source_blob.split(" / "):
        name = piece.strip()
        if not name:
            continue
        # Some reports tag English outlets too (e.g. "Libya Herald (English)");
        # the language is the tag, the stored name drops any language tag.
        language = "ar" if re.search(r"\(arabic\)", name, re.IGNORECASE) else "en"
        name = _LANG_TAG_RE.sub("", name).strip()
        if name:
            sources.append((name, language))
    return sources


def parse_pics_report(path: str | Path) -> ParsedReport:
    """Parse a PICS 'Libya News Headlines' .docx into title + bullets."""
    document = Document(str(path))
    title = ""
    bullets: list[Bullet] = []
    sections: list[str] = []
    current_section = ""
    current_subsection = ""

    for paragraph in document.paragraphs:
        text = " ".join(paragraph.text.split())
        if not text:
            continue
        normalized = normalize(text)
        style = (paragraph.style.name if paragraph.style else "") or ""

        if not title and _TITLE_RE.search(text):
            title = text
            continue
        if normalized in _STOP_HEADINGS:
            break  # appendix / disclaimer — stop collecting body content
        if normalized.startswith("draft"):
            continue  # our own DRAFT banner

        if normalized in _SECTION_SET:
            current_section = text
            current_subsection = ""
            sections.append(text)
            continue

        is_bullet = "list" in style.lower() or bool(_DASH_SPLIT_RE.search(text))
        if is_bullet:
            parts = _DASH_SPLIT_RE.split(text)
            if len(parts) >= 2:
                headline = " – ".join(parts[:-1]).strip()
                source_blob = parts[-1].strip()
                sources = _split_sources(source_blob)
            else:
                headline, sources = text, []
            bullets.append(Bullet(headline, sources, current_section, current_subsection))
        elif len(text.split()) <= 10:
            current_subsection = text  # short non-section line = subsection header
        # else: long unattributed paragraph (analysis body) — ignored

    return ParsedReport(path=str(path), title=title, bullets=bullets, sections=sections)


# --------------------------------------------------------------------------- #
# Metrics + gold profile                                                       #
# --------------------------------------------------------------------------- #

def report_metrics(report: ParsedReport) -> dict:
    bullets = report.bullets
    n = len(bullets)
    safe = max(n, 1)
    return {
        "n_bullets": n,
        "sections": list(report.sections),
        "sections_ordered": _is_canonical_order(report.sections),
        "title_ok": bool(_TITLE_RE.search(report.title)),
        "english_ratio": sum(b.is_english for b in bullets) / safe,
        "has_source_ratio": sum(bool(b.sources) for b in bullets) / safe,
        "multi_source_ratio": sum(len(b.sources) >= 2 for b in bullets) / safe,
        "role_prefix_ratio": sum(b.has_role_prefix for b in bullets) / safe,
        "noise_bullets": sum(is_boilerplate_title(b.text) for b in bullets),
        "avg_sources_per_bullet": sum(len(b.sources) for b in bullets) / safe,
    }


def _is_canonical_order(sections: list[str]) -> bool:
    """True if the sections appear as an in-order subsequence of SECTION_ORDER."""
    indices = [taxonomy.SECTION_ORDER.index(s) for s in sections if s in taxonomy.SECTION_ORDER]
    return bool(indices) and indices == sorted(indices)


@dataclass(slots=True)
class GoldProfile:
    n_reports: int
    bullets_median: float
    bullets_low: float
    bullets_high: float
    english_ratio: float
    multi_source_ratio: float
    role_prefix_ratio: float
    source_vocab: set[str]
    per_report: list[dict] = field(default_factory=list)


def build_gold_profile(samples_dir: str | Path) -> GoldProfile:
    paths = sorted(Path(samples_dir).glob("*.docx"))
    metrics, vocab = [], set()
    for path in paths:
        report = parse_pics_report(path)
        if not report.bullets:
            continue
        metrics.append(report_metrics(report))
        vocab |= report.source_names()
    if not metrics:
        raise ValueError(f"No parseable PICS reports found in {samples_dir}")
    counts = sorted(m["n_bullets"] for m in metrics)
    return GoldProfile(
        n_reports=len(metrics),
        bullets_median=statistics.median(counts),
        bullets_low=counts[max(0, len(counts) // 10)],
        bullets_high=counts[min(len(counts) - 1, (9 * len(counts)) // 10)],
        english_ratio=statistics.mean(m["english_ratio"] for m in metrics),
        multi_source_ratio=statistics.mean(m["multi_source_ratio"] for m in metrics),
        role_prefix_ratio=statistics.mean(m["role_prefix_ratio"] for m in metrics),
        source_vocab=vocab,
        per_report=metrics,
    )


# --------------------------------------------------------------------------- #
# Scoring                                                                      #
# --------------------------------------------------------------------------- #

def _ratio_score(value: float, target: float) -> float:
    """1.0 when value meets/exceeds target; linear below. Guards target==0."""
    if target <= 0:
        return 1.0
    return max(0.0, min(1.0, value / target))


def coverage_recall(
    target: ParsedReport,
    gold: ParsedReport,
    monitored: set[str] | None = None,
) -> dict:
    """Source-name recall of the target against a date-matched gold report.

    Source labels are rendered in English in both reports (e.g. 'Al Menassa
    (Arabic)'), so this works even when the target's headlines are untranslated.

    Raw recall is unfair: gold cites many one-off wires (AP, ABC, …) that the
    pipeline never monitors, so a perfect report can only ever reach a ceiling
    of ``gold ∩ monitored``. When ``monitored`` (the configured source names) is
    supplied we also report ``ceiling_recall`` — recall against the achievable
    set — which is what scoring should use.
    """
    gold_sources = gold.source_names()
    target_sources = target.source_names()
    hit = gold_sources & target_sources
    result = {
        "gold_sources": len(gold_sources),
        "matched_sources": len(hit),
        "source_recall": len(hit) / max(len(gold_sources), 1),
        "missing_sources": sorted(gold_sources - target_sources),
        "bullet_ratio": len(target.bullets) / max(len(gold.bullets), 1),
    }
    if monitored is not None:
        monitored_canon = {canonical_source(name) for name in monitored}
        achievable = gold_sources & monitored_canon
        achievable_hit = achievable & target_sources
        result.update(
            achievable_sources=len(achievable),
            unmonitored_gold=len(gold_sources - monitored_canon),
            ceiling_recall=len(achievable_hit) / max(len(achievable), 1),
            missing_monitored=sorted(achievable - target_sources),
        )
    return result


def score_report(
    report: ParsedReport,
    profile: GoldProfile,
    gold: ParsedReport | None = None,
    monitored: set[str] | None = None,
) -> dict:
    """Produce a 0-100 scorecard with a transparent component breakdown."""
    m = report_metrics(report)
    n = m["n_bullets"]

    # Structure (0-100 within component) ------------------------------------
    title_pts = 100 if m["title_ok"] else 0
    order_pts = 100 if m["sections_ordered"] else (50 if m["sections"] else 0)
    attribution_pts = 100 * m["has_source_ratio"]
    noise_pts = 100 if m["noise_bullets"] == 0 else max(0.0, 100 - 100 * m["noise_bullets"] / max(n, 1))
    structure = statistics.mean([title_pts, order_pts, attribution_pts, noise_pts])

    # Style conformance vs the gold profile ---------------------------------
    english_pts = 100 * _ratio_score(m["english_ratio"], profile.english_ratio)
    dedup_pts = 100 * _ratio_score(m["multi_source_ratio"], profile.multi_source_ratio)
    role_pts = 100 * _ratio_score(m["role_prefix_ratio"], max(profile.role_prefix_ratio, 0.05))
    in_band = profile.bullets_low <= n <= profile.bullets_high
    volume_pts = 100 if in_band else 100 * _ratio_score(n, profile.bullets_low)
    style = statistics.mean([english_pts, dedup_pts, role_pts, volume_pts])

    components = {
        "structure": round(structure, 1),
        "style_conformance": round(style, 1),
    }
    breakdown = {
        "title_ok": m["title_ok"],
        "sections_ordered": m["sections_ordered"],
        "attribution_ratio": round(m["has_source_ratio"], 3),
        "noise_bullets": m["noise_bullets"],
        "english_ratio": round(m["english_ratio"], 3),
        "multi_source_ratio": round(m["multi_source_ratio"], 3),
        "role_prefix_ratio": round(m["role_prefix_ratio"], 3),
        "n_bullets": n,
        "gold_bullet_band": [profile.bullets_low, profile.bullets_high],
    }

    coverage = None
    if gold is not None:
        coverage = coverage_recall(report, gold, monitored=monitored)
        # Score against the achievable ceiling (gold ∩ monitored sources) when
        # we know the source list; otherwise fall back to raw recall.
        recall = coverage.get("ceiling_recall", coverage["source_recall"])
        components["coverage"] = round(100 * recall, 1)
        total = 0.4 * structure + 0.35 * style + 0.25 * components["coverage"]
    else:
        total = 0.55 * structure + 0.45 * style

    return {
        "report": report.path,
        "total": round(total, 1),
        "components": components,
        "breakdown": breakdown,
        "coverage": coverage,
    }


# --------------------------------------------------------------------------- #
# Optional LLM judge (qualitative; needs API credit)                           #
# --------------------------------------------------------------------------- #

class JudgeUnavailable(RuntimeError):
    """Raised when the LLM judge cannot run (missing SDK/key/credit)."""


def llm_judge(report: ParsedReport, gold: ParsedReport, model: str = "claude-opus-4-8") -> dict:
    """Qualitative translation-quality / story-recall scores via Claude.

    Mirrors utils.enrich: raises JudgeUnavailable when the SDK, key, or credit
    is missing so callers can skip it.
    """
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise JudgeUnavailable("The 'anthropic' package is not installed.") from exc
    try:
        client = anthropic.Anthropic()
    except Exception as exc:  # pragma: no cover
        raise JudgeUnavailable(f"Could not initialise Anthropic client: {exc}") from exc

    def bullets_blob(rep: ParsedReport, limit: int = 200) -> str:
        return "\n".join(f"- {b.text}" for b in rep.bullets[:limit])

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "translation_quality": {"type": "integer"},
            "story_recall": {"type": "integer"},
            "notes": {"type": "string"},
        },
        "required": ["translation_quality", "story_recall", "notes"],
    }
    system = (
        "You compare a CANDIDATE Libya media-monitoring report against a GOLD "
        "human report covering the same days. Score 0-100: translation_quality "
        "(are candidate headlines fluent, accurate English in PICS style?) and "
        "story_recall (what share of the gold's distinct stories appear in the "
        "candidate, regardless of wording/order?). Return JSON via the schema."
    )
    user = (
        f"GOLD bullets:\n{bullets_blob(gold)}\n\n"
        f"CANDIDATE bullets:\n{bullets_blob(report)}"
    )
    try:
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user}],
        )
    except Exception as exc:  # pragma: no cover - network/billing dependent
        raise JudgeUnavailable(f"LLM judge request failed: {exc}") from exc

    import json

    text = next((b.text for b in message.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise JudgeUnavailable(f"Could not parse judge output: {exc}") from exc
