# Recent Thesis Edits — Manual Docx Merge Tracker

> Working tracker for the Phase G→J iteration (2026-06-12 → present).
> Each entry = a thesis chunk that landed in markdown and must be merged
> into the working `.docx`. Sorted **newest first** — the ones at the top
> are what you haven't merged yet.
>
> Mark `[x]` after you've pasted into the docx so you can stop tracking
> that row. Cross-reference the commit SHA if you need to see the exact
> patch (`git show <sha>`).

## Status legend

- `[ ]` not yet merged into docx
- `[x]` merged
- `[~]` partially merged (e.g. text only, figure still pending)

## Change-type legend

Each row also carries a change type so you know what action to take in the docx:

- **INSERT** — new section / paragraph that doesn't exist in the docx yet → paste in fresh
- **UPDATE** — existing section needs replacement → delete old + paste new
- **APPEND** — add to the end of an existing section (e.g. new bullet, new row in a table)
- **DELETE** — remove from the docx (text was struck or stale; nothing to paste)
- **MOVE** — same content, different location (e.g. reorder sections)
- **RENUMBER** — same content, different heading number (just edit the heading in the docx)

## What landed since 2026-06-12

### Chapter 3 — Methodology

- [ ] **INSERT §3.4.8 Confound-isolated multi-stack backtest with adversarial verification** (~480 w) — commit `26e2868`
  - Triple-backtest rationale (Stack-OFF / Stack-ON / Stack-ON-light)
  - 7-hypothesis lens + adversarial refute-pass pattern
  - Concrete evidence: 2 of 4 hypotheses rejected on refute
- [ ] **INSERT §3.4.9 Eval-infrastructure reliability protocol** (~520 w) — commit `26e2868`
  - Queue-artifact motivation
  - 4 protocol elements: env hydration / GPU-concurrency match / checkpoint resume / pre-flight smoke
- [ ] **INSERT §3.4.10 Defect backlog as a living artifact** (~290 w) — commit `26e2868`
  - AP_C event-sourced vs AP_F OPEN/PATCHED/DEFERRED ledger
  - Phase J ETL sweep as the worked example

### Chapter 7 — Discussion

- [ ] **INSERT §7.6 Transferable Techniques** (~970 w, 4 subsections) — commit pending
  - 7.6.1 Adversarial-verification workflow for regression attribution
  - 7.6.2 Eval-infrastructure reliability protocol (cross-ref CH3 §3.4.9)
  - 7.6.3 Defect backlog as methodology artifact (cross-ref CH3 §3.4.10)
  - 7.6.4 KB↔DB ETL-style drift audit as recurring procedure
- [ ] **MOVE/RENUMBER §7.5 Limitations** — no content change; just sits after §7.4 and before §7.6 now. In the docx: confirm §7.5 already exists and §7.6 (new) sits AFTER it.

### Chapter 6 — Testing & Evaluation

- [ ] **§6.5.8 Phase G–I narrative** — commit `0d866a9`
  - 6.5.8.1 Phase G/H stack inventory (5 components + env flags)
  - 6.5.8.2 Dual A/B backtest (2026-06-12) — apparent regression headline
  - 6.5.8.3 Adversarial-verification regression dig (refute-pass narrative)
  - 6.5.8.4 Probe 1 confound-isolated single-component ablation
  - 6.5.8.5 Phase I infrastructure fixes (env + parallel)
  - 6.5.8.6 Clean triple backtest plan
  - 6.5.8.7 Promotion-gate verdict (placeholder — fill once triple v3 lands)

### Appendix C — Defect Inventory

- [ ] **C.5 Queue artifact / `empty_response` from FastAPI semaphore timeout** (~700 w) — commit `efa622a`
  - Full Example / Root cause / Detection / Fix / Verification structure
  - Cites the 32 / 20 timeout-distribution evidence
- [ ] **C.Y Phase G/H/I narrative extensions** — commit `efa622a`
  - Phase G.A–C (prompt versioning + Gemma overrides)
  - Phase G.D (revert overrides)
  - Phase H.A (query rewrite), Phase H.B (multi-intent), Phase H.C (BM25 + reranker)
  - Phase H.D (per-stay WiFi)
  - Phase I.A (env hydration), Phase I.B (queue fix)
- [ ] **C.Z closing patch-list extension** — commit `efa622a`
  - All Phase G/H/I rows added, "Final production state" updated to 2026-06-13
  - Explicitly disclaims the 2026-06-12 dual aggregates as queue-contaminated

### Appendix F — Defect Backlog (NEW file)

- [ ] **AP_F entire file** (~17 KB, ~430 lines) — commits `5809c4d` (initial) + later updates
  - F.1 Headline summary
  - F.2.1 Size drift (CLOSED)
  - F.2.2 Deluxe max_occupancy drift (CLOSED — DB-is-truth pick)
  - F.2.3 Facility location/hours drift (CLOSED — 4 services aligned)
  - F.2.4 Phase K ETL pipeline recommendation (OPEN backlog)
  - F.3 Per-case backlog (17 incorrects with status)
  - F.4 Fix-effort summary
  - F.5 Projected pass-rate impact
  - F.6 Reproduction commands

### Earlier landings (still need merging if not already)

- [ ] **AP_E Claude Live Test appendix** (~189 lines, NEW) — commit `54f2a` or earlier
  - 10 live-test scenarios with verdict + defect tags
  - Headline 7/8 PASS on Phase G+H+reranker
- [ ] **AP_D Per-Case Q&A** scaffold (will auto-rebuild when triple completes; do NOT merge yet — wait for final numbers)
- [ ] **CH4 §4.X Gemma 4 12B Q8_0 model selection** (in `thesis/CH4_System_Design_INSERT.md`) — splice into CH4
- [ ] **CH4 §4.Y Retrieval architecture** (in `thesis/CH4_System_Design_INSERT.md`) — splice into CH4

## How to use this file

1. Open `thesis/CH3_Methodology.md` (or any file in the table above)
2. Find the section listed (e.g., §3.4.8)
3. Copy the markdown
4. Paste into the corresponding heading in your docx (use Word's "Keep Text Only" paste to avoid font drift)
5. Mark the checkbox `[ ]` → `[x]` here
6. Commit this file when you've batched a few merges, so the tracker stays current

## Conventions

- Each entry cites the **commit SHA** so you can `git show <sha>` if you need the exact diff
- Sections in `**bold**` are the heading in the thesis markdown
- Word counts (`~480 w`) are approximate guides for how much you're pasting
- Sub-bullets are the key claims in that section — useful for sanity-checking the docx merge

_(Maintained by Claude while running the Phase G→J eval iteration.
 Each new commit that touches `thesis/*.md` should add a row here.)_
