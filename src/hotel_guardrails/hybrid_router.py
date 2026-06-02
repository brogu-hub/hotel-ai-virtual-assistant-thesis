# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Safety Router - Routes ALL requests to LangGraph with safety filtering.

SIMPLIFIED ARCHITECTURE:
- LangGraph Agent handles ALL query processing (simple and complex)
- Regex-based safety filter blocks harmful patterns
- Complexity classification is kept for logging/metrics only

Benefits:
- Simpler single-path architecture
- Better reasoning for all queries
- Easier to debug and improve
- Consistent behavior

Usage:
    from src.hotel_guardrails.hybrid_router import HybridRouter, RoutingPath

    router = HybridRouter()
    decision = await router.route(query="Book a room", session_id="123")

    if decision.path == RoutingPath.BLOCKED:
        # Blocked by safety filter
        pass
    else:
        # Always use LangGraph
        response = await langgraph_adapter.invoke(...)
"""
import logging
import re
from enum import Enum
from typing import Optional, Callable, Awaitable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RoutingPath(Enum):
    """Available routing paths for requests."""

    LANGGRAPH_AGENT = "langgraph"  # Primary path - ALL queries
    BLOCKED = "blocked"  # Safety blocked


class ComplexityLevel(Enum):
    """Query complexity levels (for logging/metrics only)."""

    SIMPLE = "simple"  # Single-turn Q&A, greetings
    MODERATE = "moderate"  # RAG queries with context
    COMPLEX = "complex"  # Multi-step operations, bookings


class RoutingDecision(BaseModel):
    """Result of routing decision."""

    path: RoutingPath = Field(..., description="Which handler to use")
    complexity: ComplexityLevel = Field(..., description="Detected complexity (for metrics)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reason: str = Field(..., description="Human-readable reason for decision")
    historical_score: Optional[float] = Field(
        None, description="Historical performance score (for metrics)"
    )


class HybridRouter:
    """
    Safety Router - Routes ALL valid queries to LangGraph.

    This simplified router:
    1. Checks for blocked/unsafe content patterns
    2. Classifies complexity for logging purposes
    3. Routes ALL valid queries to LangGraph Agent

    Example:
        ```python
        router = HybridRouter()

        # ALL valid queries go to LangGraph
        decision = await router.route("What time is breakfast?", "session-1")
        assert decision.path == RoutingPath.LANGGRAPH_AGENT

        decision = await router.route("Book a room", "session-2")
        assert decision.path == RoutingPath.LANGGRAPH_AGENT
        ```
    """

    # Patterns that indicate blocked/unsafe content.
    # Two categories:
    #   (1) prompt-injection / social-engineering shapes
    #   (2) database / shell destructive shapes — fold of the
    #       previously-dead actions.check_input_safety() list, hardened
    #       (case-insensitive, word-boundary, common comment terminators)
    BLOCKED_PATTERNS = [
        # --- category 1: prompt injection / social engineering ---
        r"\b(hack|exploit|bypass|injection|sql injection)\b",
        r"\b(illegal|weapon|drug|steal|fraud)\b",
        r"\b(ignore previous|forget instructions|jailbreak)\b",
        r"\b(password hack|credential dump)\b",
        r"\b(xss|script injection)\b",
        r"\b(password bypass)\b",

        # --- category 2: destructive SQL / shell shapes ---
        # NL→SQL is not active in the chat path, but a hostile prompt that
        # tricks the LLM into emitting these strings as text can still trip
        # log scrapers, copy-paste pipelines, and any future SQL surface.
        r"\b(drop\s+table|drop\s+database|drop\s+schema)\b",
        r"\b(delete\s+from)\b",
        r"\b(truncate\s+table|truncate\b)",
        r"\b(union\s+select|union\s+all\s+select)\b",
        r"\b(alter\s+table|alter\s+role|alter\s+user)\b",
        r"\b(grant\s+all|revoke\s+all)\b",
        # SQL-comment-based comment-out attack: `'; -- ` or `'); -- `
        r"(;\s*--|;\s*#)",
        # Python/JS eval-style code injection
        r"\b(exec\s*\(|eval\s*\(|os\.system|subprocess)\b",
    ]

    # Patterns for complexity classification (logging/metrics only)
    SIMPLE_PATTERNS = [
        r"\b(hello|hi|hey|good morning|good afternoon|good evening)\b",
        r"\b(thank|thanks|thank you)\b",
        r"(สวัสดี|ขอบคุณ|ลาก่อน)",
        r"\b(what time|when|where is|how much)\b",
        r"\b(wifi|breakfast|checkout|check-in|pool|spa|gym)\b",
        r"(กี่โมง|ที่ไหน|ราคา|รหัส|เวลา)",
    ]

    COMPLEX_PATTERNS = [
        r"\b(book|reserve|reservation|จอง)\b",
        r"\b(cancel|cancellation|ยกเลิก)\b",
        r"\b(modify|change|update|เปลี่ยน|แก้ไข)\b",
        r"\b(and also|then|after that|แล้วก็|และ)\b",
        r"\b(compare|recommend|suggest|แนะนำ|เปรียบเทียบ)\b",
        r"\b(return|refund|คืน)\b",
    ]

    def __init__(
        self,
        feedback_store: Optional[Callable[[str], Awaitable[Optional[float]]]] = None,
        **kwargs,  # Accept but ignore legacy parameters
    ):
        """
        Initialize Safety Router.

        Args:
            feedback_store: Async function to get historical performance score (for metrics)
        """
        self.feedback_store = feedback_store

        # Compile regex patterns for efficiency
        self._blocked_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.BLOCKED_PATTERNS
        ]
        self._simple_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.SIMPLE_PATTERNS
        ]
        self._complex_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.COMPLEX_PATTERNS
        ]

        logger.info("HybridRouter initialized - LangGraph Primary mode")

    def _check_patterns(
        self, query: str, patterns: list[re.Pattern]
    ) -> tuple[bool, Optional[str]]:
        """Check if query matches any pattern."""
        for pattern in patterns:
            match = pattern.search(query)
            if match:
                return True, match.group()
        return False, None

    def _classify_complexity(self, query: str) -> tuple[ComplexityLevel, str]:
        """
        Classify query complexity for logging/metrics only.

        NOTE: This does NOT affect routing - all queries go to LangGraph.
        """
        query_lower = query.lower()

        # Check for complex patterns
        is_complex, complex_match = self._check_patterns(
            query_lower, self._complex_patterns
        )
        if is_complex:
            multi_step = ["and", "then", "also", "แล้ว", "และ"]
            if any(ind in query_lower for ind in multi_step):
                return ComplexityLevel.COMPLEX, f"multi-step:{complex_match}"
            return ComplexityLevel.COMPLEX, f"complex:{complex_match}"

        # Check for simple patterns
        is_simple, simple_match = self._check_patterns(
            query_lower, self._simple_patterns
        )
        if is_simple:
            return ComplexityLevel.SIMPLE, f"simple:{simple_match}"

        # Default to moderate
        return ComplexityLevel.MODERATE, "default:moderate"

    async def get_historical_score(
        self, complexity: ComplexityLevel
    ) -> Optional[float]:
        """Get historical performance score for metrics."""
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

        ALL valid queries are routed to LangGraph Agent.
        Only blocked content returns RoutingPath.BLOCKED.

        Args:
            query: User query
            session_id: Session identifier
            is_safe: Whether query passed external safety check

        Returns:
            RoutingDecision - always LANGGRAPH_AGENT unless blocked
        """
        # Check external safety flag
        if not is_safe:
            return RoutingDecision(
                path=RoutingPath.BLOCKED,
                complexity=ComplexityLevel.SIMPLE,
                confidence=1.0,
                reason="Query blocked by external safety filter",
            )

        # Check for blocked patterns
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

        # Classify complexity for logging/metrics
        complexity, pattern = self._classify_complexity(query)

        # Get historical performance score for metrics
        historical_score = await self.get_historical_score(complexity)

        # ALL valid queries go to LangGraph
        logger.info(
            f"Routing to LangGraph (complexity={complexity.value})",
            extra={"session_id": session_id, "pattern": pattern},
        )

        return RoutingDecision(
            path=RoutingPath.LANGGRAPH_AGENT,
            complexity=complexity,
            confidence=0.95,
            reason=f"LangGraph primary - {pattern}",
            historical_score=historical_score,
        )

    def update_thresholds(self, **kwargs) -> None:
        """Legacy method - no longer needed in LangGraph Primary mode."""
        logger.info("Threshold updates ignored in LangGraph Primary mode")
