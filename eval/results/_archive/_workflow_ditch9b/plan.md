# Ditch-9B Plan — Synthesis

## Recommendation
**Pull `gemma4:12b-it-q8_0` (~13 GB).** It is the largest Gemma 4 variant that fits the RTX 5080 16 GB alongside `bge-reranker-v2-m3` with ~1.2 GB safety margin. The 26B-a4b MoE overflows VRAM once the reranker is co-resident, and the e4b-Q8 variant is a smaller-active-param regression. Keep current `gemma4:12b-it-qat` (7.2 GB) as the fall-back if KV-cache growth at long contexts pushes total VRAM past 15 GB under load.

---

## This turn — concrete actions (~30 min)

1. **Pull both candidate weights in parallel** (one is the recommendation, the other is the safety net):
   ```powershell
   docker exec hotel-ollama ollama pull gemma4:12b-it-q8_0
   docker exec hotel-ollama ollama pull gemma4:12b-it-qat
   ```
2. **Hot-swap to Q8_0** via the existing Phase A runtime endpoint:
   ```powershell
   curl -X PUT http://localhost:8088/settings/llm -d '{"model":"gemma4:12b-it-q8_0"}'
   curl -s http://localhost:8088/healthz | jq '.llm, .rerank, .retriever, .phase_flags'
   ```
3. **VRAM check under load** — fire 5 sequential `/chat` probes (1 EN, 2 TH, 1 CN, 1 long-context booking) and watch `nvidia-smi -l 1` in another pane. Acceptance: total VRAM stays under 15.0 GB across all 5 calls, no CPU spillover in `ollama ps`.
4. **Smoke canaries** (15-case canary subset, ~3 min):
   ```powershell
   $env:OLLAMA_MODEL = 'gemma4:12b-it-q8_0'
   $env:APP_LLM_MODELNAME = 'gemma4:12b-it-q8_0'
   python scripts/eval/backtest_runner.py --tag gemma4-q8-canary `
       --endpoint http://localhost:8088 --canaries-only `
       --chat-cache-version gemma4-q8-h-stack-v1 `
       --max-chat-parallel 2 --abort-canary-failures 2
   ```
5. **Decision gate**:
   - **PASS** (VRAM <15 GB, canaries ≥13/15): proceed to next-turn full run on Q8_0.
   - **FAIL on VRAM**: swap to `gemma4:12b-it-qat`, re-run step 4, proceed on QAT.
   - **FAIL on canary regression**: roll back to current `gemma4:12b-q4_K_M`, log the regression in commit message, escalate before next-turn run.
6. **Commit the swap + test log** with a message stating: which variant pulled, VRAM peak observed, canary pass count, and which variant is the chosen baseline going forward.

---

## Next turn — the big re-run

Kick off the **full 514-case backtest** on the chosen Gemma variant against the live Phase G + H stack, with the Phase D chat cache **cold for Gemma** (forced by the model-keyed `chat_sha`) and **warm for the DeepSeek judge** across resumes.

```powershell
python scripts/eval/backtest_runner.py `
    --tag gemma4-q8-full-stack `
    --endpoint http://localhost:8088 `
    --judge-model deepseek/deepseek-chat-v3.1 `
    --chat-timeout 240 `
    --chat-cache-version gemma4-q8-h-stack-v1 `
    --max-chat-parallel 2 --abort-canary-failures 2

python scripts/eval/backtest_report.py --tag gemma4-q8-full-stack `
    --compare-to eval/results/final-postfix/20260609T205731

python eval/scripts/build_comparison_tables.py `
    --qwen-raw  eval/results/final-postfix/20260609T205731/raw.jsonl `
    --gemma-raw eval/results/gemma4-q8-full-stack/<TS>/raw.jsonl `
    --dataset-dir eval/dataset `
    --out-dir eval/results/comparison/qwen9b_vs_gemma4_q8 `
    --truncate-chars 280 `
    --live-test-log eval/results/comparison/manual_verification_log.json
```

**ETA**: ~3.5–4.5 h wallclock for 514 cases at `--max-chat-parallel 2` on a 12B-Q8 model (Q8_0 is 15–25 % slower per-token than Q4; judge calls cached across the 261-id overlap with Qwen). **Fall-back**: stratified 300 (`--sample-iteration 300 --sample-seed 42`) cuts it to ~2 h if wallclock pressure appears.

**Artifacts produced**:
- `eval/results/gemma4-q8-full-stack/<TS>/raw.jsonl` — Gemma rows
- `eval/results/comparison/qwen9b_vs_gemma4_q8/per_case.md` — per-case side-by-side (sorted en/th/cn, regressions floated to top)
- `…/appendix_full_responses.jsonl` — untruncated responses for both models
- `…/aggregate.md` — three-section headline / per-language / per-defect comparison with Wilson CIs and McNemar p-value
- `…/summary.json` — headline numbers for downstream LaTeX
- `…/manual_verification_log.md` — Appendix-C-style live-test log block

Before invoking `build_comparison_tables.py`, **write the live-test JSON log**: replay this session's `/chat` POSTs out of the transcript into `eval/results/comparison/manual_verification_log.json` using the schema fixed in plan B (`turn_idx, timestamp_iso, model_active, question, response, claude_qualitative_judgement, qualitative_verdict, user_live_test:true, source, notes`). Then wire `scripts/eval/log_live_chat.py` as a tee for future probes so the log stays current automatically.

---

## Turn N+1 — thesis writing

Apply plan C edits, in this order (Edit-tool surgical changes — no chapter rewrites):

| File | Change |
|---|---|
| `thesis/CH3_Methodology.md` §3.3.3 | Append "Model migration note" paragraph (verbatim from plan C); replace 2-col Qwen-vs-Qwen-Max decision table with 3-col (Qwen 9B baseline / Gemma 4 12B shipped / Qwen3 Max fallback) |
| `thesis/CH3_Methodology.md` §3.4.7 | Append model-agnostic backtest paragraph |
| `thesis/CH4_System_Design.md` §4.2 | Update overview-diagram caption: primary LLM = Gemma 4 12B (Ollama, local) |
| `thesis/CH4_System_Design.md` new §4.3.4 | "Runtime LLM swap and per-model prompt versioning" (Phases A + G) |
| `thesis/CH4_System_Design.md` new §4.5.2 | "Hybrid retrieval stack (Phase H)" + new `thesis/figures/Fig_4.5_Hybrid_Retrieval.png` |
| `thesis/CH4_System_Design.md` new §4.8 | Architectural-changes summary table `T_CH4_arch_changes` |
| `thesis/CH6_Evaluation.md` §6.5.5 | Rewrite single "Final shipped" sentence; append Phase G and Phase H rows to iteration table |
| `thesis/CH6_Evaluation.md` new §6.5.5e | Phase G narrative + `T_CH6_phaseG_overrides` |
| `thesis/CH6_Evaluation.md` new §6.5.5f | Phase H narrative + `T_CH6_aggregate_compare` (Phase A / A+G / A+G+H); cite AP_E for 7/8 live PASS |
| `thesis/CH6_Evaluation.md` §6.5.6 | Reframe "DO NOT SHIP" as "DO NOT SHIP at Phase A"; add trailing paragraph pointing to §6.5.5f + AP_E |
| `thesis/CH6_Evaluation.md` §6.5.7 | Append threats-to-validity bullet for informal live-test subset |
| `thesis/CH7_Discussion.md` | Add "On the Qwen-to-Gemma migration" paragraph |
| `thesis/AP_C_Defect_Inventory.md` | Reframe Phase A header to "production baseline"; append Phase G + Phase H sub-sections; append 2 rows + new "Final state" line to closing patch-list table |
| `thesis/AP_D_PerCase_QA.md` (NEW) | §D.1 golden-25 (`T_AP_D_1`); §D.2 stratified-96 roll-up (`T_AP_D_2`); §D.3 per-stratum aggregate; §D.4 reading guide |
| `thesis/AP_E_Manual_Verification.md` (NEW) | §E.0 Limitations (read-first); §E.1 summary (`T_AP_E_livetest`); §E.2 per-case verbatim; §E.3 what this confirms / does not; §E.4 cross-refs |

All numerical cells in AP_D, the Phase H row in §6.5.5, and `T_CH6_aggregate_compare` are populated from the next-turn run's `raw.jsonl` + `summary.json` — do not draft these tables before the run completes.

---

## Risks

1. **26B fits but regresses** — moot for now (it does not fit at 16 GB once the reranker is co-resident). Document this in §6.5.5f as an explicit hardware ceiling so the thesis does not look like we ignored the MoE option.
2. **Q8_0 is no better than Q4_K_M** — possible; the Q4→Q8 quality bump is typically 1–2 pp on reasoning benchmarks, which is *inside* the σ=1.58 pp variance floor from Phase F. Mitigation: report the headline delta with Wilson CI + McNemar p in `aggregate.md` and let the per-defect breakdown carry the story (Q8 should show measurable wins on Thai/Chinese token fidelity even if aggregate strict-pass is flat). If genuinely flat across all defect classes, stay on Q4_K_M, save VRAM headroom for longer KV-cache contexts, and frame the thesis as "Q4 is Pareto-optimal for this hardware."
3. **Gemma is WORSE on the 514-set despite the 7/8 live wins** — the most uncomfortable outcome. Diagnosis path: (a) check if the regression concentrates in `tool_not_called` / `format_error` (suggests Phase G overrides over-tightened refusal), (b) check `judge_source` breakdown (deterministic-fallback skew?), (c) re-run the 8 live cases through the formal backtest pipeline to confirm they still PASS under the LLM judge. If the regression is real and concentrated in one defect bucket, treat it as Phase I work, not a ship-blocker; if it is broad-spectrum, roll back to Qwen 9B for the headline numbers and reframe Gemma as an architectural exploration in CH7. **Either outcome is publishable** — the iteration methodology is the contribution, not the model choice.

---

## The "live test" treatment

Claude-typed conversations are **qualitative probes, not evaluation**. They are valuable because they:

- Bypass the Phase D chat cache and verify the *live* shipped stack end-to-end on freshly-phrased inputs the golden set has never seen.
- Catch defect classes the LLM judge does not score: politeness markers, unit-fragment leakage in CN, code-switching cleanliness, tool-call leakage in user-facing text.
- Verify hard-negative refusals (no casino, no helipad, no underwater suite) on novel phrasings.

They are **not evaluation** because: n=8 (no statistical power), single adjudicator (Claude — same model family as the future judge, not independent ground truth), not blinded, not pre-registered, and the probes were chosen *after* knowing what defects Phase A exhibited (selection bias toward cases Phase H was expected to fix).

**Treatment**: appendix AP_E only, labelled "**Informal qualitative verification**" with the §E.0 Limitations block on the very first line. Every row carries `user_live_test=true`. The 7/8 PASS number is reported in §6.5.5f and AP_E only — **never** in `aggregate.md`, **never** in the CH6 headline figure, **never** as a replacement for the §6.5.6 promotion-gate verdict. Cross-references from §6.5.5f and §6.5.7 explicitly say "informal supplementary evidence." This keeps the thesis honest while still giving Phase H the qualitative credit it earned.

Relevant absolute paths:
- `z:\Dev_Drive\hote-ai-virtual-assistant-thesis\eval\results\final-postfix\20260609T205731\raw.jsonl` (Qwen 9B baseline)
- `z:\Dev_Drive\hote-ai-virtual-assistant-thesis\eval\results\comparison\qwen9b_vs_gemma4_q8\` (next-turn output dir)
- `z:\Dev_Drive\hote-ai-virtual-assistant-thesis\eval\scripts\build_comparison_tables.py` (to be authored)
- `z:\Dev_Drive\hote-ai-virtual-assistant-thesis\scripts\eval\log_live_chat.py` (to be authored)
- `z:\Dev_Drive\hote-ai-virtual-assistant-thesis\thesis\AP_D_PerCase_QA.md`, `thesis\AP_E_Manual_Verification.md` (new appendices)