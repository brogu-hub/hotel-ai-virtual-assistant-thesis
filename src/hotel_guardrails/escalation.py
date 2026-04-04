# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Auto-Escalation Monitor — detects when a conversation should be handed to staff.

Triggers:
1. Sentiment: guest uses frustrated/angry language
2. Repetition: guest asks same question 3+ times (bot failing)
3. High-value: booking total > 50,000 THB or Penthouse room

Usage:
    from src.hotel_guardrails.escalation import EscalationMonitor

    monitor = EscalationMonitor()
    should, reason, priority = monitor.should_escalate(session_id, message, context)
"""

import logging
from collections import defaultdict, deque
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Frustration signals — keywords that indicate the guest needs human help
FRUSTRATION_EN = [
    "speak to manager", "talk to a real person", "human agent",
    "this is ridiculous", "terrible service", "unacceptable",
    "worst hotel", "never coming back", "i want to complain",
    "complaint", "very upset", "extremely disappointed",
    "not working", "useless bot", "stupid bot",
]

FRUSTRATION_TH = [
    "ขอพูดกับผู้จัดการ", "ต้องการคุยกับคน", "ร้องเรียน",
    "แย่มาก", "ยอมรับไม่ได้", "ผิดหวังมาก", "โกรธ",
    "ไม่พอใจ", "เลวร้าย", "บอทไม่เก่ง", "ช่วยอะไรไม่ได้",
]

HIGH_VALUE_THRESHOLD = 50_000  # THB
HIGH_VALUE_ROOM_TYPES = {"penthouse"}
REPETITION_SIMILARITY = 0.7
REPETITION_COUNT = 3
MAX_HISTORY = 10


class EscalationMonitor:
    """Monitors conversations for auto-escalation triggers."""

    def __init__(self):
        # session_id -> deque of recent user messages
        self._session_messages: Dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

    def check_sentiment(self, message: str) -> Tuple[bool, str]:
        """Check for frustration/escalation keywords in Thai + English."""
        msg_lower = message.lower()

        for phrase in FRUSTRATION_EN:
            if phrase in msg_lower:
                return True, f"Frustrated guest (EN): '{phrase}'"

        for phrase in FRUSTRATION_TH:
            if phrase in message:
                return True, f"Frustrated guest (TH): '{phrase}'"

        return False, ""

    def check_repetition(self, session_id: str, message: str) -> Tuple[bool, str]:
        """Detect if guest is repeating the same question (bot failing)."""
        history = self._session_messages[session_id]
        history.append(message)

        if len(history) < REPETITION_COUNT:
            return False, ""

        # Count how many recent messages are similar to the current one
        similar_count = 0
        for prev in list(history)[:-1]:
            ratio = SequenceMatcher(None, message.lower(), prev.lower()).ratio()
            if ratio > REPETITION_SIMILARITY:
                similar_count += 1

        if similar_count >= REPETITION_COUNT - 1:
            return True, f"Guest repeated similar question {similar_count + 1} times"

        return False, ""

    def check_high_value(self, context: Optional[Dict]) -> Tuple[bool, str]:
        """Flag high-value bookings that may need personal attention."""
        if not context:
            return False, ""

        response = context.get("response", "")
        tool_calls = context.get("tool_calls") or []

        # Check for Penthouse mentions
        resp_lower = response.lower()
        if "penthouse" in resp_lower:
            return True, "High-value: Penthouse room inquiry"

        # Check tool call results for high amounts
        for tc in tool_calls:
            args = tc.get("args", {})
            # If we can detect amount from tool output
            if "total_amount" in str(args) or "penthouse" in str(args).lower():
                return True, "High-value: Premium booking detected"

        # Check response text for large amounts (rough heuristic)
        import re
        amounts = re.findall(r"(\d{1,3}(?:,\d{3})*)\s*(?:THB|บาท)", response)
        for amt_str in amounts:
            amt = int(amt_str.replace(",", ""))
            if amt >= HIGH_VALUE_THRESHOLD:
                return True, f"High-value: {amt:,} THB booking"

        return False, ""

    def should_escalate(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict] = None,
    ) -> Tuple[bool, str, str]:
        """
        Check all escalation triggers.

        Returns:
            (should_escalate, reason, priority)
            priority: "high", "medium", "low"
        """
        # Sentiment (highest priority)
        triggered, reason = self.check_sentiment(message)
        if triggered:
            return True, reason, "high"

        # Repetition (high priority — bot is failing)
        triggered, reason = self.check_repetition(session_id, message)
        if triggered:
            return True, reason, "high"

        # High-value (medium priority — FYI for staff)
        triggered, reason = self.check_high_value(context)
        if triggered:
            return True, reason, "medium"

        return False, "", ""
