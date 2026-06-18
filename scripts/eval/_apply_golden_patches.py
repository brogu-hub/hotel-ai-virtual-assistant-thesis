"""
Apply A1+A2+A3 golden patches to align with Phase-J KB+DB ground truth
and remove impossible-self-conflict cases.

Idempotent: re-running is safe (each edit checks the current state).
Writes a backup before editing.
"""
from __future__ import annotations
import json, shutil, sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "dataset"

# Backup tag (no Date.now/now() restriction here)
BACKUP_TAG = "before_2026-06-16_phaseJ2_patch"

# Per-case patches: {(filename, case_id): patch_dict}
# Each patch_dict has keys to set/list-modify.
PATCHES = {
    # === A1. Phase-J stale leftovers ===
    ("golden_en.jsonl", "rooms_room_types_en_1"): {
        "expected_facts": ["28 sqm", "Standard Room"],
        "must_contain_any": ["28 sqm", "28 square meters", "28sqm"],
    },
    ("golden_en.jsonl", "rooms_deluxe_room_en_2"): {
        "expected_facts": ["2 adults"],
        "must_contain_any": ["2 adults", "2 guests", "maximum of 2"],
        # Removes the stale "1 child" requirement (DB max_occupancy = 2)
    },
    ("golden_en.jsonl", "spa_operating_hours_en_2"): {
        "expected_facts": ["Last Booking", "7:30 PM"],
        "must_contain_any": ["7:30 PM", "7:30 pm", "19:30"],
    },
    ("golden_th.jsonl", "spa_operating_hours_th_2"): {
        "expected_facts": ["จองครั้งสุดท้าย", "19:30", "7:30"],
        "must_contain_any": ["19:30", "7:30", "เจ็ดโมงครึ่ง"],
    },
    ("golden_cn.jsonl", "spa_operating_hours_cn_2"): {
        "expected_facts": ["最后预约", "7:30 PM", "19:30"],
        "must_contain_any": ["7:30 PM", "19:30", "7:30"],
    },
    ("golden_en.jsonl", "facilities_fitness_center_en_1"): {
        "expected_facts": ["6:00 AM", "10:00 PM", "Level 2"],
        "must_contain_any": ["6:00 AM", "10:00 PM", "6 AM", "10 PM", "Level 2"],
    },

    # === A2. Impossible self-conflict goldens ===
    ("golden_en.jsonl", "faq_check_in_check_out_en_2"): {
        # expected_facts requires "contact the front desk" so we must REMOVE that
        # phrase from must_not_contain
        "_remove_from_must_not_contain": ["contact the front desk"],
    },
    ("multi_intent_and_out_of_kb.jsonl", "oo_kb_mountain_view_th"): {
        # "วิวภูเขา" / "วิวทะเล" appear in both expected and forbidden — strip from forbidden
        "_remove_from_must_not_contain": ["วิวภูเขา", "วิวทะเล"],
    },

    # === A3. Over-restrictive must_not_contain (front-desk-as-action-channel) ===
    # All these cases: bot answers correctly + suggests front desk as action channel.
    ("golden_en.jsonl", "policies_lost_and_found_en_1"): {
        "_remove_from_must_not_contain": ["contact the front desk"],
    },
    ("golden_en.jsonl", "rooms_extra_beds_en_1"): {
        "_remove_from_must_not_contain": ["contact the front desk"],
    },
    ("golden_en.jsonl", "rooms_extra_beds_en_2"): {
        "_remove_from_must_not_contain": ["contact the front desk"],
    },
    ("golden_en.jsonl", "rooms_special_requests_en_1"): {
        "_remove_from_must_not_contain": ["contact the front desk"],
    },
    ("golden_en.jsonl", "facilities_wifi_en_1"): {
        "_remove_from_must_not_contain": ["contact the front desk"],
    },
    ("golden_en.jsonl", "facilities_wifi_en_3"): {
        "_remove_from_must_not_contain": ["contact the front desk"],
    },
}


def apply_patches():
    by_file = {}
    for (fname, cid), patch in PATCHES.items():
        by_file.setdefault(fname, []).append((cid, patch))

    summary = []
    for fname, items in by_file.items():
        fp = DATASET / fname
        if not fp.exists():
            print(f"  SKIP {fname} — file not found")
            continue
        backup = fp.with_suffix(fp.suffix + "." + BACKUP_TAG)
        if not backup.exists():
            shutil.copy(fp, backup)
            print(f"  backup written: {backup.name}")

        records = []
        for line in fp.open(encoding="utf-8"):
            if line.strip():
                records.append(json.loads(line))

        patched_ids = set()
        for rec in records:
            for cid, patch in items:
                if rec.get("id") != cid: continue
                patched_ids.add(cid)
                for k, v in patch.items():
                    if k == "_remove_from_must_not_contain":
                        cur = rec.get("must_not_contain") or []
                        new = [x for x in cur if x not in v]
                        rec["must_not_contain"] = new
                    else:
                        rec[k] = v
                summary.append(f"  patched [{fname}] {cid}")

        # Verify all expected cases were found
        for cid, _ in items:
            if cid not in patched_ids:
                summary.append(f"  WARN [{fname}] {cid} NOT FOUND")

        # Write back
        with fp.open("w", encoding="utf-8", newline="\n") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  wrote {len(records)} records to {fname}")

    print("\n=== Patch summary ===")
    for line in summary:
        print(line)


if __name__ == "__main__":
    apply_patches()
