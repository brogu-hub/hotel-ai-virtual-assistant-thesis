#!/usr/bin/env bash
# Apply Phase 5 fixes for the strategic backtest pipeline.
#
# Run this AFTER the pre-fix baseline backtest completes, so the baseline
# numbers reflect the true pre-fix system. Each step is idempotent so it
# can be re-run safely.
#
# Fix order matters: edits to src/* trigger uvicorn auto-reload; re-ingest
# changes Qdrant. Doing them in order means the chatbot picks up all four
# fixes simultaneously before the post-fix backtest starts.
set -euo pipefail
cd "$(dirname "$0")/../.."  # repo root

echo
echo "=== Phase 5 fix application ==="
echo

# --- Fix 1: pop the stashed KB strip + pricing-inject helper ---
echo "Fix 1: restore stashed KB strip + pricing-inject helper"
if git stash list | grep -q "phase5-fixes-saved-for-postbaseline"; then
    STASH_REF=$(git stash list | grep "phase5-fixes-saved-for-postbaseline" | head -1 | awk -F: '{print $1}')
    git stash pop "$STASH_REF"
    echo "  ok — applied $STASH_REF"
else
    echo "  no stash entry found (already applied?); skipping"
fi

# --- Fix 2: chunk_size in src/retrievers/hotel_knowledge/chains.py ---
echo
echo "Fix 2: reduce chunk_size 26212 -> 2000 (env-overridable)"
python - <<'PYEOF'
import re
from pathlib import Path
path = Path("src/retrievers/hotel_knowledge/chains.py")
text = path.read_text(encoding="utf-8")
# Match the auto-calculated chunk_size assignment
target_re = re.compile(
    r"^(\s*)chunk_size\s*=\s*max\(1, int\(token_limit \* 0\.8 \* 4\)\)\s*$",
    re.MULTILINE,
)
target_overlap = re.compile(
    r"^(\s*)chunk_overlap\s*=\s*int\(chunk_size \* 0\.2\)\s*$",
    re.MULTILINE,
)
new_size = '    chunk_size = int(os.getenv("CHUNK_SIZE_CHARS", "2000"))'
new_overlap = '    chunk_overlap = int(os.getenv("CHUNK_OVERLAP_CHARS", "200"))'
if target_re.search(text):
    text = target_re.sub(new_size, text)
    text = target_overlap.sub(new_overlap, text)
    path.write_text(text, encoding="utf-8")
    print("  ok — replaced chunk_size/overlap with env-overridable defaults")
else:
    print("  WARN: chunk_size pattern not found — may already be patched")
PYEOF

# --- Fix 3: num_docs 3 -> 5 in src/agent/hotel_tools.py ---
echo
echo "Fix 3: increase num_docs 3 -> 5 in hotel_tools.py"
python - <<'PYEOF'
import re
from pathlib import Path
path = Path("src/agent/hotel_tools.py")
text = path.read_text(encoding="utf-8")
# Find the document_search invocation
new_text = re.sub(
    r"(\.document_search\([^)]*?num_docs\s*=\s*)3",
    r"\g<1>5",
    text,
    count=1,
)
if new_text != text:
    path.write_text(new_text, encoding="utf-8")
    print("  ok — bumped num_docs to 5")
else:
    print("  WARN: num_docs=3 not found at expected site — may already be patched or pattern shifted")
PYEOF

# --- Fix 4: re-ingest Qdrant ---
echo
echo "Fix 4: re-ingest Qdrant hotel_knowledge collection"
echo "  (drops existing collection + re-indexes 49 sections at chunk_size=2000)"
docker exec hotel-api python /app/scripts/ingest_hotel_knowledge.py 2>&1 | tail -5
echo

# --- Sanity: drift audit should now exit 0 ---
echo "Sanity check: drift audit should exit 0"
DATABASE_URL="postgresql://hotel_app:hotel_app_pass_CHANGE_ME@localhost:5433/hotel" \
    PYTHONIOENCODING=utf-8 python scripts/audit_data_db_drift.py --strict || \
    { echo "  WARN: drift still present — investigate"; }
echo
echo "=== Phase 5 complete ==="
echo "Next: run post-fix backtest"
echo "  python scripts/eval/backtest_runner.py --tag postfix --sample-iteration 200"
