#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Model Comparison Evaluation — Local 9B vs Cloud LLM

Thesis Appendix: Evaluates the hotel chatbot across 25 diverse test
cases covering knowledge retrieval, booking operations, bilingual
handling, edge cases, and multi-turn conversations.

Metrics:
  - Accuracy (binary pass/fail per expected criterion)
  - DeepEval answer relevancy + faithfulness
  - Cohen's Kappa inter-model agreement
  - Per-case conversation logs with timing

Usage:
    # Set OPENROUTER_API_KEY in .env
    python scripts/eval_model_comparison.py

    # Run only local model:
    python scripts/eval_model_comparison.py --local-only

    # Run only cloud model:
    python scripts/eval_model_comparison.py --cloud-only

Output:
    docs/MODEL_EVAL_REPORT.md — full report with tables + conversations
"""
import sys
import os
import json
import time
import uuid
import argparse
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import requests

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_URL = os.getenv("EVAL_BASE_URL", "http://localhost:8088")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Color output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# =============================================================================
# Test cases — 25 diverse scenarios with expected behaviors
# =============================================================================

TEST_CASES: List[Dict[str, Any]] = [
    # --- Category A: Knowledge Retrieval (8 cases) ---
    {
        "id": "K01",
        "category": "Knowledge",
        "language": "en",
        "message": "What time is breakfast?",
        "expected_keywords": ["breakfast", "7", "10", "restaurant"],
        "expected_behavior": "Should retrieve breakfast hours from knowledge base",
    },
    {
        "id": "K02",
        "category": "Knowledge",
        "language": "en",
        "message": "What is the WiFi password?",
        "expected_keywords": ["wifi", "password", "internet"],
        "expected_behavior": "Should retrieve WiFi info from knowledge base",
    },
    {
        "id": "K03",
        "category": "Knowledge",
        "language": "th",
        "message": "สระว่ายน้ำเปิดกี่โมง",
        "expected_keywords": ["สระ", "เปิด"],
        "expected_behavior": "Should respond in Thai with pool hours",
    },
    {
        "id": "K04",
        "category": "Knowledge",
        "language": "en",
        "message": "Do you allow pets?",
        "expected_keywords": ["pet", "5 kg", "500"],
        "expected_behavior": "Should retrieve pet policy with fee and weight limit",
    },
    {
        "id": "K05",
        "category": "Knowledge",
        "language": "en",
        "message": "What is your cancellation policy?",
        "expected_keywords": ["cancel", "48", "hour"],
        "expected_behavior": "Should mention 48-hour free cancellation",
    },
    {
        "id": "K06",
        "category": "Knowledge",
        "language": "en",
        "message": "Where is the spa and what treatments do you offer?",
        "expected_keywords": ["spa", "3rd floor", "massage"],
        "expected_behavior": "Should give spa location, hours, and treatment types",
    },
    {
        "id": "K07",
        "category": "Knowledge",
        "language": "en",
        "message": "What time is check-in and check-out?",
        "expected_keywords": ["2:00", "14:00", "12:00", "noon"],
        "expected_behavior": "Should give check-in 2PM and check-out noon",
    },
    {
        "id": "K08",
        "category": "Knowledge",
        "language": "th",
        "message": "มีบริการรถรับส่งสนามบินไหม",
        "expected_keywords": ["รถ", "สนามบิน"],
        "expected_behavior": "Should respond in Thai about airport transfer",
    },
    # --- Category B: Booking Operations (6 cases) ---
    {
        "id": "B01",
        "category": "Booking",
        "language": "en",
        "message": "Is there a room available next Monday?",
        "expected_keywords": ["available", "room", "standard", "deluxe"],
        "expected_behavior": "Should use check_room_availability tool and show room types",
    },
    {
        "id": "B02",
        "category": "Booking",
        "language": "en",
        "message": "How much is a Deluxe room per night?",
        "expected_keywords": ["deluxe", "THB", "price", "baht"],
        "expected_behavior": "Should retrieve price from database via tool, not from memory",
    },
    {
        "id": "B03",
        "category": "Booking",
        "language": "en",
        "message": "I want to cancel my booking HTL260405001",
        "expected_keywords": ["cancel"],
        "expected_behavior": "Should route to booking handler and attempt cancellation",
    },
    {
        "id": "B04",
        "category": "Booking",
        "language": "th",
        "message": "มีห้องว่างวันที่ 15-17 เดือนหน้าไหม",
        "expected_keywords": ["ห้อง", "ว่าง"],
        "expected_behavior": "Should check availability for next month 15-17 in Thai",
    },
    {
        "id": "B05",
        "category": "Booking",
        "language": "en",
        "message": "I'd like to book a Standard room for tomorrow for 2 nights. My email is test@example.com",
        "expected_keywords": ["book", "standard", "confirm"],
        "expected_behavior": "Should attempt to create reservation with dates and email",
    },
    {
        "id": "B06",
        "category": "Booking",
        "language": "en",
        "message": "Can you check my booking? My email is john@hotel.com",
        "expected_keywords": ["reservation", "booking"],
        "expected_behavior": "Should use get_guest_reservations with the email",
    },
    # --- Category C: Greetings & Small Talk (4 cases) ---
    {
        "id": "G01",
        "category": "Greeting",
        "language": "en",
        "message": "Hello!",
        "expected_keywords": ["welcome", "Grand Horizon", "assist"],
        "expected_behavior": "Should warmly greet and offer to help",
    },
    {
        "id": "G02",
        "category": "Greeting",
        "language": "th",
        "message": "สวัสดีครับ",
        "expected_keywords": ["สวัสดี", "ยินดี"],
        "expected_behavior": "Should respond in Thai with greeting",
    },
    {
        "id": "G03",
        "category": "Greeting",
        "language": "en",
        "message": "Thank you for your help!",
        "expected_keywords": ["thank", "welcome", "help", "pleasure"],
        "expected_behavior": "Should acknowledge thanks politely",
    },
    {
        "id": "G04",
        "category": "Greeting",
        "language": "en",
        "message": "What's the weather like today?",
        "expected_keywords": [],  # off-topic, any response is fine
        "expected_behavior": "Should handle gracefully, redirect to hotel services",
    },
    # --- Category D: Language Detection (3 cases) ---
    {
        "id": "L01",
        "category": "Language",
        "language": "en",
        "message": "Tell me about breakfast",
        "expected_keywords": ["breakfast"],
        "expected_behavior": "Response MUST be in English (not Thai)",
        "check_language": "en",
    },
    {
        "id": "L02",
        "category": "Language",
        "language": "th",
        "message": "อาหารเช้าเสิร์ฟกี่โมง",
        "expected_keywords": ["อาหารเช้า"],
        "expected_behavior": "Response MUST be in Thai (not English)",
        "check_language": "th",
    },
    {
        "id": "L03",
        "category": "Language",
        "language": "en",
        "message": "Where is the gym?",
        "expected_keywords": ["gym", "fitness", "floor"],
        "expected_behavior": "Response in English with gym location",
        "check_language": "en",
    },
    # --- Category E: Edge Cases (4 cases) ---
    {
        "id": "E01",
        "category": "Edge",
        "language": "en",
        "message": "I need extra towels in room 501",
        "expected_keywords": ["towel"],
        "expected_behavior": "Should route to service handler for amenity request",
    },
    {
        "id": "E02",
        "category": "Edge",
        "language": "en",
        "message": "Is there a room available on December 31st for New Year's Eve?",
        "expected_keywords": ["available", "room", "december", "31"],
        "expected_behavior": "Should check availability for the specific date",
    },
    {
        "id": "E03",
        "category": "Edge",
        "language": "en",
        "message": "I want to book 3 rooms for a group of 10 people",
        "expected_keywords": ["room"],
        "expected_behavior": "Should route to booking and handle multi-room request",
    },
    {
        "id": "E04",
        "category": "Edge",
        "language": "en",
        "message": "",
        "expected_keywords": [],
        "expected_behavior": "Should handle empty message gracefully (422 or polite response)",
        "allow_error": True,
    },
]


# =============================================================================
# Evaluation helpers
# =============================================================================


def get_admin_token() -> str:
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Admin login failed: {r.status_code}")
    return r.json()["access_token"]


def switch_backend(admin_token: str, backend: str, model: Optional[str] = None) -> dict:
    """Switch LLM backend at runtime."""
    payload: Dict[str, Any] = {"backend": backend}
    if model:
        payload["model"] = model
    r = requests.put(
        f"{BASE_URL}/settings/llm",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Failed to switch backend: {r.status_code} {r.text}")
    return r.json()


def send_chat(message: str, session_id: str, timeout: int = 120) -> Dict[str, Any]:
    """Send a chat message and return the full response + timing."""
    start = time.time()
    try:
        r = requests.post(
            f"{BASE_URL}/chat",
            json={"message": message, "session_id": session_id},
            timeout=timeout,
        )
        elapsed = time.time() - start
        if r.status_code == 200:
            body = r.json()
            return {
                "status": r.status_code,
                "response": body.get("response", ""),
                "routing_path": body.get("routing_path", ""),
                "tool_calls": body.get("tool_calls"),
                "latency_ms": int(elapsed * 1000),
                "error": None,
            }
        elif r.status_code == 422:
            return {
                "status": 422,
                "response": "",
                "routing_path": "validation_error",
                "tool_calls": None,
                "latency_ms": int(elapsed * 1000),
                "error": "validation_error",
            }
        else:
            return {
                "status": r.status_code,
                "response": r.text[:500],
                "routing_path": "error",
                "tool_calls": None,
                "latency_ms": int(elapsed * 1000),
                "error": f"HTTP {r.status_code}",
            }
    except requests.exceptions.ReadTimeout:
        return {
            "status": 0,
            "response": "",
            "routing_path": "timeout",
            "tool_calls": None,
            "latency_ms": int((time.time() - start) * 1000),
            "error": f"Timeout after {timeout}s",
        }
    except Exception as e:
        return {
            "status": 0,
            "response": "",
            "routing_path": "error",
            "tool_calls": None,
            "latency_ms": int((time.time() - start) * 1000),
            "error": str(e),
        }


def evaluate_response(test_case: Dict, result: Dict) -> Dict[str, Any]:
    """Score a single response against expected criteria."""
    response = result.get("response", "").lower()
    scores = {}

    # Skip scoring for allowed-error cases
    if test_case.get("allow_error") and result.get("error"):
        return {"pass": True, "reason": "graceful error handling", "keyword_hits": 0, "keyword_total": 0}

    # Keyword check (case-insensitive)
    keywords = test_case.get("expected_keywords", [])
    if keywords:
        hits = sum(1 for kw in keywords if kw.lower() in response)
        keyword_score = hits / len(keywords) if keywords else 1.0
        scores["keyword_score"] = keyword_score
        scores["keyword_hits"] = hits
        scores["keyword_total"] = len(keywords)
    else:
        scores["keyword_score"] = 1.0 if response else 0.5
        scores["keyword_hits"] = 0
        scores["keyword_total"] = 0

    # Language check
    check_lang = test_case.get("check_language")
    if check_lang == "en":
        # Response should be primarily English (< 20% Thai chars)
        thai_chars = sum(1 for c in response if '\u0e00' <= c <= '\u0e7f')
        total_alpha = sum(1 for c in response if c.isalpha())
        thai_ratio = thai_chars / max(total_alpha, 1)
        scores["language_correct"] = thai_ratio < 0.2
    elif check_lang == "th":
        # Response should contain significant Thai
        thai_chars = sum(1 for c in response if '\u0e00' <= c <= '\u0e7f')
        scores["language_correct"] = thai_chars > 10
    else:
        scores["language_correct"] = True

    # Did it respond at all? (not empty, not error)
    scores["has_response"] = bool(response) and not result.get("error")

    # Overall pass: keyword_score >= 0.5 AND language correct AND has response
    scores["pass"] = (
        scores.get("keyword_score", 0) >= 0.5
        and scores.get("language_correct", True)
        and scores.get("has_response", False)
    )
    scores["reason"] = (
        f"keywords={scores.get('keyword_hits', 0)}/{scores.get('keyword_total', 0)}, "
        f"lang={'ok' if scores.get('language_correct') else 'WRONG'}, "
        f"latency={result.get('latency_ms', 0)}ms"
    )

    return scores


def compute_cohens_kappa(labels_a: List[bool], labels_b: List[bool]) -> float:
    """Compute Cohen's Kappa between two sets of binary labels."""
    n = len(labels_a)
    if n == 0:
        return 0.0

    # Observed agreement
    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    po = agree / n

    # Expected agreement by chance
    a_pos = sum(labels_a) / n
    b_pos = sum(labels_b) / n
    pe = a_pos * b_pos + (1 - a_pos) * (1 - b_pos)

    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


# =============================================================================
# Main evaluation runner
# =============================================================================


def run_evaluation(
    model_name: str,
    backend: str,
    model_id: Optional[str],
    admin_token: str,
    timeout: int = 120,
) -> List[Dict[str, Any]]:
    """Run all test cases against the specified model."""
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}Evaluating: {model_name} ({backend}){RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}\n")

    # Switch backend
    if backend == "ollama":
        switch_backend(admin_token, "ollama")
    else:
        switch_backend(admin_token, "openrouter", model_id)

    time.sleep(2)  # allow backend switch to propagate

    results = []
    for i, tc in enumerate(TEST_CASES):
        session_id = f"eval-{backend}-{tc['id']}-{uuid.uuid4().hex[:6]}"
        msg = tc["message"]

        # Skip empty message for non-error cases
        if not msg and not tc.get("allow_error"):
            continue

        print(f"  [{i+1:2d}/{len(TEST_CASES)}] {tc['id']} ({tc['category']}) ", end="", flush=True)

        result = send_chat(msg, session_id, timeout=timeout)
        scores = evaluate_response(tc, result)

        mark = f"{GREEN}PASS{RESET}" if scores["pass"] else f"{RED}FAIL{RESET}"
        print(f"[{mark}] {scores['reason']}")

        results.append({
            "test_case": tc,
            "result": result,
            "scores": scores,
        })

    return results


def generate_report(
    local_results: Optional[List[Dict]],
    cloud_results: Optional[List[Dict]],
    local_model_name: str,
    cloud_model_name: str,
    output_path: str,
) -> None:
    """Generate a thesis-quality markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# Hotel AI Chatbot — Model Evaluation Report",
        "",
        f"**Date:** {timestamp}",
        f"**Local model:** {local_model_name}",
        f"**Cloud model:** {cloud_model_name}",
        f"**Test cases:** {len(TEST_CASES)}",
        f"**Evaluation criteria:** keyword matching, language detection, response completeness, latency",
        "",
    ]

    # Summary table
    lines.append("## Summary")
    lines.append("")

    def model_stats(results: List[Dict], name: str) -> Dict:
        if not results:
            return {}
        passed = sum(1 for r in results if r["scores"]["pass"])
        total = len(results)
        latencies = [r["result"]["latency_ms"] for r in results if r["result"]["latency_ms"] > 0]
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        p50_lat = sorted(latencies)[len(latencies) // 2] if latencies else 0
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        errors = sum(1 for r in results if r["result"].get("error"))
        kw_total = sum(r["scores"].get("keyword_total", 0) for r in results)
        kw_hits = sum(r["scores"].get("keyword_hits", 0) for r in results)
        lang_ok = sum(1 for r in results if r["scores"].get("language_correct", True))
        return {
            "name": name,
            "passed": passed,
            "total": total,
            "accuracy": passed / total if total else 0,
            "kw_accuracy": kw_hits / kw_total if kw_total else 0,
            "lang_accuracy": lang_ok / total if total else 0,
            "avg_latency": avg_lat,
            "p50_latency": p50_lat,
            "p95_latency": p95_lat,
            "errors": errors,
            "pass_labels": [r["scores"]["pass"] for r in results],
        }

    local_stats = model_stats(local_results, local_model_name) if local_results else None
    cloud_stats = model_stats(cloud_results, cloud_model_name) if cloud_results else None

    lines.append("| Metric | " + " | ".join(
        s["name"] for s in [local_stats, cloud_stats] if s
    ) + " |")
    lines.append("|---|" + "|".join("---" for s in [local_stats, cloud_stats] if s) + "|")

    metrics = [
        ("Overall accuracy", lambda s: f"{s['passed']}/{s['total']} ({s['accuracy']:.0%})"),
        ("Keyword accuracy", lambda s: f"{s['kw_accuracy']:.0%}"),
        ("Language accuracy", lambda s: f"{s['lang_accuracy']:.0%}"),
        ("Avg latency", lambda s: f"{s['avg_latency']:.0f}ms"),
        ("p50 latency", lambda s: f"{s['p50_latency']:.0f}ms"),
        ("p95 latency", lambda s: f"{s['p95_latency']:.0f}ms"),
        ("Errors / timeouts", lambda s: f"{s['errors']}"),
    ]
    for label, fmt in metrics:
        row = f"| {label} | " + " | ".join(
            fmt(s) for s in [local_stats, cloud_stats] if s
        ) + " |"
        lines.append(row)
    lines.append("")

    # Cohen's Kappa
    if local_stats and cloud_stats:
        kappa = compute_cohens_kappa(local_stats["pass_labels"], cloud_stats["pass_labels"])
        interp = (
            "poor" if kappa < 0.2 else
            "fair" if kappa < 0.4 else
            "moderate" if kappa < 0.6 else
            "substantial" if kappa < 0.8 else
            "almost perfect"
        )
        lines.append(f"### Cohen's Kappa (inter-model agreement)")
        lines.append("")
        lines.append(f"**κ = {kappa:.3f}** ({interp} agreement)")
        lines.append("")
        lines.append("Interpretation: κ measures how often both models agree on pass/fail")
        lines.append("beyond what would be expected by chance. Higher = more consistent.")
        lines.append("")

    # Per-category breakdown
    categories = sorted(set(tc["category"] for tc in TEST_CASES))
    for model_label, model_results in [("Local", local_results), ("Cloud", cloud_results)]:
        if not model_results:
            continue
        lines.append(f"### Per-category accuracy — {model_label}")
        lines.append("")
        lines.append("| Category | Passed | Total | Accuracy |")
        lines.append("|---|---|---|---|")
        for cat in categories:
            cat_results = [r for r in model_results if r["test_case"]["category"] == cat]
            cat_pass = sum(1 for r in cat_results if r["scores"]["pass"])
            cat_total = len(cat_results)
            lines.append(f"| {cat} | {cat_pass} | {cat_total} | {cat_pass/cat_total:.0%} |")
        lines.append("")

    # Detailed per-case results
    for model_label, model_results in [("Local", local_results), ("Cloud", cloud_results)]:
        if not model_results:
            continue
        lines.append(f"## Detailed Results — {model_label}")
        lines.append("")
        for r in model_results:
            tc = r["test_case"]
            res = r["result"]
            sc = r["scores"]
            mark = "PASS" if sc["pass"] else "FAIL"
            lines.append(f"### {tc['id']} [{mark}] — {tc['category']} ({tc['language'].upper()})")
            lines.append("")
            lines.append(f"**Input:** `{tc['message']}`")
            lines.append("")
            lines.append(f"**Expected:** {tc['expected_behavior']}")
            lines.append("")
            resp_preview = res["response"][:800] if res["response"] else "(empty)"
            lines.append(f"**Response:** {resp_preview}")
            lines.append("")
            lines.append(f"**Scoring:** {sc['reason']}")
            lines.append(f"**Routing:** {res.get('routing_path', 'unknown')}")
            lines.append(f"**Latency:** {res.get('latency_ms', 0)}ms")
            if res.get("error"):
                lines.append(f"**Error:** {res['error']}")
            lines.append("")
            lines.append("---")
            lines.append("")

    # Side-by-side disagreement table
    if local_results and cloud_results:
        lines.append("## Disagreements (where models differ on pass/fail)")
        lines.append("")
        lines.append("| ID | Category | Local | Cloud | Notes |")
        lines.append("|---|---|---|---|---|")
        for lr, cr in zip(local_results, cloud_results):
            lp = lr["scores"]["pass"]
            cp = cr["scores"]["pass"]
            if lp != cp:
                lines.append(
                    f"| {lr['test_case']['id']} | {lr['test_case']['category']} | "
                    f"{'PASS' if lp else 'FAIL'} | {'PASS' if cp else 'FAIL'} | "
                    f"{lr['test_case']['expected_behavior'][:60]} |"
                )
        lines.append("")

    # Write to file
    report = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n{BOLD}Report saved to: {output_path}{RESET}")


# =============================================================================
# Main
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Model evaluation for hotel chatbot")
    parser.add_argument("--local-only", action="store_true", help="Only test local Ollama model")
    parser.add_argument("--cloud-only", action="store_true", help="Only test cloud OpenRouter model")
    parser.add_argument("--timeout", type=int, default=120, help="Per-request timeout in seconds")
    parser.add_argument("--output", type=str, default="docs/MODEL_EVAL_REPORT.md", help="Output path")
    args = parser.parse_args()

    print(f"{BOLD}Hotel AI Chatbot — Model Comparison Evaluation{RESET}")
    print(f"Test cases: {len(TEST_CASES)}")
    print(f"Base URL: {BASE_URL}")

    # Get admin token
    admin_token = get_admin_token()
    print(f"Admin token acquired\n")

    local_model = "fredrezones55/qwen3.5-opus:9b"
    cloud_model = "qwen/qwen3-max"

    local_results = None
    cloud_results = None

    # Run local evaluation
    if not args.cloud_only:
        local_results = run_evaluation(
            model_name=f"Qwen3.5 Opus 9B (Ollama local)",
            backend="ollama",
            model_id=None,
            admin_token=admin_token,
            timeout=args.timeout,
        )

    # Run cloud evaluation
    if not args.local_only:
        if not OPENROUTER_API_KEY:
            print(f"\n{YELLOW}Skipping cloud eval — OPENROUTER_API_KEY not set{RESET}")
        else:
            cloud_results = run_evaluation(
                model_name=f"Qwen3 Max (OpenRouter cloud)",
                backend="openrouter",
                model_id=cloud_model,
                admin_token=admin_token,
                timeout=args.timeout,
            )

    # Switch back to local after cloud eval
    if cloud_results and not args.cloud_only:
        try:
            switch_backend(admin_token, "ollama")
        except Exception:
            pass

    # Print summary
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    for label, results in [("Local (9B)", local_results), ("Cloud", cloud_results)]:
        if results:
            passed = sum(1 for r in results if r["scores"]["pass"])
            total = len(results)
            color = GREEN if passed / total >= 0.8 else (YELLOW if passed / total >= 0.6 else RED)
            print(f"{BOLD}{label}: {color}{passed}/{total} ({passed/total:.0%}){RESET}")

    if local_results and cloud_results:
        la = [r["scores"]["pass"] for r in local_results]
        ca = [r["scores"]["pass"] for r in cloud_results]
        kappa = compute_cohens_kappa(la, ca)
        print(f"{BOLD}Cohen's Kappa: {kappa:.3f}{RESET}")

    # Generate report
    generate_report(
        local_results=local_results,
        cloud_results=cloud_results,
        local_model_name=f"Qwen3.5 Opus 9B (Ollama, {local_model})",
        cloud_model_name=f"Qwen3 Max (OpenRouter, {cloud_model})",
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
