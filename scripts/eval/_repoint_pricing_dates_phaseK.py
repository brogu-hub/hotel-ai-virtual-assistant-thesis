"""
Phase K: Repoint pricing_* golden dates so each tier window is correct
when measured from anchor = today (2026-06-17).

Tier windows used by _calculate_dynamic_multiplier:
  - last_minute:  today + 2 to today + 5 days (inside [1,7) days_ahead)
  - standard_rate: today + 10 to today + 25 days (inside [7,30) days_ahead)
  - early_bird:   today + 45 to today + 60 days (inside [30,inf) days_ahead)

Affects both the question text (EN / TH / CN) and expected_tool_args.
"""
from __future__ import annotations
import json, sys, shutil, re
from datetime import date, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "dataset"

ANCHOR = date(2026, 6, 17)

TIER_DATES = {
    "early_bird":   (ANCHOR + timedelta(days=45), ANCHOR + timedelta(days=47)),  # 2-night stay
    "standard_rate": (ANCHOR + timedelta(days=10), ANCHOR + timedelta(days=12)),
    "last_minute":  (ANCHOR + timedelta(days=2), ANCHOR + timedelta(days=4)),
}

EN_MONTHS = ["", "January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
TH_MONTHS = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม",
             "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม",
             "พฤศจิกายน", "ธันวาคม"]

def fmt_en(d: date) -> str:
    return f"{EN_MONTHS[d.month]} {d.day}, {d.year}"

def fmt_th(d: date) -> str:
    return f"{d.day} {TH_MONTHS[d.month]} {d.year}"

def fmt_cn(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"

def rewrite_question(q: str, lang: str, ci: date, co: date) -> str:
    """
    Replace the two date occurrences in the original question with the new
    tier-correct dates. We rely on the fact that the original phrasing always
    encodes both check-in and check-out dates in the same canonical form for
    each language.
    """
    if lang == "en":
        # Pattern: "from <Month> DD, YYYY to <Month> DD, YYYY"
        pat = r"from\s+\w+\s+\d{1,2},\s*\d{4}\s+to\s+\w+\s+\d{1,2},\s*\d{4}"
        repl = f"from {fmt_en(ci)} to {fmt_en(co)}"
        return re.sub(pat, repl, q)
    if lang == "th":
        # Pattern: "วันที่ DD <month> YYYY ถึง DD <month> YYYY"
        pat = r"วันที่\s+\d{1,2}\s+\S+\s+\d{4}\s+ถึง\s+\d{1,2}\s+\S+\s+\d{4}"
        # TH source uses Gregorian (e.g. "15 กรกฎาคม 2027"), keep that style.
        repl = f"วันที่ {fmt_th(ci)} ถึง {fmt_th(co)}"
        return re.sub(pat, repl, q)
    if lang == "cn":
        # Pattern: "<YYYY>年<M>月<D>日到<YYYY>年<M>月<D>日"
        pat = r"\d{4}年\d{1,2}月\d{1,2}日到\d{4}年\d{1,2}月\d{1,2}日"
        repl = f"{fmt_cn(ci)}到{fmt_cn(co)}"
        return re.sub(pat, repl, q)
    return q

def tier_of(cid: str) -> str | None:
    for t in TIER_DATES:
        if f"_{t}_" in cid:
            return t
    return None

def main():
    patched_log = []
    for fname, lang in (("golden_en.jsonl", "en"),
                        ("golden_th.jsonl", "th"),
                        ("golden_cn.jsonl", "cn")):
        fp = DATASET / fname
        if not fp.exists(): continue
        backup = fp.with_suffix(fp.suffix + ".before_phaseK_repoint")
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
            tier = tier_of(cid)
            if not tier:
                records.append(rec)
                continue
            ci, co = TIER_DATES[tier]
            old_q = rec.get("question", "")
            new_q = rewrite_question(old_q, lang, ci, co)
            old_args = rec.get("expected_tool_args", [])
            new_args = []
            for a in old_args:
                if isinstance(a, dict) and "check_in_date" in a and "check_out_date" in a:
                    na = dict(a)
                    na["check_in_date"] = ci.isoformat()
                    na["check_out_date"] = co.isoformat()
                    new_args.append(na)
                else:
                    new_args.append(a)
            if new_q != old_q or new_args != old_args:
                patched_log.append({
                    "file": fname, "case_id": cid, "tier": tier,
                    "old_question": old_q, "new_question": new_q,
                    "old_args": old_args, "new_args": new_args,
                })
                rec["question"] = new_q
                rec["expected_tool_args"] = new_args
                n_patched += 1
            records.append(rec)
        with fp.open("w", encoding="utf-8", newline="\n") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  {fname}: {n_patched} pricing cases repointed")
    out = DATASET.parent / "results" / "_phaseK_repoint_log.json"
    out.write_text(json.dumps(patched_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  log -> {out}")

if __name__ == "__main__":
    main()
