# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Configuration for Hotel Guardrails API Server

Provides Pydantic Settings for LLM and server configuration with
environment variable support.

Environment Variables:
    HOTEL_LLM_MODEL: LLM model name (default: qwen/qwen3-max)
    HOTEL_LLM_TEMPERATURE: Sampling temperature (default: 0.7)
    HOTEL_LLM_MAX_TOKENS: Max response tokens (default: 1024)
    HOTEL_CORS_ORIGINS: CORS allowed origins (default: ["*"])
    LOG_LEVEL: Logging level (default: INFO)
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    """LLM configuration with environment variable support."""

    model: str = Field(
        default="qwen/qwen3-max",
        description="OpenRouter model name",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=1024,
        ge=1,
        le=8192,
        description="Maximum response tokens",
    )
    streaming: bool = Field(
        default=True,
        description="Enable streaming responses",
    )

    model_config = {
        "env_prefix": "HOTEL_LLM_",
        "case_sensitive": False,
    }


class ServerSettings(BaseSettings):
    """Server configuration."""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8081, description="Server port")
    cors_origins: List[str] = Field(
        default=["*"],
        description="CORS allowed origins",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    model_config = {
        "env_prefix": "HOTEL_",
        "case_sensitive": False,
    }


# Available models for frontend dropdown
AVAILABLE_MODELS = [
    {
        "id": "qwen/qwen3-max",
        "name": "Qwen3 Max",
        "provider": "Qwen",
        "description": "High-quality bilingual model",
    },
    {
        "id": "qwen/qwen3-235b",
        "name": "Qwen3 235B",
        "provider": "Qwen",
        "description": "Largest Qwen model",
    },
    {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "provider": "Anthropic",
        "description": "Fast and efficient",
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "GPT-4o Mini",
        "provider": "OpenAI",
        "description": "Cost-effective GPT-4",
    },
]


def get_llm_settings() -> LLMSettings:
    """Get current LLM settings from environment."""
    return LLMSettings()


def get_server_settings() -> ServerSettings:
    """Get server settings from environment."""
    return ServerSettings()
