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
    LANGGRAPH_MODE: LangGraph mode: 'embedded' (default) or 'http'
    LLM_FALLBACK_ENABLED: Enable OpenRouter -> NVIDIA fallback (default: true)
    NVIDIA_LLM_MODEL: NVIDIA fallback model (default: meta/llama-3.3-70b-instruct)
    RERANKER_BACKEND: Reranker backend: 'nvidia' (default) or 'qwen'
"""

import os
import time
import threading
import logging
from collections import deque
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class LLMBackend(str, Enum):
    """Available LLM backends."""
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"


class LLMSettings(BaseSettings):
    """LLM configuration with environment variable support."""

    model: str = Field(
        default="qwen/qwen3-max",
        description="OpenRouter model name (primary)",
    )
    temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=16384,
        description="Maximum response tokens",
    )
    streaming: bool = Field(
        default=True,
        description="Enable streaming responses",
    )
    fallback_enabled: bool = Field(
        default=True,
        description="Enable automatic fallback to NVIDIA if OpenRouter fails",
    )
    nvidia_model: str = Field(
        default="meta/llama-3.3-70b-instruct",
        description="NVIDIA model for fallback",
    )

    model_config = {
        "env_prefix": "HOTEL_LLM_",
        "case_sensitive": False,
    }


class LangGraphSettings(BaseSettings):
    """LangGraph configuration."""

    mode: str = Field(
        default="embedded",
        description="LangGraph mode: 'embedded' (default) or 'http'",
    )
    endpoint: str = Field(
        default="http://localhost:8090",
        description="LangGraph HTTP endpoint (for http mode)",
    )
    timeout: float = Field(
        default=60.0,
        description="Request timeout in seconds",
    )

    model_config = {
        "env_prefix": "LANGGRAPH_",
        "case_sensitive": False,
    }


class RerankerSettings(BaseSettings):
    """Reranker configuration."""

    backend: str = Field(
        default="nvidia",
        description="Reranker backend: 'nvidia' (fast, API) or 'qwen' (local CPU)",
    )
    model: str = Field(
        default="nvidia/nv-rerankqa-mistral-4b-v3",
        description="Reranker model name",
    )
    top_n: int = Field(
        default=4,
        description="Number of documents to return after reranking",
    )

    model_config = {
        "env_prefix": "RERANKER_",
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


# Available models with per-model optimization presets
# Each model has optimal temperature, max_tokens tuned for hotel assistant use case
AVAILABLE_MODELS = [
    # Ollama (local)
    {
        "id": "fredrezones55/qwen3.5-opus:9b",
        "name": "Qwen3.5 Opus 9B",
        "provider": "Ollama",
        "backend": "ollama",
        "description": "Local 9B model with tool calling, native thinking tags",
        # Qwen3.5 on Ollama outputs <think> tags natively — explicit thinking
        # only adds overhead. max_tokens=2048 is sufficient for hotel responses.
        # max_retries=2 compensates for 9B flakiness (tool-call leaks in Thai).
        "presets": {"temperature": 0.3, "max_tokens": 2048, "thinking": False, "max_retries": 2},
    },
    {
        "id": "qwen3.5:9b",
        "name": "Qwen3.5 9B",
        "provider": "Ollama",
        "backend": "ollama",
        "description": "Local Qwen3.5 base model, native thinking tags",
        "presets": {"temperature": 0.3, "max_tokens": 2048, "thinking": False, "max_retries": 2},
    },
    # OpenRouter (cloud) — max_retries=0 or 1 to avoid doubling API costs
    {
        "id": "qwen/qwen3-max-thinking",
        "name": "Qwen3 Max Thinking",
        "provider": "Qwen",
        "backend": "openrouter",
        "description": "Primary cloud model - extended reasoning, 262K context",
        "presets": {"temperature": 0.1, "max_tokens": 4096, "thinking": True, "max_retries": 1},
    },
    {
        "id": "qwen/qwen3-max",
        "name": "Qwen3 Max",
        "provider": "Qwen",
        "backend": "openrouter",
        "description": "Qwen3 Max without thinking mode",
        "presets": {"temperature": 0.3, "max_tokens": 4096, "thinking": False, "max_retries": 1},
    },
    {
        "id": "qwen/qwen3.5-397b-a17b",
        "name": "Qwen3.5 397B MoE",
        "provider": "Qwen",
        "backend": "openrouter",
        "description": "Latest Qwen3.5, MoE 397B (17B active)",
        "presets": {"temperature": 0.3, "max_tokens": 4096, "thinking": True, "max_retries": 1},
    },
    {
        "id": "qwen/qwen3.5-flash-02-23",
        "name": "Qwen3.5 Flash",
        "provider": "Qwen",
        "backend": "openrouter",
        "description": "Fast and cheap, 1M context",
        "presets": {"temperature": 0.3, "max_tokens": 2048, "thinking": False, "max_retries": 1},
    },
    {
        "id": "minimax/minimax-m2.7",
        "name": "MiniMax M2.7",
        "provider": "MiniMax",
        "backend": "openrouter",
        "description": "Budget option - strong agentic, 205K context, $0.30/$1.20 per 1M",
        "presets": {"temperature": 0.3, "max_tokens": 4096, "thinking": True, "max_retries": 1},
    },
]


# OpenRouter models that have a thinking variant (auto-mapped when thinking=True)
THINKING_VARIANTS = {
    "qwen/qwen3-max": "qwen/qwen3-max-thinking",
    "qwen/qwen3-next-80b-a3b-instruct": "qwen/qwen3-next-80b-a3b-thinking",
    "qwen/qwen3-235b-a22b": "qwen/qwen3-235b-a22b-thinking-2507",
    "qwen/qwen3-30b-a3b": "qwen/qwen3-30b-a3b-thinking-2507",
    "qwen/qwen-plus-2025-07-28": "qwen/qwen-plus-2025-07-28:thinking",
}


def get_model_presets(model_id: str) -> dict:
    """
    Get optimization presets for a model.
    Known models get tuned presets; unknown models get sensible defaults
    based on provider heuristics.

    Presets include:
    - temperature, max_tokens: generation params
    - thinking: enable extended reasoning (default True if available)
    - max_retries: retries on empty/leaked responses (higher for flaky local 9B)
    """
    # Check known models first
    for m in AVAILABLE_MODELS:
        if m["id"] == model_id:
            return m.get("presets", {})

    # Auto-detect sensible defaults for unknown OpenRouter models
    model_lower = model_id.lower()

    # Thinking/reasoning models → low temp, high tokens
    if "thinking" in model_lower:
        return {"temperature": 0.1, "max_tokens": 4096, "thinking": True, "max_retries": 1}

    # Large/max models → lower temp, more tokens, thinking on
    if any(k in model_lower for k in ["max", "397b", "235b", "opus", "large", "pro"]):
        return {"temperature": 0.2, "max_tokens": 4096, "thinking": True, "max_retries": 1}

    # Flash/mini/small → higher temp, fewer tokens, thinking off (speed)
    if any(k in model_lower for k in ["flash", "mini", "small", "haiku", "nano"]):
        return {"temperature": 0.4, "max_tokens": 2048, "thinking": False, "max_retries": 1}

    # Default: balanced, thinking on, 1 retry for cloud
    return {"temperature": 0.3, "max_tokens": 4096, "thinking": True, "max_retries": 1}


def resolve_thinking_model(model_id: str, thinking_enabled: bool) -> str:
    """
    If thinking is enabled and the model has a thinking variant, return it.
    If already a thinking model, return as-is.
    """
    if not thinking_enabled:
        return model_id
    if "thinking" in model_id.lower():
        return model_id  # already a thinking model
    return THINKING_VARIANTS.get(model_id, model_id)


def get_llm_settings() -> LLMSettings:
    """Get current LLM settings from environment."""
    return LLMSettings()


def get_server_settings() -> ServerSettings:
    """Get server settings from environment."""
    return ServerSettings()


def get_langgraph_settings() -> LangGraphSettings:
    """Get LangGraph settings from environment."""
    return LangGraphSettings()


def get_reranker_settings() -> RerankerSettings:
    """Get reranker settings from environment."""
    return RerankerSettings()


# =============================================================================
# Runtime LLM Configuration (mutable singleton, switchable via API)
# =============================================================================


class RateLimiter:
    """Sliding window rate limiter to prevent 429 errors."""

    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """
        Check if a request can proceed. Returns wait time in seconds.
        Returns 0 if request can proceed immediately.
        """
        with self._lock:
            now = time.time()
            # Remove timestamps outside the window
            while self._timestamps and self._timestamps[0] < now - self.window_seconds:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return 0.0

            # Calculate wait time
            wait = self._timestamps[0] + self.window_seconds - now
            return max(wait, 0.1)

    def wait_and_acquire(self):
        """Block until a request slot is available."""
        while True:
            wait = self.acquire()
            if wait == 0:
                return
            logger.info(f"Rate limit: waiting {wait:.1f}s ({len(self._timestamps)}/{self.max_requests} in window)")
            time.sleep(wait)

    @property
    def current_usage(self) -> dict:
        with self._lock:
            now = time.time()
            active = sum(1 for t in self._timestamps if t >= now - self.window_seconds)
            return {
                "requests_in_window": active,
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
            }


class RuntimeLLMConfig:
    """
    Thread-safe mutable runtime LLM configuration.

    Initialized from environment variables at startup.
    Can be updated at runtime via PUT /settings/llm without restart.
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._lock_rw = threading.Lock()
        # Determine initial backend from env
        backend_str = os.getenv("LLM_BACKEND", "openrouter").lower()
        self.backend = LLMBackend(backend_str) if backend_str in ("ollama", "openrouter") else LLMBackend.OPENROUTER

        # Ollama settings
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "fredrezones55/qwen3.5-opus:9b")

        # OpenRouter settings
        self.openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.5-397b-a17b")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")

        # Thinking mode — disabled by default for Ollama (native <think> tags,
        # explicit thinking adds overhead and breaks streaming).
        # Cloud model presets enable it when switching via PUT /settings/llm.
        self.thinking = os.getenv("LLM_THINKING", "false").lower() == "true"

        # Rate limiter (prevents 429s from OpenRouter)
        rate_limit = int(os.getenv("OPENROUTER_RATE_LIMIT", "20"))  # requests per minute
        self.rate_limiter = RateLimiter(max_requests=rate_limit, window_seconds=60)

        # Common settings
        self.temperature = float(os.getenv("HOTEL_LLM_TEMPERATURE", "0.3"))
        self.max_tokens = int(os.getenv("HOTEL_LLM_MAX_TOKENS", "4096"))
        self.streaming = True

        # Retry budget for empty/leaked responses.
        # Tuned per-model via preset (2 for local 9B, 1 for cloud).
        active_presets = get_model_presets(self.active_model)
        self.max_retries = int(os.getenv(
            "LLM_MAX_RETRIES",
            str(active_presets.get("max_retries", 2 if self.backend == LLMBackend.OLLAMA else 1)),
        ))

        logger.info(f"RuntimeLLMConfig initialized: backend={self.backend.value}, "
                     f"model={self.active_model}, max_retries={self.max_retries}")

    @classmethod
    def get_instance(cls) -> "RuntimeLLMConfig":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    @property
    def active_model(self) -> str:
        """Get the currently active model name."""
        if self.backend == LLMBackend.OLLAMA:
            return self.ollama_model
        return self.openrouter_model

    @property
    def active_base_url(self) -> str:
        """Get the currently active API base URL."""
        if self.backend == LLMBackend.OLLAMA:
            return self.ollama_base_url
        return self.openrouter_base_url

    @property
    def active_api_key(self) -> str:
        """Get the currently active API key."""
        if self.backend == LLMBackend.OLLAMA:
            return "sk-ollama-not-needed"
        return self.openrouter_api_key

    def update(self, backend: Optional[str] = None, model: Optional[str] = None,
               temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> dict:
        """
        Update runtime configuration. Returns dict of changes made.

        When switching models, per-model optimization presets are auto-applied
        unless temperature/max_tokens are explicitly provided in the request.
        """
        changes = {}
        with self._lock_rw:
            if backend is not None:
                new_backend = LLMBackend(backend.lower())
                if new_backend != self.backend:
                    changes["backend"] = {"old": self.backend.value, "new": new_backend.value}
                    self.backend = new_backend

            if model is not None:
                old_model = self.active_model
                if self.backend == LLMBackend.OLLAMA:
                    self.ollama_model = model
                else:
                    self.openrouter_model = model
                if model != old_model:
                    changes["model"] = {"old": old_model, "new": model}

                    # Auto-apply per-model presets when switching models
                    presets = get_model_presets(model)
                    if presets:
                        if temperature is None and presets.get("temperature") is not None:
                            old_temp = self.temperature
                            self.temperature = presets["temperature"]
                            changes["temperature"] = {"old": old_temp, "new": self.temperature, "source": "preset"}
                        if max_tokens is None and presets.get("max_tokens") is not None:
                            old_mt = self.max_tokens
                            self.max_tokens = presets["max_tokens"]
                            changes["max_tokens"] = {"old": old_mt, "new": self.max_tokens, "source": "preset"}
                        if "thinking" in presets:
                            old_thinking = self.thinking
                            self.thinking = presets["thinking"]
                            if old_thinking != self.thinking:
                                changes["thinking"] = {"old": old_thinking, "new": self.thinking, "source": "preset"}
                        if "max_retries" in presets:
                            old_retries = self.max_retries
                            self.max_retries = int(presets["max_retries"])
                            if old_retries != self.max_retries:
                                changes["max_retries"] = {"old": old_retries, "new": self.max_retries, "source": "preset"}

            # Explicit overrides always win over presets
            if temperature is not None and temperature != self.temperature:
                changes["temperature"] = {"old": self.temperature, "new": temperature}
                self.temperature = temperature

            if max_tokens is not None and max_tokens != self.max_tokens:
                changes["max_tokens"] = {"old": self.max_tokens, "new": max_tokens}
                self.max_tokens = max_tokens

        if changes:
            logger.info(f"RuntimeLLMConfig updated: {changes}")
        return changes

    def to_dict(self) -> dict:
        """Serialize current config to dict."""
        return {
            "backend": self.backend.value,
            "model": self.active_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "streaming": self.streaming,
            "thinking": self.thinking,
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.ollama_model,
            "openrouter_model": self.openrouter_model,
        }


def get_runtime_llm_config() -> RuntimeLLMConfig:
    """Get the runtime LLM configuration singleton."""
    return RuntimeLLMConfig.get_instance()
