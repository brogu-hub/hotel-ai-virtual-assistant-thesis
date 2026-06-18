"""
Bump 2026 → 2027 inside pricing_* golden cases so test dates stay >30
days out from today (2026-06-16). This keeps Early Bird / Standard /
Last-Minute multiplier classifications stable across the eval window.
"""
from __future__ import annotations
import json, sys, shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "dataset"

def main():
    for fname in ("golden_en.jsonl", "golden_th.jsonl", "golden_cn.jsonl"):
        fp = DATASET / fname
        if not fp.exists(): continue
        backup = fp.with_suffix(fp.suffix + ".before_date_rot_fix")
        if not backup.exists():
            shutil.copy(fp, backup)
        records = []
        n_patched = 0
        for line in fp.open(encoding="utf-8"):
            if not line.strip(): continue
            rec = json.loads(line)
            cid = rec.get("id", "")
            if not cid.startswith("pricing_"):
                records.append(rec)
                continue
            # Bump 2026 -> 2027 in the question
            q = rec.get("question") or ""
            new_q = q.replace("2026", "2027")
            if new_q != q:
                rec["question"] = new_q
                n_patched += 1
            records.append(rec)
        with fp.open("w", encoding="utf-8", newline="\n") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  {fname}: {n_patched} pricing cases patched (2026 -> 2027)")


if __name__ == "__main__":
    main()
