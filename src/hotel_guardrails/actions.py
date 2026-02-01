# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
NeMo Guardrails Custom Actions

Wraps existing hotel_tools.py and RAG chain for NeMo integration.
All actions are async and return ActionResult objects.

Usage:
    # These actions are registered with NeMo Guardrails in server.py
    # and invoked via Colang flows in rails.co
"""
import logging
from typing import Optional

from nemoguardrails.actions import action
from nemoguardrails.actions.actions import ActionResult

logger = logging.getLogger(__name__)

# Initialize RAG retriever (singleton)
_retriever = None


def get_retriever():
    """Get or create the hotel knowledge retriever."""
    global _retriever
    if _retriever is None:
        try:
            from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever
            _retriever = HotelKnowledgeRetriever()
            logger.info("Hotel knowledge retriever initialized")
        except Exception as e:
            logger.error(f"Failed to initialize retriever: {e}")
            raise
    return _retriever


# =============================================================================
# RAG Action
# =============================================================================


@action(name="search_hotel_knowledge")
async def search_hotel_knowledge(query: str) -> ActionResult:
    """
    Search hotel knowledge base using RAG.

    Pipeline: Qdrant retrieval -> Rerank -> Format response

    Args:
        query: Search query in Thai or English

    Returns:
        ActionResult with formatted knowledge content
    """
    try:
        retriever = get_retriever()
        results = retriever.document_search(query, num_docs=3)

        if not results:
            logger.info(f"No results found for query: {query[:50]}...")
            return ActionResult(
                return_value="ขออภัยค่ะ ไม่พบข้อมูลที่ต้องการ / Sorry, I couldn't find that information."
            )

        # Format results for response
        content = "\n\n".join([r["content"] for r in results])
        logger.info(f"RAG returned {len(results)} results for: {query[:50]}...")

        return ActionResult(return_value=content)

    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        return ActionResult(
            return_value="ขออภัยค่ะ เกิดข้อผิดพลาดในการค้นหา / Sorry, an error occurred during search."
        )


async def search_hotel_knowledge_with_sources(query: str) -> tuple:
    """
    Search hotel knowledge base and return both content and sources.

    Args:
        query: Search query in Thai or English

    Returns:
        Tuple of (content: str, sources: List[str])
    """
    try:
        retriever = get_retriever()
        results = retriever.document_search(query, num_docs=3)

        if not results:
            logger.info(f"No results found for query: {query[:50]}...")
            return (
                "ขออภัยค่ะ ไม่พบข้อมูลที่ต้องการ / Sorry, I couldn't find that information.",
                []
            )

        # Format results for response
        content = "\n\n".join([r["content"] for r in results])
        # Extract sources from results
        sources = [r.get("source", "unknown") for r in results]
        # Also include the actual content chunks as context for evaluation
        retrieval_context = [r["content"] for r in results]

        logger.info(f"RAG returned {len(results)} results for: {query[:50]}...")

        return (content, sources, retrieval_context)

    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        return (
            "ขออภัยค่ะ เกิดข้อผิดพลาดในการค้นหา / Sorry, an error occurred during search.",
            [],
            []
        )


# =============================================================================
# Booking Actions
# =============================================================================


@action(name="check_room_availability")
async def check_room_availability(
    check_in: str,
    check_out: str,
    room_type: Optional[str] = None,
) -> ActionResult:
    """
    Check available rooms for specified dates.

    Args:
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        room_type: Optional room type filter

    Returns:
        ActionResult with availability information
    """
    try:
        from src.agent.hotel_tools import check_room_availability as _check_availability

        result = _check_availability.invoke({
            "check_in": check_in,
            "check_out": check_out,
            "room_type": room_type or "any",
        })

        logger.info(f"Availability check: {check_in} to {check_out}, type={room_type}")
        return ActionResult(return_value=result)

    except Exception as e:
        logger.error(f"Availability check failed: {e}")
        return ActionResult(
            return_value=f"ขออภัยค่ะ ไม่สามารถตรวจสอบห้องว่างได้ / Error checking availability: {e}"
        )


@action(name="create_reservation")
async def create_reservation(
    guest_id: str,
    room_id: str,
    check_in: str,
    check_out: str,
    special_requests: Optional[str] = None,
) -> ActionResult:
    """
    Create a new room reservation.

    Args:
        guest_id: Guest identifier
        room_id: Room to reserve
        check_in: Check-in date (YYYY-MM-DD)
        check_out: Check-out date (YYYY-MM-DD)
        special_requests: Optional special requests

    Returns:
        ActionResult with reservation confirmation
    """
    try:
        from src.agent.hotel_tools import create_reservation as _create_reservation

        result = _create_reservation.invoke({
            "guest_id": guest_id,
            "room_id": room_id,
            "check_in": check_in,
            "check_out": check_out,
            "special_requests": special_requests or "",
        })

        logger.info(f"Reservation created: guest={guest_id}, room={room_id}")
        return ActionResult(return_value=result)

    except Exception as e:
        logger.error(f"Reservation creation failed: {e}")
        return ActionResult(
            return_value=f"ขออภัยค่ะ ไม่สามารถจองห้องได้ / Error creating reservation: {e}"
        )


@action(name="confirm_reservation")
async def confirm_reservation(reservation_id: str) -> ActionResult:
    """
    Confirm a pending reservation.

    Args:
        reservation_id: Reservation to confirm

    Returns:
        ActionResult with confirmation status
    """
    try:
        from src.agent.hotel_tools import confirm_reservation as _confirm_reservation

        result = _confirm_reservation.invoke({"reservation_id": reservation_id})

        logger.info(f"Reservation confirmed: {reservation_id}")
        return ActionResult(return_value=result)

    except Exception as e:
        logger.error(f"Reservation confirmation failed: {e}")
        return ActionResult(
            return_value=f"ขออภัยค่ะ ไม่สามารถยืนยันการจองได้ / Error confirming reservation: {e}"
        )


@action(name="cancel_reservation")
async def cancel_reservation(
    reservation_id: str,
    reason: Optional[str] = None,
) -> ActionResult:
    """
    Cancel an existing reservation.

    Args:
        reservation_id: Reservation to cancel
        reason: Optional cancellation reason

    Returns:
        ActionResult with cancellation confirmation
    """
    try:
        from src.agent.hotel_tools import cancel_reservation as _cancel_reservation

        result = _cancel_reservation.invoke({
            "reservation_id": reservation_id,
            "reason": reason or "Guest requested cancellation",
        })

        logger.info(f"Reservation cancelled: {reservation_id}")
        return ActionResult(return_value=result)

    except Exception as e:
        logger.error(f"Reservation cancellation failed: {e}")
        return ActionResult(
            return_value=f"ขออภัยค่ะ ไม่สามารถยกเลิกการจองได้ / Error cancelling reservation: {e}"
        )


@action(name="get_reservation_details")
async def get_reservation_details(reservation_id: str) -> ActionResult:
    """
    Get details of a specific reservation.

    Args:
        reservation_id: Reservation to retrieve

    Returns:
        ActionResult with reservation details
    """
    try:
        from src.agent.hotel_tools import get_reservation_details as _get_details

        result = _get_details.invoke({"reservation_id": reservation_id})

        logger.info(f"Retrieved reservation details: {reservation_id}")
        return ActionResult(return_value=result)

    except Exception as e:
        logger.error(f"Failed to get reservation details: {e}")
        return ActionResult(
            return_value=f"ขออภัยค่ะ ไม่พบข้อมูลการจอง / Error getting reservation: {e}"
        )


# =============================================================================
# Safety Actions
# =============================================================================


@action(name="check_input_safety")
async def check_input_safety(user_message: Optional[str] = None) -> ActionResult:
    """
    Check user input for inappropriate or harmful content.

    Args:
        user_message: The user's message to check

    Returns:
        ActionResult with boolean (True = safe, False = blocked)
    """
    # Handle None or empty message
    if not user_message:
        return ActionResult(return_value=True)

    # Blocked patterns for security
    blocked_patterns = [
        "hack",
        "exploit",
        "attack",
        "illegal",
        "password bypass",
        "sql injection",
        "xss",
        "script injection",
        "drop table",
        "delete from",
        "exec(",
        "eval(",
    ]

    message_lower = user_message.lower()
    for pattern in blocked_patterns:
        if pattern in message_lower:
            logger.warning(f"Blocked input containing: {pattern}")
            return ActionResult(return_value=False)

    return ActionResult(return_value=True)


@action(name="check_output_safety")
async def check_output_safety(bot_message: Optional[str] = None) -> ActionResult:
    """
    Check bot output for sensitive data leaks.

    Args:
        bot_message: The bot's message to check

    Returns:
        ActionResult with boolean (True = safe, False = blocked)
    """
    # Handle None or empty message
    if not bot_message:
        return ActionResult(return_value=True)

    # Sensitive patterns that should not appear in output
    sensitive_patterns = [
        "credit card",
        "card number",
        "cvv",
        "password:",
        "api_key",
        "secret_key",
        "private key",
        "access_token",
        "bearer ",
        "authorization:",
    ]

    message_lower = bot_message.lower()
    for pattern in sensitive_patterns:
        if pattern in message_lower:
            logger.warning(f"Blocked output containing: {pattern}")
            return ActionResult(return_value=False)

    return ActionResult(return_value=True)


# =============================================================================
# Utility Actions
# =============================================================================


@action(name="detect_language")
async def detect_language(text: str) -> ActionResult:
    """
    Detect if text is Thai or English.

    Args:
        text: Text to analyze

    Returns:
        ActionResult with language code ('th' or 'en')
    """
    # Simple Thai character detection
    thai_chars = set("กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรฤลฦวศษสหฬอฮ")
    text_chars = set(text)

    if thai_chars & text_chars:
        return ActionResult(return_value="th")
    return ActionResult(return_value="en")


@action(name="format_bilingual_response")
async def format_bilingual_response(
    thai_text: str,
    english_text: str,
) -> ActionResult:
    """
    Format a bilingual response.

    Args:
        thai_text: Thai version of the response
        english_text: English version of the response

    Returns:
        ActionResult with formatted bilingual response
    """
    formatted = f"{thai_text} / {english_text}"
    return ActionResult(return_value=formatted)
