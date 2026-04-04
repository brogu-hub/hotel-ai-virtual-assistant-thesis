# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
LangGraph Adapter - Bridge to embedded LangGraph agent from the hybrid router.

Now uses an embedded LangGraph agent (hotel_langgraph.py) instead of making
HTTP calls to an external service. This eliminates the need for a separate
LangGraph server deployment.

Features:
- Embedded LangGraph state machine for hotel operations
- OpenRouter -> NVIDIA LLM fallback for resilience
- Session management with in-memory checkpointing
- Full tool support for booking, services, and knowledge

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

logger = logging.getLogger(__name__)

# Mode: embedded (default) or http (legacy)
LANGGRAPH_MODE = os.getenv("LANGGRAPH_MODE", "embedded").lower()
LANGGRAPH_ENDPOINT = os.getenv("LANGGRAPH_ENDPOINT", "http://localhost:8090")


class LangGraphAdapter:
    """
    Adapter for calling LangGraph agent from the guardrails server.

    Supports two modes:
    - embedded (default): Uses the embedded hotel_langgraph agent
    - http: Makes HTTP calls to external LangGraph endpoint (legacy)

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
        mode: str = LANGGRAPH_MODE,
        endpoint: str = LANGGRAPH_ENDPOINT,
        timeout: float = 60.0,
        max_retries: int = 2,
        checkpointer=None,
    ):
        """
        Initialize LangGraph Adapter.

        Args:
            mode: 'embedded' (default) or 'http' (legacy)
            endpoint: LangGraph server endpoint URL (for http mode)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
            checkpointer: LangGraph checkpointer (PostgresSaver or MemorySaver)
        """
        self.mode = mode
        self.endpoint = endpoint
        self.timeout = timeout
        self.max_retries = max_retries

        logger.info(f"LangGraphAdapter initialized: mode={mode}")

        if mode == "embedded":
            # Pre-load the embedded graph with persistent checkpointer
            try:
                from src.hotel_guardrails.hotel_langgraph import get_hotel_graph
                self._graph = get_hotel_graph(checkpointer=checkpointer)
                logger.info("Embedded LangGraph agent loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedded LangGraph agent: {e}")
                self._graph = None

    async def invoke(
        self,
        message: str,
        session_id: str,
        user_id: str = "guest",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        llm_settings: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Invoke LangGraph agent with the message.

        Args:
            message: User message to process
            session_id: Session identifier for conversation tracking
            user_id: User identifier for personalization
            conversation_history: Previous messages for context
            llm_settings: Optional LLM configuration overrides

        Returns:
            Dict with:
            - success: bool - Whether invocation succeeded
            - response: str - Agent response text
            - path: str - Always "langgraph"
            - tool_calls: List - Tools called during processing
            - error: str - Error message if failed
        """
        if self.mode == "embedded":
            return await self._invoke_embedded(
                message, session_id, user_id, conversation_history, llm_settings
            )
        else:
            return await self._invoke_http(
                message, session_id, user_id, conversation_history
            )

    async def _invoke_embedded(
        self,
        message: str,
        session_id: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, str]]],
        llm_settings: Optional[Dict],
    ) -> Dict[str, Any]:
        """Invoke embedded LangGraph agent."""
        if self._graph is None:
            return {
                "success": False,
                "response": None,
                "path": "langgraph",
                "error": "Embedded LangGraph agent not loaded",
            }

        try:
            from src.hotel_guardrails.hotel_langgraph import invoke_hotel_agent

            result = await invoke_hotel_agent(
                message=message,
                session_id=session_id,
                user_id=user_id,
                conversation_history=conversation_history,
                llm_settings=llm_settings,
            )
            return result

        except Exception as e:
            import traceback
            error_msg = str(e) if str(e) else type(e).__name__
            logger.error(f"Embedded LangGraph invocation failed: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "response": None,
                "path": "langgraph",
                "error": f"{type(e).__name__}: {error_msg}" if error_msg else type(e).__name__,
            }

    async def _invoke_http(
        self,
        message: str,
        session_id: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, str]]],
    ) -> Dict[str, Any]:
        """Invoke LangGraph via HTTP (legacy mode)."""
        import httpx

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
                result = await self._make_http_request(payload)
                if result["success"]:
                    return result
                last_error = result.get("error", "Unknown error")
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"LangGraph HTTP request failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )

        # All retries failed
        logger.error(f"LangGraph HTTP invocation failed after {self.max_retries + 1} attempts")
        return {
            "success": False,
            "response": None,
            "path": "langgraph",
            "error": last_error,
        }

    async def _make_http_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to LangGraph endpoint."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/generate",
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                content = await self._parse_streaming_response(response.text)
                return {
                    "success": True,
                    "response": content,
                    "path": "langgraph",
                    "tool_calls": None,
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
        """Parse SSE streaming response from LangGraph."""
        content_parts = []

        for line in response_text.split("\n"):
            line = line.strip()

            if not line:
                continue
            if line == "data: [DONE]":
                break

            if line.startswith("data: "):
                chunk = line[6:]
                if chunk and chunk != "[DONE]":
                    content_parts.append(chunk)

        return "".join(content_parts)

    async def health_check(self) -> Dict[str, Any]:
        """Check if LangGraph is healthy."""
        if self.mode == "embedded":
            # Check embedded graph
            if self._graph is not None:
                return {
                    "status": "healthy",
                    "mode": "embedded",
                }
            else:
                return {
                    "status": "unhealthy",
                    "mode": "embedded",
                    "error": "Graph not loaded",
                }
        else:
            # Check HTTP endpoint
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.endpoint}/health",
                        timeout=5.0,
                    )

                    if response.status_code == 200:
                        return {
                            "status": "healthy",
                            "mode": "http",
                            "endpoint": self.endpoint,
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "mode": "http",
                            "endpoint": self.endpoint,
                            "error": f"Status {response.status_code}",
                        }
            except Exception as e:
                return {
                    "status": "unreachable",
                    "mode": "http",
                    "endpoint": self.endpoint,
                    "error": str(e),
                }

    async def create_session(self) -> Optional[str]:
        """
        Create a new session.

        For embedded mode, session is created automatically during invoke.
        Returns a UUID for tracking.
        """
        import uuid
        return str(uuid.uuid4())

    async def end_session(self, session_id: str) -> bool:
        """
        End a session.

        For embedded mode with MemorySaver, sessions are cleaned up automatically.
        """
        logger.info(f"Session {session_id} ended")
        return True
