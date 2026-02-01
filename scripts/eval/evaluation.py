# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Main RAG Evaluation Pipeline

Orchestrates the full evaluation flow:
1. Load golden dataset (Q&A pairs)
2. Query FastAPI endpoint for each question
3. Score responses using DeepEval metrics (via OpenRouter judge)
4. Generate HTML report with Pass/Fail results

Usage:
    from scripts.eval.evaluation import HotelRAGEvaluator

    evaluator = HotelRAGEvaluator()
    results = await evaluator.run_evaluation()
"""

import asyncio
import logging
import time
from typing import List, Optional
from datetime import datetime

import httpx
from deepeval.test_case import LLMTestCase

# Rate limiting constants for OpenRouter (20 req/min = 1 req per 3 seconds)
# Adding extra buffer to avoid hitting the limit
RATE_LIMIT_DELAY_SECONDS = 3.5  # Delay between API calls within a metric
INTER_METRIC_DELAY_SECONDS = 5.0  # Delay between each metric evaluation
INTER_TEST_DELAY_SECONDS = 8.0  # Delay between test cases

from .config import EvalConfig, get_config
from .models import (
    GoldenQAPair,
    GoldenDataset,
    EvaluationResult,
    EvaluationSummary,
    Language,
)
from .golden_dataset import load_golden_dataset
from .metrics import OpenRouterJudge, create_metrics, SimpleKeywordMetric

logger = logging.getLogger(__name__)


class HotelRAGEvaluator:
    """
    Main evaluator class for Hotel RAG system.

    Queries the FastAPI endpoint and scores responses using DeepEval.
    """

    def __init__(self, config: Optional[EvalConfig] = None):
        """
        Initialize evaluator.

        Args:
            config: Evaluation configuration (uses defaults if not provided)
        """
        self.config = config or get_config()
        self.config.validate()

        # Initialize LLM judge
        self.judge = OpenRouterJudge(
            model_name=self.config.judge_model,
            api_key=self.config.openrouter_api_key,
            http_referer=self.config.http_referer,
            x_title=self.config.x_title,
        )

        # Create metrics
        (
            self.faithfulness,
            self.context_recall,
            self.answer_relevancy,
            self.bilingual_helpfulness,
        ) = create_metrics(self.judge, self.config.pass_threshold)

        # Simple keyword metric for quick checks
        self.keyword_metric = SimpleKeywordMetric(threshold=0.5)

        # HTTP client for API calls
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=self.config.request_timeout,
            )
        return self.http_client

    async def _query_endpoint(self, question: str) -> tuple:
        """
        Query the FastAPI chat endpoint.

        Args:
            question: User question to send

        Returns:
            Tuple of (response_text, sources, retrieval_context, latency_ms)
        """
        client = await self._get_client()
        url = f"{self.config.endpoint_url}/chat"

        start_time = time.time()

        for attempt in range(self.config.max_retries):
            try:
                response = await client.post(
                    url,
                    json={"message": question},
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                latency_ms = (time.time() - start_time) * 1000
                data = response.json()

                # Get retrieval_context for proper evaluation (actual document chunks)
                retrieval_context = data.get("retrieval_context", [])

                return (
                    data.get("response", ""),
                    data.get("sources", []),
                    retrieval_context,
                    latency_ms,
                )

            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Request failed on attempt {attempt + 1}: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(1)

        raise RuntimeError("All retry attempts failed")

    async def _evaluate_single(
        self,
        pair: GoldenQAPair,
        index: int,
        total: int,
    ) -> EvaluationResult:
        """
        Evaluate a single Q&A pair.

        Args:
            pair: The Q&A pair to evaluate
            index: Current index (for progress display)
            total: Total number of pairs

        Returns:
            EvaluationResult with all scores
        """
        logger.info(f"  [{index}/{total}] {pair.id}: {pair.question[:50]}...")

        try:
            # Query the endpoint
            actual_output, sources, retrieval_context, latency_ms = await self._query_endpoint(
                pair.question
            )

            # Use actual retrieved document chunks for evaluation
            # If retrieval_context is empty, use sources as fallback (backward compatibility)
            eval_context = retrieval_context if retrieval_context else sources if sources else []

            # Create DeepEval test case
            test_case = LLMTestCase(
                input=pair.question,
                actual_output=actual_output,
                expected_output=pair.expected_answer,
                retrieval_context=eval_context,
                context=pair.expected_context,
            )

            # Run keyword check first (fast)
            keyword_result = self.keyword_metric.evaluate(
                actual_output,
                pair.expected_keywords,
            )

            # Run LLM-based metrics with rate limiting between each
            scores = {}
            reasons = []

            # Faithfulness
            try:
                logger.debug("    Running Faithfulness metric...")
                self.faithfulness.measure(test_case)
                scores["faithfulness"] = self.faithfulness.score or 0.0
                if not self.faithfulness.is_successful():
                    reasons.append(f"Faithfulness: {self.faithfulness.reason}")
            except Exception as e:
                logger.warning(f"Faithfulness metric failed: {e}")
                scores["faithfulness"] = 0.0
                reasons.append(f"Faithfulness: Error - {str(e)[:50]}")

            # Rate limit delay before next metric
            await asyncio.sleep(INTER_METRIC_DELAY_SECONDS)

            # Context Recall
            try:
                logger.debug("    Running Context Recall metric...")
                self.context_recall.measure(test_case)
                scores["context_recall"] = self.context_recall.score or 0.0
                if not self.context_recall.is_successful():
                    reasons.append(f"Context Recall: {self.context_recall.reason}")
            except Exception as e:
                logger.warning(f"Context Recall metric failed: {e}")
                scores["context_recall"] = 0.0
                reasons.append(f"Context Recall: Error - {str(e)[:50]}")

            # Rate limit delay before next metric
            await asyncio.sleep(INTER_METRIC_DELAY_SECONDS)

            # Answer Relevancy
            try:
                logger.debug("    Running Answer Relevancy metric...")
                self.answer_relevancy.measure(test_case)
                scores["answer_relevancy"] = self.answer_relevancy.score or 0.0
                if not self.answer_relevancy.is_successful():
                    reasons.append(f"Answer Relevancy: {self.answer_relevancy.reason}")
            except Exception as e:
                logger.warning(f"Answer Relevancy metric failed: {e}")
                scores["answer_relevancy"] = 0.0
                reasons.append(f"Answer Relevancy: Error - {str(e)[:50]}")

            # Rate limit delay before next metric
            await asyncio.sleep(INTER_METRIC_DELAY_SECONDS)

            # Bilingual Helpfulness (GEval)
            try:
                logger.debug("    Running Helpfulness metric...")
                self.bilingual_helpfulness.measure(test_case)
                scores["helpfulness"] = self.bilingual_helpfulness.score or 0.0
                if not self.bilingual_helpfulness.is_successful():
                    reasons.append(
                        f"Helpfulness: {self.bilingual_helpfulness.reason}"
                    )
            except Exception as e:
                logger.warning(f"Helpfulness metric failed: {e}")
                scores["helpfulness"] = 0.0
                reasons.append(f"Helpfulness: Error - {str(e)[:50]}")

            # Determine overall pass/fail
            all_scores = list(scores.values())
            avg_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
            passed = (
                avg_score >= self.config.pass_threshold
                and keyword_result["score"] >= 0.5
            )

            # Add keyword failures to reasons
            if not keyword_result["passed"]:
                reasons.append(keyword_result["reason"])

            status = "PASS" if passed else "FAIL"
            logger.info(f"    -> {status} (avg: {avg_score:.2f}, latency: {latency_ms:.0f}ms)")

            return EvaluationResult(
                question_id=pair.id,
                question=pair.question,
                language=pair.language,
                category=pair.category,
                actual_output=actual_output,
                expected_output=pair.expected_answer,
                retrieval_context=retrieval_context,
                expected_context=pair.expected_context,
                latency_ms=latency_ms,
                faithfulness_score=scores.get("faithfulness", 0.0),
                context_recall_score=scores.get("context_recall", 0.0),
                answer_relevancy_score=scores.get("answer_relevancy", 0.0),
                helpfulness_score=scores.get("helpfulness", 0.0),
                passed=passed,
                failure_reasons=reasons if not passed else [],
            )

        except Exception as e:
            logger.error(f"    -> ERROR: {e}")
            return EvaluationResult(
                question_id=pair.id,
                question=pair.question,
                language=pair.language,
                category=pair.category,
                actual_output=f"ERROR: {str(e)}",
                expected_output=pair.expected_answer,
                retrieval_context=[],
                expected_context=pair.expected_context,
                latency_ms=0.0,
                faithfulness_score=0.0,
                context_recall_score=0.0,
                answer_relevancy_score=0.0,
                helpfulness_score=0.0,
                passed=False,
                failure_reasons=[f"Evaluation error: {str(e)}"],
            )

    async def run_evaluation(
        self,
        dataset: Optional[GoldenDataset] = None,
        test_ids: Optional[List[str]] = None,
    ) -> tuple:
        """
        Run full evaluation on the dataset.

        Args:
            dataset: Golden dataset (loads from config path if not provided)
            test_ids: Optional list of specific test IDs to run (filters dataset)

        Returns:
            Tuple of (results_list, summary)
        """
        # Load dataset
        if dataset is None:
            dataset = load_golden_dataset(self.config.dataset_path)

        # Filter by specific test IDs if provided
        if test_ids:
            filtered_pairs = [p for p in dataset.pairs if p.id in test_ids]
            if not filtered_pairs:
                logger.error(f"No matching tests found for IDs: {test_ids}")
                raise ValueError(f"No matching tests found for IDs: {test_ids}")
            logger.info(f"Filtering to {len(filtered_pairs)} specific tests: {test_ids}")
            # Create filtered dataset
            from .models import GoldenDataset as GD
            dataset = GD(
                version=dataset.version,
                generated_at=dataset.generated_at,
                total_pairs=len(filtered_pairs),
                pairs=filtered_pairs,
            )

        logger.info("=" * 60)
        logger.info("Hotel RAG Evaluation")
        logger.info("=" * 60)
        logger.info(f"Endpoint: {self.config.endpoint_url}")
        logger.info(f"Judge Model: {self.config.judge_model}")
        logger.info(f"Pass Threshold: {self.config.pass_threshold}")
        logger.info(f"Total Test Cases: {dataset.total_pairs}")
        logger.info("=" * 60)

        # Run evaluations with rate limiting between test cases
        results = []
        for i, pair in enumerate(dataset.pairs, 1):
            result = await self._evaluate_single(pair, i, dataset.total_pairs)
            results.append(result)

            # Rate limit delay between test cases (skip for last test)
            if i < dataset.total_pairs:
                logger.debug(f"    Waiting {INTER_TEST_DELAY_SECONDS}s before next test...")
                await asyncio.sleep(INTER_TEST_DELAY_SECONDS)

        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

        # Generate summary
        summary = self._generate_summary(results)

        logger.info("=" * 60)
        logger.info("Evaluation Complete")
        logger.info("=" * 60)
        logger.info(f"Total: {summary.total_tests}")
        logger.info(f"Passed: {summary.passed_tests}")
        logger.info(f"Failed: {summary.failed_tests}")
        logger.info(f"Pass Rate: {summary.pass_rate:.1f}%")
        logger.info("=" * 60)

        return results, summary

    def _generate_summary(self, results: List[EvaluationResult]) -> EvaluationSummary:
        """
        Generate summary statistics from results.

        Args:
            results: List of evaluation results

        Returns:
            EvaluationSummary with aggregated stats
        """
        if not results:
            return EvaluationSummary(
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                pass_rate=0.0,
                avg_faithfulness=0.0,
                avg_context_recall=0.0,
                avg_answer_relevancy=0.0,
                avg_helpfulness=0.0,
                avg_latency_ms=0.0,
                p95_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                english_pass_rate=0.0,
                thai_pass_rate=0.0,
                category_pass_rates={},
            )

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        # Average metric scores
        avg_faithfulness = sum(r.faithfulness_score for r in results) / total
        avg_context_recall = sum(r.context_recall_score for r in results) / total
        avg_answer_relevancy = sum(r.answer_relevancy_score for r in results) / total
        avg_helpfulness = sum(r.helpfulness_score for r in results) / total

        # Latency stats
        latencies = [r.latency_ms for r in results if r.latency_ms > 0]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            sorted_latencies = sorted(latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
            min_latency = min(latencies)
            max_latency = max(latencies)
        else:
            avg_latency = p95_latency = min_latency = max_latency = 0.0

        # Language breakdown
        en_results = [r for r in results if r.language == Language.ENGLISH]
        th_results = [r for r in results if r.language == Language.THAI]
        en_pass_rate = (
            (sum(1 for r in en_results if r.passed) / len(en_results) * 100)
            if en_results
            else 0.0
        )
        th_pass_rate = (
            (sum(1 for r in th_results if r.passed) / len(th_results) * 100)
            if th_results
            else 0.0
        )

        # Category breakdown
        categories = {}
        for result in results:
            cat = result.category.value
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0}
            categories[cat]["total"] += 1
            if result.passed:
                categories[cat]["passed"] += 1

        category_pass_rates = {
            cat: (data["passed"] / data["total"] * 100) if data["total"] > 0 else 0.0
            for cat, data in categories.items()
        }

        return EvaluationSummary(
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            pass_rate=(passed / total * 100) if total > 0 else 0.0,
            avg_faithfulness=avg_faithfulness,
            avg_context_recall=avg_context_recall,
            avg_answer_relevancy=avg_answer_relevancy,
            avg_helpfulness=avg_helpfulness,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            english_pass_rate=en_pass_rate,
            thai_pass_rate=th_pass_rate,
            category_pass_rates=category_pass_rates,
            evaluated_at=datetime.now().isoformat(),
        )


async def run_evaluation_async(
    config: Optional[EvalConfig] = None,
    test_ids: Optional[List[str]] = None,
) -> tuple:
    """
    Convenience function to run evaluation.

    Args:
        config: Optional evaluation configuration
        test_ids: Optional list of specific test IDs to run

    Returns:
        Tuple of (results_list, summary)
    """
    evaluator = HotelRAGEvaluator(config)
    return await evaluator.run_evaluation(test_ids=test_ids)


def run_evaluation(
    config: Optional[EvalConfig] = None,
    test_ids: Optional[List[str]] = None,
) -> tuple:
    """
    Synchronous wrapper for run_evaluation_async.

    Args:
        config: Optional evaluation configuration
        test_ids: Optional list of specific test IDs to run

    Returns:
        Tuple of (results_list, summary)
    """
    return asyncio.run(run_evaluation_async(config, test_ids))


if __name__ == "__main__":
    # Run evaluation when executed directly
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    results, summary = run_evaluation()
    print(f"\nResults: {summary.passed_tests}/{summary.total_tests} passed")
