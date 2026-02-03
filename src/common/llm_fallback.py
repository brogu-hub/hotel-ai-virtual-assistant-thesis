# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
LLM with Automatic Fallback - OpenRouter to NVIDIA

Provides a fault-tolerant LLM wrapper that:
1. Tries OpenRouter first (qwen/qwen3-max)
2. Falls back to NVIDIA NIM if OpenRouter fails
3. Handles rate limits gracefully (NVIDIA: 40 RPM)

Usage:
    from src.common.llm_fallback import get_llm_with_fallback

    llm = get_llm_with_fallback()
    response = llm.invoke("Hello!")
"""

import os
import time
import logging
from typing import Optional, List, Any, Dict, Iterator, Union
from collections import deque
from threading import Lock

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter for NVIDIA API (40 requests per minute).
    Uses a sliding window approach.
    """

    def __init__(self, max_requests: int = 40, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self.lock = Lock()

    def acquire(self) -> float:
        """
        Acquire permission to make a request.
        Returns wait time in seconds (0 if no wait needed).
        """
        with self.lock:
            now = time.time()

            # Remove old requests outside the window
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return 0.0

            # Calculate wait time
            wait_time = self.requests[0] + self.window_seconds - now
            return max(0.0, wait_time)

    def wait_and_acquire(self) -> None:
        """Wait if necessary and then acquire permission."""
        wait_time = self.acquire()
        if wait_time > 0:
            logger.info(f"Rate limit: waiting {wait_time:.2f}s before NVIDIA API call")
            time.sleep(wait_time)
            self.acquire()


# Global rate limiter for NVIDIA API
nvidia_rate_limiter = RateLimiter(max_requests=40, window_seconds=60)


class FallbackLLM(BaseChatModel):
    """
    LLM with automatic fallback from OpenRouter to NVIDIA.

    Tries OpenRouter first, falls back to NVIDIA on failure.
    Handles rate limits for NVIDIA API (40 RPM).
    """

    primary_llm: Optional[Any] = None
    fallback_llm: Optional[Any] = None
    primary_provider: str = "openrouter"
    fallback_provider: str = "nvidia"
    _primary_available: bool = True
    _last_failure_time: float = 0
    _retry_interval: float = 60.0

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 1024,
        streaming: bool = False,
        **kwargs
    ):
        super().__init__(**kwargs)

        # Initialize primary LLM (OpenRouter)
        try:
            from src.common.llm_openrouter import get_openrouter_llm
            self.primary_llm = get_openrouter_llm(
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=streaming,
            )
            logger.info("Primary LLM initialized: OpenRouter")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenRouter LLM: {e}")
            self.primary_llm = None
            self._primary_available = False

        # Initialize fallback LLM (NVIDIA NIM)
        try:
            nvidia_api_key = os.getenv("NVIDIA_API_KEY")
            if nvidia_api_key:
                from langchain_nvidia_ai_endpoints import ChatNVIDIA

                nvidia_model = os.getenv("NVIDIA_LLM_MODEL", "meta/llama-3.3-70b-instruct")
                self.fallback_llm = ChatNVIDIA(
                    model=nvidia_model,
                    api_key=nvidia_api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                logger.info(f"Fallback LLM initialized: NVIDIA NIM ({nvidia_model})")
            else:
                logger.warning("NVIDIA_API_KEY not set, fallback LLM unavailable")
                self.fallback_llm = None
        except Exception as e:
            logger.warning(f"Failed to initialize NVIDIA LLM: {e}")
            self.fallback_llm = None

    @property
    def _llm_type(self) -> str:
        return "fallback_llm"

    def _should_retry_primary(self) -> bool:
        """Check if we should retry the primary LLM."""
        if self._primary_available:
            return True
        return (time.time() - self._last_failure_time) > self._retry_interval

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """Generate response with automatic fallback."""

        # Try primary (OpenRouter)
        if self.primary_llm and self._should_retry_primary():
            try:
                # Use invoke for compatibility
                response = self.primary_llm.invoke(messages, stop=stop, **kwargs)
                self._primary_available = True
                logger.debug("Response from primary LLM (OpenRouter)")

                # Wrap in ChatResult
                if isinstance(response, AIMessage):
                    return ChatResult(generations=[ChatGeneration(message=response)])
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=str(response)))])
            except Exception as e:
                logger.warning(f"Primary LLM (OpenRouter) failed: {e}")
                self._primary_available = False
                self._last_failure_time = time.time()

        # Fallback to NVIDIA
        if self.fallback_llm:
            try:
                # Apply rate limiting for NVIDIA
                nvidia_rate_limiter.wait_and_acquire()

                response = self.fallback_llm.invoke(messages, stop=stop, **kwargs)
                logger.info("Response from fallback LLM (NVIDIA)")

                # Wrap in ChatResult
                if isinstance(response, AIMessage):
                    return ChatResult(generations=[ChatGeneration(message=response)])
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=str(response)))])
            except Exception as e:
                logger.error(f"Fallback LLM (NVIDIA) also failed: {e}")
                raise

        raise ValueError("No LLM available - both primary and fallback failed")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """Async generate with automatic fallback."""

        # Try primary (OpenRouter)
        if self.primary_llm and self._should_retry_primary():
            try:
                # Use ainvoke for compatibility
                response = await self.primary_llm.ainvoke(messages, stop=stop, **kwargs)
                self._primary_available = True
                logger.debug("Async response from primary LLM (OpenRouter)")

                # Wrap in ChatResult
                if isinstance(response, AIMessage):
                    return ChatResult(generations=[ChatGeneration(message=response)])
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=str(response)))])
            except Exception as e:
                logger.warning(f"Primary LLM (OpenRouter) failed: {e}")
                self._primary_available = False
                self._last_failure_time = time.time()

        # Fallback to NVIDIA
        if self.fallback_llm:
            try:
                # Apply rate limiting for NVIDIA
                nvidia_rate_limiter.wait_and_acquire()

                response = await self.fallback_llm.ainvoke(messages, stop=stop, **kwargs)
                logger.info("Async response from fallback LLM (NVIDIA)")

                # Wrap in ChatResult
                if isinstance(response, AIMessage):
                    return ChatResult(generations=[ChatGeneration(message=response)])
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=str(response)))])
            except Exception as e:
                logger.error(f"Fallback LLM (NVIDIA) also failed: {e}")
                raise

        raise ValueError("No LLM available - both primary and fallback failed")

    def bind_tools(self, tools, **kwargs):
        """Bind tools to the primary LLM (for function calling)."""
        if self.primary_llm and hasattr(self.primary_llm, 'bind_tools'):
            # Return a new instance with bound tools on primary
            bound = FallbackLLM.__new__(FallbackLLM)
            bound.primary_llm = self.primary_llm.bind_tools(tools, **kwargs)
            bound.fallback_llm = self.fallback_llm
            if self.fallback_llm and hasattr(self.fallback_llm, 'bind_tools'):
                bound.fallback_llm = self.fallback_llm.bind_tools(tools, **kwargs)
            bound.primary_provider = self.primary_provider
            bound.fallback_provider = self.fallback_provider
            bound._primary_available = self._primary_available
            bound._last_failure_time = self._last_failure_time
            bound._retry_interval = self._retry_interval
            return bound
        return self

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "primary_provider": self.primary_provider,
            "fallback_provider": self.fallback_provider,
            "primary_available": self._primary_available,
        }


def get_llm_with_fallback(
    temperature: float = 0.7,
    max_tokens: Optional[int] = 1024,
    streaming: bool = False,
    **kwargs
) -> FallbackLLM:
    """
    Get LLM with automatic OpenRouter -> NVIDIA fallback.

    Args:
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum response tokens
        streaming: Enable streaming (not yet supported in fallback mode)
        **kwargs: Additional arguments

    Returns:
        FallbackLLM instance
    """
    return FallbackLLM(
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        **kwargs
    )


# Convenience function that matches existing get_llm interface
def get_llm(**kwargs) -> FallbackLLM:
    """
    Get LLM with fallback - drop-in replacement for existing get_llm().
    """
    return get_llm_with_fallback(**kwargs)
