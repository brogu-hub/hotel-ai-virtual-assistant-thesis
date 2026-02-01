# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
OpenRouter LLM Wrapper for NeMo Guardrails

Provides OpenRouter integration using OpenAI-compatible API.
Includes required headers for Paid Tier compliance.

Usage:
    from src.hotel_guardrails.openrouter_llm import get_openrouter_llm

    llm = get_openrouter_llm()
    response = llm.invoke("Hello, how are you?")
"""
import os
import logging
from typing import Optional

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Default model for hotel operations
DEFAULT_MODEL = "qwen/qwen3-max"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_llm(
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    streaming: bool = True,
) -> ChatOpenAI:
    """
    Create OpenRouter LLM instance for NeMo Guardrails.

    Uses OpenAI-compatible API with required headers for Paid Tier.

    Args:
        model: OpenRouter model name (default: qwen/qwen3-max)
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        streaming: Enable streaming responses

    Returns:
        ChatOpenAI instance configured for OpenRouter

    Raises:
        ValueError: If OPENROUTER_API_KEY is not set

    Example:
        ```python
        llm = get_openrouter_llm()
        response = llm.invoke([
            {"role": "user", "content": "What time is breakfast?"}
        ])
        print(response.content)
        ```
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable required")

    # Get optional configuration from environment
    referer = os.getenv("OPENROUTER_REFERER", "https://siam-serenity-hotel.com")
    title = os.getenv("OPENROUTER_TITLE", "Siam Serenity Concierge")

    logger.info(f"Initializing OpenRouter LLM with model: {model}")

    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        openai_api_base=OPENROUTER_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        default_headers={
            "HTTP-Referer": referer,
            "X-Title": title,
        },
    )


def get_openrouter_chat_model(**kwargs) -> ChatOpenAI:
    """
    Alias for get_openrouter_llm for compatibility.

    This function provides a drop-in replacement pattern.
    """
    return get_openrouter_llm(**kwargs)


# Available models on OpenRouter for hotel operations
AVAILABLE_MODELS = [
    "qwen/qwen3-max",           # Primary model
    "qwen/qwen3-235b",          # Larger Qwen3
    "anthropic/claude-3-haiku", # Fast responses
    "openai/gpt-4o-mini",       # Alternative
]


def list_available_models():
    """Return list of recommended models for hotel operations."""
    return AVAILABLE_MODELS.copy()
