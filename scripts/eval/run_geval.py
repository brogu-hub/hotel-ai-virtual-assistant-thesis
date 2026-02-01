#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
GEval RAG Evaluation Pipeline with DeepEval Metrics

Metrics:
- Faithfulness: Does the answer strictly follow the retrieved context? (No hallucinations)
- Context Recall: Did Qdrant find the right policy document?
- Answer Relevancy: Is the answer helpful to the user?

Pipeline test flow:
1. Auto-generate 20 Q&A pairs from Golden Dataset
2. Run questions through FastAPI endpoint (http://localhost:8000/chat)
3. Score using GEval (LLM-as-a-Judge) with DeepEval metrics
4. Generate test_results.html report with Pass/Fail

Target: 0.85 average score

Usage:
    # Run full evaluation
    python scripts/eval/run_geval.py

    # Custom endpoint
    python scripts/eval/run_geval.py --endpoint http://localhost:8000/chat

    # Custom number of test cases
    python scripts/eval/run_geval.py --num-tests 20

    # Quick test (5 cases)
    python scripts/eval/run_geval.py --quick
"""

import os
import sys
import json
import time
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
import random

import httpx

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Auto-load .env file from deploy/compose/.env
ENV_FILE = PROJECT_ROOT / "deploy" / "compose" / ".env"
if ENV_FILE.exists() and not os.getenv("OPENROUTER_API_KEY"):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key not in os.environ:  # Don't override existing env vars
                    os.environ[key] = value

from scripts.eval.golden_dataset import generate_golden_dataset, get_dataset_stats
from scripts.eval.models import GoldenQAPair, Language, Category, Difficulty

# Note: DeepEval dependency removed - using OpenRouter LLM-as-Judge instead
# This eliminates the need for OPENAI_API_KEY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# GEval scoring prompt with DeepEval-style metrics
GEVAL_PROMPT = """You are an expert evaluator for a hotel AI assistant RAG system.
Evaluate the AI's response using these specific metrics:

## Metrics (Score 0-10 each)

1. **Faithfulness (0-10)**: Does the answer strictly follow the retrieved context?
   - Score 10: All claims can be verified from the context, no hallucinations
   - Score 0: Contains made-up information not in context

2. **Context Recall (0-10)**: Did the system retrieve the right information?
   - Score 10: Response covers all expected keywords/information
   - Score 0: Missing critical information that should have been retrieved

3. **Answer Relevancy (0-10)**: Is the answer helpful to the user?
   - Score 10: Directly addresses the question with actionable information
   - Score 0: Irrelevant or unhelpful response

## Input

**Guest Query**: {query}

**Expected Answer (Golden)**: {expected_answer}

**Actual AI Response**: {actual_response}

**Expected Keywords** (should appear in response): {keywords}

**Retrieved Context**: {context}

## Output Format

Respond with ONLY a JSON object (no markdown):
{{
    "faithfulness": <0-10>,
    "context_recall": <0-10>,
    "answer_relevancy": <0-10>,
    "overall_score": <0-10>,
    "passed": <true/false>,
    "reason": "<brief explanation of scores>"
}}

Calculate overall_score as average of the three metrics.
Score "passed" as true if overall_score >= 7 (0.7 threshold).
"""


@dataclass
class GEvalResult:
    """Result from GEval scoring with DeepEval metrics."""
    faithfulness: float = 0.0  # No hallucinations
    context_recall: float = 0.0  # Right documents retrieved
    answer_relevancy: float = 0.0  # Helpful to user
    overall_score: float = 0.0
    passed: bool = False
    reason: str = ""


@dataclass
class TestResult:
    """Complete test result for one Q&A pair."""
    id: str
    question: str
    language: str
    category: str
    difficulty: str
    expected_answer: str
    actual_response: str
    expected_keywords: List[str]
    keywords_found: List[str]
    keywords_missing: List[str]
    keyword_score: float
    geval: GEvalResult
    latency_ms: float
    passed: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class GEvalEvaluator:
    """LLM-as-a-Judge evaluator using OpenRouter (no OpenAI dependency)."""

    def __init__(self, model: str = "openai/gpt-4o-mini"):
        self.model = model
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1"

        if self.api_key:
            logger.info(f"Using LLM-as-a-Judge via OpenRouter (model: {model})")
        else:
            logger.warning("OPENROUTER_API_KEY not set - using keyword-only scoring")

    async def score(
        self,
        query: str,
        expected_answer: str,
        actual_response: str,
        keywords: List[str],
        retrieval_context: Optional[List[str]] = None,
    ) -> GEvalResult:
        """Score a response using LLM-as-a-Judge via OpenRouter (no OpenAI dependency)."""

        context = retrieval_context or [expected_answer]

        # Use LLM-as-a-Judge via OpenRouter (primary method)
        if self.api_key:
            return await self._llm_judge_score(query, expected_answer, actual_response, keywords, context)

        # Fallback to keyword-based scoring if no API key
        return self._keyword_score(query, expected_answer, actual_response, keywords)

    async def _llm_judge_score(
        self,
        query: str,
        expected_answer: str,
        actual_response: str,
        keywords: List[str],
        context: List[str],
    ) -> GEvalResult:
        """Score using LLM-as-a-Judge via OpenRouter."""
        try:
            prompt = GEVAL_PROMPT.format(
                query=query,
                expected_answer=expected_answer,
                actual_response=actual_response,
                keywords=", ".join(keywords),
                context="\n".join(context[:3]),  # Limit context length
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "https://hotel-eval.local",
                        "X-Title": "Hotel RAG Evaluation",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 500,
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.warning(f"GEval API error: {response.status_code}")
                    return self._keyword_score(query, expected_answer, actual_response, keywords)

                data = response.json()
                content = data["choices"][0]["message"]["content"]

                # Parse JSON response - remove markdown code blocks if present
                content = content.strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                content = content.strip()

                result = json.loads(content)

                return GEvalResult(
                    faithfulness=result.get("faithfulness", 0) / 10.0,
                    context_recall=result.get("context_recall", 0) / 10.0,
                    answer_relevancy=result.get("answer_relevancy", 0) / 10.0,
                    overall_score=result.get("overall_score", 0) / 10.0,
                    passed=result.get("passed", False),
                    reason=result.get("reason", ""),
                )

        except Exception as e:
            logger.warning(f"LLM Judge scoring failed: {e}")
            return self._keyword_score(query, expected_answer, actual_response, keywords)

    def _keyword_score(
        self,
        query: str,
        expected_answer: str,
        actual_response: str,
        keywords: List[str],
    ) -> GEvalResult:
        """Fallback keyword-based scoring mapped to DeepEval metrics."""
        response_lower = actual_response.lower()
        expected_lower = expected_answer.lower()

        # Faithfulness: Check if response doesn't contradict expected (simplified)
        # Higher if response contains expected keywords
        found_kw = sum(1 for kw in keywords if kw.lower() in response_lower)
        faithfulness = found_kw / len(keywords) if keywords else 0.5

        # Context Recall: Check keyword coverage
        context_recall = faithfulness  # Same as keyword match for fallback

        # Answer Relevancy: Check if response is substantial and in right language
        query_thai = any("\u0e00" <= c <= "\u0e7f" for c in query)
        response_thai = any("\u0e00" <= c <= "\u0e7f" for c in actual_response)
        lang_match = 1.0 if query_thai == response_thai else 0.5
        length_ok = min(1.0, len(actual_response) / 100) if actual_response else 0.0
        answer_relevancy = (lang_match * 0.5 + length_ok * 0.5)

        overall = (faithfulness + context_recall + answer_relevancy) / 3

        return GEvalResult(
            faithfulness=faithfulness,
            context_recall=context_recall,
            answer_relevancy=answer_relevancy,
            overall_score=overall,
            passed=overall >= 0.7,
            reason=f"Keyword fallback: {found_kw}/{len(keywords)} keywords, lang_match={lang_match:.0%}",
        )


class HotelAPIClient:
    """Client for calling the Hotel AI API."""

    def __init__(self, endpoint: str = "http://localhost:8000/chat"):
        self.endpoint = endpoint

    async def chat(self, message: str) -> tuple[str, float, Optional[List[str]]]:
        """Send a message and get response with latency and retrieval context."""
        start_time = time.time()

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.endpoint,
                    json={"message": message},
                    timeout=60.0,
                )

                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    response_text = data.get("response", "")
                    # Try to get retrieval context if available
                    sources = data.get("sources", [])
                    retrieval_context = data.get("retrieval_context", sources)
                    return response_text, latency_ms, retrieval_context
                else:
                    logger.warning(f"API error {response.status_code}: {response.text[:200]}")
                    return f"Error: {response.status_code}", latency_ms, None

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"API call failed: {e}")
            return f"Error: {str(e)}", latency_ms, None


def select_test_cases(num_tests: int = 20) -> List[GoldenQAPair]:
    """Select diverse test cases from golden dataset."""
    dataset = generate_golden_dataset()
    all_pairs = dataset.pairs

    if num_tests >= len(all_pairs):
        return all_pairs

    # Stratified sampling: ensure diversity
    selected = []

    # Group by category
    by_category: Dict[str, List[GoldenQAPair]] = {}
    for pair in all_pairs:
        cat = pair.category.value
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(pair)

    # Select proportionally from each category
    per_category = max(1, num_tests // len(by_category))

    for cat, pairs in by_category.items():
        # Balance English and Thai
        en_pairs = [p for p in pairs if p.language == Language.ENGLISH]
        th_pairs = [p for p in pairs if p.language == Language.THAI]

        # Select half from each language
        half = per_category // 2
        selected.extend(random.sample(en_pairs, min(half, len(en_pairs))))
        selected.extend(random.sample(th_pairs, min(half, len(th_pairs))))

    # Fill remaining slots randomly
    remaining = [p for p in all_pairs if p not in selected]
    while len(selected) < num_tests and remaining:
        pair = random.choice(remaining)
        selected.append(pair)
        remaining.remove(pair)

    return selected[:num_tests]


async def run_evaluation(
    test_cases: List[GoldenQAPair],
    api_client: HotelAPIClient,
    evaluator: GEvalEvaluator,
    verbose: bool = True,
) -> List[TestResult]:
    """Run evaluation on all test cases."""
    results = []
    total = len(test_cases)

    logger.info(f"Starting evaluation of {total} test cases...")
    logger.info(f"API Endpoint: {api_client.endpoint}")
    logger.info(f"Metrics: Faithfulness, Context Recall, Answer Relevancy")

    for i, test_case in enumerate(test_cases):
        if verbose:
            logger.info(f"[{i+1}/{total}] {test_case.id}: {test_case.question[:50]}...")

        # Call API
        actual_response, latency_ms, retrieval_context = await api_client.chat(test_case.question)

        # Check keywords
        response_lower = actual_response.lower()
        keywords_found = [kw for kw in test_case.expected_keywords if kw.lower() in response_lower]
        keywords_missing = [kw for kw in test_case.expected_keywords if kw.lower() not in response_lower]
        keyword_score = len(keywords_found) / len(test_case.expected_keywords) if test_case.expected_keywords else 0.5

        # GEval scoring with DeepEval metrics
        geval_result = await evaluator.score(
            query=test_case.question,
            expected_answer=test_case.expected_answer,
            actual_response=actual_response,
            keywords=test_case.expected_keywords,
            retrieval_context=retrieval_context or [test_case.expected_answer],
        )

        # Create result
        result = TestResult(
            id=test_case.id,
            question=test_case.question,
            language=test_case.language.value,
            category=test_case.category.value,
            difficulty=test_case.difficulty.value,
            expected_answer=test_case.expected_answer,
            actual_response=actual_response,
            expected_keywords=test_case.expected_keywords,
            keywords_found=keywords_found,
            keywords_missing=keywords_missing,
            keyword_score=keyword_score,
            geval=geval_result,
            latency_ms=latency_ms,
            passed=geval_result.passed,
        )
        results.append(result)

        # Log result with DeepEval metrics
        status = "✓ PASS" if result.passed else "✗ FAIL"
        if verbose:
            logger.info(
                f"  {status} | F={geval_result.faithfulness:.2f} CR={geval_result.context_recall:.2f} "
                f"AR={geval_result.answer_relevancy:.2f} | overall={geval_result.overall_score:.2f} | "
                f"latency={latency_ms:.0f}ms"
            )

        # Rate limiting
        await asyncio.sleep(0.5)

    return results


def generate_html_report(results: List[TestResult], output_path: str = "test_results.html") -> str:
    """Generate HTML report with Pass/Fail for each question."""

    # Calculate summary statistics
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = passed / total if total > 0 else 0

    avg_score = sum(r.geval.overall_score for r in results) / total if total > 0 else 0
    avg_latency = sum(r.latency_ms for r in results) / total if total > 0 else 0

    # By language
    en_results = [r for r in results if r.language == "en"]
    th_results = [r for r in results if r.language == "th"]
    en_pass_rate = sum(1 for r in en_results if r.passed) / len(en_results) if en_results else 0
    th_pass_rate = sum(1 for r in th_results if r.passed) / len(th_results) if th_results else 0

    # By category
    categories = set(r.category for r in results)
    category_stats = {}
    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        category_stats[cat] = {
            "total": len(cat_results),
            "passed": sum(1 for r in cat_results if r.passed),
            "avg_score": sum(r.geval.overall_score for r in cat_results) / len(cat_results),
        }

    # Calculate metric averages
    avg_faithfulness = sum(r.geval.faithfulness for r in results) / total if total > 0 else 0
    avg_context_recall = sum(r.geval.context_recall for r in results) / total if total > 0 else 0
    avg_answer_relevancy = sum(r.geval.answer_relevancy for r in results) / total if total > 0 else 0

    # Generate HTML
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_score = 0.85
    score_color = "green" if avg_score >= target_score else "orange" if avg_score >= 0.7 else "red"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hotel AI RAG Evaluation Report - DeepEval Metrics</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 20px;
        }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .header p {{ margin: 0; opacity: 0.9; }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }}
        .stat-card .label {{
            color: #666;
            margin-top: 5px;
        }}
        .stat-card.score .value {{ color: {score_color}; }}
        .stat-card.target {{ border: 2px dashed #667eea; }}

        .section {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .section h2 {{
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}
        tr:hover {{ background: #f8f9fa; }}

        .pass {{
            color: #28a745;
            background: #d4edda;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
        }}
        .fail {{
            color: #dc3545;
            background: #f8d7da;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
        }}

        .score-bar {{
            width: 100px;
            height: 8px;
            background: #eee;
            border-radius: 4px;
            overflow: hidden;
            display: inline-block;
            vertical-align: middle;
            margin-right: 8px;
        }}
        .score-bar-fill {{
            height: 100%;
            border-radius: 4px;
        }}
        .score-bar-fill.high {{ background: #28a745; }}
        .score-bar-fill.medium {{ background: #ffc107; }}
        .score-bar-fill.low {{ background: #dc3545; }}

        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }}
        .badge-en {{ background: #e3f2fd; color: #1976d2; }}
        .badge-th {{ background: #fff3e0; color: #f57c00; }}
        .badge-easy {{ background: #e8f5e9; color: #388e3c; }}
        .badge-medium {{ background: #fff8e1; color: #ffa000; }}
        .badge-hard {{ background: #ffebee; color: #d32f2f; }}

        .details {{ font-size: 12px; color: #666; }}
        .keywords {{ font-size: 11px; }}
        .keywords .found {{ color: #28a745; }}
        .keywords .missing {{ color: #dc3545; }}

        .expandable {{
            cursor: pointer;
        }}
        .expandable:hover {{
            background: #e8f4fd;
        }}
        .expanded-content {{
            display: none;
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }}
        .expanded-content.show {{ display: block; }}

        .progress-ring {{
            width: 120px;
            height: 120px;
        }}

        footer {{
            text-align: center;
            color: #666;
            padding: 20px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🏨 Hotel AI RAG Evaluation Report</h1>
        <p>DeepEval Metrics (Faithfulness, Context Recall, Answer Relevancy) • Generated: {timestamp}</p>
    </div>

    <div class="summary">
        <div class="stat-card score">
            <div class="value">{avg_score:.1%}</div>
            <div class="label">Overall Score</div>
        </div>
        <div class="stat-card target">
            <div class="value">{target_score:.0%}</div>
            <div class="label">Target Score</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color: #28a745;">{passed}</div>
            <div class="label">Passed</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color: #dc3545;">{failed}</div>
            <div class="label">Failed</div>
        </div>
        <div class="stat-card">
            <div class="value">{pass_rate:.0%}</div>
            <div class="label">Pass Rate</div>
        </div>
        <div class="stat-card">
            <div class="value">{avg_latency:.0f}ms</div>
            <div class="label">Avg Latency</div>
        </div>
    </div>

    <div class="section">
        <h2>📊 DeepEval Metrics Summary</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Description</th>
                <th>Score</th>
                <th>Status</th>
            </tr>
            <tr>
                <td><strong>Faithfulness</strong></td>
                <td>No hallucinations - answer follows retrieved context</td>
                <td>
                    <div class="score-bar">
                        <div class="score-bar-fill {'high' if avg_faithfulness >= 0.85 else 'medium' if avg_faithfulness >= 0.7 else 'low'}"
                             style="width: {avg_faithfulness * 100}%"></div>
                    </div>
                    {avg_faithfulness:.2f}
                </td>
                <td><span class="{'pass' if avg_faithfulness >= 0.7 else 'fail'}">{'✓' if avg_faithfulness >= 0.7 else '✗'}</span></td>
            </tr>
            <tr>
                <td><strong>Context Recall</strong></td>
                <td>Qdrant retrieved the right documents</td>
                <td>
                    <div class="score-bar">
                        <div class="score-bar-fill {'high' if avg_context_recall >= 0.85 else 'medium' if avg_context_recall >= 0.7 else 'low'}"
                             style="width: {avg_context_recall * 100}%"></div>
                    </div>
                    {avg_context_recall:.2f}
                </td>
                <td><span class="{'pass' if avg_context_recall >= 0.7 else 'fail'}">{'✓' if avg_context_recall >= 0.7 else '✗'}</span></td>
            </tr>
            <tr>
                <td><strong>Answer Relevancy</strong></td>
                <td>Answer is helpful to the user</td>
                <td>
                    <div class="score-bar">
                        <div class="score-bar-fill {'high' if avg_answer_relevancy >= 0.85 else 'medium' if avg_answer_relevancy >= 0.7 else 'low'}"
                             style="width: {avg_answer_relevancy * 100}%"></div>
                    </div>
                    {avg_answer_relevancy:.2f}
                </td>
                <td><span class="{'pass' if avg_answer_relevancy >= 0.7 else 'fail'}">{'✓' if avg_answer_relevancy >= 0.7 else '✗'}</span></td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>📊 Performance by Language</h2>
        <table>
            <tr>
                <th>Language</th>
                <th>Tests</th>
                <th>Pass Rate</th>
                <th>Score</th>
            </tr>
            <tr>
                <td><span class="badge badge-en">English</span></td>
                <td>{len(en_results)}</td>
                <td>{en_pass_rate:.0%}</td>
                <td>
                    <div class="score-bar">
                        <div class="score-bar-fill {'high' if en_pass_rate >= 0.85 else 'medium' if en_pass_rate >= 0.7 else 'low'}"
                             style="width: {en_pass_rate * 100}%"></div>
                    </div>
                    {en_pass_rate:.2f}
                </td>
            </tr>
            <tr>
                <td><span class="badge badge-th">Thai</span></td>
                <td>{len(th_results)}</td>
                <td>{th_pass_rate:.0%}</td>
                <td>
                    <div class="score-bar">
                        <div class="score-bar-fill {'high' if th_pass_rate >= 0.85 else 'medium' if th_pass_rate >= 0.7 else 'low'}"
                             style="width: {th_pass_rate * 100}%"></div>
                    </div>
                    {th_pass_rate:.2f}
                </td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>📁 Performance by Category</h2>
        <table>
            <tr>
                <th>Category</th>
                <th>Tests</th>
                <th>Passed</th>
                <th>Avg Score</th>
            </tr>
"""

    for cat, stats in sorted(category_stats.items()):
        cat_pass_rate = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
        score_class = "high" if stats["avg_score"] >= 0.85 else "medium" if stats["avg_score"] >= 0.7 else "low"
        html += f"""            <tr>
                <td>{cat.title()}</td>
                <td>{stats["total"]}</td>
                <td>{stats["passed"]}/{stats["total"]} ({cat_pass_rate:.0%})</td>
                <td>
                    <div class="score-bar">
                        <div class="score-bar-fill {score_class}" style="width: {stats['avg_score'] * 100}%"></div>
                    </div>
                    {stats['avg_score']:.2f}
                </td>
            </tr>
"""

    html += """        </table>
    </div>

    <div class="section">
        <h2>📝 Detailed Test Results</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Question</th>
                <th>Lang</th>
                <th>Category</th>
                <th>Score</th>
                <th>Keywords</th>
                <th>Latency</th>
                <th>Status</th>
            </tr>
"""

    for r in results:
        status_class = "pass" if r.passed else "fail"
        status_text = "PASS" if r.passed else "FAIL"
        score_class = "high" if r.geval.overall_score >= 0.85 else "medium" if r.geval.overall_score >= 0.7 else "low"
        lang_class = f"badge-{r.language}"
        diff_class = f"badge-{r.difficulty}"

        # Truncate question for display
        question_display = r.question[:60] + "..." if len(r.question) > 60 else r.question

        html += f"""            <tr class="expandable" onclick="toggleDetails('{r.id}')">
                <td><code>{r.id}</code></td>
                <td title="{r.question}">{question_display}</td>
                <td><span class="badge {lang_class}">{r.language.upper()}</span></td>
                <td>{r.category}</td>
                <td>
                    <div class="score-bar">
                        <div class="score-bar-fill {score_class}" style="width: {r.geval.overall_score * 100}%"></div>
                    </div>
                    {r.geval.overall_score:.2f}
                </td>
                <td class="keywords">
                    <span class="found">{len(r.keywords_found)}</span>/<span>{len(r.expected_keywords)}</span>
                </td>
                <td>{r.latency_ms:.0f}ms</td>
                <td><span class="{status_class}">{status_text}</span></td>
            </tr>
            <tr>
                <td colspan="8">
                    <div id="details-{r.id}" class="expanded-content">
                        <p><strong>Question:</strong> {r.question}</p>
                        <p><strong>Expected:</strong> {r.expected_answer}</p>
                        <p><strong>Actual:</strong> {r.actual_response}</p>
                        <p><strong>GEval Reason:</strong> {r.geval.reason}</p>
                        <p class="keywords">
                            <strong>Keywords Found:</strong> <span class="found">{', '.join(r.keywords_found) or 'None'}</span><br>
                            <strong>Keywords Missing:</strong> <span class="missing">{', '.join(r.keywords_missing) or 'None'}</span>
                        </p>
                        <p><strong>DeepEval Metrics:</strong>
                            Faithfulness: {r.geval.faithfulness:.2f} |
                            Context Recall: {r.geval.context_recall:.2f} |
                            Answer Relevancy: {r.geval.answer_relevancy:.2f}
                        </p>
                    </div>
                </td>
            </tr>
"""

    html += f"""        </table>
    </div>

    <div class="section">
        <h2>📈 Score Analysis</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Average</th>
                <th>Target</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>Overall Score</td>
                <td>{avg_score:.2f}</td>
                <td>{target_score}</td>
                <td><span class="{'pass' if avg_score >= target_score else 'fail'}">{'✓ MET' if avg_score >= target_score else '✗ NOT MET'}</span></td>
            </tr>
            <tr>
                <td>Pass Rate</td>
                <td>{pass_rate:.0%}</td>
                <td>85%</td>
                <td><span class="{'pass' if pass_rate >= 0.85 else 'fail'}">{'✓ MET' if pass_rate >= 0.85 else '✗ NOT MET'}</span></td>
            </tr>
        </table>
    </div>

    <footer>
        <p>Generated by Hotel AI RAG Evaluation Pipeline</p>
        <p>Total Tests: {total} | Passed: {passed} | Failed: {failed}</p>
    </footer>

    <script>
        function toggleDetails(id) {{
            const details = document.getElementById('details-' + id);
            details.classList.toggle('show');
        }}
    </script>
</body>
</html>
"""

    # Write to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTML report saved to: {output_file}")
    return str(output_file)


def print_summary(results: List[TestResult]) -> None:
    """Print evaluation summary to console."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = passed / total if total > 0 else 0
    avg_score = sum(r.geval.overall_score for r in results) / total if total > 0 else 0

    print("\n" + "=" * 70)
    print("                    EVALUATION SUMMARY")
    print("=" * 70)
    print(f"  Total Tests:    {total}")
    print(f"  Passed:         {passed} ({'✓' if passed > 0 else ''})")
    print(f"  Failed:         {failed} ({'✗' if failed > 0 else ''})")
    print(f"  Pass Rate:      {pass_rate:.1%}")
    print(f"  Average Score:  {avg_score:.3f}")
    print(f"  Target Score:   0.850")
    print("-" * 70)

    if avg_score >= 0.85:
        print("  ✅ TARGET ACHIEVED!")
    else:
        print(f"  ❌ Target not met. Need +{(0.85 - avg_score):.3f} to reach 0.85")

    print("=" * 70)


async def main():
    parser = argparse.ArgumentParser(description="GEval RAG Evaluation Pipeline")
    parser.add_argument("--endpoint", default="http://localhost:8000/chat", help="API endpoint URL")
    parser.add_argument("--num-tests", type=int, default=20, help="Number of test cases")
    parser.add_argument("--quick", action="store_true", help="Quick test (5 cases)")
    parser.add_argument("--output", default="test_results.html", help="Output HTML file")
    parser.add_argument("--model", default="openai/gpt-4o-mini", help="GEval model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    num_tests = 5 if args.quick else args.num_tests

    print("\n" + "=" * 70)
    print("          🏨 HOTEL AI RAG EVALUATION PIPELINE")
    print("=" * 70)
    print(f"  Endpoint:     {args.endpoint}")
    print(f"  Test Cases:   {num_tests}")
    print(f"  GEval Model:  {args.model}")
    print(f"  Output:       {args.output}")
    print("=" * 70 + "\n")

    # Select test cases
    logger.info("Selecting test cases from golden dataset...")
    test_cases = select_test_cases(num_tests)

    stats = {}
    for tc in test_cases:
        lang = tc.language.value
        stats[lang] = stats.get(lang, 0) + 1
    logger.info(f"Selected {len(test_cases)} test cases: {stats}")

    # Initialize clients
    api_client = HotelAPIClient(args.endpoint)
    evaluator = GEvalEvaluator(args.model)

    # Run evaluation
    results = await run_evaluation(test_cases, api_client, evaluator, verbose=args.verbose)

    # Generate HTML report
    html_path = generate_html_report(results, args.output)

    # Print summary
    print_summary(results)

    print(f"\n📊 HTML Report: {html_path}")
    print(f"   Open in browser: file://{Path(html_path).absolute()}\n")


if __name__ == "__main__":
    asyncio.run(main())
