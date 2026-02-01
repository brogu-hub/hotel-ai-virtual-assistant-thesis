# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Qwen3-0.6B Reranker using sentence-transformers CrossEncoder

Replaces NVIDIA NVIDIARerank with local Qwen3 reranker for CPU-friendly deployment.
Provides LangChain-compatible BaseDocumentCompressor interface.

Usage:
    from src.common.reranker_qwen import get_qwen_reranker

    reranker = get_qwen_reranker(top_n=4)
    reranked_docs = reranker.compress_documents(documents=docs, query="breakfast time")
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

# Default reranker model
# BAAI/bge-reranker-v2-m3 is multilingual and properly trained (unlike Qwen3-0.6B which shows "score.weight not initialized")
DEFAULT_RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")


class Qwen3Reranker(BaseDocumentCompressor):
    """
    LangChain-compatible reranker using Qwen3-0.6B CrossEncoder.

    Uses sentence-transformers CrossEncoder for reranking documents
    based on relevance to the query. Works on CPU without GPU requirements.

    Attributes:
        model_name: HuggingFace model name for the CrossEncoder
        top_n: Number of top documents to return after reranking
        device: Device to run the model on ("cpu" or "cuda")
        max_length: Maximum sequence length for the model

    Example:
        ```python
        reranker = Qwen3Reranker(top_n=4)

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

    model_name: str = Field(default=DEFAULT_RERANKER_MODEL)
    top_n: int = Field(default=4)
    device: str = Field(default="cpu")
    max_length: int = Field(default=512)

    # Private attribute for the CrossEncoder model
    _model: Any = PrivateAttr(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        model_name: Optional[str] = None,
        top_n: int = 4,
        device: str = "cpu",
        max_length: int = 512,
        **kwargs
    ):
        """
        Initialize Qwen3 reranker.

        Args:
            model_name: HuggingFace model name (default: Qwen/Qwen3-Reranker-0.6B)
            top_n: Number of top documents to return
            device: Device to run model on ("cpu" or "cuda")
            max_length: Maximum sequence length
        """
        super().__init__(**kwargs)

        self.model_name = model_name or os.getenv("RERANKER_MODEL", DEFAULT_RERANKER_MODEL)
        self.top_n = top_n
        self.device = device
        self.max_length = max_length

        # Lazy load the model
        self._model = None

    def _get_model(self):
        """Lazy load the CrossEncoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info(f"Loading Qwen3 reranker: {self.model_name}")

                self._model = CrossEncoder(
                    self.model_name,
                    max_length=self.max_length,
                    device=self.device,
                    trust_remote_code=True
                )

                # Set padding token (required for batch processing)
                if self._model.tokenizer.pad_token is None:
                    self._model.tokenizer.pad_token = self._model.tokenizer.eos_token

                logger.info(f"Qwen3 reranker loaded successfully on {self.device}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for Qwen3Reranker. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error(f"Failed to load reranker model: {e}")
                raise

        return self._model

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> List[Document]:
        """
        Rerank documents based on relevance to query.

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

        model = self._get_model()

        # Create query-document pairs for CrossEncoder
        pairs = [(query, doc.page_content) for doc in documents]

        logger.debug(f"Reranking {len(pairs)} documents for query: {query[:50]}...")

        # Prepare input documents for audit logging
        input_docs = [
            {"source": doc.metadata.get("source", "unknown"), "score": 0.0, "content": doc.page_content}
            for doc in documents
        ]

        # Get relevance scores from CrossEncoder
        try:
            # Process one at a time to avoid batch padding issues
            scores = []
            for pair in pairs:
                score = model.predict([pair])[0]
                scores.append(score)
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            success = False
            error_msg = str(e)
            # Return original documents without reranking on error
            return list(documents[:self.top_n])

        # Combine documents with scores
        doc_scores = list(zip(documents, scores))

        # Sort by score (descending) and take top_n
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        top_docs = doc_scores[:self.top_n]

        # Add relevance score to metadata and return
        result = []
        for doc, score in top_docs:
            # Create a copy to avoid modifying original
            new_doc = Document(
                page_content=doc.page_content,
                metadata={**doc.metadata, "relevance_score": float(score)}
            )
            result.append(new_doc)

        logger.info(
            f"Reranked {len(documents)} docs to top {len(result)}, "
            f"scores: [{', '.join(f'{s:.3f}' for _, s in top_docs)}]"
        )

        # Audit logging
        elapsed_ms = (time.time() - start_time) * 1000
        if get_audit_logger is not None:
            try:
                audit_logger = get_audit_logger()
                reranked_docs = [
                    {"source": doc.metadata.get("source", "unknown"), "score": float(score), "content": doc.page_content}
                    for doc, score in top_docs
                ]
                audit_logger.log_reranking(
                    query=query,
                    model=self.model_name,
                    input_documents=input_docs,
                    reranked_documents=reranked_docs,
                    top_n=self.top_n,
                    latency_ms=elapsed_ms,
                    success=success,
                    error=error_msg,
                )
            except Exception as log_error:
                logger.debug(f"Audit logging failed: {log_error}")

        return result


@lru_cache(maxsize=1)
def get_qwen_reranker(
    top_n: int = 4,
    device: str = "cpu",
    max_length: int = 512,
) -> Qwen3Reranker:
    """
    Factory function to create Qwen3 reranker instance.

    Uses LRU cache to avoid loading the model multiple times.

    Args:
        top_n: Number of top documents to return
        device: Device to run model on
        max_length: Maximum sequence length

    Returns:
        Qwen3Reranker instance
    """
    return Qwen3Reranker(
        top_n=top_n,
        device=device,
        max_length=max_length
    )


def get_ranking_model(**kwargs) -> Qwen3Reranker:
    """
    Alias for get_qwen_reranker for compatibility with existing code.

    This function provides a drop-in replacement for the NVIDIA ranking getter.
    """
    return get_qwen_reranker(**kwargs)
