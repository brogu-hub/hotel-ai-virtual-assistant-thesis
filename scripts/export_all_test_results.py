#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Export all 193 infrastructure/auth/scaling test results as structured JSON + markdown.

Runs all 4 test suites, captures every assertion, and produces:
  - docs/ALL_TEST_RESULTS.json — machine-readable
  - Appends to docs/MODEL_EVAL_REPORT.md — human-readable summary table

Usage:
    python scripts/export_all_test_results.py
"""
import sys
import os
import json
import subprocess
import re
import time
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

SUITES = [
    {"name": "Auth Baseline", "script": "scripts/test_auth.py", "expected": 72},
    {"name": "Auth Hardening", "script": "scripts/test_auth_hardening.py", "expected": 38},
    {"name": "Audit + DB Scaling", "script": "scripts/test_audit_and_scaling.py", "expected": 46},
    {"name": "Chat Scaling", "script": "scripts/test_chat_scaling.py", "expected": 37},
]


def run_suite(script: str) -> tuple[list[dict], str, int]:
    """Run a test suite and parse results from output."""
    start = time.time()
    result = subprocess.run(
        [sys.executable, script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    elapsed = time.time() - start
    output = result.stdout + result.stderr

    # Parse [PASS] and [FAIL] lines
    tests = []
    for line in output.split("\n"):
        # Match colored PASS/FAIL
        clean = re.sub(r'\033\[[0-9;]*m', '', line)  # strip ANSI
        m = re.match(r'\s*\[(PASS|FAIL)\]\s*(.*?)(?:\s*—\s*(.*))?$', clean)
        if m:
            status = m.group(1)
            name = m.group(2).strip()
            detail = m.group(3).strip() if m.group(3) else ""
            tests.append({
                "name": name,
                "passed": status == "PASS",
                "detail": detail,
            })

    # Parse summary line
    summary_match = re.search(r'(\d+)/(\d+) passed', clean if not tests else output)

    return tests, output, int(elapsed)


def main():
    print(f"{BOLD}Exporting all test results...{RESET}\n")

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "suites": [],
        "total_tests": 0,
        "total_passed": 0,
    }

    for suite in SUITES:
        print(f"{CYAN}Running {suite['name']}...{RESET}", end=" ", flush=True)
        try:
            tests, raw_output, elapsed_sec = run_suite(suite["script"])
            passed = sum(1 for t in tests if t["passed"])
            total = len(tests)
            color = GREEN if passed == total else RED
            print(f"{color}{passed}/{total}{RESET} ({elapsed_sec}s)")

            all_results["suites"].append({
                "name": suite["name"],
                "script": suite["script"],
                "expected_tests": suite["expected"],
                "actual_tests": total,
                "passed": passed,
                "failed": total - passed,
                "elapsed_seconds": elapsed_sec,
                "tests": tests,
            })
            all_results["total_tests"] += total
            all_results["total_passed"] += passed
        except subprocess.TimeoutExpired:
            print(f"{RED}TIMEOUT{RESET}")
            all_results["suites"].append({
                "name": suite["name"],
                "script": suite["script"],
                "expected_tests": suite["expected"],
                "actual_tests": 0,
                "passed": 0,
                "failed": 0,
                "elapsed_seconds": 600,
                "tests": [],
                "error": "timeout",
            })
        except Exception as e:
            print(f"{RED}ERROR: {e}{RESET}")
            all_results["suites"].append({
                "name": suite["name"],
                "script": suite["script"],
                "expected_tests": suite["expected"],
                "actual_tests": 0,
                "passed": 0,
                "failed": 0,
                "elapsed_seconds": 0,
                "tests": [],
                "error": str(e),
            })

    # Save JSON
    json_path = "docs/ALL_TEST_RESULTS.json"
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # Print summary
    total = all_results["total_tests"]
    passed = all_results["total_passed"]
    failed = total - passed
    color = GREEN if failed == 0 else RED

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}Total: {color}{passed}/{total} passed{RESET}")
    print(f"JSON saved: {json_path}")

    # Generate markdown summary table for appendix
    md_lines = [
        "",
        "## Infrastructure Test Results (Auth, Hardening, Audit, Scaling)",
        "",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Total: {passed}/{total} ({passed/total:.0%})**",
        "",
        "| Suite | Tests | Passed | Failed | Time |",
        "|---|---|---|---|---|",
    ]
    for s in all_results["suites"]:
        md_lines.append(
            f"| {s['name']} | {s['actual_tests']} | {s['passed']} | "
            f"{s['failed']} | {s['elapsed_seconds']}s |"
        )
    md_lines.append("")

    # Failed tests detail
    has_failures = any(s["failed"] > 0 for s in all_results["suites"])
    if has_failures:
        md_lines.append("### Failed Tests")
        md_lines.append("")
        for s in all_results["suites"]:
            for t in s["tests"]:
                if not t["passed"]:
                    md_lines.append(f"- **{s['name']}** / {t['name']}: {t['detail']}")
        md_lines.append("")

    # Append to MODEL_EVAL_REPORT.md if it exists
    eval_report = "docs/MODEL_EVAL_REPORT.md"
    if os.path.exists(eval_report):
        with open(eval_report, "a", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        print(f"Appended infrastructure results to: {eval_report}")
    else:
        # Write as standalone
        with open("docs/INFRA_TEST_RESULTS.md", "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))
        print(f"Saved: docs/INFRA_TEST_RESULTS.md")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
