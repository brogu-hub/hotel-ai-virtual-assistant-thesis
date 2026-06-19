"""Build the Phase V variance sample (60 cases) from the canonical 354."""
import json
import random
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path(r"z:/Dev_Drive/hote-ai-virtual-assistant-thesis")
DATA = ROOT / "eval/dataset"
RAW = ROOT / "eval/results/clean_v3_final/20260616T203134/raw.jsonl"
OUT = ROOT / "eval/results/_variance_phase_v/variance_ids.json"

# ----- Load canonical 354 -----
canonical_ids = []
canonical_rows = {}
with RAW.open("r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        r = json.loads(line)
        canonical_ids.append(r["id"])
        canonical_rows[r["id"]] = r

# ----- Load per-case metadata from dataset files -----
meta = {}
for fn in [
    "golden_en.jsonl", "golden_th.jsonl", "golden_cn.jsonl",
    "adversarial.jsonl", "hard_negatives.jsonl",
    "multi_intent_and_out_of_kb.jsonl", "quantity_inventory.jsonl",
    "multi_turn.jsonl", "wifi_checkedin.jsonl", "canaries.jsonl",
    "rubric_calibration.jsonl",
]:
    p = DATA / fn
    if not p.exists():
        continue
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            meta[r.get("id")] = r


def lang(i):
    return canonical_rows[i].get("language")


def rtype(i):
    return meta.get(i, {}).get("rubric_type", "unknown")


def tool_invoking(i):
    return bool(meta.get(i, {}).get("expected_tool_calls"))


def defects(i):
    s = set(meta.get(i, {}).get("defect_categories_tested", []))
    s.update(canonical_rows[i].get("defects", []))
    return s


# ----- Residuals from canonical run -----
residuals = [i for i in canonical_ids if canonical_rows[i].get("verdict") != "correct"]
print("Residuals (all", len(residuals), "included):", residuals)

selected = set(residuals)

TARGET_LANG = {"en": 31, "th": 29}
TARGET_RUBRIC = {
    "exact_match_with_unit": 19,
    "exact_match":           11,
    "semantic_match":        10,
    "set_match":             10,
    "refusal_correct":        5,
    "tool_invocation":        5,
}

ACTIVE_DEFECTS = [
    "hallucination", "incomplete", "over_refuse", "rag_drift",
    "rag_miss", "spec_wrong", "tool_not_called", "wrong_routing",
    "empty_response",
]

rng = random.Random(42)

# Account for residuals in quotas
rubric_remaining = dict(TARGET_RUBRIC)
lang_remaining = dict(TARGET_LANG)

for rid in residuals:
    rt = rtype(rid)
    lg = lang(rid)
    if tool_invoking(rid):
        bucket = "tool_invocation"
    elif rt in rubric_remaining:
        bucket = rt
    else:
        bucket = "semantic_match"
    if rubric_remaining.get(bucket, 0) > 0:
        rubric_remaining[bucket] -= 1
    if lang_remaining.get(lg, 0) > 0:
        lang_remaining[lg] -= 1


def pool_for(bucket):
    if bucket == "tool_invocation":
        return [i for i in canonical_ids if tool_invoking(i)]
    if bucket == "exact_match_with_unit":
        return [i for i in canonical_ids if rtype(i) == "exact_match_with_unit" and not tool_invoking(i)]
    if bucket == "exact_match":
        return [i for i in canonical_ids if rtype(i) == "exact_match" and not tool_invoking(i)]
    if bucket == "semantic_match":
        return [i for i in canonical_ids if rtype(i) == "semantic_match" and not tool_invoking(i)]
    if bucket == "set_match":
        return [i for i in canonical_ids if rtype(i) == "set_match" and not tool_invoking(i)]
    if bucket == "refusal_correct":
        return [i for i in canonical_ids if rtype(i) == "refusal_correct" and not tool_invoking(i)]
    return []


for bucket, n in rubric_remaining.items():
    if n <= 0:
        continue
    pool = [i for i in pool_for(bucket) if i not in selected]
    pool_en = [i for i in pool if lang(i) == "en"]
    pool_th = [i for i in pool if lang(i) == "th"]
    total = lang_remaining["en"] + lang_remaining["th"]
    if total > 0:
        n_en = round(n * lang_remaining["en"] / total)
        n_th = n - n_en
    else:
        n_en, n_th = n // 2, n - n // 2
    n_en = min(n_en, len(pool_en))
    n_th = min(n_th, len(pool_th))
    deficit = n - (n_en + n_th)
    if deficit > 0:
        if len(pool_en) - n_en >= deficit:
            n_en += deficit
        elif len(pool_th) - n_th >= deficit:
            n_th += deficit
    rng.shuffle(pool_en)
    rng.shuffle(pool_th)
    chosen = pool_en[:n_en] + pool_th[:n_th]
    for i in chosen:
        selected.add(i)
        if lang_remaining.get(lang(i), 0) > 0:
            lang_remaining[lang(i)] -= 1


# Ensure every active defect class is represented
selected_defect_classes = set()
for i in selected:
    selected_defect_classes.update(defects(i))

for ad in ACTIVE_DEFECTS:
    if ad in selected_defect_classes:
        continue
    cand = [i for i in canonical_ids if i not in selected and ad in defects(i)]
    if not cand:
        continue
    cand_en = [i for i in cand if lang(i) == "en"]
    cand_th = [i for i in cand if lang(i) == "th"]
    pick = None
    if lang_remaining.get("th", 0) > 0 and cand_th:
        pick = rng.choice(cand_th)
    elif lang_remaining.get("en", 0) > 0 and cand_en:
        pick = rng.choice(cand_en)
    elif cand_th:
        pick = rng.choice(cand_th)
    elif cand_en:
        pick = rng.choice(cand_en)
    if pick:
        selected.add(pick)
        selected_defect_classes.update(defects(pick))


def lang_counts(ids):
    return Counter(lang(i) for i in ids)


# Trim to 60 if over
while len(selected) > 60:
    c = lang_counts(selected)
    over_lang = "en" if (c["en"] - TARGET_LANG["en"]) >= (c["th"] - TARGET_LANG["th"]) else "th"
    droppable = [i for i in selected if i not in residuals and lang(i) == over_lang]
    if not droppable:
        droppable = [i for i in selected if i not in residuals]
    rng.shuffle(droppable)
    selected.remove(droppable[0])

# Fill to 60 if under
while len(selected) < 60:
    c = lang_counts(selected)
    under_lang = "en" if c["en"] < TARGET_LANG["en"] else "th"
    pool = [i for i in canonical_ids if i not in selected and lang(i) == under_lang]
    if not pool:
        pool = [i for i in canonical_ids if i not in selected]
    rng.shuffle(pool)
    selected.add(pool[0])


# Force exact lang split
def shift_lang(target_en, target_th):
    c = lang_counts(selected)
    while c["en"] > target_en:
        en_drop = [i for i in selected if lang(i) == "en" and i not in residuals]
        th_add = [i for i in canonical_ids if i not in selected and lang(i) == "th"]
        if not en_drop or not th_add:
            break
        rng.shuffle(en_drop)
        rng.shuffle(th_add)
        selected.remove(en_drop[0])
        selected.add(th_add[0])
        c = lang_counts(selected)
    while c["th"] > target_th:
        th_drop = [i for i in selected if lang(i) == "th" and i not in residuals]
        en_add = [i for i in canonical_ids if i not in selected and lang(i) == "en"]
        if not th_drop or not en_add:
            break
        rng.shuffle(th_drop)
        rng.shuffle(en_add)
        selected.remove(th_drop[0])
        selected.add(en_add[0])
        c = lang_counts(selected)


shift_lang(31, 29)

final = sorted(selected)
print("\nFINAL N:", len(final))
print("FINAL lang counts:", lang_counts(final))
rubric_final = Counter(rtype(i) for i in final)
print("FINAL rubric counts:", rubric_final)
tool_invocation_count = sum(1 for i in final if tool_invoking(i))
print("FINAL tool_invocation cases (cross-cut):", tool_invocation_count)

final_defects = set()
for i in final:
    final_defects.update(defects(i))
print("Active defect coverage:")
for ad in ACTIVE_DEFECTS:
    print(f"  {ad}: {'YES' if ad in final_defects else 'NO'}")

print("\nResiduals included:", [r for r in residuals if r in selected])

rubric_counts_obj = {k: int(v) for k, v in rubric_final.items()}
counts_by_lang = {k: int(v) for k, v in lang_counts(final).items()}

rationale = (
    "Stratified by language (31 EN / 29 TH) to match the 354-case canonical "
    "split (EN 52.5% / TH 47.5%; CN deferred per Phase J.2). Stratified by "
    "rubric_type: 30 exact-style (19 exact_match_with_unit + 11 exact_match, "
    "proportional to canonical 100:57), 10 semantic_match, 10 set_match, "
    "5 refusal_correct, 5 tool_invocation (cases with non-empty "
    "expected_tool_calls, drawn cross-rubric). All 6 currently-failing "
    "residuals from clean_v3_final/20260616T203134 are included by "
    "construction (within the 5-10 target band) so the sample disproportionately "
    "covers the pass-fail boundary where run-to-run flips are most likely. "
    "Each still-active defect class (hallucination, incomplete, over_refuse, "
    "rag_drift, rag_miss, spec_wrong, tool_not_called, wrong_routing, "
    "empty_response) is covered at least once via dataset defect_categories_tested "
    "tags or judged defects from the canonical run. Seed=42; the same 60 ids "
    "are replayed 3x back-to-back with fresh session_ids to isolate sigma to "
    "chatbot stochasticity (temperature 0.3, top_p 0.8); judge held at "
    "temperature 0.0."
)

out = {
    "variance_ids": final,
    "counts_by_lang": counts_by_lang,
    "counts_by_rubric_type": rubric_counts_obj,
    "residuals_included": sorted([r for r in residuals if r in selected]),
    "rationale": rationale,
    "metadata": {
        "canonical_source": "eval/results/clean_v3_final/20260616T203134/raw.jsonl",
        "canonical_n": 354,
        "canonical_lang_split": {"en": 186, "th": 168},
        "canonical_rubric_distribution": {
            "exact_match_with_unit": 100,
            "exact_match": 57,
            "set_match": 90,
            "semantic_match": 81,
            "refusal_correct": 11,
            "language_match": 1,
            "unknown": 14,
        },
        "target_rubric_counts": {
            "exact_match_with_unit": 19,
            "exact_match": 11,
            "semantic_match": 10,
            "set_match": 10,
            "refusal_correct": 5,
            "tool_invocation_match": 5,
        },
        "tool_invocation_cases_in_sample": int(tool_invocation_count),
        "active_defect_classes_covered": sorted(list(final_defects & set(ACTIVE_DEFECTS))),
        "seed": 42,
        "n_runs_planned": 3,
        "session_id_policy": "fresh per case per run",
    },
}
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nWROTE {OUT}")
