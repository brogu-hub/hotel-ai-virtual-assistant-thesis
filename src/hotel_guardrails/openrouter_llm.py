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
    temperature: float = 0.3,
    max_tokens: int = 1024,
    streaming: bool = True,
) -> ChatOpenAI:
    """
    Create LLM instance — supports both OpenRouter and Ollama backends.

    Backend is determined by RuntimeLLMConfig singleton (switchable at runtime).

    Args:
        model: Model name override (uses runtime config if not specified)
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        streaming: Enable streaming responses

    Returns:
        ChatOpenAI instance configured for the active backend
    """
    from .config import get_runtime_llm_config, LLMBackend

    runtime_config = get_runtime_llm_config()

    if runtime_config.backend == LLMBackend.OLLAMA:
        logger.info(f"Creating Ollama LLM: {runtime_config.ollama_model}")
        return ChatOpenAI(
            model=runtime_config.ollama_model,
            openai_api_key="sk-ollama-not-needed",
            openai_api_base=runtime_config.ollama_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )

    # OpenRouter path
    api_key = runtime_config.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable required")

    referer = os.getenv("OPENROUTER_REFERER", "https://siam-serenity-hotel.com")
    title = os.getenv("OPENROUTER_TITLE", "Grand Horizon Concierge")
    use_model = model if model != DEFAULT_MODEL else runtime_config.openrouter_model

    logger.info(f"Creating OpenRouter LLM: {use_model}")

    return ChatOpenAI(
        model=use_model,
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
