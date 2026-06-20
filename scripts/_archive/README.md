# Archived: `scripts/_archive/`

This directory contains one-off and exploratory scripts from earlier iterations of the Hotel AI Virtual Assistant thesis that are **no longer part of the active evaluation pipeline**. Many descend from or were written against the original [NVIDIA AI Blueprint for AI Virtual Assistant](https://github.com/NVIDIA-AI-Blueprints/ai-virtual-assistant).

## Why preserved

1. **Attribution to upstream** — `test_chat.py` and `print_env.sh` originate from the NVIDIA blueprint sample tests.
2. **Reproducibility** — superseded sanity-check, scaling, and auth-hardening probes are kept so any historical claim in the thesis (e.g. "we ran chat scaling at N concurrency") can be re-executed.
3. **Thesis defense clarity** — separates the canonical evaluation harness (`scripts/eval/`) from earlier exploratory scripts.

## What is still active (NOT archived)

The active evaluation entrypoints remain at the original paths:

- `scripts/eval/` — canonical backtest / metric / report pipeline
- `scripts/ingest_hotel_knowledge.py` — hotel KB ingestion
- `scripts/generate_hotel_dataset.py`, `scripts/generate_hotel_knowledge.py` — dataset/KB generators
- `scripts/audit_data_db_drift.py` — KB ↔ PMS DB drift check (Phase J)
- thesis-build scripts (`build_thesis_docx.py`, `inject_into_template.py`, `patch_*.py`, `gen_*.py`)

## Contents

| File | Origin / purpose |
|---|---|
| `print_env.sh` | NVIDIA blueprint env-dump helper |
| `test_chat.py` | NVIDIA blueprint sample chat smoke test |
| `test_4_subagents.py` | Early probe of the 4 sub-agent routing (booking / service / knowledge / other_talk) |
| `test_audit_and_scaling.py` | Audit + concurrency probe (superseded by `scripts/eval/`) |
| `test_auth.py` | Initial auth happy-path probe |
| `test_auth_hardening.py` | Auth-hardening regression probe |
| `test_chat_scaling.py` | Chat concurrency / scaling probe |
| `test_chinese_leak.py` | Language-lock cross-contamination probe (superseded by Phase B/D evals) |
| `test_hotel_rag.py` | Manual hotel-RAG probe against `src/retrievers/hotel_knowledge/` |
