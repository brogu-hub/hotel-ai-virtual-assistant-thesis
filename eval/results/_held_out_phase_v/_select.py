"""Held-out subset selection for Phase V evaluation.

Strategy:
- Run #1 baseline (2026-06-17T16:40:15) = first snapshot before any replay.
- Current raw.jsonl = state after all Phase J->R replays.
- Cases that are 'correct' in BOTH have never been replayed AND never had their
  prompts/data patched in a way that flipped a non-correct verdict.
- Exclude canaries (separate sentinel set).
- Stratify by (language, domain) matching the 354-case canonical distribution.
- Target 60 cases (~17% of 354). Lang split: 31 EN, 29 TH.
"""
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("z:/Dev_Drive/hote-ai-virtual-assistant-thesis")
RUN1 = ROOT / "eval/results/clean_v3_final/20260616T203134/_backups/raw.jsonl.before_replay_20260617T164015"
CURR = ROOT / "eval/results/clean_v3_final/20260616T203134/raw.jsonl"
CANARIES = ROOT / "eval/dataset/canaries.jsonl"
OUT = ROOT / "eval/results/_held_out_phase_v/held_out_ids.json"

random.seed(20260618)  # reproducible

def load_jsonl(p):
    rows = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

run1 = load_jsonl(RUN1)
curr = load_jsonl(CURR)
canaries = load_jsonl(CANARIES)

canary_ids = {c["id"] for c in canaries}

run1_by_id = {r["id"]: r for r in run1}
curr_by_id = {r["id"]: r for r in curr}

# Sanity: 354 cases each.
print(f"Run#1 baseline: {len(run1)} rows; current: {len(curr)} rows; canaries: {len(canary_ids)}")

# Pool: correct in both, not a canary id.
pool = []
why_excluded_summary = Counter()
for cid, r1 in run1_by_id.items():
    if cid in canary_ids:
        why_excluded_summary["canary_id"] += 1
        continue
    if cid not in curr_by_id:
        why_excluded_summary["missing_in_current"] += 1
        continue
    if r1.get("verdict") != "correct":
        why_excluded_summary["run1_not_correct"] += 1
        continue
    if curr_by_id[cid].get("verdict") != "correct":
        why_excluded_summary["current_not_correct_after_replay"] += 1
        continue
    pool.append(r1)

print(f"Pool size (never replayed, never patched, correct in both): {len(pool)}")
print(f"Exclusions: {dict(why_excluded_summary)}")

# Canonical stratification: count by (language, domain) in the full 354 set (current).
canonical_lang = Counter(r.get("language") for r in curr)
canonical_dom = Counter(r.get("domain") for r in curr)
canonical_strata = Counter((r.get("language"), r.get("domain")) for r in curr)

print("\nCanonical lang counts (354):", dict(canonical_lang))
print("Canonical domain counts (354):", dict(canonical_dom))

# Pool stratification
pool_strata = Counter((r.get("language"), r.get("domain")) for r in pool)
print("\nPool lang counts:", dict(Counter(r.get("language") for r in pool)))
print("Pool domain counts:", dict(Counter(r.get("domain") for r in pool)))

# Target: 60 cases. Lang split per canonical proportions.
TARGET = 60
n_total = sum(canonical_lang.values())
lang_targets = {lang: round(TARGET * canonical_lang[lang] / n_total) for lang in canonical_lang}
# Fix rounding to exactly TARGET
diff = TARGET - sum(lang_targets.values())
if diff != 0:
    # adjust largest bucket
    biggest = max(lang_targets, key=lambda k: canonical_lang[k])
    lang_targets[biggest] += diff
print(f"\nLang targets (sum to {TARGET}):", lang_targets)

# Within each lang, distribute across domains proportional to canonical (language, domain) share.
lang_domain_targets = {}
for lang, n_lang in lang_targets.items():
    # canonical domain shares within this language
    in_lang = {dom: canonical_strata[(lang, dom)] for (l, dom) in canonical_strata if l == lang}
    total_in_lang = sum(in_lang.values())
    # proportional allocation
    raw = {dom: n_lang * cnt / total_in_lang for dom, cnt in in_lang.items()}
    # integer allocation: floor then top up by largest fractional remainders
    floors = {dom: int(v) for dom, v in raw.items()}
    remainder = n_lang - sum(floors.values())
    frac = sorted(raw.items(), key=lambda kv: kv[1] - floors[kv[0]], reverse=True)
    for i in range(remainder):
        floors[frac[i][0]] += 1
    lang_domain_targets[lang] = floors

print("\nLang+domain targets:")
for lang, doms in lang_domain_targets.items():
    print(f"  {lang}: {doms}  (sum={sum(doms.values())})")

# Now pick from pool. For each (lang, dom), pick min(target, available).
pool_by_strata = defaultdict(list)
for r in pool:
    pool_by_strata[(r.get("language"), r.get("domain"))].append(r)

# Sort each bucket deterministically by id, then sample.
for k in pool_by_strata:
    pool_by_strata[k].sort(key=lambda r: r["id"])

selected = []
shortfall = {}
for lang, doms in lang_domain_targets.items():
    for dom, tgt in doms.items():
        bucket = pool_by_strata.get((lang, dom), [])
        if len(bucket) < tgt:
            shortfall[(lang, dom)] = tgt - len(bucket)
            picks = bucket[:]
        else:
            # deterministic sample
            picks = random.sample(bucket, tgt)
        selected.extend(picks)

# If shortfall, fill from any remaining cases in same language, proportional to remaining domain availability.
if shortfall:
    print(f"\nShortfalls (lang, dom -> missing): {shortfall}")
    selected_ids = {r["id"] for r in selected}
    for (lang, dom), miss in shortfall.items():
        # find other pool items in same lang not yet selected
        candidates = [r for r in pool if r.get("language") == lang and r["id"] not in selected_ids]
        candidates.sort(key=lambda r: r["id"])
        # pick from largest remaining bucket in same lang
        remaining_by_dom = defaultdict(list)
        for r in candidates:
            remaining_by_dom[r.get("domain")].append(r)
        # prefer domains with the most slack
        ordered_doms = sorted(remaining_by_dom.keys(), key=lambda d: len(remaining_by_dom[d]), reverse=True)
        added = 0
        for d in ordered_doms:
            if added >= miss:
                break
            need = miss - added
            take = remaining_by_dom[d][:need]
            for t in take:
                if t["id"] not in selected_ids:
                    selected.append(t)
                    selected_ids.add(t["id"])
                    added += 1

held_out_ids = sorted({r["id"] for r in selected})
print(f"\nFinal held-out size: {len(held_out_ids)}")

# Recompute final counts
selected_rows = [curr_by_id[i] for i in held_out_ids]
final_lang = Counter(r.get("language") for r in selected_rows)
final_dom = Counter(r.get("domain") for r in selected_rows)
final_strata = Counter((r.get("language"), r.get("domain")) for r in selected_rows)

print("Final lang counts:", dict(final_lang))
print("Final domain counts:", dict(final_dom))
print("Final strata:")
for (l, d), n in sorted(final_strata.items()):
    print(f"  {l} / {d}: {n}")

out = {
    "held_out_ids": held_out_ids,
    "counts_by_lang": dict(final_lang),
    "counts_by_domain": dict(final_dom),
    "counts_by_strata": {f"{l}__{d}": n for (l, d), n in sorted(final_strata.items())},
    "never_replayed_pool_size": len(pool),
    "target_size": TARGET,
    "lang_targets": lang_targets,
    "lang_domain_targets": {lang: dict(doms) for lang, doms in lang_domain_targets.items()},
    "why_excluded": [
        f"canary_id={why_excluded_summary['canary_id']} (separate sentinel set, monitored every run)",
        f"run1_not_correct={why_excluded_summary['run1_not_correct']} (was non-correct at Run #1 baseline; therefore eligible for replay)",
        f"current_not_correct_after_replay={why_excluded_summary['current_not_correct_after_replay']} (was correct at baseline but flipped after a Phase J->R patch — touched by some intervention)",
        f"missing_in_current={why_excluded_summary['missing_in_current']} (case absent from current raw.jsonl)",
    ],
    "shortfalls": {f"{l}__{d}": n for (l, d), n in shortfall.items()} if shortfall else {},
    "selection_method": "Intersection of correct verdicts in Run #1 baseline (raw.jsonl.before_replay_20260617T164015) AND current raw.jsonl. Replay tool (scripts/eval/_replay_63_fails.py) only re-runs verdict != correct, so this intersection is provably untouched by Phase J->R replays. Stratified by (language, domain) matching the 354-case canonical proportions, deterministic seed=20260618.",
    "sources": {
        "run1_baseline": str(RUN1.relative_to(ROOT)).replace("\\", "/"),
        "current": str(CURR.relative_to(ROOT)).replace("\\", "/"),
        "canaries_excluded": str(CANARIES.relative_to(ROOT)).replace("\\", "/"),
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f"\nWrote: {OUT}")
