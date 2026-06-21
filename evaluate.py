"""Score a generated PICS report against the gold ``samples/`` corpus.

Examples
--------
    # Score the latest generated report against the gold profile
    python evaluate.py output/unsmil_pics_daily_media_report.docx

    # Add source-coverage recall vs a date-matched gold report
    python evaluate.py output/unsmil_pics_daily_media_report.docx \
        --gold ~/Downloads/20260621_headlines.docx

    # Just print what the gold corpus looks like
    python evaluate.py --profile
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from utils.config import load_sources
from utils.report_eval import (
    JudgeUnavailable,
    build_gold_profile,
    llm_judge,
    parse_pics_report,
    score_report,
)

DEFAULT_TARGET = "output/unsmil_pics_daily_media_report.docx"


def _bar(value: float, width: int = 28) -> str:
    filled = int(round(width * max(0.0, min(100.0, value)) / 100))
    return "█" * filled + "·" * (width - filled)


def print_profile(profile) -> None:
    print(f"Gold profile  ({profile.n_reports} reports in samples/)")
    print(f"  bullets/report   median {profile.bullets_median:.0f}  "
          f"(p10-p90 band {profile.bullets_low:.0f}-{profile.bullets_high:.0f})")
    print(f"  English ratio    {profile.english_ratio:.2f}")
    print(f"  multi-source     {profile.multi_source_ratio:.2f}  (dedup citing >=2 outlets)")
    print(f"  role-prefix      {profile.role_prefix_ratio:.2f}  (\"[Role] Name:\" bullets)")
    print(f"  source vocab     {len(profile.source_vocab)} distinct outlets")


def print_scorecard(card: dict, profile) -> None:
    print("=" * 60)
    print(f"REPORT: {card['report']}")
    print("=" * 60)
    comps = card["components"]
    for name, value in comps.items():
        print(f"  {name:<18} {value:5.1f}  {_bar(value)}")
    print(f"  {'TOTAL':<18} {card['total']:5.1f}  {_bar(card['total'])}")

    b = card["breakdown"]
    print("\n  checks:")
    print(f"    title ok ............. {b['title_ok']}")
    print(f"    sections in order .... {b['sections_ordered']}")
    print(f"    attributed bullets ... {b['attribution_ratio']:.0%}")
    print(f"    boilerplate noise .... {b['noise_bullets']}")
    print(f"    English headlines .... {b['english_ratio']:.0%}  (gold {profile.english_ratio:.0%})")
    print(f"    multi-source/dedup ... {b['multi_source_ratio']:.0%}  (gold {profile.multi_source_ratio:.0%})")
    print(f"    bullets .............. {b['n_bullets']}  (gold band {b['gold_bullet_band'][0]}-{b['gold_bullet_band'][1]})")

    cov = card.get("coverage")
    if cov:
        print("\n  coverage vs gold:")
        if "ceiling_recall" in cov:
            print(f"    ceiling recall ....... {cov['ceiling_recall']:.0%}  "
                  f"({cov['achievable_matched']}/{cov['achievable_sources']} of the gold outlets present in the collected data)")
            print(f"    raw recall ........... {cov['source_recall']:.0%}  "
                  f"({cov['matched_sources']}/{cov['gold_sources']}; "
                  f"{cov['unmonitored_gold']} gold outlets were not in the data)")
            if cov["missing_monitored"]:
                print(f"    available & missed ... {', '.join(cov['missing_monitored'][:12])}")
        else:
            print(f"    source recall ........ {cov['source_recall']:.0%}  "
                  f"({cov['matched_sources']}/{cov['gold_sources']} outlets)")
        print(f"    bullet ratio ......... {cov['bullet_ratio']:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a PICS report against the gold corpus.")
    parser.add_argument("target", nargs="?", default=DEFAULT_TARGET, help="Report .docx to score.")
    parser.add_argument("--samples", default="samples", help="Directory of gold reports.")
    parser.add_argument("--gold", help="Date-matched gold .docx for source-coverage recall.")
    parser.add_argument("--collected", default="output/libya_media_headlines.csv",
                        help="Collected articles CSV; its outlets define the achievable coverage ceiling.")
    parser.add_argument("--sources", default="sources.json",
                        help="Fallback source config when the collected CSV is absent.")
    parser.add_argument("--profile", action="store_true", help="Print the gold profile and exit.")
    parser.add_argument("--llm-judge", action="store_true", help="Add qualitative LLM scores (needs API credit).")
    parser.add_argument("--json", dest="json_out", help="Write the scorecard JSON to this path.")
    args = parser.parse_args()

    profile = build_gold_profile(args.samples)
    if args.profile:
        print_profile(profile)
        return

    monitored = None
    if args.gold:
        # The achievable ceiling is the outlets actually present in the collected
        # data the report was built from; fall back to configured source names.
        if Path(args.collected).exists():
            with open(args.collected, encoding="utf-8-sig") as handle:
                monitored = {row["source_name"] for row in csv.DictReader(handle)}
        else:
            try:
                monitored = {s["name"] for s in load_sources(args.sources)}
            except Exception:
                monitored = None

    report = parse_pics_report(args.target)
    gold = parse_pics_report(args.gold) if args.gold else None
    card = score_report(report, profile, gold=gold, monitored=monitored)

    if args.llm_judge and gold is not None:
        try:
            card["llm_judge"] = llm_judge(report, gold)
        except JudgeUnavailable as exc:
            card["llm_judge"] = {"skipped": str(exc)}

    print_profile(profile)
    print()
    print_scorecard(card, profile)

    if card.get("llm_judge"):
        print("\n  llm judge:", json.dumps(card["llm_judge"], ensure_ascii=False))

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote scorecard to {args.json_out}")


if __name__ == "__main__":
    main()
