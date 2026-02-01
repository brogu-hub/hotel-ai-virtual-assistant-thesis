# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Evaluation Feedback Loop - Async evaluation and routing optimization.

This module provides continuous evaluation of responses using DeepEval metrics
and feeds back results to optimize routing decisions.

Components:
1. EvaluationFeedbackLoop - Background task for batch evaluation
2. RoutingOptimizer - Updates routing thresholds based on performance
3. FeedbackStore - Persistent storage for evaluation results

Usage:
    from src.common.evaluation_feedback import EvaluationFeedbackLoop

    # Start the feedback loop
    loop = EvaluationFeedbackLoop()
    await loop.start()

    # Stop when shutting down
    await loop.stop()
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Configuration
EVAL_BATCH_INTERVAL = int(os.getenv("EVAL_BATCH_INTERVAL", "300"))  # 5 minutes
MIN_SAMPLES_FOR_UPDATE = int(os.getenv("MIN_SAMPLES_FOR_UPDATE", "20"))
FEEDBACK_DIR = os.getenv("FEEDBACK_LOG_DIR", "logs/feedback")
EVAL_RESULTS_DIR = os.getenv("EVAL_RESULTS_DIR", "logs/eval_results")


@dataclass
class RoutingPerformance:
    """Performance statistics for a routing path."""

    path: str  # "nemo" or "langgraph"
    total_samples: int = 0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    pass_rate: float = 0.0

    # By complexity
    simple_score: float = 0.0
    moderate_score: float = 0.0
    complex_score: float = 0.0


@dataclass
class RoutingRecommendation:
    """Recommendation for routing threshold updates."""

    current_threshold: float
    recommended_threshold: float
    confidence: float
    reasoning: str
    should_update: bool = False


class EvaluationFeedbackLoop:
    """
    Async evaluation pipeline for continuous improvement.

    Runs in background and:
    1. Collects unevaluated responses from feedback store
    2. Runs DeepEval metrics (faithfulness, relevancy, helpfulness)
    3. Updates routing thresholds based on performance
    4. Generates improvement recommendations
    """

    def __init__(
        self,
        eval_interval: int = EVAL_BATCH_INTERVAL,
        min_samples: int = MIN_SAMPLES_FOR_UPDATE,
        feedback_dir: str = FEEDBACK_DIR,
        results_dir: str = EVAL_RESULTS_DIR,
        threshold_update_callback: Optional[
            Callable[[float, float], Awaitable[None]]
        ] = None,
    ):
        """
        Initialize Evaluation Feedback Loop.

        Args:
            eval_interval: Seconds between evaluation batches
            min_samples: Minimum samples before updating thresholds
            feedback_dir: Directory containing feedback JSONL files
            results_dir: Directory to store evaluation results
            threshold_update_callback: Callback to update router thresholds
        """
        self.eval_interval = eval_interval
        self.min_samples = min_samples
        self.feedback_dir = Path(feedback_dir)
        self.results_dir = Path(results_dir)
        self.threshold_callback = threshold_update_callback

        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Performance tracking
        self._nemo_performance = RoutingPerformance(path="nemo")
        self._langgraph_performance = RoutingPerformance(path="langgraph")

        # Create directories
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"EvaluationFeedbackLoop initialized: interval={eval_interval}s, "
            f"min_samples={min_samples}"
        )

    async def start(self) -> None:
        """Start the background evaluation loop."""
        if self._running:
            logger.warning("Evaluation loop already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._evaluation_loop())
        logger.info("Evaluation feedback loop started")

    async def stop(self) -> None:
        """Stop the background evaluation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Evaluation feedback loop stopped")

    async def _evaluation_loop(self) -> None:
        """Main evaluation loop running in background."""
        while self._running:
            try:
                await self._run_evaluation_batch()
                await asyncio.sleep(self.eval_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Evaluation loop error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    async def _run_evaluation_batch(self) -> None:
        """Run evaluation on a batch of unevaluated responses."""
        logger.info("Starting evaluation batch...")

        # 1. Load unevaluated feedback records
        records = await self._load_unevaluated_records()
        if not records:
            logger.info("No unevaluated records found")
            return

        logger.info(f"Found {len(records)} unevaluated records")

        # 2. Run DeepEval metrics on each record
        evaluated_records = []
        for record in records:
            try:
                result = await self._evaluate_single_record(record)
                evaluated_records.append(result)
            except Exception as e:
                logger.warning(f"Failed to evaluate record: {e}")
                continue

        # 3. Save evaluation results
        await self._save_evaluation_results(evaluated_records)

        # 4. Update performance statistics
        await self._update_performance_stats(evaluated_records)

        # 5. Generate routing recommendations if enough samples
        if len(evaluated_records) >= self.min_samples:
            recommendation = await self._generate_routing_recommendation()
            if recommendation.should_update and self.threshold_callback:
                await self.threshold_callback(
                    recommendation.recommended_threshold,
                    recommendation.recommended_threshold,  # Same for now
                )
                logger.info(
                    f"Updated routing thresholds: {recommendation.recommended_threshold}"
                )

        logger.info(
            f"Evaluation batch complete: {len(evaluated_records)} records processed"
        )

    async def _load_unevaluated_records(self) -> List[Dict[str, Any]]:
        """Load feedback records that haven't been evaluated yet."""
        records = []

        # Scan recent feedback files
        for filepath in sorted(
            self.feedback_dir.glob("feedback_*.jsonl"), reverse=True
        )[:7]:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        record = json.loads(line)
                        # Only include records without score
                        if record.get("score") is None:
                            records.append(record)
                            if len(records) >= 50:  # Batch limit
                                return records
            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")

        return records

    async def _evaluate_single_record(
        self, record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a single feedback record using DeepEval metrics.

        Uses a simplified evaluation for online use - full DeepEval
        metrics are run in the offline evaluation script.
        """
        query = record.get("query", "")
        response = record.get("response", "")

        # Simple keyword-based evaluation for online use
        # Full DeepEval metrics are expensive and should run offline
        score = await self._quick_evaluate(query, response)

        result = {
            **record,
            "score": score,
            "evaluation_type": "online",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

        return result

    async def _quick_evaluate(self, query: str, response: str) -> float:
        """
        Quick evaluation using keyword matching.

        For more thorough evaluation, use the offline DeepEval pipeline
        in scripts/eval/run_evaluation.py
        """
        if not response:
            return 0.0

        # Basic quality signals
        score = 0.5  # Start with neutral

        # Positive signals
        if len(response) > 50:  # Not too short
            score += 0.1
        if len(response) < 1000:  # Not too long
            score += 0.05
        if "sorry" not in response.lower() and "error" not in response.lower():
            score += 0.1

        # Check for Thai/English consistency
        query_has_thai = any("\u0e00" <= c <= "\u0e7f" for c in query)
        response_has_thai = any("\u0e00" <= c <= "\u0e7f" for c in response)
        if query_has_thai == response_has_thai:
            score += 0.15  # Language consistency

        # Negative signals
        if "i don't know" in response.lower() or "ไม่ทราบ" in response:
            score -= 0.2

        return max(0.0, min(1.0, score))

    async def _save_evaluation_results(
        self, records: List[Dict[str, Any]]
    ) -> None:
        """Save evaluation results to JSONL file."""
        if not records:
            return

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filepath = self.results_dir / f"eval_results_{today}.jsonl"

        try:
            with open(filepath, "a", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.info(f"Saved {len(records)} evaluation results to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save evaluation results: {e}")

    async def _update_performance_stats(
        self, records: List[Dict[str, Any]]
    ) -> None:
        """Update performance statistics from evaluated records."""
        nemo_scores = []
        langgraph_scores = []
        nemo_latencies = []
        langgraph_latencies = []

        for record in records:
            score = record.get("score", 0)
            latency = record.get("latency_ms", 0)
            path = record.get("routing_path", "nemo")

            if path == "nemo":
                nemo_scores.append(score)
                nemo_latencies.append(latency)
            else:
                langgraph_scores.append(score)
                langgraph_latencies.append(latency)

        # Update NeMo performance
        if nemo_scores:
            self._nemo_performance.total_samples += len(nemo_scores)
            self._nemo_performance.avg_score = sum(nemo_scores) / len(nemo_scores)
            self._nemo_performance.avg_latency_ms = (
                sum(nemo_latencies) / len(nemo_latencies) if nemo_latencies else 0
            )
            self._nemo_performance.pass_rate = (
                sum(1 for s in nemo_scores if s >= 0.7) / len(nemo_scores)
            )

        # Update LangGraph performance
        if langgraph_scores:
            self._langgraph_performance.total_samples += len(langgraph_scores)
            self._langgraph_performance.avg_score = (
                sum(langgraph_scores) / len(langgraph_scores)
            )
            self._langgraph_performance.avg_latency_ms = (
                sum(langgraph_latencies) / len(langgraph_latencies)
                if langgraph_latencies
                else 0
            )
            self._langgraph_performance.pass_rate = (
                sum(1 for s in langgraph_scores if s >= 0.7) / len(langgraph_scores)
            )

    async def _generate_routing_recommendation(self) -> RoutingRecommendation:
        """Generate recommendation for routing threshold updates."""
        nemo = self._nemo_performance
        langgraph = self._langgraph_performance

        current_threshold = 0.7  # Default

        # If NeMo performs significantly better on moderate queries
        if nemo.avg_score > langgraph.avg_score + 0.1:
            return RoutingRecommendation(
                current_threshold=current_threshold,
                recommended_threshold=0.8,  # Route more to NeMo
                confidence=0.7,
                reasoning=(
                    f"NeMo outperforms LangGraph "
                    f"(NeMo: {nemo.avg_score:.2f} vs LangGraph: {langgraph.avg_score:.2f})"
                ),
                should_update=True,
            )

        # If LangGraph performs significantly better
        if langgraph.avg_score > nemo.avg_score + 0.1:
            return RoutingRecommendation(
                current_threshold=current_threshold,
                recommended_threshold=0.6,  # Route more to LangGraph
                confidence=0.7,
                reasoning=(
                    f"LangGraph outperforms NeMo "
                    f"(LangGraph: {langgraph.avg_score:.2f} vs NeMo: {nemo.avg_score:.2f})"
                ),
                should_update=True,
            )

        # Performance is similar, keep current threshold
        return RoutingRecommendation(
            current_threshold=current_threshold,
            recommended_threshold=current_threshold,
            confidence=0.5,
            reasoning="Performance is similar between paths, keeping current threshold",
            should_update=False,
        )

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get current performance summary for monitoring."""
        return {
            "nemo": {
                "total_samples": self._nemo_performance.total_samples,
                "avg_score": self._nemo_performance.avg_score,
                "avg_latency_ms": self._nemo_performance.avg_latency_ms,
                "pass_rate": self._nemo_performance.pass_rate,
            },
            "langgraph": {
                "total_samples": self._langgraph_performance.total_samples,
                "avg_score": self._langgraph_performance.avg_score,
                "avg_latency_ms": self._langgraph_performance.avg_latency_ms,
                "pass_rate": self._langgraph_performance.pass_rate,
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def get_routing_recommendations(self) -> Dict[str, Any]:
        """
        Get routing recommendations based on current performance.

        Returns:
            Dict with performance comparison and recommendations
        """
        recommendation = await self._generate_routing_recommendation()

        return {
            "nemo_performance": self._nemo_performance.avg_score,
            "langgraph_performance": self._langgraph_performance.avg_score,
            "current_threshold": recommendation.current_threshold,
            "recommended_threshold": recommendation.recommended_threshold,
            "confidence": recommendation.confidence,
            "reasoning": recommendation.reasoning,
            "should_update": recommendation.should_update,
        }


class RoutingOptimizer:
    """
    Optimizes routing thresholds based on historical performance.

    Uses evaluation results to dynamically adjust when to route
    to NeMo vs LangGraph.
    """

    def __init__(self, feedback_loop: EvaluationFeedbackLoop):
        self.feedback_loop = feedback_loop
        self.threshold_history: List[Dict[str, Any]] = []

    async def optimize(self) -> Optional[float]:
        """
        Run optimization and return new threshold if recommended.

        Returns:
            New threshold value if update recommended, None otherwise
        """
        recommendation = await self.feedback_loop._generate_routing_recommendation()

        if recommendation.should_update:
            # Log threshold change
            self.threshold_history.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "old_threshold": recommendation.current_threshold,
                    "new_threshold": recommendation.recommended_threshold,
                    "reasoning": recommendation.reasoning,
                }
            )
            return recommendation.recommended_threshold

        return None

    def get_threshold_history(self) -> List[Dict[str, Any]]:
        """Get history of threshold changes."""
        return self.threshold_history.copy()
