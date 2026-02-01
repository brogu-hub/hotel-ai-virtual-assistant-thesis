#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
DeepEval RAG Evaluation Runner

Runs comprehensive evaluation using DeepEval metrics:
- Faithfulness: Does the response follow the retrieved context?
- Answer Relevancy: Is the response relevant to the question?
- Context Recall: Were the right documents retrieved?
- Bilingual Helpfulness: Custom metric for Thai/English responses

Supports TWO evaluation modes:
1. Golden Dataset Mode: Evaluate against golden Q&A pairs (calls live API)
2. Log Evaluation Mode: Evaluate logged conversations from feedback files

Usage:
    # Mode 1: Evaluate against golden dataset (calls live API)
    python scripts/eval/run_deepeval.py

    # Mode 2: Evaluate logged conversations (NO API calls)
    python scripts/eval/run_deepeval.py --logs logs/feedback

    # Filter logs by routing path
    python scripts/eval/run_deepeval.py --logs logs/feedback --routing-path nemo

    # Filter logs by date
    python scripts/eval/run_deepeval.py --logs logs/feedback --date 2024-01-15

    # Run specific category (golden dataset mode)
    python scripts/eval/run_deepeval.py --category dining

    # Run specific language
    python scripts/eval/run_deepeval.py --language en

    # Quick test (first 5 cases)
    python scripts/eval/run_deepeval.py --quick

    # Save results to file
    python scripts/eval/run_deepeval.py --output results.json
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.eval.golden_dataset import generate_golden_dataset, get_dataset_stats
from scripts.eval.models import GoldenQAPair, Language, Category, Difficulty


@dataclass
class LoggedConversation:
    """A logged conversation from feedback files."""
    request_id: str
    session_id: str
    timestamp: str
    query: str
    response: str
    routing_path: str
    complexity: str
    latency_ms: float
    existing_score: Optional[float] = None

    @property
    def language(self) -> str:
        """Detect language from query."""
        thai_chars = sum(1 for c in self.query if "\u0e00" <= c <= "\u0e7f")
        return "th" if thai_chars > len(self.query) * 0.2 else "en"


class FeedbackLogLoader:
    """Loads logged conversations from feedback JSONL files."""

    def __init__(self, feedback_dir: str = "logs/feedback"):
        self.feedback_dir = Path(feedback_dir)

    def load_conversations(
        self,
        date_filter: Optional[str] = None,
        routing_path_filter: Optional[str] = None,
        complexity_filter: Optional[str] = None,
        unevaluated_only: bool = False,
        limit: Optional[int] = None,
    ) -> List[LoggedConversation]:
        """
        Load logged conversations from feedback files.

        Args:
            date_filter: Only load from specific date (YYYY-MM-DD)
            routing_path_filter: Filter by routing path (nemo/langgraph)
            complexity_filter: Filter by complexity (simple/moderate/complex)
            unevaluated_only: Only load records without scores
            limit: Maximum number of records to load

        Returns:
            List of LoggedConversation objects
        """
        conversations = []

        # Find feedback files
        if date_filter:
            pattern = f"feedback_{date_filter}.jsonl"
            files = list(self.feedback_dir.glob(pattern))
        else:
            files = sorted(self.feedback_dir.glob("feedback_*.jsonl"), reverse=True)

        if not files:
            logger.warning(f"No feedback files found in {self.feedback_dir}")
            return []

        logger.info(f"Found {len(files)} feedback files")

        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue

                        record = json.loads(line)

                        # Apply filters
                        if routing_path_filter and record.get("routing_path") != routing_path_filter:
                            continue
                        if complexity_filter and record.get("complexity") != complexity_filter:
                            continue
                        if unevaluated_only and record.get("score") is not None:
                            continue

                        conv = LoggedConversation(
                            request_id=record.get("request_id", "unknown"),
                            session_id=record.get("session_id", "unknown"),
                            timestamp=record.get("timestamp", ""),
                            query=record.get("query", ""),
                            response=record.get("response", ""),
                            routing_path=record.get("routing_path", "unknown"),
                            complexity=record.get("complexity", "unknown"),
                            latency_ms=record.get("latency_ms", 0.0),
                            existing_score=record.get("score"),
                        )

                        if conv.query and conv.response:  # Only include valid conversations
                            conversations.append(conv)

                            if limit and len(conversations) >= limit:
                                return conversations

            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")

        logger.info(f"Loaded {len(conversations)} conversations from logs")
        return conversations

    def get_stats(self, conversations: List[LoggedConversation]) -> Dict[str, Any]:
        """Get statistics about loaded conversations."""
        if not conversations:
            return {"total": 0}

        by_path = {}
        by_complexity = {}
        by_language = {}

        for conv in conversations:
            by_path[conv.routing_path] = by_path.get(conv.routing_path, 0) + 1
            by_complexity[conv.complexity] = by_complexity.get(conv.complexity, 0) + 1
            by_language[conv.language] = by_language.get(conv.language, 0) + 1

        return {
            "total": len(conversations),
            "by_routing_path": by_path,
            "by_complexity": by_complexity,
            "by_language": by_language,
            "evaluated": sum(1 for c in conversations if c.existing_score is not None),
            "unevaluated": sum(1 for c in conversations if c.existing_score is None),
        }

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# DeepEval imports (optional - graceful fallback if not installed)
try:
    from deepeval import evaluate
    from deepeval.metrics import (
        FaithfulnessMetric,
        AnswerRelevancyMetric,
        ContextualRecallMetric,
        GEval,
    )
    from deepeval.test_case import LLMTestCase
    DEEPEVAL_AVAILABLE = True
except ImportError:
    DEEPEVAL_AVAILABLE = False
    logger.warning("DeepEval not installed. Using keyword-based evaluation.")


@dataclass
class TestCaseResult:
    """Result for a single test case."""
    id: str
    question: str
    language: str
    category: str
    difficulty: str

    # Scores (0.0 - 1.0)
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_recall: float = 0.0
    helpfulness: float = 0.0
    keyword_match: float = 0.0

    # Computed
    average_score: float = 0.0
    passed: bool = False

    # Details
    actual_output: str = ""
    expected_output: str = ""
    retrieval_context: List[str] = field(default_factory=list)
    latency_ms: float = 0.0

    # Failure analysis
    failure_reasons: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    """Complete evaluation report."""
    timestamp: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    pass_rate: float

    # Average scores
    avg_faithfulness: float
    avg_answer_relevancy: float
    avg_context_recall: float
    avg_helpfulness: float
    avg_keyword_match: float

    # Latency
    avg_latency_ms: float
    p95_latency_ms: float

    # By language
    english_pass_rate: float
    thai_pass_rate: float

    # By category
    category_scores: Dict[str, float]

    # By difficulty
    difficulty_scores: Dict[str, float]

    # Improvement areas
    worst_categories: List[str]
    worst_test_cases: List[str]
    improvement_recommendations: List[str]

    # All results
    results: List[TestCaseResult]


class KeywordEvaluator:
    """Simple keyword-based evaluator when DeepEval is not available."""

    def evaluate_keywords(self, response: str, keywords: List[str]) -> float:
        """Check what percentage of expected keywords are present."""
        if not keywords:
            return 1.0

        response_lower = response.lower()
        matches = sum(1 for kw in keywords if kw.lower() in response_lower)
        return matches / len(keywords)

    def evaluate_relevancy(self, question: str, response: str) -> float:
        """Simple relevancy check based on response length and content."""
        if not response or len(response) < 20:
            return 0.2

        # Check if response mentions key terms from question
        question_words = set(question.lower().split())
        response_words = set(response.lower().split())
        overlap = len(question_words & response_words)

        score = min(1.0, 0.5 + (overlap / max(len(question_words), 1)) * 0.5)
        return score

    def evaluate_helpfulness(self, response: str, expected: str) -> float:
        """Compare response to expected answer."""
        if not response:
            return 0.0

        # Normalize
        response_lower = response.lower()
        expected_lower = expected.lower()

        # Check for key phrases
        expected_phrases = expected_lower.split(". ")
        matches = sum(1 for phrase in expected_phrases if phrase[:20] in response_lower)

        score = min(1.0, matches / max(len(expected_phrases), 1))
        return max(score, 0.3)  # Minimum 0.3 if response exists


class RAGEvaluator:
    """Evaluates RAG responses using DeepEval or fallback methods."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8081",
        pass_threshold: float = 0.7,
        use_deepeval: bool = True,
    ):
        self.endpoint_url = endpoint_url
        self.pass_threshold = pass_threshold
        self.use_deepeval = use_deepeval and DEEPEVAL_AVAILABLE
        self.keyword_evaluator = KeywordEvaluator()

        if self.use_deepeval:
            logger.info("Using DeepEval metrics for evaluation")
            self._init_deepeval_metrics()
        else:
            logger.info("Using keyword-based evaluation (DeepEval not available)")

    def _init_deepeval_metrics(self):
        """Initialize DeepEval metrics."""
        # Use OpenRouter as the judge model
        judge_model = os.getenv("DEEPEVAL_JUDGE_MODEL", "qwen/qwen3-max")

        self.faithfulness_metric = FaithfulnessMetric(
            threshold=self.pass_threshold,
            model=judge_model,
        )
        self.relevancy_metric = AnswerRelevancyMetric(
            threshold=self.pass_threshold,
            model=judge_model,
        )
        self.recall_metric = ContextualRecallMetric(
            threshold=self.pass_threshold,
            model=judge_model,
        )
        # Custom bilingual helpfulness metric
        self.helpfulness_metric = GEval(
            name="Bilingual Helpfulness",
            criteria="""Evaluate the response for a hotel concierge chatbot:
            1. Accuracy: Information matches hotel policies and services
            2. Completeness: All parts of the question are addressed
            3. Language: Response is in the same language as the question
            4. Professionalism: Polite and helpful tone
            5. Actionability: Guest knows what to do next""",
            evaluation_params=["actual_output", "expected_output"],
            threshold=self.pass_threshold,
            model=judge_model,
        )

    async def get_response(self, question: str) -> Dict[str, Any]:
        """Get response from the RAG endpoint."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                start_time = time.time()
                response = await client.post(
                    f"{self.endpoint_url}/chat",
                    json={"message": question},
                    timeout=60.0,
                )
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "response": data.get("response", ""),
                        "sources": data.get("sources", []),
                        "retrieval_context": data.get("retrieval_context", []),
                        "latency_ms": latency_ms,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "latency_ms": latency_ms,
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "latency_ms": 0,
            }

    async def evaluate_test_case(self, test_case: GoldenQAPair) -> TestCaseResult:
        """Evaluate a single test case."""
        result = TestCaseResult(
            id=test_case.id,
            question=test_case.question,
            language=test_case.language.value,
            category=test_case.category.value,
            difficulty=test_case.difficulty.value,
            expected_output=test_case.expected_answer,
        )

        # Get response from endpoint
        response_data = await self.get_response(test_case.question)

        if not response_data["success"]:
            result.failure_reasons.append(f"API error: {response_data.get('error')}")
            result.improvement_suggestions.append("Fix API connectivity issues")
            return result

        result.actual_output = response_data["response"]
        result.latency_ms = response_data["latency_ms"]
        result.retrieval_context = response_data.get("retrieval_context", [])

        # Keyword match (always run)
        result.keyword_match = self.keyword_evaluator.evaluate_keywords(
            result.actual_output, test_case.expected_keywords
        )

        if self.use_deepeval:
            # Run DeepEval metrics
            await self._run_deepeval_metrics(test_case, result)
        else:
            # Use keyword-based evaluation
            result.answer_relevancy = self.keyword_evaluator.evaluate_relevancy(
                test_case.question, result.actual_output
            )
            result.helpfulness = self.keyword_evaluator.evaluate_helpfulness(
                result.actual_output, test_case.expected_answer
            )
            result.faithfulness = result.keyword_match  # Approximate
            result.context_recall = 0.7 if result.retrieval_context else 0.5

        # Calculate average score
        scores = [
            result.faithfulness,
            result.answer_relevancy,
            result.context_recall,
            result.helpfulness,
            result.keyword_match,
        ]
        result.average_score = sum(scores) / len(scores)
        result.passed = result.average_score >= self.pass_threshold

        # Analyze failures
        self._analyze_failures(test_case, result)

        return result

    async def _run_deepeval_metrics(
        self, test_case: GoldenQAPair, result: TestCaseResult
    ):
        """Run DeepEval metrics on the test case."""
        try:
            # Create LLM test case
            llm_test_case = LLMTestCase(
                input=test_case.question,
                actual_output=result.actual_output,
                expected_output=test_case.expected_answer,
                retrieval_context=result.retrieval_context or ["No context retrieved"],
            )

            # Run each metric with delay (rate limiting)
            await asyncio.sleep(3.5)  # Rate limit for OpenRouter

            try:
                self.faithfulness_metric.measure(llm_test_case)
                result.faithfulness = self.faithfulness_metric.score or 0.0
            except Exception as e:
                logger.warning(f"Faithfulness metric failed: {e}")
                result.faithfulness = result.keyword_match

            await asyncio.sleep(3.5)

            try:
                self.relevancy_metric.measure(llm_test_case)
                result.answer_relevancy = self.relevancy_metric.score or 0.0
            except Exception as e:
                logger.warning(f"Relevancy metric failed: {e}")
                result.answer_relevancy = 0.5

            await asyncio.sleep(3.5)

            try:
                self.recall_metric.measure(llm_test_case)
                result.context_recall = self.recall_metric.score or 0.0
            except Exception as e:
                logger.warning(f"Context recall metric failed: {e}")
                result.context_recall = 0.5

            await asyncio.sleep(3.5)

            try:
                self.helpfulness_metric.measure(llm_test_case)
                result.helpfulness = self.helpfulness_metric.score or 0.0
            except Exception as e:
                logger.warning(f"Helpfulness metric failed: {e}")
                result.helpfulness = 0.5

        except Exception as e:
            logger.error(f"DeepEval metrics failed: {e}")
            # Fallback to keyword evaluation
            result.faithfulness = result.keyword_match
            result.answer_relevancy = 0.5
            result.context_recall = 0.5
            result.helpfulness = 0.5

    def _analyze_failures(self, test_case: GoldenQAPair, result: TestCaseResult):
        """Analyze why a test case might have failed."""
        if result.keyword_match < 0.5:
            missing = [kw for kw in test_case.expected_keywords
                      if kw.lower() not in result.actual_output.lower()]
            result.failure_reasons.append(f"Missing keywords: {missing[:3]}")
            result.improvement_suggestions.append(
                f"Ensure RAG retrieves content with: {', '.join(missing[:3])}"
            )

        if result.faithfulness < 0.7:
            result.failure_reasons.append("Response may contain hallucinations")
            result.improvement_suggestions.append(
                "Improve grounding - response should closely follow retrieved context"
            )

        if result.answer_relevancy < 0.7:
            result.failure_reasons.append("Response not relevant to question")
            result.improvement_suggestions.append(
                "Check query understanding and response generation prompt"
            )

        if result.context_recall < 0.7:
            result.failure_reasons.append(
                f"Wrong documents retrieved. Expected: {test_case.expected_context}"
            )
            result.improvement_suggestions.append(
                "Improve retrieval - check embeddings and reranking"
            )

        # Language mismatch check
        query_thai = any("\u0e00" <= c <= "\u0e7f" for c in test_case.question)
        response_thai = any("\u0e00" <= c <= "\u0e7f" for c in result.actual_output)
        if query_thai != response_thai:
            result.failure_reasons.append("Language mismatch between query and response")
            result.improvement_suggestions.append(
                "Add language detection to ensure response matches query language"
            )

    def _analyze_logged_failures(self, result: TestCaseResult):
        """Analyze failures for logged conversations (no expected keywords)."""
        if result.faithfulness < 0.7:
            result.failure_reasons.append("Response may contain hallucinations")
            result.improvement_suggestions.append(
                "Improve grounding - response should closely follow retrieved context"
            )

        if result.answer_relevancy < 0.7:
            result.failure_reasons.append("Response not relevant to question")
            result.improvement_suggestions.append(
                "Check query understanding and response generation prompt"
            )

        if result.helpfulness < 0.7:
            result.failure_reasons.append("Response not helpful enough")
            result.improvement_suggestions.append(
                "Improve response generation to be more actionable and complete"
            )

        # Language mismatch check
        query_thai = any("\u0e00" <= c <= "\u0e7f" for c in result.question)
        response_thai = any("\u0e00" <= c <= "\u0e7f" for c in result.actual_output)
        if query_thai != response_thai:
            result.failure_reasons.append("Language mismatch between query and response")
            result.improvement_suggestions.append(
                "Add language detection to ensure response matches query language"
            )

    async def evaluate_logged_conversation(
        self, conv: "LoggedConversation"
    ) -> TestCaseResult:
        """
        Evaluate a logged conversation.

        Unlike evaluate_test_case, this doesn't call the API - it uses
        the already-stored response from the feedback logs.
        """
        result = TestCaseResult(
            id=conv.request_id,
            question=conv.query,
            language=conv.language,
            category=conv.routing_path,  # Use routing path as category for logs
            difficulty=conv.complexity,
            actual_output=conv.response,
            expected_output="",  # No expected output for logs
            latency_ms=conv.latency_ms,
        )

        # No keyword match for logged conversations (no expected keywords)
        result.keyword_match = 0.7  # Neutral default

        if self.use_deepeval:
            # Run DeepEval metrics
            await self._run_deepeval_metrics_for_logs(conv, result)
        else:
            # Use keyword-based evaluation
            result.answer_relevancy = self.keyword_evaluator.evaluate_relevancy(
                conv.query, conv.response
            )
            result.helpfulness = 0.6  # Neutral default without expected answer
            result.faithfulness = 0.6  # Neutral default
            result.context_recall = 0.6  # No context for logs

        # Calculate average score
        scores = [
            result.faithfulness,
            result.answer_relevancy,
            result.helpfulness,
        ]
        result.average_score = sum(scores) / len(scores)
        result.passed = result.average_score >= self.pass_threshold

        # Analyze failures
        self._analyze_logged_failures(result)

        return result

    async def _run_deepeval_metrics_for_logs(
        self, conv: "LoggedConversation", result: TestCaseResult
    ):
        """Run DeepEval metrics on a logged conversation."""
        try:
            # Create LLM test case (no expected output or context for logs)
            llm_test_case = LLMTestCase(
                input=conv.query,
                actual_output=conv.response,
                # For logs, we don't have expected output or retrieval context
                retrieval_context=["Response from logged conversation"],
            )

            # Rate limit for OpenRouter
            await asyncio.sleep(3.5)

            # Answer Relevancy (most important for logs)
            try:
                self.relevancy_metric.measure(llm_test_case)
                result.answer_relevancy = self.relevancy_metric.score or 0.0
            except Exception as e:
                logger.warning(f"Relevancy metric failed: {e}")
                result.answer_relevancy = 0.5

            await asyncio.sleep(3.5)

            # Helpfulness (custom GEval for bilingual hotel context)
            try:
                self.helpfulness_metric.measure(llm_test_case)
                result.helpfulness = self.helpfulness_metric.score or 0.0
            except Exception as e:
                logger.warning(f"Helpfulness metric failed: {e}")
                result.helpfulness = 0.5

            await asyncio.sleep(3.5)

            # Faithfulness (use response itself as context for logs)
            try:
                self.faithfulness_metric.measure(llm_test_case)
                result.faithfulness = self.faithfulness_metric.score or 0.0
            except Exception as e:
                logger.warning(f"Faithfulness metric failed: {e}")
                result.faithfulness = 0.5

            # No context recall for logs (we don't have expected context)
            result.context_recall = 0.5  # Neutral

        except Exception as e:
            logger.error(f"DeepEval metrics failed for logs: {e}")
            result.faithfulness = 0.5
            result.answer_relevancy = 0.5
            result.context_recall = 0.5
            result.helpfulness = 0.5


async def run_evaluation(
    evaluator: RAGEvaluator,
    test_cases: List[GoldenQAPair],
    verbose: bool = True,
) -> EvaluationReport:
    """Run evaluation on all test cases."""
    results: List[TestCaseResult] = []

    total = len(test_cases)
    logger.info(f"Starting evaluation of {total} test cases...")

    for i, test_case in enumerate(test_cases):
        if verbose:
            logger.info(f"[{i+1}/{total}] {test_case.id}: {test_case.question[:50]}...")

        result = await evaluator.evaluate_test_case(test_case)
        results.append(result)

        status = "✓ PASS" if result.passed else "✗ FAIL"
        if verbose:
            logger.info(
                f"  {status} | avg={result.average_score:.2f} | "
                f"faith={result.faithfulness:.2f} | rel={result.answer_relevancy:.2f} | "
                f"recall={result.context_recall:.2f} | help={result.helpfulness:.2f}"
            )

        # Small delay between tests
        await asyncio.sleep(1.0)

    # Generate report
    return generate_report(results)


async def run_log_evaluation(
    evaluator: RAGEvaluator,
    conversations: List[LoggedConversation],
    verbose: bool = True,
) -> EvaluationReport:
    """Run evaluation on logged conversations (no API calls)."""
    results: List[TestCaseResult] = []

    total = len(conversations)
    logger.info(f"Starting evaluation of {total} logged conversations...")

    for i, conv in enumerate(conversations):
        if verbose:
            logger.info(f"[{i+1}/{total}] {conv.request_id}: {conv.query[:50]}...")

        result = await evaluator.evaluate_logged_conversation(conv)
        results.append(result)

        status = "✓ PASS" if result.passed else "✗ FAIL"
        if verbose:
            logger.info(
                f"  {status} | avg={result.average_score:.2f} | "
                f"faith={result.faithfulness:.2f} | rel={result.answer_relevancy:.2f} | "
                f"help={result.helpfulness:.2f} | path={conv.routing_path}"
            )

        # Small delay between evaluations (for rate limiting)
        await asyncio.sleep(0.5)

    # Generate report
    return generate_log_report(results, conversations)


def generate_log_report(
    results: List[TestCaseResult],
    conversations: List[LoggedConversation],
) -> EvaluationReport:
    """Generate evaluation report from logged conversation results."""
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    # Calculate averages
    avg_faith = sum(r.faithfulness for r in results) / len(results) if results else 0
    avg_rel = sum(r.answer_relevancy for r in results) / len(results) if results else 0
    avg_recall = sum(r.context_recall for r in results) / len(results) if results else 0
    avg_help = sum(r.helpfulness for r in results) / len(results) if results else 0
    avg_kw = sum(r.keyword_match for r in results) / len(results) if results else 0

    latencies = [r.latency_ms for r in results if r.latency_ms > 0]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    sorted_latencies = sorted(latencies)
    p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)] if latencies else 0

    # By language
    en_results = [r for r in results if r.language == "en"]
    th_results = [r for r in results if r.language == "th"]
    en_pass_rate = sum(1 for r in en_results if r.passed) / len(en_results) if en_results else 0
    th_pass_rate = sum(1 for r in th_results if r.passed) / len(th_results) if th_results else 0

    # By routing path (category field holds routing_path for logs)
    routing_paths = set(r.category for r in results)
    category_scores = {}
    for path in routing_paths:
        path_results = [r for r in results if r.category == path]
        category_scores[path] = sum(r.average_score for r in path_results) / len(path_results)

    # By complexity (difficulty field holds complexity for logs)
    complexities = set(r.difficulty for r in results)
    difficulty_scores = {}
    for comp in complexities:
        comp_results = [r for r in results if r.difficulty == comp]
        difficulty_scores[comp] = sum(r.average_score for r in comp_results) / len(comp_results)

    # Worst routing paths
    sorted_paths = sorted(category_scores.items(), key=lambda x: x[1])
    worst_categories = [path for path, score in sorted_paths[:3] if score < 0.8]

    # Worst test cases
    sorted_results = sorted(results, key=lambda r: r.average_score)
    worst_cases = [r.id for r in sorted_results[:5] if not r.passed]

    # Improvement recommendations
    recommendations = []
    if avg_faith < 0.7:
        recommendations.append("Improve faithfulness: Responses should closely follow retrieved context")
    if avg_rel < 0.7:
        recommendations.append("Improve relevancy: Responses should directly answer the question")
    if avg_help < 0.7:
        recommendations.append("Improve helpfulness: Responses should be actionable and complete")
    if en_pass_rate < th_pass_rate - 0.1:
        recommendations.append("English responses need improvement")
    if th_pass_rate < en_pass_rate - 0.1:
        recommendations.append("Thai responses need improvement")

    # Routing path recommendations
    for path in worst_categories:
        if path == "nemo":
            recommendations.append("NeMo path needs improvement - consider adjusting prompts or routing thresholds")
        elif path == "langgraph":
            recommendations.append("LangGraph path needs improvement - review agent behavior and tool usage")

    # Complexity recommendations
    for comp, score in difficulty_scores.items():
        if score < 0.7:
            recommendations.append(f"'{comp}' complexity queries need improvement")

    return EvaluationReport(
        timestamp=datetime.now().isoformat(),
        total_tests=len(results),
        passed_tests=len(passed),
        failed_tests=len(failed),
        pass_rate=len(passed) / len(results) if results else 0,
        avg_faithfulness=avg_faith,
        avg_answer_relevancy=avg_rel,
        avg_context_recall=avg_recall,
        avg_helpfulness=avg_help,
        avg_keyword_match=avg_kw,
        avg_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        english_pass_rate=en_pass_rate,
        thai_pass_rate=th_pass_rate,
        category_scores=category_scores,  # Routing paths for log mode
        difficulty_scores=difficulty_scores,  # Complexity levels for log mode
        worst_categories=worst_categories,
        worst_test_cases=worst_cases,
        improvement_recommendations=recommendations,
        results=results,
    )


def generate_report(results: List[TestCaseResult]) -> EvaluationReport:
    """Generate evaluation report from results."""
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    # Calculate averages
    avg_faith = sum(r.faithfulness for r in results) / len(results)
    avg_rel = sum(r.answer_relevancy for r in results) / len(results)
    avg_recall = sum(r.context_recall for r in results) / len(results)
    avg_help = sum(r.helpfulness for r in results) / len(results)
    avg_kw = sum(r.keyword_match for r in results) / len(results)

    latencies = [r.latency_ms for r in results if r.latency_ms > 0]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    sorted_latencies = sorted(latencies)
    p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)] if latencies else 0

    # By language
    en_results = [r for r in results if r.language == "en"]
    th_results = [r for r in results if r.language == "th"]
    en_pass_rate = sum(1 for r in en_results if r.passed) / len(en_results) if en_results else 0
    th_pass_rate = sum(1 for r in th_results if r.passed) / len(th_results) if th_results else 0

    # By category
    categories = set(r.category for r in results)
    category_scores = {}
    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        category_scores[cat] = sum(r.average_score for r in cat_results) / len(cat_results)

    # By difficulty
    difficulties = set(r.difficulty for r in results)
    difficulty_scores = {}
    for diff in difficulties:
        diff_results = [r for r in results if r.difficulty == diff]
        difficulty_scores[diff] = sum(r.average_score for r in diff_results) / len(diff_results)

    # Worst categories
    sorted_cats = sorted(category_scores.items(), key=lambda x: x[1])
    worst_categories = [cat for cat, score in sorted_cats[:3] if score < 0.8]

    # Worst test cases
    sorted_results = sorted(results, key=lambda r: r.average_score)
    worst_cases = [r.id for r in sorted_results[:5] if not r.passed]

    # Improvement recommendations
    recommendations = []
    if avg_faith < 0.7:
        recommendations.append("Improve faithfulness: Responses should closely follow retrieved context")
    if avg_rel < 0.7:
        recommendations.append("Improve relevancy: Responses should directly answer the question")
    if avg_recall < 0.7:
        recommendations.append("Improve retrieval: Check embeddings, chunk size, and reranking")
    if avg_kw < 0.7:
        recommendations.append("Improve accuracy: Ensure key facts (times, prices, names) are included")
    if en_pass_rate < th_pass_rate - 0.1:
        recommendations.append("English responses need improvement")
    if th_pass_rate < en_pass_rate - 0.1:
        recommendations.append("Thai responses need improvement")
    for cat in worst_categories:
        recommendations.append(f"Focus on improving {cat} category")

    return EvaluationReport(
        timestamp=datetime.now().isoformat(),
        total_tests=len(results),
        passed_tests=len(passed),
        failed_tests=len(failed),
        pass_rate=len(passed) / len(results) if results else 0,
        avg_faithfulness=avg_faith,
        avg_answer_relevancy=avg_rel,
        avg_context_recall=avg_recall,
        avg_helpfulness=avg_help,
        avg_keyword_match=avg_kw,
        avg_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        english_pass_rate=en_pass_rate,
        thai_pass_rate=th_pass_rate,
        category_scores=category_scores,
        difficulty_scores=difficulty_scores,
        worst_categories=worst_categories,
        worst_test_cases=worst_cases,
        improvement_recommendations=recommendations,
        results=results,
    )


def print_report(report: EvaluationReport):
    """Print formatted report to console."""
    print("\n" + "=" * 70)
    print("                    RAG EVALUATION REPORT")
    print("=" * 70)
    print(f"Timestamp: {report.timestamp}")
    print()

    # Overall results
    print("─" * 70)
    print("OVERALL RESULTS")
    print("─" * 70)
    pass_pct = report.pass_rate * 100
    print(f"  Pass Rate: {report.passed_tests}/{report.total_tests} ({pass_pct:.1f}%)")
    print()

    # Metric scores
    print("─" * 70)
    print("METRIC SCORES (0.0 - 1.0)")
    print("─" * 70)
    print(f"  Faithfulness:     {report.avg_faithfulness:.3f}  {'✓' if report.avg_faithfulness >= 0.7 else '✗'}")
    print(f"  Answer Relevancy: {report.avg_answer_relevancy:.3f}  {'✓' if report.avg_answer_relevancy >= 0.7 else '✗'}")
    print(f"  Context Recall:   {report.avg_context_recall:.3f}  {'✓' if report.avg_context_recall >= 0.7 else '✗'}")
    print(f"  Helpfulness:      {report.avg_helpfulness:.3f}  {'✓' if report.avg_helpfulness >= 0.7 else '✗'}")
    print(f"  Keyword Match:    {report.avg_keyword_match:.3f}  {'✓' if report.avg_keyword_match >= 0.7 else '✗'}")
    print()

    # Latency
    print("─" * 70)
    print("LATENCY")
    print("─" * 70)
    print(f"  Average: {report.avg_latency_ms:.0f} ms")
    print(f"  P95:     {report.p95_latency_ms:.0f} ms")
    print()

    # By language
    print("─" * 70)
    print("BY LANGUAGE")
    print("─" * 70)
    print(f"  English: {report.english_pass_rate * 100:.1f}% pass rate")
    print(f"  Thai:    {report.thai_pass_rate * 100:.1f}% pass rate")
    print()

    # By category
    print("─" * 70)
    print("BY CATEGORY")
    print("─" * 70)
    for cat, score in sorted(report.category_scores.items(), key=lambda x: -x[1]):
        status = "✓" if score >= 0.7 else "✗"
        print(f"  {cat:15} {score:.3f}  {status}")
    print()

    # By difficulty
    print("─" * 70)
    print("BY DIFFICULTY")
    print("─" * 70)
    for diff, score in sorted(report.difficulty_scores.items()):
        status = "✓" if score >= 0.7 else "✗"
        print(f"  {diff:10} {score:.3f}  {status}")
    print()

    # Improvement recommendations
    if report.improvement_recommendations:
        print("─" * 70)
        print("IMPROVEMENT RECOMMENDATIONS")
        print("─" * 70)
        for i, rec in enumerate(report.improvement_recommendations, 1):
            print(f"  {i}. {rec}")
        print()

    # Worst test cases
    if report.worst_test_cases:
        print("─" * 70)
        print("WORST PERFORMING TEST CASES")
        print("─" * 70)
        for case_id in report.worst_test_cases:
            result = next(r for r in report.results if r.id == case_id)
            print(f"  {case_id}: score={result.average_score:.2f}")
            if result.failure_reasons:
                for reason in result.failure_reasons[:2]:
                    print(f"    - {reason}")
        print()

    print("=" * 70)


def save_report(report: EvaluationReport, output_path: str):
    """Save report to JSON file."""
    # Convert dataclasses to dict
    report_dict = {
        "timestamp": report.timestamp,
        "total_tests": report.total_tests,
        "passed_tests": report.passed_tests,
        "failed_tests": report.failed_tests,
        "pass_rate": report.pass_rate,
        "avg_faithfulness": report.avg_faithfulness,
        "avg_answer_relevancy": report.avg_answer_relevancy,
        "avg_context_recall": report.avg_context_recall,
        "avg_helpfulness": report.avg_helpfulness,
        "avg_keyword_match": report.avg_keyword_match,
        "avg_latency_ms": report.avg_latency_ms,
        "p95_latency_ms": report.p95_latency_ms,
        "english_pass_rate": report.english_pass_rate,
        "thai_pass_rate": report.thai_pass_rate,
        "category_scores": report.category_scores,
        "difficulty_scores": report.difficulty_scores,
        "worst_categories": report.worst_categories,
        "worst_test_cases": report.worst_test_cases,
        "improvement_recommendations": report.improvement_recommendations,
        "results": [asdict(r) for r in report.results],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info(f"Report saved to {output_path}")


async def main():
    parser = argparse.ArgumentParser(description="Run DeepEval RAG evaluation")

    # Mode selection
    parser.add_argument("--logs", help="Path to feedback logs directory (enables log evaluation mode)")
    parser.add_argument("--endpoint", default="http://localhost:8081", help="API endpoint URL (golden dataset mode)")

    # Log mode filters
    parser.add_argument("--date", help="Filter logs by date (YYYY-MM-DD)")
    parser.add_argument("--routing-path", choices=["nemo", "langgraph"], help="Filter by routing path")
    parser.add_argument("--complexity", choices=["simple", "moderate", "complex"], help="Filter by complexity")
    parser.add_argument("--unevaluated", action="store_true", help="Only evaluate records without scores")

    # Golden dataset mode filters
    parser.add_argument("--category", help="Filter by category (dining, facilities, spa, etc.)")
    parser.add_argument("--language", choices=["en", "th"], help="Filter by language")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], help="Filter by difficulty")

    # Common options
    parser.add_argument("--quick", action="store_true", help="Run quick test (first 5 cases)")
    parser.add_argument("--limit", type=int, help="Maximum number of records to evaluate")
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument("--threshold", type=float, default=0.7, help="Pass threshold (default: 0.7)")
    parser.add_argument("--no-deepeval", action="store_true", help="Use keyword-based evaluation only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Create evaluator
    evaluator = RAGEvaluator(
        endpoint_url=args.endpoint,
        pass_threshold=args.threshold,
        use_deepeval=not args.no_deepeval,
    )

    if args.logs:
        # Log Evaluation Mode - evaluate logged conversations
        logger.info("=" * 60)
        logger.info("LOG EVALUATION MODE")
        logger.info("=" * 60)
        logger.info(f"Loading conversations from: {args.logs}")

        loader = FeedbackLogLoader(args.logs)
        conversations = loader.load_conversations(
            date_filter=args.date,
            routing_path_filter=args.routing_path,
            complexity_filter=args.complexity,
            unevaluated_only=args.unevaluated,
            limit=args.limit if args.limit else (5 if args.quick else None),
        )

        if not conversations:
            logger.error("No conversations found matching the filters")
            return

        stats = loader.get_stats(conversations)
        logger.info(f"Loaded {stats['total']} conversations")
        logger.info(f"  By routing path: {stats['by_routing_path']}")
        logger.info(f"  By complexity: {stats['by_complexity']}")
        logger.info(f"  By language: {stats['by_language']}")
        logger.info(f"  Already evaluated: {stats['evaluated']}")
        logger.info(f"  Unevaluated: {stats['unevaluated']}")

        # Run evaluation on logs
        report = await run_log_evaluation(evaluator, conversations, verbose=args.verbose)

    else:
        # Golden Dataset Mode - evaluate against golden Q&A pairs
        logger.info("=" * 60)
        logger.info("GOLDEN DATASET MODE")
        logger.info("=" * 60)
        logger.info("Loading golden dataset...")

        dataset = generate_golden_dataset()
        stats = get_dataset_stats(dataset)
        logger.info(f"Dataset: {stats['total']} test cases")
        logger.info(f"  Languages: {stats['by_language']}")
        logger.info(f"  Categories: {stats['by_category']}")
        logger.info(f"  Difficulties: {stats['by_difficulty']}")

        # Filter test cases
        test_cases = dataset.pairs

        if args.category:
            test_cases = [tc for tc in test_cases if tc.category.value == args.category]
            logger.info(f"Filtered to {len(test_cases)} {args.category} test cases")

        if args.language:
            test_cases = [tc for tc in test_cases if tc.language.value == args.language]
            logger.info(f"Filtered to {len(test_cases)} {args.language} test cases")

        if args.difficulty:
            test_cases = [tc for tc in test_cases if tc.difficulty.value == args.difficulty]
            logger.info(f"Filtered to {len(test_cases)} {args.difficulty} test cases")

        if args.quick:
            test_cases = test_cases[:5]
            logger.info(f"Quick mode: {len(test_cases)} test cases")

        if args.limit:
            test_cases = test_cases[:args.limit]
            logger.info(f"Limited to {len(test_cases)} test cases")

        if not test_cases:
            logger.error("No test cases match the filters")
            return

        # Run evaluation
        report = await run_evaluation(evaluator, test_cases, verbose=args.verbose)

    # Print report
    print_report(report)

    # Save if requested
    if args.output:
        save_report(report, args.output)


if __name__ == "__main__":
    asyncio.run(main())
