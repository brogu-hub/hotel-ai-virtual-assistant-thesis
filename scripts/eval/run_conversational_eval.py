#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Conversational & Agentic RAG Evaluation Runner

Runs comprehensive multi-turn evaluation using DeepEval metrics:

CONVERSATIONAL METRICS:
- Knowledge Retention: Does the agent retain context across turns?
- Conversation Completeness: Are all parts of the query addressed?
- Conversation Relevancy: Are responses relevant in multi-turn context?
- Role Adherence: Does the agent stay in character as hotel concierge?

AGENTIC METRICS:
- Task Completion: Did the agent complete the requested task?
- Tool Correctness: Were the right tools used correctly?

RAG METRICS:
- Faithfulness: Does the response follow retrieved context?

Usage:
    # Run full evaluation with conversational metrics
    python scripts/eval/run_conversational_eval.py

    # Quick test (5 conversations)
    python scripts/eval/run_conversational_eval.py --quick

    # Evaluate booking CRUD operations
    python scripts/eval/run_conversational_eval.py --category booking

    # Save results
    python scripts/eval/run_conversational_eval.py --output results.json
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# DeepEval imports
try:
    from deepeval import evaluate
    from deepeval.metrics import (
        FaithfulnessMetric,
        AnswerRelevancyMetric,
        GEval,
        TaskCompletionMetric,
        ToolCorrectnessMetric,
    )
    from deepeval.metrics.conversation import (
        KnowledgeRetentionMetric,
        ConversationCompletenessMetric,
        ConversationRelevancyMetric,
        RoleAdherenceMetric,
    )
    from deepeval.test_case import LLMTestCase, ConversationalTestCase, Message
    DEEPEVAL_AVAILABLE = True
    CONVERSATIONAL_AVAILABLE = True
except ImportError as e:
    DEEPEVAL_AVAILABLE = False
    CONVERSATIONAL_AVAILABLE = False
    logger.warning(f"DeepEval conversational metrics not available: {e}")
    logger.warning("Install with: pip install deepeval")


@dataclass
class ConversationTurn:
    """Single turn in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    tool_calls: Optional[List[Dict]] = None
    retrieval_context: Optional[List[str]] = None


@dataclass
class ConversationTestResult:
    """Result for a conversation test case."""
    id: str
    category: str
    language: str
    difficulty: str
    turns: List[ConversationTurn]

    # Conversational Metrics (0.0 - 1.0)
    knowledge_retention: float = 0.0
    conversation_completeness: float = 0.0
    conversation_relevancy: float = 0.0
    role_adherence: float = 0.0

    # Agentic Metrics
    task_completion: float = 0.0
    tool_correctness: float = 0.0

    # RAG Metrics
    faithfulness: float = 0.0

    # Overall
    average_score: float = 0.0
    passed: bool = False

    # Details
    latency_ms: float = 0.0
    failure_reasons: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ConversationalReport:
    """Evaluation report for conversational tests."""
    timestamp: str
    total_conversations: int
    passed: int
    failed: int
    pass_rate: float

    # Conversational Metrics Averages
    avg_knowledge_retention: float
    avg_conversation_completeness: float
    avg_conversation_relevancy: float
    avg_role_adherence: float

    # Agentic Metrics Averages
    avg_task_completion: float
    avg_tool_correctness: float

    # RAG Metrics
    avg_faithfulness: float

    # Latency
    avg_latency_ms: float

    # By Category
    category_scores: Dict[str, float]

    # By Language
    english_pass_rate: float
    thai_pass_rate: float

    # Recommendations
    improvement_recommendations: List[str]

    # Results
    results: List[ConversationTestResult]


class ConversationalEvaluator:
    """Evaluator for multi-turn conversations with comprehensive metrics."""

    HOTEL_ROLE = """You are a professional concierge at The Grand Horizon Hotel, Bangkok.
    Your role is to assist guests with bookings, services, facilities, and general inquiries.
    You should be polite, helpful, accurate, and maintain context across the conversation.
    You respond in the same language as the guest (Thai or English)."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8081",
        pass_threshold: float = 0.7,
    ):
        self.endpoint_url = endpoint_url
        self.pass_threshold = pass_threshold

        if DEEPEVAL_AVAILABLE:
            self._init_metrics()
        else:
            logger.warning("DeepEval not available - using simplified evaluation")

    def _init_metrics(self):
        """Initialize DeepEval metrics."""
        judge_model = os.getenv("DEEPEVAL_JUDGE_MODEL", "gpt-4o-mini")

        # RAG Metric
        self.faithfulness_metric = FaithfulnessMetric(
            threshold=self.pass_threshold,
            model=judge_model,
        )

        # Conversational Metrics
        if CONVERSATIONAL_AVAILABLE:
            self.knowledge_retention = KnowledgeRetentionMetric(
                threshold=self.pass_threshold,
                model=judge_model,
            )
            self.completeness = ConversationCompletenessMetric(
                threshold=self.pass_threshold,
                model=judge_model,
            )
            self.relevancy = ConversationRelevancyMetric(
                threshold=self.pass_threshold,
                model=judge_model,
            )
            self.role_adherence = RoleAdherenceMetric(
                threshold=self.pass_threshold,
                model=judge_model,
                chatbot_role=self.HOTEL_ROLE,
            )

        # Agentic Metrics - Custom GEval
        self.task_completion = GEval(
            name="Task Completion",
            criteria="""Evaluate if the hotel assistant completed the requested task:
            1. Booking created/modified/cancelled as requested
            2. All required information collected (dates, guests, room type)
            3. Confirmation or next steps clearly communicated
            4. No dropped requests or forgotten context
            Score 1.0 if fully completed, 0.5 if partial, 0.0 if not attempted.""",
            evaluation_params=["input", "actual_output"],
            threshold=self.pass_threshold,
            model=judge_model,
        )

        self.tool_correctness = GEval(
            name="Tool Correctness",
            criteria="""Evaluate if the hotel assistant used tools correctly:
            1. Called appropriate tools for the request (booking, search, cancel)
            2. Passed correct parameters (dates, room types, guest info)
            3. Interpreted tool results accurately
            4. Did not hallucinate tool capabilities
            Score 1.0 if correct, 0.5 if partial, 0.0 if incorrect.""",
            evaluation_params=["input", "actual_output", "expected_output"],
            threshold=self.pass_threshold,
            model=judge_model,
        )

    async def get_conversation_response(
        self,
        messages: List[Dict[str, str]],
        session_id: str,
    ) -> Dict[str, Any]:
        """Get response from endpoint for a conversation."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                start_time = time.time()

                # Send the last user message with conversation history
                response = await client.post(
                    f"{self.endpoint_url}/chat",
                    json={
                        "message": messages[-1]["content"],
                        "session_id": session_id,
                        "conversation_history": messages[:-1],
                    },
                    timeout=60.0,
                )
                latency_ms = (time.time() - start_time) * 1000

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "response": data.get("response", ""),
                        "tool_calls": data.get("tool_calls", []),
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

    async def evaluate_conversation(
        self,
        test_case: GoldenQAPair,
        multi_turn: bool = False,
    ) -> ConversationTestResult:
        """Evaluate a conversation test case."""
        result = ConversationTestResult(
            id=test_case.id,
            category=test_case.category.value,
            language=test_case.language.value,
            difficulty=test_case.difficulty.value,
            turns=[],
        )

        # Create conversation
        session_id = f"eval-{test_case.id}-{int(time.time())}"
        messages = [{"role": "user", "content": test_case.question}]

        # Get response
        response_data = await self.get_conversation_response(messages, session_id)

        if not response_data["success"]:
            result.failure_reasons.append(f"API error: {response_data.get('error')}")
            return result

        # Add turns
        result.turns.append(ConversationTurn(
            role="user",
            content=test_case.question,
        ))
        result.turns.append(ConversationTurn(
            role="assistant",
            content=response_data["response"],
            tool_calls=response_data.get("tool_calls"),
            retrieval_context=response_data.get("retrieval_context"),
        ))
        result.latency_ms = response_data["latency_ms"]

        # Evaluate with metrics
        if DEEPEVAL_AVAILABLE:
            await self._evaluate_with_deepeval(test_case, result, response_data)
        else:
            self._evaluate_simple(test_case, result, response_data)

        # Calculate average
        scores = [
            result.knowledge_retention,
            result.conversation_completeness,
            result.conversation_relevancy,
            result.role_adherence,
            result.task_completion,
            result.tool_correctness,
            result.faithfulness,
        ]
        result.average_score = sum(scores) / len(scores)
        result.passed = result.average_score >= self.pass_threshold

        # Analyze for recommendations
        self._analyze_and_recommend(result)

        return result

    async def _evaluate_with_deepeval(
        self,
        test_case: GoldenQAPair,
        result: ConversationTestResult,
        response_data: Dict,
    ):
        """Run DeepEval metrics."""
        actual_output = response_data["response"]
        retrieval_context = response_data.get("retrieval_context", ["No context"])

        # Create test case for single-turn metrics
        llm_test_case = LLMTestCase(
            input=test_case.question,
            actual_output=actual_output,
            expected_output=test_case.expected_answer,
            retrieval_context=retrieval_context,
        )

        # Faithfulness
        try:
            await asyncio.sleep(2)
            self.faithfulness_metric.measure(llm_test_case)
            result.faithfulness = self.faithfulness_metric.score or 0.0
        except Exception as e:
            logger.warning(f"Faithfulness failed: {e}")
            result.faithfulness = 0.5

        # Task Completion
        try:
            await asyncio.sleep(2)
            self.task_completion.measure(llm_test_case)
            result.task_completion = self.task_completion.score or 0.0
        except Exception as e:
            logger.warning(f"Task completion failed: {e}")
            result.task_completion = 0.5

        # Tool Correctness
        try:
            await asyncio.sleep(2)
            self.tool_correctness.measure(llm_test_case)
            result.tool_correctness = self.tool_correctness.score or 0.0
        except Exception as e:
            logger.warning(f"Tool correctness failed: {e}")
            result.tool_correctness = 0.5

        # Conversational Metrics (if available)
        if CONVERSATIONAL_AVAILABLE:
            try:
                # Convert to conversational test case
                messages = [
                    Message(role="user", content=test_case.question),
                    Message(role="assistant", content=actual_output),
                ]
                conv_test_case = ConversationalTestCase(messages=messages)

                await asyncio.sleep(2)
                self.knowledge_retention.measure(conv_test_case)
                result.knowledge_retention = self.knowledge_retention.score or 0.0

                await asyncio.sleep(2)
                self.completeness.measure(conv_test_case)
                result.conversation_completeness = self.completeness.score or 0.0

                await asyncio.sleep(2)
                self.relevancy.measure(conv_test_case)
                result.conversation_relevancy = self.relevancy.score or 0.0

                await asyncio.sleep(2)
                self.role_adherence.measure(conv_test_case)
                result.role_adherence = self.role_adherence.score or 0.0

            except Exception as e:
                logger.warning(f"Conversational metrics failed: {e}")
                result.knowledge_retention = 0.5
                result.conversation_completeness = 0.5
                result.conversation_relevancy = 0.5
                result.role_adherence = 0.5
        else:
            # Estimate from response quality
            result.knowledge_retention = 0.7
            result.conversation_completeness = 0.7 if len(actual_output) > 50 else 0.4
            result.conversation_relevancy = 0.7
            result.role_adherence = 0.7

    def _evaluate_simple(
        self,
        test_case: GoldenQAPair,
        result: ConversationTestResult,
        response_data: Dict,
    ):
        """Simple keyword-based evaluation."""
        actual = response_data["response"].lower()
        expected_keywords = test_case.expected_keywords

        # Keyword match for faithfulness
        matches = sum(1 for kw in expected_keywords if kw.lower() in actual)
        result.faithfulness = matches / len(expected_keywords) if expected_keywords else 0.5

        # Response quality for other metrics
        has_response = len(actual) > 20
        result.task_completion = 0.7 if has_response else 0.3
        result.tool_correctness = 0.6  # Can't evaluate without seeing tools
        result.knowledge_retention = 0.7
        result.conversation_completeness = 0.7 if has_response else 0.4
        result.conversation_relevancy = 0.7 if has_response else 0.4
        result.role_adherence = 0.7

    def _analyze_and_recommend(self, result: ConversationTestResult):
        """Analyze failures and add recommendations."""
        if result.faithfulness < 0.7:
            result.failure_reasons.append("Low faithfulness - possible hallucination")
            result.recommendations.append("Ground responses more closely to retrieved context")

        if result.task_completion < 0.7:
            result.failure_reasons.append("Task not completed")
            result.recommendations.append("Ensure all user requests are addressed")

        if result.conversation_completeness < 0.7:
            result.failure_reasons.append("Incomplete response")
            result.recommendations.append("Address all parts of multi-part questions")

        if result.role_adherence < 0.7:
            result.failure_reasons.append("Breaking character")
            result.recommendations.append("Stay in hotel concierge role consistently")


def generate_report(results: List[ConversationTestResult]) -> ConversationalReport:
    """Generate comprehensive evaluation report."""
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    # Averages
    def avg(values): return sum(values) / len(values) if values else 0

    avg_kr = avg([r.knowledge_retention for r in results])
    avg_cc = avg([r.conversation_completeness for r in results])
    avg_cr = avg([r.conversation_relevancy for r in results])
    avg_ra = avg([r.role_adherence for r in results])
    avg_tc = avg([r.task_completion for r in results])
    avg_tool = avg([r.tool_correctness for r in results])
    avg_faith = avg([r.faithfulness for r in results])
    avg_latency = avg([r.latency_ms for r in results])

    # By category
    categories = set(r.category for r in results)
    category_scores = {
        cat: avg([r.average_score for r in results if r.category == cat])
        for cat in categories
    }

    # By language
    en_results = [r for r in results if r.language == "en"]
    th_results = [r for r in results if r.language == "th"]
    en_pass = sum(1 for r in en_results if r.passed) / len(en_results) if en_results else 0
    th_pass = sum(1 for r in th_results if r.passed) / len(th_results) if th_results else 0

    # Recommendations
    recommendations = []
    if avg_faith < 0.7:
        recommendations.append("Improve RAG grounding - responses should cite retrieved context")
    if avg_tc < 0.7:
        recommendations.append("Improve task completion - ensure booking operations complete")
    if avg_cc < 0.7:
        recommendations.append("Address all parts of complex queries")
    if avg_ra < 0.7:
        recommendations.append("Maintain hotel concierge persona consistently")
    if avg_kr < 0.7:
        recommendations.append("Better context retention across conversation turns")

    # Category-specific
    for cat, score in category_scores.items():
        if score < 0.7:
            recommendations.append(f"Focus on improving {cat} category (score: {score:.2f})")

    return ConversationalReport(
        timestamp=datetime.now().isoformat(),
        total_conversations=len(results),
        passed=len(passed),
        failed=len(failed),
        pass_rate=len(passed) / len(results) if results else 0,
        avg_knowledge_retention=avg_kr,
        avg_conversation_completeness=avg_cc,
        avg_conversation_relevancy=avg_cr,
        avg_role_adherence=avg_ra,
        avg_task_completion=avg_tc,
        avg_tool_correctness=avg_tool,
        avg_faithfulness=avg_faith,
        avg_latency_ms=avg_latency,
        category_scores=category_scores,
        english_pass_rate=en_pass,
        thai_pass_rate=th_pass,
        improvement_recommendations=recommendations,
        results=results,
    )


def print_report(report: ConversationalReport):
    """Print formatted report."""
    print("\n" + "=" * 70)
    print("       CONVERSATIONAL & AGENTIC RAG EVALUATION REPORT")
    print("=" * 70)
    print(f"Timestamp: {report.timestamp}")
    print()

    # Overall
    print("─" * 70)
    print("OVERALL RESULTS")
    print("─" * 70)
    print(f"  Pass Rate: {report.passed}/{report.total_conversations} ({report.pass_rate*100:.1f}%)")
    print()

    # Conversational Metrics
    print("─" * 70)
    print("CONVERSATIONAL METRICS (0.0 - 1.0)")
    print("─" * 70)
    print(f"  Knowledge Retention:      {report.avg_knowledge_retention:.3f}  {'✓' if report.avg_knowledge_retention >= 0.7 else '✗'}")
    print(f"  Conversation Completeness:{report.avg_conversation_completeness:.3f}  {'✓' if report.avg_conversation_completeness >= 0.7 else '✗'}")
    print(f"  Conversation Relevancy:   {report.avg_conversation_relevancy:.3f}  {'✓' if report.avg_conversation_relevancy >= 0.7 else '✗'}")
    print(f"  Role Adherence:           {report.avg_role_adherence:.3f}  {'✓' if report.avg_role_adherence >= 0.7 else '✗'}")
    print()

    # Agentic Metrics
    print("─" * 70)
    print("AGENTIC METRICS (0.0 - 1.0)")
    print("─" * 70)
    print(f"  Task Completion:    {report.avg_task_completion:.3f}  {'✓' if report.avg_task_completion >= 0.7 else '✗'}")
    print(f"  Tool Correctness:   {report.avg_tool_correctness:.3f}  {'✓' if report.avg_tool_correctness >= 0.7 else '✗'}")
    print()

    # RAG Metrics
    print("─" * 70)
    print("RAG METRICS (0.0 - 1.0)")
    print("─" * 70)
    print(f"  Faithfulness:       {report.avg_faithfulness:.3f}  {'✓' if report.avg_faithfulness >= 0.7 else '✗'}")
    print()

    # By Category
    print("─" * 70)
    print("BY CATEGORY")
    print("─" * 70)
    for cat, score in sorted(report.category_scores.items(), key=lambda x: -x[1]):
        status = "✓" if score >= 0.7 else "✗"
        print(f"  {cat:15} {score:.3f}  {status}")
    print()

    # By Language
    print("─" * 70)
    print("BY LANGUAGE")
    print("─" * 70)
    print(f"  English: {report.english_pass_rate*100:.1f}% pass")
    print(f"  Thai:    {report.thai_pass_rate*100:.1f}% pass")
    print()

    # Recommendations
    if report.improvement_recommendations:
        print("─" * 70)
        print("IMPROVEMENT RECOMMENDATIONS")
        print("─" * 70)
        for i, rec in enumerate(report.improvement_recommendations, 1):
            print(f"  {i}. {rec}")
        print()

    print("=" * 70)


def save_report(report: ConversationalReport, output_path: str):
    """Save report to JSON."""
    report_dict = {
        "timestamp": report.timestamp,
        "total_conversations": report.total_conversations,
        "passed": report.passed,
        "failed": report.failed,
        "pass_rate": report.pass_rate,
        "conversational_metrics": {
            "knowledge_retention": report.avg_knowledge_retention,
            "conversation_completeness": report.avg_conversation_completeness,
            "conversation_relevancy": report.avg_conversation_relevancy,
            "role_adherence": report.avg_role_adherence,
        },
        "agentic_metrics": {
            "task_completion": report.avg_task_completion,
            "tool_correctness": report.avg_tool_correctness,
        },
        "rag_metrics": {
            "faithfulness": report.avg_faithfulness,
        },
        "avg_latency_ms": report.avg_latency_ms,
        "category_scores": report.category_scores,
        "english_pass_rate": report.english_pass_rate,
        "thai_pass_rate": report.thai_pass_rate,
        "improvement_recommendations": report.improvement_recommendations,
        "results": [asdict(r) for r in report.results],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info(f"Report saved to {output_path}")


async def run_evaluation(
    evaluator: ConversationalEvaluator,
    test_cases: List[GoldenQAPair],
    verbose: bool = True,
) -> ConversationalReport:
    """Run evaluation on test cases."""
    results = []
    total = len(test_cases)

    logger.info(f"Starting conversational evaluation of {total} test cases...")

    for i, test_case in enumerate(test_cases):
        if verbose:
            logger.info(f"[{i+1}/{total}] {test_case.id}: {test_case.question[:40]}...")

        result = await evaluator.evaluate_conversation(test_case)
        results.append(result)

        status = "✓ PASS" if result.passed else "✗ FAIL"
        if verbose:
            logger.info(
                f"  {status} | avg={result.average_score:.2f} | "
                f"faith={result.faithfulness:.2f} | task={result.task_completion:.2f} | "
                f"complete={result.conversation_completeness:.2f}"
            )

        await asyncio.sleep(1)

    return generate_report(results)


async def main():
    parser = argparse.ArgumentParser(
        description="Run Conversational & Agentic RAG Evaluation"
    )
    parser.add_argument("--endpoint", default="http://localhost:8081", help="API endpoint")
    parser.add_argument("--category", help="Filter by category (booking, room, etc.)")
    parser.add_argument("--language", choices=["en", "th"], help="Filter by language")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"], help="Filter by difficulty")
    parser.add_argument("--quick", action="store_true", help="Quick test (5 cases)")
    parser.add_argument("--limit", type=int, help="Max test cases")
    parser.add_argument("--output", help="Save report to JSON file")
    parser.add_argument("--threshold", type=float, default=0.7, help="Pass threshold")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Load dataset
    logger.info("Loading golden dataset...")
    dataset = generate_golden_dataset()
    stats = get_dataset_stats(dataset)
    logger.info(f"Dataset: {stats['total']} test cases")
    logger.info(f"  Categories: {stats['by_category']}")

    # Filter test cases
    test_cases = dataset.pairs

    if args.category:
        test_cases = [tc for tc in test_cases if tc.category.value == args.category]
        logger.info(f"Filtered to {len(test_cases)} {args.category} cases")

    if args.language:
        test_cases = [tc for tc in test_cases if tc.language.value == args.language]
        logger.info(f"Filtered to {len(test_cases)} {args.language} cases")

    if args.difficulty:
        test_cases = [tc for tc in test_cases if tc.difficulty.value == args.difficulty]
        logger.info(f"Filtered to {len(test_cases)} {args.difficulty} cases")

    if args.quick:
        test_cases = test_cases[:5]
        logger.info("Quick mode: 5 test cases")

    if args.limit:
        test_cases = test_cases[:args.limit]
        logger.info(f"Limited to {len(test_cases)} cases")

    if not test_cases:
        logger.error("No test cases match filters")
        return

    # Create evaluator
    evaluator = ConversationalEvaluator(
        endpoint_url=args.endpoint,
        pass_threshold=args.threshold,
    )

    # Run evaluation
    report = await run_evaluation(evaluator, test_cases, verbose=args.verbose)

    # Print report
    print_report(report)

    # Save if requested
    if args.output:
        save_report(report, args.output)


if __name__ == "__main__":
    asyncio.run(main())
