# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
LangGraph Adapter - Bridge to call LangGraph agent from the hybrid router.

Provides a unified interface between NeMo Guardrails server and LangGraph agent,
handling streaming responses, error handling, and session management.

Usage:
    from src.hotel_guardrails.langgraph_adapter import LangGraphAdapter

    adapter = LangGraphAdapter()
    result = await adapter.invoke(
        message="Book a room for tomorrow",
        session_id="session-123",
        user_id="guest-456"
    )

    if result["success"]:
        print(result["response"])
"""
import os
import logging
from typing import Dict, Any, Optional, List

import httpx

logger = logging.getLogger(__name__)

# Default LangGraph endpoint
LANGGRAPH_ENDPOINT = os.getenv("LANGGRAPH_ENDPOINT", "http://localhost:8090")


class LangGraphAdapter:
    """
    Adapter for calling LangGraph agent from the guardrails server.

    Handles:
    - HTTP communication with LangGraph endpoint
    - Streaming response parsing
    - Error handling with detailed logging
    - Session and user ID passthrough

    Example:
        ```python
        adapter = LangGraphAdapter()

        result = await adapter.invoke(
            message="I need to book a room and cancel my previous reservation",
            session_id="session-123",
            user_id="guest-456"
        )

        if result["success"]:
            print(result["response"])
        else:
            print(f"Error: {result['error']}")
        ```
    """

    def __init__(
        self,
        endpoint: str = LANGGRAPH_ENDPOINT,
        timeout: float = 60.0,
        max_retries: int = 2,
    ):
        """
        Initialize LangGraph Adapter.

        Args:
            endpoint: LangGraph server endpoint URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
        """
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries

        logger.info(f"LangGraphAdapter initialized: endpoint={endpoint}")

    async def invoke(
        self,
        message: str,
        session_id: str,
        user_id: str = "guest",
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Invoke LangGraph agent with the message.

        Args:
            message: User message to process
            session_id: Session identifier for conversation tracking
            user_id: User identifier for personalization
            conversation_history: Previous messages for context

        Returns:
            Dict with:
            - success: bool - Whether invocation succeeded
            - response: str - Agent response text
            - path: str - Always "langgraph"
            - tool_calls: List - Tools called during processing
            - error: str - Error message if failed
        """
        # Build messages list
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        # Prepare request payload
        payload = {
            "messages": messages,
            "user_id": user_id,
            "session_id": session_id,
        }

        # Try with retries
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await self._make_request(payload)
                if result["success"]:
                    return result
                last_error = result.get("error", "Unknown error")
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"LangGraph request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )

        # All retries failed
        logger.error(f"LangGraph invocation failed after {self.max_retries + 1} attempts")
        return {
            "success": False,
            "response": None,
            "path": "langgraph",
            "error": last_error,
        }

    async def _make_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to LangGraph endpoint.

        Args:
            payload: Request payload

        Returns:
            Result dict with success status and response
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/generate",
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                # Parse streaming response (collect all chunks)
                content = await self._parse_streaming_response(response.text)
                return {
                    "success": True,
                    "response": content,
                    "path": "langgraph",
                    "tool_calls": None,  # TODO: Extract from response if available
                }
            else:
                error_msg = f"LangGraph returned status {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg = f"{error_msg}: {error_detail.get('detail', response.text)}"
                except Exception:
                    error_msg = f"{error_msg}: {response.text[:200]}"

                logger.error(error_msg)
                return {
                    "success": False,
                    "response": None,
                    "path": "langgraph",
                    "error": error_msg,
                }

    async def _parse_streaming_response(self, response_text: str) -> str:
        """
        Parse SSE streaming response from LangGraph.

        Args:
            response_text: Raw response text with SSE format

        Returns:
            Concatenated content from all chunks
        """
        content_parts = []

        for line in response_text.split("\n"):
            line = line.strip()

            # Skip empty lines and done marker
            if not line:
                continue
            if line == "data: [DONE]":
                break

            # Parse data lines
            if line.startswith("data: "):
                chunk = line[6:]  # Remove "data: " prefix
                if chunk and chunk != "[DONE]":
                    content_parts.append(chunk)

        return "".join(content_parts)

    async def health_check(self) -> Dict[str, Any]:
        """
        Check if LangGraph endpoint is healthy.

        Returns:
            Dict with status and details
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.endpoint}/health",
                    timeout=5.0,
                )

                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "endpoint": self.endpoint,
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "endpoint": self.endpoint,
                        "error": f"Status {response.status_code}",
                    }
        except Exception as e:
            return {
                "status": "unreachable",
                "endpoint": self.endpoint,
                "error": str(e),
            }

    async def create_session(self) -> Optional[str]:
        """
        Create a new session on LangGraph endpoint.

        Returns:
            Session ID if created, None on failure
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.endpoint}/create_session",
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("session_id")
                else:
                    logger.warning(
                        f"Failed to create LangGraph session: {response.status_code}"
                    )
                    return None
        except Exception as e:
            logger.warning(f"Failed to create LangGraph session: {e}")
            return None

    async def end_session(self, session_id: str) -> bool:
        """
        End a session on LangGraph endpoint.

        Args:
            session_id: Session to end

        Returns:
            True if successfully ended
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.endpoint}/end_session",
                    json={"session_id": session_id},
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to end LangGraph session: {e}")
            return False
