# .raw/ — Source Documents

This folder holds immutable source documents: papers (PDFs), transcripts, data exports, scraped pages, raw session logs, anything that feeds the wiki.

## Rules

- **Never modify** files here after they land. Sources are frozen evidence.
- Filename convention: `YYYY-MM-DD_short-slug.ext` (e.g., `2026-04-19_subagent-test-run.md`).
- When a source is processed into the wiki, the ingest operation creates/updates pages in `wiki/` and logs the action in `wiki/log.md`. The raw file stays here.
- To retire a source that is no longer relevant, move it to `.archive/` (create that folder when first needed) rather than deleting it.

## Suggested first sources to drop here

- NVIDIA AI Blueprint docs / white paper (PDF)
- LangGraph docs export
- NeMo Guardrails paper (Rebedea et al., 2023)
- Qwen3 technical report
- Thesis chapter drafts (`.docx` or `.md` exports)
- Recent DeepEval run outputs (`.json`)
- `scripts/test_4_subagents.py` output transcript
