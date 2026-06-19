"""
Phase K non-pricing patches from the multi-intent investigation.

Patches applied:
  1. mi_wifi_and_breakfast_en — expected_facts swap 'per-stay' -> 'welcome card'
     and accept 'ToHotelKnowledge' as an alias for 'search_hotel_knowledge'.
  2. mi_th_wifi_and_breakfast — accept 'ToHotelKnowledge' alias.
  3. mi_th_named_guest_pricing — date-rot fix (2026-06-15 was in the past; bump
     to 2026-06-22 inside Last-Minute window, update expected_tool_args).
"""
from __future__ import annotations
import json, sys, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "dataset"
FP = DATASET / "multi_intent_and_out_of_kb.jsonl"

PATCHES = {
    "mi_wifi_and_breakfast_en": {
        "expected_facts": (["6:30 AM", "10:30 AM", "per-stay"],
                           ["6:30 AM", "10:30 AM", "welcome card"]),
        "expected_tool_calls": (["search_hotel_knowledge"],
                                ["search_hotel_knowledge", "ToHotelKnowledge"]),
    },
    "mi_th_wifi_and_breakfast": {
        "expected_tool_calls": (["search_hotel_knowledge"],
                                ["search_hotel_knowledge", "ToHotelKnowledge"]),
    },
    "mi_th_named_guest_pricing": {
        "question": (
            "ดิฉันชื่อสิริค่ะ จะมาพักวันที่ 15 มิถุนายน 3 คืน ขอทราบราคาห้องดีลักซ์ค่ะ",
            "ดิฉันชื่อสิริค่ะ จะมาพักวันที่ 22 มิถุนายน 3 คืน ขอทราบราคาห้องดีลักซ์ค่ะ",
        ),
        "expected_tool_args": (
            [{"room_type": "Deluxe", "check_in_date": "2026-06-15",
              "check_out_date": "2026-06-18"}],
            [{"room_type": "Deluxe", "check_in_date": "2026-06-22",
              "check_out_date": "2026-06-25"}],
        ),
    },
}

def main():
    backup = FP.with_suffix(FP.suffix + ".before_phaseK_nonpricing")
    if not backup.exists():
        shutil.copy(FP, backup)
    records = []
    log = []
    for line in FP.open(encoding="utf-8"):
        if not line.strip(): continue
        rec = json.loads(line)
        cid = rec.get("id", "")
        if cid in PATCHES:
            patches = PATCHES[cid]
            for field, (old, new) in patches.items():
                cur = rec.get(field)
                if cur == old:
                    rec[field] = new
                    log.append({"file": FP.name, "case_id": cid,
                                "field": field, "old": old, "new": new,
                                "status": "applied"})
                else:
                    log.append({"file": FP.name, "case_id": cid,
                                "field": field, "old": old, "new": new,
                                "status": "skipped_mismatch",
                                "current": cur})
        records.append(rec)
    with FP.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out = ROOT / "eval" / "results" / "_phaseK_nonpricing_log.json"
    out.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {len([e for e in log if e['status']=='applied'])} field patches applied")
    print(f"  {len([e for e in log if e['status']!='applied'])} field patches skipped (mismatch)")
    print(f"  log -> {out}")

if __name__ == "__main__":
    main()
