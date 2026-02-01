# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
OpenRouter LLM Integration for LangChain

Provides a drop-in replacement for NVIDIA endpoints using OpenRouter API.
Compatible with existing LangChain patterns in the codebase.

Usage:
    from src.common.llm_openrouter import get_openrouter_llm

    llm = get_openrouter_llm()
    response = llm.invoke("Hello, how can I help you?")
"""

import os
import logging
from typing import Optional, List, Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.callbacks import CallbackManagerForLLMRun

logger = logging.getLogger(__name__)


class ChatOpenRouter(ChatOpenAI):
    """
    OpenRouter-compatible LLM client extending LangChain's ChatOpenAI.

    OpenRouter provides access to multiple LLM models through a unified API
    that is compatible with the OpenAI API format.

    Attributes:
        model_name: The model to use (e.g., 'qwen/qwen3-max', 'anthropic/claude-3-opus')
        openai_api_base: OpenRouter API endpoint
        openai_api_key: OpenRouter API key
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        streaming: bool = False,
        **kwargs
    ):
        """
        Initialize OpenRouter LLM client.

        Args:
            model_name: Model to use (default from env APP_LLM_MODELNAME)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            streaming: Enable streaming responses
            **kwargs: Additional arguments passed to ChatOpenAI
        """
        # Get configuration from environment
        api_key = os.getenv('OPENROUTER_API_KEY')
        base_url = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
        model = model_name or os.getenv('APP_LLM_MODELNAME', 'qwen/qwen3-max')

        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        logger.info(f"Initializing OpenRouter LLM with model: {model}")

        super().__init__(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            **kwargs
        )

    @property
    def _llm_type(self) -> str:
        """Return the type of LLM."""
        return "openrouter"


def get_openrouter_llm(
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    streaming: bool = False,
    **kwargs
) -> ChatOpenRouter:
    """
    Factory function to create an OpenRouter LLM instance.

    Args:
        model_name: Model to use (default from env)
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        streaming: Enable streaming responses
        **kwargs: Additional arguments

    Returns:
        ChatOpenRouter instance

    Example:
        ```python
        from src.common.llm_openrouter import get_openrouter_llm

        # Basic usage
        llm = get_openrouter_llm()
        response = llm.invoke("What rooms are available?")

        # With custom settings
        llm = get_openrouter_llm(
            model_name="anthropic/claude-3-sonnet",
            temperature=0.5,
            streaming=True
        )
        ```
    """
    return ChatOpenRouter(
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        **kwargs
    )


def get_llm(**kwargs) -> ChatOpenRouter:
    """
    Alias for get_openrouter_llm for compatibility with existing code.

    This function provides a drop-in replacement for the NVIDIA LLM getter.
    """
    return get_openrouter_llm(**kwargs)


# Available models on OpenRouter (commonly used)
AVAILABLE_MODELS = [
    "qwen/qwen3-max",
    "qwen/qwen-2.5-72b-instruct",
    "anthropic/claude-3-opus",
    "anthropic/claude-3-sonnet",
    "anthropic/claude-3-haiku",
    "openai/gpt-4-turbo",
    "openai/gpt-4o",
    "openai/gpt-3.5-turbo",
    "google/gemini-pro",
    "meta-llama/llama-3-70b-instruct",
    "mistralai/mixtral-8x7b-instruct",
]


def list_available_models() -> List[str]:
    """Return list of commonly used models on OpenRouter."""
    return AVAILABLE_MODELS.copy()
