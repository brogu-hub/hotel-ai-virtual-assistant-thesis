"""Generate the dynamic-pricing eval cases programmatically.

These cases test the `calculate_dynamic_price` tool path. The expected
values are computed from the same arithmetic the chatbot uses
(`_calculate_dynamic_multiplier` in src/agent/hotel_tools.py:965), so the
ground truth comes from the same place as the system under test —
which is exactly what we want for the `tool_invocation_match` and
`exact_match_with_unit` rubrics.

Output: appended to eval/dataset/golden_{en,th,cn}.jsonl.

Usage:
    python scripts/eval/backtest_pricing_templates.py
    python scripts/eval/backtest_pricing_templates.py --today 2026-06-09  # override
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from eval.backtest_common import append_jsonl  # noqa: E402

OUT_DIR = ROOT / "eval" / "dataset"

# Source of truth = DB prices, NOT the .md files (which drift).
DB_PRICES = {
    "Standard": 2500.0,
    "Deluxe": 4500.0,
    "Suite": 8500.0,
    "Penthouse": 25000.0,
}

# Same brackets as _calculate_dynamic_multiplier(); (label, mult, days_offset)
PRICE_BRACKETS = [
    ("Early Bird", 0.85, 36),    # >= 30 days
    ("Standard Rate", 1.00, 9),  # 7-13 days
    ("Last-Minute", 1.20, 3),    # 1-6 days
]

TH_MONTHS = {
    1: "มกราคม", 2: "กุมภาพันธ์", 3: "มีนาคม", 4: "เมษายน",
    5: "พฤษภาคม", 6: "มิถุนายน", 7: "กรกฎาคม", 8: "สิงหาคม",
    9: "กันยายน", 10: "ตุลาคม", 11: "พฤศจิกายน", 12: "ธันวาคม",
}

TH_ROOMS = {
    "Standard": "Standard",
    "Deluxe": "Deluxe",
    "Suite": "Suite",
    "Penthouse": "Penthouse",
}
CN_ROOMS = {
    "Standard": "标准间",
    "Deluxe": "豪华间",
    "Suite": "套房",
    "Penthouse": "顶层套房",
}


def fmt_thb(n: float) -> str:
    return f"{int(round(n)):,}"


def th_date(d: date) -> str:
    return f"{d.day} {TH_MONTHS[d.month]} {d.year}"


def cn_date(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


def build_case(
    room: str,
    bracket_label: str,
    multiplier: float,
    check_in: date,
    check_out: date,
    nights: int,
    lang: str,
) -> Dict[str, Any]:
    base = DB_PRICES[room]
    per_night = base * multiplier
    total = per_night * nights

    base_s = fmt_thb(base)
    per_night_s = fmt_thb(per_night)
    total_s = fmt_thb(total)

    # Construct question per language
    if lang == "en":
        question = (
            f"How much is a {room} Room from {check_in.strftime('%B %d, %Y')} "
            f"to {check_out.strftime('%B %d, %Y')}?"
        )
    elif lang == "th":
        room_th = TH_ROOMS[room]
        question = (
            f"ห้อง {room_th} เช็คอินวันที่ {th_date(check_in)} ถึง "
            f"{th_date(check_out)} ราคาเท่าไหร่ครับ"
        )
    else:  # cn
        room_cn = CN_ROOMS[room]
        question = (
            f"{room_cn}从{cn_date(check_in)}到{cn_date(check_out)}的价格是多少？"
        )

    expected_facts = [per_night_s, total_s, bracket_label]
    must_contain_any = [per_night_s, total_s]
    must_not_contain = [
        # Drift artefacts from the OLD .md file
        "3,500 THB",  # Old Deluxe
        "5,500 THB",  # Old Suite
        "15,000 THB",  # Old Penthouse
    ] if room in ("Deluxe", "Suite", "Penthouse") else []
    # And ensure the base-price-only answer is rejected when a discount applies
    if multiplier != 1.0:
        must_not_contain.append(base_s + " THB/night")

    bracket_slug = bracket_label.lower().replace(" ", "_").replace("-", "_")
    case = {
        "id": f"pricing_{room.lower()}_{bracket_slug}_{lang}",
        "category": "main",
        "domain": "rooms",
        "subdomain": f"{room.lower()}_pricing",
        "language": lang,
        "register": "formal",
        "channel": "web",
        "complexity": "computation",
        "input_completeness": "complete",
        "question": question,
        "expected_facts": expected_facts,
        "must_contain_any": must_contain_any,
        "must_not_contain": must_not_contain,
        "expected_tool_calls": ["calculate_dynamic_price"],
        "expected_tool_args": [{
            "room_type": room,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        }],
        "source_files": ["db:room_types"],
        "source_section": f"DB base_price={fmt_thb(base)}, multiplier {multiplier:.2f}",
        "rubric_type": "exact_match_with_unit",
        "rubric_emphasis": ["factual_accuracy", "tool_invocation"],
        "defect_categories_tested": ["rag_drift", "tool_not_called"],
        "status": "clean",
        "tags": ["pricing", "early_bird" if multiplier == 0.85 else
                 "last_minute" if multiplier == 1.20 else "standard_rate"],
    }
    return case


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--today", default=None, help="override today (YYYY-MM-DD)")
    p.add_argument("--nights", type=int, default=2, help="stay length (default: 2)")
    args = p.parse_args()

    if args.today:
        today = date.fromisoformat(args.today)
    else:
        # Hardcoded to 2026-06-09 (the date the eval framework was built);
        # we don't use date.today() so the dataset is deterministic across CI runs.
        today = date(2026, 6, 9)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {"en": 0, "th": 0, "cn": 0}

    for room in DB_PRICES.keys():
        for bracket_label, multiplier, days_offset in PRICE_BRACKETS:
            check_in = today + timedelta(days=days_offset)
            check_out = check_in + timedelta(days=args.nights)
            for lang in ("en", "th", "cn"):
                case = build_case(
                    room, bracket_label, multiplier,
                    check_in, check_out, args.nights, lang,
                )
                out = OUT_DIR / f"golden_{lang}.jsonl"
                append_jsonl(out, case)
                counts[lang] += 1

    total = sum(counts.values())
    print(f"\n=== pricing templates appended ===")
    print(f"  today (reference): {today}")
    print(f"  nights stay      : {args.nights}")
    print(f"  rooms × brackets × langs = {len(DB_PRICES)} × {len(PRICE_BRACKETS)} × 3 = {total}")
    print(f"  per language     : EN={counts['en']}, TH={counts['th']}, CN={counts['cn']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
