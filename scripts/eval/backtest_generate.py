"""Generate golden Q&A pairs from data/hotel/*.md using Gemini 2.5 Flash.

Strategy: split each .md into H2 sections; for each section, send the
exact text as authoritative source to Gemini Flash and request 3 EN +
3 TH + 3 CN Q&A pairs, returned as strict JSON matching our schema.

Pricing cases (rooms × dates × discount multipliers) are NOT generated
here — they're computed deterministically by backtest_generate_pricing.py
because the .md no longer holds prices and the Early Bird math is in
code, not in any KB document.

Usage:
    # Dry-run: print prompts for 2 sections, no API calls
    python scripts/eval/backtest_generate.py --dry-run --limit-sections 2

    # Generate from a single file
    python scripts/eval/backtest_generate.py --files dining_services.md

    # Full generation across all files
    python scripts/eval/backtest_generate.py

    # Per-section Q&A counts (default 3 per language = 9 per section)
    python scripts/eval/backtest_generate.py --per-language 4

Output:
    eval/dataset/golden_en.jsonl   (appended; deduped by id)
    eval/dataset/golden_th.jsonl
    eval/dataset/golden_cn.jsonl
    eval/dataset/_raw/<file>__<section>.json   (Gemini's raw response)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from eval.backtest_common import call_openrouter, extract_content, append_jsonl  # noqa: E402

KB_DIR = ROOT / "data" / "hotel"
OUT_DIR = ROOT / "eval" / "dataset"
RAW_DIR = OUT_DIR / "_raw"

GENERATOR_MODEL = os.getenv("GENERATOR_MODEL", "google/gemini-2.5-flash")

# Map .md filenames to canonical domain values for our schema
DOMAIN_MAP = {
    "room_types.md": "rooms",
    "room_guide.md": "rooms",
    "dining_services.md": "dining",
    "spa_wellness.md": "spa",
    "facilities_amenities.md": "facilities",
    "hotel_faq.md": "faq",
    "policies_rules.md": "policies",
    "transportation.md": "transportation",
    "local_attractions.md": "attractions",
    "emergency_contacts.md": "emergency",
}

GENERATOR_PROMPT = """You are generating evaluation test cases for a trilingual hotel chatbot
(English / Thai / Mandarin Chinese). The chatbot serves guests of "The Grand
Horizon Hotel" in Bangkok.

You will receive the EXACT TEXT of one section of the hotel's knowledge
base. Generate {per_lang} factual Q&A pairs PER LANGUAGE (EN, TH, CN)
based ONLY on this section. Total: {total} pairs.

Strict requirements:
 1. Every question must be answerable from this section alone — do NOT
    invent facts not in the source text.
 2. Questions must be NATURAL questions a real guest would ask. Vary
    phrasings: not all "What is X?" — include "Do you have ...", "Can I
    ...", "How can I ...", "Tell me about ...", etc.
 3. "expected_facts" = 2-4 short strings the answer MUST mention.
 4. "must_contain_any" = 1-2 of the most specific tokens that ANY correct
    response will include (e.g. a price, a time, a room number, a name).
 5. "must_not_contain" = phrases that indicate refusal or RAG-miss
    ("don't have access", "contact the front desk", "ไม่มีข้อมูล", "没有").
 6. Translations between EN/TH/CN versions of the SAME question should
    be true equivalents (so the chatbot's per-language consistency is
    testable), but you do NOT need to keep IDs paired across languages.
 7. Thai questions must use a polite particle (ครับ for male guest, ค่ะ
    for female; rotate so we test both).
 8. Chinese questions should use 您 for politeness.
 9. EACH pair must have a unique id: "<domain>_<subdomain>_<lang>_<n>".
10. "rubric_type" = pick one of: exact_match, exact_match_with_unit,
    semantic_match, set_match.

Return ONLY a JSON object with this EXACT shape (no other text):
{{
  "pairs": [
    {{
      "id": "...",
      "language": "en|th|cn",
      "question": "...",
      "expected_facts": ["..."],
      "must_contain_any": ["..."],
      "must_not_contain": ["..."],
      "rubric_type": "exact_match|exact_match_with_unit|semantic_match|set_match",
      "rubric_emphasis": ["factual_accuracy", "completeness"],
      "defect_categories_tested": ["rag_miss"]
    }}
  ]
}}

Domain: {domain}
Subdomain (section): {subdomain}
Source file: {source_file}

=== SECTION TEXT (authoritative) ===
{section_text}
=== END SECTION ===
"""


def split_sections(md_path: Path) -> List[Tuple[str, str]]:
    """Split a markdown file by H2 (`## `) headers.

    Returns list of (section_title, section_body_including_header).
    The overview/intro before the first H2 is returned as ("(intro)", text)
    only if it's substantial (>200 chars).
    """
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    current_title = "(intro)"
    current_body: List[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_body:
                joined = "\n".join(current_body).strip()
                if joined and (current_title != "(intro)" or len(joined) > 200):
                    sections.append((current_title, joined))
            current_title = line[3:].strip()
            current_body = [line]
        else:
            current_body.append(line)
    if current_body:
        joined = "\n".join(current_body).strip()
        if joined and (current_title != "(intro)" or len(joined) > 200):
            sections.append((current_title, joined))
    return [(t, b) for t, b in sections]


def normalise_subdomain(section_title: str) -> str:
    """Pull a slug-style subdomain from an H2 like '## WiFi / อินเทอร์เน็ตไร้สาย'."""
    en_part = section_title.split("/")[0].strip()
    slug = re.sub(r"[^a-z0-9]+", "_", en_part.lower()).strip("_")
    return slug or "general"


def build_prompt(
    domain: str,
    subdomain: str,
    source_file: str,
    section_text: str,
    per_lang: int,
) -> str:
    total = per_lang * 3
    return GENERATOR_PROMPT.format(
        per_lang=per_lang,
        total=total,
        domain=domain,
        subdomain=subdomain,
        source_file=source_file,
        section_text=section_text[:6000],  # cap to keep input cheap
    )


def call_generator(prompt: str, *, retries: int = 2) -> Optional[List[Dict[str, Any]]]:
    """Call Gemini Flash, return parsed pairs list or None on irrecoverable error."""
    for attempt in range(retries + 1):
        try:
            env = call_openrouter(
                model=GENERATOR_MODEL,
                messages=[
                    {"role": "system", "content": "You generate strict-JSON evaluation datasets."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # mild diversity but mostly source-grounded
                max_tokens=3500,
                response_format_json=True,
                timeout=120.0,
            )
            raw = extract_content(env)
            data = json.loads(raw)
            return data.get("pairs", [])
        except (json.JSONDecodeError, RuntimeError) as exc:
            print(f"  [attempt {attempt+1}] generator parse error: {exc}", file=sys.stderr)
            time.sleep(2.0 * (attempt + 1))
        except Exception as exc:
            print(f"  [attempt {attempt+1}] generator call failed: {exc}", file=sys.stderr)
            time.sleep(2.0 * (attempt + 1))
    return None


def validate_pair(p: Dict[str, Any], expected_domain: str, expected_subdomain: str) -> bool:
    """Pre-flight schema check; drop malformed records."""
    required = ("id", "language", "question", "expected_facts",
                "must_contain_any", "rubric_type")
    if not all(k in p for k in required):
        return False
    if p["language"] not in ("en", "th", "cn"):
        return False
    if not p["question"].strip() or len(p["question"]) < 5:
        return False
    if not isinstance(p["expected_facts"], list) or not p["expected_facts"]:
        return False
    if not isinstance(p["must_contain_any"], list) or not p["must_contain_any"]:
        return False
    if p["rubric_type"] not in ("exact_match", "exact_match_with_unit",
                                 "semantic_match", "set_match"):
        return False
    return True


def enrich_pair(
    p: Dict[str, Any],
    *,
    domain: str,
    subdomain: str,
    source_file: str,
    source_section: str,
) -> Dict[str, Any]:
    """Add the constant fields that are not asked of the model."""
    out = dict(p)
    out.setdefault("category", "main")
    out["domain"] = domain
    out["subdomain"] = subdomain
    out.setdefault("register", "formal")
    out.setdefault("channel", "web")
    out.setdefault("complexity", "factual_lookup")
    out.setdefault("input_completeness", "complete")
    out.setdefault("must_not_contain", [])
    out.setdefault("expected_tool_calls", [])
    out["source_files"] = [f"data/hotel/{source_file}"]
    out["source_section"] = source_section
    out.setdefault("rubric_emphasis", ["factual_accuracy"])
    out.setdefault("defect_categories_tested", ["rag_miss"])
    out["status"] = "clean"
    out.setdefault("tags", [subdomain])
    return out


def already_have_id(existing_ids: set, new_id: str) -> bool:
    return new_id in existing_ids


def load_existing_ids() -> Dict[str, set]:
    """Load existing ids per language so we can dedupe across re-runs."""
    out = {"en": set(), "th": set(), "cn": set()}
    for lang in out:
        path = OUT_DIR / f"golden_{lang}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "id" in rec:
                    out[lang].add(rec["id"])
            except json.JSONDecodeError:
                pass
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--files", nargs="*", help="specific md files (basenames). Default: all known.")
    p.add_argument("--per-language", type=int, default=3,
                   help="Q&A pairs per language per section (default: 3)")
    p.add_argument("--limit-sections", type=int, default=0,
                   help="cap total sections processed (debugging)")
    p.add_argument("--dry-run", action="store_true",
                   help="print prompts but make NO API calls")
    p.add_argument("--max-cost-usd", type=float, default=2.50,
                   help="abort if estimated cost exceeds this (default: $2.50)")
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    files = args.files or list(DOMAIN_MAP.keys())
    files = [f for f in files if (KB_DIR / f).exists()]
    if not files:
        print("No knowledge files found.", file=sys.stderr)
        return 2

    existing_ids = load_existing_ids()

    # Build the section work-list
    work: List[Tuple[str, str, str]] = []  # (md_filename, section_title, section_text)
    for fname in files:
        for title, body in split_sections(KB_DIR / fname):
            work.append((fname, title, body))

    if args.limit_sections > 0:
        work = work[: args.limit_sections]

    est_tokens_in = sum(len(b) for _, _, b in work) / 4 + (1500 * len(work))
    est_tokens_out = 3000 * len(work)
    est_cost = (est_tokens_in / 1_000_000) * 0.075 + (est_tokens_out / 1_000_000) * 0.30
    print(f"\n=== Plan ===")
    print(f"  files          : {len(files)} ({', '.join(files)})")
    print(f"  sections       : {len(work)}")
    print(f"  per-language Q : {args.per_language}")
    print(f"  est tokens in  : {int(est_tokens_in):>9,}")
    print(f"  est tokens out : {int(est_tokens_out):>9,}")
    print(f"  est cost       : ${est_cost:.3f} (cap ${args.max_cost_usd:.2f})")
    print()
    if est_cost > args.max_cost_usd and not args.dry_run:
        print(f"ABORT: estimated cost ${est_cost:.3f} > cap ${args.max_cost_usd:.2f}")
        print("       raise --max-cost-usd or reduce --per-language / --limit-sections")
        return 2

    stats = {"sections": 0, "pairs": 0, "dropped_schema": 0, "dropped_dup": 0, "lang": {"en": 0, "th": 0, "cn": 0}}

    for fname, title, body in work:
        domain = DOMAIN_MAP.get(fname, "general")
        subdomain = normalise_subdomain(title)
        print(f"  -> {fname} :: {title}  (domain={domain}, sub={subdomain})")
        prompt = build_prompt(
            domain=domain,
            subdomain=subdomain,
            source_file=fname,
            section_text=body,
            per_lang=args.per_language,
        )
        if args.dry_run:
            preview = prompt[:600].replace("\n", " ")
            print(f"     [DRY-RUN] prompt preview: {preview}...")
            stats["sections"] += 1
            continue

        pairs = call_generator(prompt)
        if pairs is None:
            print(f"     [SKIP] {fname}::{title} — generator failed")
            continue

        # Save raw response for review
        raw_path = RAW_DIR / f"{fname.replace('.md', '')}__{subdomain}.json"
        raw_path.write_text(json.dumps({"section": title, "pairs": pairs}, ensure_ascii=False, indent=2), encoding="utf-8")

        valid = 0
        for p in pairs:
            if not validate_pair(p, domain, subdomain):
                stats["dropped_schema"] += 1
                continue
            lang = p["language"]
            if p["id"] in existing_ids[lang]:
                stats["dropped_dup"] += 1
                continue
            existing_ids[lang].add(p["id"])
            enriched = enrich_pair(
                p,
                domain=domain,
                subdomain=subdomain,
                source_file=fname,
                source_section=title,
            )
            out_path = OUT_DIR / f"golden_{lang}.jsonl"
            append_jsonl(out_path, enriched)
            stats["lang"][lang] += 1
            valid += 1
            stats["pairs"] += 1
        print(f"     {valid}/{len(pairs)} pairs accepted")
        stats["sections"] += 1

    print(f"\n=== done ===")
    print(f"  sections processed : {stats['sections']}")
    print(f"  pairs accepted     : {stats['pairs']}")
    print(f"  per language       : EN={stats['lang']['en']}, TH={stats['lang']['th']}, CN={stats['lang']['cn']}")
    print(f"  dropped (schema)   : {stats['dropped_schema']}")
    print(f"  dropped (dup id)   : {stats['dropped_dup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
