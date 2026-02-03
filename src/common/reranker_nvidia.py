# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
NVIDIA NIM Reranker using langchain_nvidia_ai_endpoints

Uses NVIDIA's NIM API for fast, high-quality document reranking.
Provides LangChain-compatible BaseDocumentCompressor interface.

Usage:
    from src.common.reranker_nvidia import get_nvidia_reranker

    reranker = get_nvidia_reranker(top_n=4)
    reranked_docs = reranker.compress_documents(documents=docs, query="breakfast time")

Environment Variables:
    NVIDIA_API_KEY: Required API key for NVIDIA NIM
    RERANKER_MODEL: Model name (default: nvidia/nv-rerankqa-mistral-4b-v3)
"""

import os
import logging
import time
from typing import List, Sequence, Optional, Any
from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.documents.compressor import BaseDocumentCompressor
from langchain_core.callbacks import Callbacks
from pydantic import Field, PrivateAttr

logger = logging.getLogger(__name__)

# Import audit logger
try:
    from src.common.audit_logger import get_audit_logger
except ImportError:
    get_audit_logger = None

# Default NVIDIA reranker model
# nvidia/nv-rerankqa-mistral-4b-v3 is fast and high-quality
DEFAULT_NVIDIA_RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL", "nvidia/nv-rerankqa-mistral-4b-v3"
)


class NVIDIARerankerWrapper(BaseDocumentCompressor):
    """
    LangChain-compatible reranker using NVIDIA NIM API.

    Uses NVIDIA's hosted reranking model for fast, high-quality
    document reranking. Requires NVIDIA_API_KEY environment variable.

    Attributes:
        model_name: NVIDIA model name for reranking
        top_n: Number of top documents to return after reranking
        truncate: How to handle long documents ("END" or "NONE")

    Example:
        ```python
        reranker = NVIDIARerankerWrapper(top_n=4)

        # Rerank documents
        reranked = reranker.compress_documents(
            documents=retrieved_docs,
            query="What time is breakfast?"
        )

        # Access relevance scores
        for doc in reranked:
            print(f"Score: {doc.metadata['relevance_score']:.3f}")
            print(f"Content: {doc.page_content[:100]}...")
        ```
    """

    model_name: str = Field(default=DEFAULT_NVIDIA_RERANKER_MODEL)
    top_n: int = Field(default=4)
    truncate: str = Field(default="END")

    # Private attribute for the NVIDIARerank model
    _reranker: Any = PrivateAttr(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        model_name: Optional[str] = None,
        top_n: int = 4,
        truncate: str = "END",
        **kwargs
    ):
        """
        Initialize NVIDIA reranker.

        Args:
            model_name: NVIDIA model name (default: nvidia/nv-rerankqa-mistral-4b-v3)
            top_n: Number of top documents to return
            truncate: How to handle long documents ("END" or "NONE")
        """
        super().__init__(**kwargs)

        self.model_name = model_name or os.getenv(
            "RERANKER_MODEL", DEFAULT_NVIDIA_RERANKER_MODEL
        )
        self.top_n = top_n
        self.truncate = truncate

        # Lazy load the model
        self._reranker = None

    def _get_reranker(self):
        """Lazy load the NVIDIA reranker."""
        if self._reranker is None:
            try:
                from langchain_nvidia_ai_endpoints import NVIDIARerank

                api_key = os.getenv("NVIDIA_API_KEY")
                if not api_key:
                    raise ValueError(
                        "NVIDIA_API_KEY environment variable is required for NVIDIA reranker"
                    )

                logger.info(f"Initializing NVIDIA reranker: {self.model_name}")

                self._reranker = NVIDIARerank(
                    model=self.model_name,
                    top_n=self.top_n,
                    truncate=self.truncate,
                )

                logger.info(f"NVIDIA reranker initialized successfully")
            except ImportError:
                raise ImportError(
                    "langchain-nvidia-ai-endpoints is required for NVIDIA reranker. "
                    "Install with: pip install langchain-nvidia-ai-endpoints"
                )
            except Exception as e:
                logger.error(f"Failed to initialize NVIDIA reranker: {e}")
                raise

        return self._reranker

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> List[Document]:
        """
        Rerank documents based on relevance to query using NVIDIA NIM.

        Args:
            documents: List of documents to rerank
            query: The search query (Thai or English)
            callbacks: Optional callbacks (not used, for interface compatibility)

        Returns:
            Top N documents sorted by relevance score, with
            'relevance_score' added to each document's metadata
        """
        if not documents:
            logger.debug("No documents to rerank")
            return []

        start_time = time.time()
        success = True
        error_msg = None

        # Prepare input documents for audit logging
        input_docs = [
            {
                "source": doc.metadata.get("source", "unknown"),
                "score": 0.0,
                "content": doc.page_content,
            }
            for doc in documents
        ]

        try:
            reranker = self._get_reranker()

            # Update top_n if changed
            reranker.top_n = self.top_n

            logger.debug(f"Reranking {len(documents)} documents with NVIDIA NIM")

            # Use NVIDIA reranker
            reranked_docs = reranker.compress_documents(
                documents=list(documents), query=query
            )

            logger.info(
                f"Reranked {len(documents)} docs to top {len(reranked_docs)}, "
                f"scores: [{', '.join(f'{doc.metadata.get(\"relevance_score\", 0):.3f}' for doc in reranked_docs)}]"
            )

            # Audit logging
            elapsed_ms = (time.time() - start_time) * 1000
            if get_audit_logger is not None:
                try:
                    audit_logger = get_audit_logger()
                    reranked_audit = [
                        {
                            "source": doc.metadata.get("source", "unknown"),
                            "score": doc.metadata.get("relevance_score", 0.0),
                            "content": doc.page_content,
                        }
                        for doc in reranked_docs
                    ]
                    audit_logger.log_reranking(
                        query=query,
                        model=self.model_name,
                        input_documents=input_docs,
                        reranked_documents=reranked_audit,
                        top_n=self.top_n,
                        latency_ms=elapsed_ms,
                        success=success,
                        error=error_msg,
                    )
                except Exception as log_error:
                    logger.debug(f"Audit logging failed: {log_error}")

            return reranked_docs

        except Exception as e:
            logger.error(f"NVIDIA reranking failed: {e}")
            success = False
            error_msg = str(e)

            # Audit logging for failure
            elapsed_ms = (time.time() - start_time) * 1000
            if get_audit_logger is not None:
                try:
                    audit_logger = get_audit_logger()
                    audit_logger.log_reranking(
                        query=query,
                        model=self.model_name,
                        input_documents=input_docs,
                        reranked_documents=[],
                        top_n=self.top_n,
                        latency_ms=elapsed_ms,
                        success=False,
                        error=error_msg,
                    )
                except Exception:
                    pass

            # Return original documents without reranking on error
            return list(documents[: self.top_n])


# Singleton instance for caching
_nvidia_reranker_instance: Optional[NVIDIARerankerWrapper] = None


def get_nvidia_reranker(
    top_n: int = 4,
    model_name: Optional[str] = None,
    truncate: str = "END",
) -> NVIDIARerankerWrapper:
    """
    Factory function to create NVIDIA reranker instance.

    Uses singleton pattern to avoid reinitializing the model.

    Args:
        top_n: Number of top documents to return
        model_name: NVIDIA model name (optional)
        truncate: How to handle long documents

    Returns:
        NVIDIARerankerWrapper instance
    """
    global _nvidia_reranker_instance

    if _nvidia_reranker_instance is None:
        _nvidia_reranker_instance = NVIDIARerankerWrapper(
            model_name=model_name,
            top_n=top_n,
            truncate=truncate,
        )
    else:
        # Update top_n if different
        _nvidia_reranker_instance.top_n = top_n

    return _nvidia_reranker_instance


def get_ranking_model(**kwargs) -> NVIDIARerankerWrapper:
    """
    Alias for get_nvidia_reranker for compatibility with existing code.
    """
    return get_nvidia_reranker(**kwargs)
