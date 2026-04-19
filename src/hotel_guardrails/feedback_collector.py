# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Feedback Collector - Captures response quality signals for continuous improvement.

Collects three types of feedback:
1. Explicit - User thumbs up/down ratings
2. Implicit - Inferred from behavior (follow-up questions, retries)
3. Automated - From evaluation pipeline (DeepEval metrics)

The feedback is used to:
- Track response quality over time
- Optimize routing decisions based on historical performance
- Identify areas for improvement

Usage:
    from src.hotel_guardrails.feedback_collector import FeedbackCollector

    collector = FeedbackCollector()

    # Record every response
    await collector.record_response(
        request_id="req-123",
        session_id="session-456",
        query="What time is breakfast?",
        response="Breakfast is served 6:30 AM - 10:30 AM",
        routing_path="langgraph",
        complexity="simple",
        latency_ms=150.0
    )

    # Record explicit feedback
    await collector.record_explicit_feedback(
        request_id="req-123",
        score=1.0,  # Thumbs up
    )
"""
import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback signals."""

    EXPLICIT = "explicit"  # User thumbs up/down
    IMPLICIT = "implicit"  # Inferred from behavior
    AUTOMATED = "automated"  # From evaluation pipeline


class FeedbackRecord(BaseModel):
    """Record of a response with feedback signals."""

    request_id: str = Field(..., description="Unique request identifier")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the response was generated",
    )
    query: str = Field(..., description="User query")
    response: str = Field(..., description="AI response")
    routing_path: str = Field(..., description="Routing path (langgraph)")
    complexity: str = Field(..., description="simple, moderate, or complex")
    latency_ms: float = Field(..., description="Response latency in milliseconds")
    feedback_type: FeedbackType = Field(
        default=FeedbackType.AUTOMATED, description="Type of feedback"
    )
    score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Quality score (0.0-1.0)"
    )
    feedback_details: Optional[Dict[str, Any]] = Field(
        None, description="Additional feedback metadata"
    )


class FeedbackCollector:
    """
    Collects and stores feedback for evaluation pipeline.

    Feedback is stored in JSONL files for:
    - Easy append-only writes
    - Streaming reads for evaluation
    - Simple querying with grep/jq

    Example:
        ```python
        collector = FeedbackCollector()

        # Record response
        await collector.record_response(
            request_id="req-123",
            session_id="session-456",
            query="Book a room",
            response="I can help you book a room...",
            routing_path="langgraph",
            complexity="complex",
            latency_ms=2500.0
        )

        # Record user feedback
        await collector.record_explicit_feedback("req-123", score=0.8)

        # Detect implicit feedback from follow-up
        implicit_score = await collector.detect_implicit_feedback(
            session_id="session-456",
            current_query="That's not what I asked",
            previous_response="I can help you book..."
        )
        # Returns 0.3 (low score indicating poor response)
        ```
    """

    # Signals indicating poor response quality
    NEGATIVE_SIGNALS = [
        # English
        "not what i asked",
        "that's wrong",
        "that's not right",
        "incorrect",
        "i meant",
        "no,",
        "try again",
        "you misunderstood",
        "that doesn't help",
        "not helpful",
        # Thai
        "ไม่ใช่",
        "ผิด",
        "ลองใหม่",
        "ไม่ถูก",
        "ไม่ช่วย",
    ]

    # Signals indicating good response quality
    POSITIVE_SIGNALS = [
        # English
        "thanks",
        "thank you",
        "perfect",
        "great",
        "exactly",
        "that's right",
        "helpful",
        # Thai
        "ขอบคุณ",
        "ดีมาก",
        "เยี่ยม",
        "ถูกต้อง",
    ]

    def __init__(
        self,
        feedback_dir: Optional[str] = None,
        buffer_size: int = 10,
        enable_persistence: bool = True,
    ):
        """
        Initialize Feedback Collector.

        Args:
            feedback_dir: Directory to store feedback files
            buffer_size: Number of records to buffer before flush
            enable_persistence: Whether to persist to files
        """
        self.feedback_dir = Path(
            feedback_dir or os.getenv("FEEDBACK_LOG_DIR", "logs/feedback")
        )
        self.buffer_size = buffer_size
        self.enable_persistence = enable_persistence

        self._buffer: List[FeedbackRecord] = []
        self._request_map: Dict[str, FeedbackRecord] = {}  # For updating scores

        # Create feedback directory if needed
        if self.enable_persistence:
            self.feedback_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"FeedbackCollector initialized: dir={self.feedback_dir}")

    async def record_response(
        self,
        request_id: str,
        session_id: str,
        query: str,
        response: str,
        routing_path: str,
        complexity: str,
        latency_ms: float,
    ) -> None:
        """
        Record a response for later evaluation.

        Args:
            request_id: Unique request identifier
            session_id: Session identifier
            query: User query
            response: AI response
            routing_path: Which path handled the request (langgraph)
            complexity: Query complexity level
            latency_ms: Response latency
        """
        record = FeedbackRecord(
            request_id=request_id,
            session_id=session_id,
            query=query,
            response=response,
            routing_path=routing_path,
            complexity=complexity,
            latency_ms=latency_ms,
            feedback_type=FeedbackType.AUTOMATED,
            score=None,  # Will be filled by evaluation pipeline
        )

        self._buffer.append(record)
        self._request_map[request_id] = record

        logger.debug(
            f"Recorded response: request_id={request_id}, path={routing_path}, "
            f"complexity={complexity}, latency={latency_ms:.0f}ms"
        )

        # Flush buffer if full
        if len(self._buffer) >= self.buffer_size:
            await self._flush_buffer()

    async def record_explicit_feedback(
        self,
        request_id: str,
        score: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record explicit user feedback (thumbs up/down).

        Args:
            request_id: Request to add feedback to
            score: Quality score (0.0 = bad, 1.0 = good)
            details: Additional feedback details

        Returns:
            True if feedback was recorded
        """
        # Find the record
        record = self._request_map.get(request_id)
        if record:
            record.feedback_type = FeedbackType.EXPLICIT
            record.score = score
            record.feedback_details = details
            logger.info(f"Recorded explicit feedback: request_id={request_id}, score={score}")
            return True

        # Record not in buffer - try to update persisted record
        if self.enable_persistence:
            return await self._update_persisted_feedback(request_id, score, details)

        logger.warning(f"Request not found for feedback: {request_id}")
        return False

    async def detect_implicit_feedback(
        self,
        session_id: str,
        current_query: str,
        previous_response: str,
    ) -> Optional[float]:
        """
        Detect implicit feedback from user behavior.

        Analyzes the current query to detect signals of:
        - Negative feedback: "that's wrong", "not what I asked"
        - Positive feedback: "thanks", "perfect"

        Args:
            session_id: Session identifier
            current_query: Current user message
            previous_response: Previous AI response

        Returns:
            Inferred score (0.0-1.0) or None if no signal detected
        """
        query_lower = current_query.lower()

        # Check for negative signals
        for signal in self.NEGATIVE_SIGNALS:
            if signal in query_lower:
                logger.info(
                    f"Detected negative implicit feedback: '{signal}' in session {session_id}"
                )
                return 0.3  # Low score for negative feedback

        # Check for positive signals
        for signal in self.POSITIVE_SIGNALS:
            if signal in query_lower:
                logger.info(
                    f"Detected positive implicit feedback: '{signal}' in session {session_id}"
                )
                return 0.9  # High score for positive feedback

        return None  # No implicit feedback detected

    async def get_average_score(self, query_type: str) -> Optional[float]:
        """
        Get average score for a query type from historical data.

        This is used by the HybridRouter to make routing decisions
        based on historical performance.

        Args:
            query_type: Query complexity type (simple, moderate, complex)

        Returns:
            Average score (0.0-1.0) or None if insufficient data
        """
        scores = []

        # Check buffer first
        for record in self._buffer:
            if record.complexity == query_type and record.score is not None:
                scores.append(record.score)

        # Check persisted records if needed
        if len(scores) < 10 and self.enable_persistence:
            persisted_scores = await self._get_persisted_scores(query_type)
            scores.extend(persisted_scores)

        if not scores:
            return None

        return sum(scores) / len(scores)

    async def get_path_performance(
        self, routing_path: str, limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get performance statistics for a routing path.

        Args:
            routing_path: "langgraph"
            limit: Maximum records to analyze

        Returns:
            Dict with avg_score, avg_latency, count
        """
        records = []

        # Check buffer
        for record in self._buffer:
            if record.routing_path == routing_path:
                records.append(record)

        # TODO: Query persisted records

        if not records:
            return {
                "avg_score": None,
                "avg_latency_ms": None,
                "count": 0,
            }

        scored_records = [r for r in records if r.score is not None]
        avg_score = (
            sum(r.score for r in scored_records) / len(scored_records)
            if scored_records
            else None
        )
        avg_latency = sum(r.latency_ms for r in records) / len(records)

        return {
            "avg_score": avg_score,
            "avg_latency_ms": avg_latency,
            "count": len(records),
        }

    async def _flush_buffer(self) -> None:
        """Flush feedback buffer to persistent storage."""
        if not self._buffer or not self.enable_persistence:
            return

        # Write to JSONL file
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filepath = self.feedback_dir / f"feedback_{today}.jsonl"

        try:
            with open(filepath, "a", encoding="utf-8") as f:
                for record in self._buffer:
                    line = record.model_dump_json() + "\n"
                    f.write(line)

            logger.info(f"Flushed {len(self._buffer)} feedback records to {filepath}")
        except Exception as e:
            logger.error(f"Failed to flush feedback buffer: {e}")

        self._buffer.clear()
        self._request_map.clear()

    async def _update_persisted_feedback(
        self,
        request_id: str,
        score: float,
        details: Optional[Dict[str, Any]],
    ) -> bool:
        """Update feedback score in persisted records."""
        # Scan recent feedback files
        for filepath in sorted(self.feedback_dir.glob("feedback_*.jsonl"), reverse=True)[:7]:
            try:
                lines = []
                updated = False

                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        record = json.loads(line)
                        if record.get("request_id") == request_id:
                            record["score"] = score
                            record["feedback_type"] = FeedbackType.EXPLICIT.value
                            if details:
                                record["feedback_details"] = details
                            updated = True
                        lines.append(json.dumps(record, ensure_ascii=False))

                if updated:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")
                    logger.info(f"Updated persisted feedback: {request_id} in {filepath}")
                    return True

            except Exception as e:
                logger.warning(f"Error scanning {filepath}: {e}")

        return False

    async def _get_persisted_scores(self, query_type: str, limit: int = 100) -> List[float]:
        """Get historical scores from persisted files."""
        scores = []

        for filepath in sorted(self.feedback_dir.glob("feedback_*.jsonl"), reverse=True):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        record = json.loads(line)
                        if (
                            record.get("complexity") == query_type
                            and record.get("score") is not None
                        ):
                            scores.append(record["score"])
                            if len(scores) >= limit:
                                return scores
            except Exception as e:
                logger.warning(f"Error reading {filepath}: {e}")

        return scores

    async def close(self) -> None:
        """Flush remaining buffer and close collector."""
        await self._flush_buffer()
        logger.info("FeedbackCollector closed")
