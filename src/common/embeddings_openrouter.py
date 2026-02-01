# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
OpenRouter Embeddings using qwen/qwen3-embedding-8b

Uses direct API calls to OpenRouter's embeddings endpoint.
Provides drop-in replacement for NVIDIA embeddings.

Usage:
    from src.common.embeddings_openrouter import get_openrouter_embeddings

    embeddings = get_openrouter_embeddings()
    vectors = embeddings.embed_documents(["Hello world"])
"""

import os
import logging
import time
from typing import Optional, List

import requests
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

# Import audit logger
try:
    from src.common.audit_logger import get_audit_logger
except ImportError:
    get_audit_logger = None

# Default embedding model on OpenRouter
# Model: qwen/qwen3-embedding-8b - designed for text embedding and ranking
DEFAULT_EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Token limits per embedding model (conservative estimates)
# Used for auto-calculating optimal chunk sizes
EMBEDDING_MODEL_TOKEN_LIMITS = {
    "qwen/qwen3-embedding-8b": 8192,
    "qwen/qwen3-embedding-0.6b": 2048,
    "openai/text-embedding-3-small": 8191,
    "openai/text-embedding-3-large": 8191,
    "openai/text-embedding-ada-002": 8191,
}


def get_model_token_limit(model: str) -> int:
    """
    Get token limit for an embedding model.

    Args:
        model: Model name

    Returns:
        Token limit for the model (defaults to 2048 for unknown models)
    """
    return EMBEDDING_MODEL_TOKEN_LIMITS.get(model, 2048)


class OpenRouterEmbeddings(Embeddings):
    """
    OpenRouter Embeddings class using OpenAI-compatible API.

    Uses the OpenRouter embeddings API endpoint at /v1/embeddings.
    Compatible with LangChain's Embeddings interface.
    """

    def __init__(
        self,
        model: str = DEFAULT_EMBEDDING_MODEL,
        api_key: Optional[str] = None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: int = 60,
    ):
        """
        Initialize OpenRouter Embeddings.

        Args:
            model: Embedding model name (default: qwen/qwen3-embedding-8b)
            api_key: OpenRouter API key (or set OPENROUTER_API_KEY env var)
            base_url: OpenRouter API base URL
            timeout: Request timeout in seconds
        """
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        logger.info(f"Initializing OpenRouter embeddings with model: {self.model}")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of documents.

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        start_time = time.time()
        error_msg = None
        success = True
        dimensions = 0

        try:
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": texts,
                },
                timeout=self.timeout,
            )

            if response.status_code != 200:
                error_msg = response.text
                success = False
                logger.error(f"OpenRouter API error: {error_msg}")
                raise ValueError(f"OpenRouter API error: {error_msg}")

            data = response.json()
            # Sort by index to ensure correct order
            embeddings = sorted(data["data"], key=lambda x: x["index"])
            result = [item["embedding"] for item in embeddings]
            dimensions = len(result[0]) if result else 0

            return result

        except Exception as e:
            success = False
            error_msg = str(e)
            raise

        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            # Log to audit logger
            if get_audit_logger is not None:
                try:
                    audit_logger = get_audit_logger()
                    audit_logger.log_embedding_request(
                        texts=texts,
                        model=self.model,
                        response_time_ms=elapsed_ms,
                        dimensions=dimensions,
                        success=success,
                        error=error_msg,
                    )
                except Exception as log_error:
                    logger.debug(f"Audit logging failed: {log_error}")

    def embed_query(self, text: str) -> List[float]:
        """
        Embed a single query text.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector
        """
        return self.embed_documents([text])[0]


def get_openrouter_embeddings(
    model_name: Optional[str] = None,
    dimensions: Optional[int] = None,
) -> OpenRouterEmbeddings:
    """
    Create embeddings using OpenRouter's embedding models.

    OpenRouter provides OpenAI-compatible API for embeddings at /v1/embeddings.

    Args:
        model_name: Embedding model to use (default: qwen/qwen3-embedding-8b)
        dimensions: Vector dimensions (not used, for API compatibility)

    Returns:
        OpenRouterEmbeddings instance

    Raises:
        ValueError: If OPENROUTER_API_KEY environment variable is not set

    Example:
        ```python
        embeddings = get_openrouter_embeddings()

        # Embed single text
        vector = embeddings.embed_query("What time is breakfast?")

        # Embed multiple texts
        vectors = embeddings.embed_documents([
            "Breakfast is served 6:30 AM to 10:30 AM",
            "WiFi password is HOTEL2024GUEST"
        ])
        ```
    """
    model = model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    return OpenRouterEmbeddings(model=model)


def get_embedding_model(**kwargs) -> OpenRouterEmbeddings:
    """
    Alias for get_openrouter_embeddings for compatibility with existing code.

    This function provides a drop-in replacement for the NVIDIA embedding getter.
    """
    return get_openrouter_embeddings(**kwargs)


# Common embedding models available on OpenRouter
AVAILABLE_EMBEDDING_MODELS = [
    "qwen/qwen3-embedding-8b",
    "qwen/qwen3-embedding-0.6b",
    "openai/text-embedding-3-small",
    "openai/text-embedding-3-large",
    "openai/text-embedding-ada-002",
]


def list_available_embedding_models():
    """Return list of commonly used embedding models on OpenRouter."""
    return AVAILABLE_EMBEDDING_MODELS.copy()
