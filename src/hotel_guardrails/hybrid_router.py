# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hybrid Router - Routes requests to NeMo Guardrails or LangGraph Agent
based on query complexity and historical performance.

This router implements a smart gateway that:
1. Classifies query complexity (simple, moderate, complex)
2. Checks historical performance scores from feedback loop
3. Routes to the optimal handler (NeMo for speed, LangGraph for reasoning)

Usage:
    from src.hotel_guardrails.hybrid_router import HybridRouter, RoutingPath

    router = HybridRouter()
    decision = await router.route(query="Book a room", session_id="123")

    if decision.path == RoutingPath.LANGGRAPH_AGENT:
        # Use LangGraph for complex reasoning
        pass
    elif decision.path == RoutingPath.NEMO_GUARDRAILS:
        # Use NeMo for fast response
        pass
"""
import os
import logging
import re
from enum import Enum
from typing import Optional, Callable, Awaitable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RoutingPath(Enum):
    """Available routing paths for requests."""

    NEMO_GUARDRAILS = "nemo"  # Fast path - simple queries, RAG
    LANGGRAPH_AGENT = "langgraph"  # Complex path - multi-step reasoning
    BLOCKED = "blocked"  # Safety blocked


class ComplexityLevel(Enum):
    """Query complexity levels."""

    SIMPLE = "simple"  # Single-turn Q&A, greetings
    MODERATE = "moderate"  # Booking check, RAG with context
    COMPLEX = "complex"  # Multi-step operations, returns, chained tools


class RoutingDecision(BaseModel):
    """Result of routing decision."""

    path: RoutingPath = Field(..., description="Which handler to use")
    complexity: ComplexityLevel = Field(..., description="Detected complexity")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reason: str = Field(..., description="Human-readable reason for decision")
    historical_score: Optional[float] = Field(
        None, description="Historical performance score from feedback loop"
    )


class HybridRouter:
    """
    Routes requests based on complexity and historical performance.

    The router uses a combination of:
    1. Pattern matching for obvious simple/complex queries
    2. Historical performance scores to optimize over time
    3. Configurable thresholds for routing decisions

    Example:
        ```python
        router = HybridRouter()

        # Simple query -> NeMo
        decision = await router.route("What time is breakfast?", "session-1")
        assert decision.path == RoutingPath.NEMO_GUARDRAILS

        # Complex query -> LangGraph
        decision = await router.route("Book a room and cancel my previous one", "session-2")
        assert decision.path == RoutingPath.LANGGRAPH_AGENT
        ```
    """

    # Patterns for simple queries (NeMo handles these efficiently)
    SIMPLE_PATTERNS = [
        # English greetings
        r"\b(hello|hi|hey|good morning|good afternoon|good evening)\b",
        r"\b(thank|thanks|thank you)\b",
        r"\b(bye|goodbye|see you)\b",
        # Thai greetings
        r"(สวัสดี|ขอบคุณ|ลาก่อน)",
        # Simple questions
        r"\b(what time|when|where is|how much|how long)\b",
        r"\b(wifi|breakfast|checkout|check-in|pool|spa|gym)\b",
        r"\b(password|hours|location|address|phone)\b",
        # Thai simple questions
        r"(กี่โมง|ที่ไหน|ราคา|รหัส|เวลา)",
    ]

    # Patterns requiring complex reasoning (LangGraph handles these)
    COMPLEX_PATTERNS = [
        # Booking operations
        r"\b(book|reserve|reservation|จอง)\b",
        r"\b(cancel|cancellation|ยกเลิก)\b",
        r"\b(modify|change|update|เปลี่ยน|แก้ไข)\b",
        # Multi-step operations
        r"\b(and also|then|after that|แล้วก็|และ)\b",
        r"\b(compare|recommend|suggest|แนะนำ|เปรียบเทียบ)\b",
        # Returns and refunds
        r"\b(return|refund|คืน)\b",
        # Order/status tracking
        r"\b(order status|track|ติดตาม|สถานะ)\b",
        # Complex conditions
        r"\b(if|unless|depending|ถ้า|หาก)\b",
    ]

    # Patterns that indicate blocked content
    BLOCKED_PATTERNS = [
        r"\b(hack|exploit|bypass|injection)\b",
        r"\b(illegal|weapon|drug)\b",
    ]

    def __init__(
        self,
        feedback_store: Optional[Callable[[str], Awaitable[Optional[float]]]] = None,
        complexity_threshold: Optional[float] = None,
        performance_override: Optional[float] = None,
    ):
        """
        Initialize Hybrid Router.

        Args:
            feedback_store: Async function to get historical performance score
            complexity_threshold: Threshold for routing moderate queries to LangGraph
            performance_override: If NeMo performs above this, keep using it
        """
        self.feedback_store = feedback_store
        self.complexity_threshold = complexity_threshold or float(
            os.getenv("ROUTING_COMPLEXITY_THRESHOLD", "0.7")
        )
        self.performance_override = performance_override or float(
            os.getenv("ROUTING_PERFORMANCE_OVERRIDE", "0.8")
        )

        # Compile regex patterns for efficiency
        self._simple_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SIMPLE_PATTERNS
        ]
        self._complex_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.COMPLEX_PATTERNS
        ]
        self._blocked_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.BLOCKED_PATTERNS
        ]

        logger.info(
            f"HybridRouter initialized: complexity_threshold={self.complexity_threshold}, "
            f"performance_override={self.performance_override}"
        )

    def _check_patterns(
        self, query: str, patterns: list[re.Pattern]
    ) -> tuple[bool, Optional[str]]:
        """Check if query matches any pattern."""
        for pattern in patterns:
            match = pattern.search(query)
            if match:
                return True, match.group()
        return False, None

    async def classify_complexity(
        self, query: str
    ) -> tuple[ComplexityLevel, float, str]:
        """
        Classify query complexity using pattern matching.

        Args:
            query: User query to classify

        Returns:
            Tuple of (complexity level, confidence, matched pattern)
        """
        query_lower = query.lower()

        # Check for blocked patterns first
        is_blocked, blocked_match = self._check_patterns(
            query_lower, self._blocked_patterns
        )
        if is_blocked:
            return ComplexityLevel.SIMPLE, 1.0, f"blocked:{blocked_match}"

        # Check for complex patterns
        is_complex, complex_match = self._check_patterns(
            query_lower, self._complex_patterns
        )
        if is_complex:
            # Check if it's a multi-step request (higher complexity)
            multi_step_indicators = ["and", "then", "also", "แล้ว", "และ"]
            if any(ind in query_lower for ind in multi_step_indicators):
                return ComplexityLevel.COMPLEX, 0.95, f"multi-step:{complex_match}"
            return ComplexityLevel.COMPLEX, 0.85, f"complex:{complex_match}"

        # Check for simple patterns
        is_simple, simple_match = self._check_patterns(
            query_lower, self._simple_patterns
        )
        if is_simple:
            return ComplexityLevel.SIMPLE, 0.9, f"simple:{simple_match}"

        # Default to moderate complexity
        return ComplexityLevel.MODERATE, 0.6, "default:moderate"

    async def get_historical_score(
        self, complexity: ComplexityLevel
    ) -> Optional[float]:
        """
        Get historical performance score for similar queries.

        Args:
            complexity: Query complexity level

        Returns:
            Average score (0.0-1.0) or None if no data
        """
        if self.feedback_store:
            try:
                return await self.feedback_store(complexity.value)
            except Exception as e:
                logger.warning(f"Failed to get historical score: {e}")
        return None

    async def route(
        self,
        query: str,
        session_id: str,
        is_safe: bool = True,
    ) -> RoutingDecision:
        """
        Determine routing path for the query.

        Args:
            query: User query
            session_id: Session identifier
            is_safe: Whether query passed safety check

        Returns:
            RoutingDecision with path, complexity, and reasoning
        """
        # Safety check first
        if not is_safe:
            return RoutingDecision(
                path=RoutingPath.BLOCKED,
                complexity=ComplexityLevel.SIMPLE,
                confidence=1.0,
                reason="Query blocked by safety filter",
            )

        # Check for explicitly blocked patterns
        is_blocked, blocked_match = self._check_patterns(
            query.lower(), self._blocked_patterns
        )
        if is_blocked:
            logger.warning(
                f"Query blocked by pattern match: {blocked_match}",
                extra={"session_id": session_id},
            )
            return RoutingDecision(
                path=RoutingPath.BLOCKED,
                complexity=ComplexityLevel.SIMPLE,
                confidence=1.0,
                reason=f"Query contains blocked pattern: {blocked_match}",
            )

        # Classify complexity
        complexity, confidence, pattern = await self.classify_complexity(query)

        # Get historical performance score
        historical_score = await self.get_historical_score(complexity)

        # Make routing decision
        if complexity == ComplexityLevel.SIMPLE:
            path = RoutingPath.NEMO_GUARDRAILS
            reason = f"Simple query ({pattern}) - using fast path"

        elif complexity == ComplexityLevel.COMPLEX:
            path = RoutingPath.LANGGRAPH_AGENT
            reason = f"Complex query ({pattern}) - using reasoning path"

        else:
            # Moderate complexity - use historical performance to decide
            if (
                historical_score is not None
                and historical_score > self.performance_override
            ):
                # NeMo performs well on these, keep using it
                path = RoutingPath.NEMO_GUARDRAILS
                reason = (
                    f"Moderate query - NeMo performs well "
                    f"(historical: {historical_score:.2f})"
                )
            else:
                # Default moderate queries to LangGraph for better reasoning
                path = RoutingPath.LANGGRAPH_AGENT
                reason = f"Moderate query ({pattern}) - using reasoning path"

        logger.info(
            f"Routing decision: {path.value} (complexity={complexity.value}, "
            f"confidence={confidence:.2f})",
            extra={"session_id": session_id, "pattern": pattern},
        )

        return RoutingDecision(
            path=path,
            complexity=complexity,
            confidence=confidence,
            reason=reason,
            historical_score=historical_score,
        )

    def update_thresholds(
        self,
        complexity_threshold: Optional[float] = None,
        performance_override: Optional[float] = None,
    ) -> None:
        """
        Update routing thresholds dynamically.

        This is called by the evaluation feedback loop to optimize routing.

        Args:
            complexity_threshold: New complexity threshold
            performance_override: New performance override threshold
        """
        if complexity_threshold is not None:
            self.complexity_threshold = complexity_threshold
            logger.info(f"Updated complexity_threshold to {complexity_threshold}")

        if performance_override is not None:
            self.performance_override = performance_override
            logger.info(f"Updated performance_override to {performance_override}")
