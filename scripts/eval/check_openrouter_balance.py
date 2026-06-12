"""Check OpenRouter credit balance and exit with a status code.

Used by the eval pipeline pre-flight + periodically during long backtest runs
so we don't drain the user's budget mid-run.

Exit codes:
  0  ≥ $1.00 available   (OK to proceed)
  1  $0.50 ≤ x < $1.00   (warn; topup recommended)
  2  $0.00 < x < $0.50   (block; ask user)
  3  ≤ $0.00             (hard stop; out of credits)
  10 network / auth error
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_api_key() -> str | None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    return None


def fetch_balance(api_key: str) -> tuple[float, float]:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data", {})
    total = float(data.get("total_credits", 0))
    used = float(data.get("total_usage", 0))
    return total - used, used


def classify(balance: float) -> tuple[int, str]:
    if balance <= 0:
        return 3, "OUT OF CREDITS — hard stop"
    if balance < 0.50:
        return 2, "CRITICAL — block new batches"
    if balance < 1.00:
        return 1, "LOW — topup recommended"
    return 0, "OK"


def main() -> int:
    key = load_api_key()
    if not key:
        print("ERR: no OPENROUTER_API_KEY in env or .env", file=sys.stderr)
        return 10
    try:
        balance, used = fetch_balance(key)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        print(f"ERR: balance check failed: {e}", file=sys.stderr)
        return 10
    code, status = classify(balance)
    print(f"OpenRouter balance: ${balance:.4f} available  (used ${used:.2f} of total)  [{status}]")
    if code >= 1:
        print(f"  -> alert level {code}: {status}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
