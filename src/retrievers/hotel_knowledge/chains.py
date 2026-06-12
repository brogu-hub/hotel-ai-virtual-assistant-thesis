# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hotel Knowledge RAG Chain

Retrieves hotel information from Qdrant using OpenRouter embeddings.
Supports bilingual Thai/English queries. Reranking is OFF by default
(embedding search is already accurate enough and the reranker was
blocking the event loop under load).

Usage:
    from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever

    retriever = HotelKnowledgeRetriever()
    retriever.ingest_docs("data/hotel/hotel_faq.pdf", "hotel_faq.pdf")
    results = retriever.document_search("What time is breakfast?")

Environment Variables:
    RERANKER_BACKEND: "none" (default, fastest), "qwen" (local CPU), or "nvidia" (API)
    NVIDIA_API_KEY: Required only if RERANKER_BACKEND=nvidia
"""

import os
import logging
import re as _re
import threading
import time
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document

# Phase H.B — BM25 hybrid retrieval. rank_bm25 is in requirements.dev.txt.
try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

from src.retrievers.base import BaseExample
from src.common.embeddings_openrouter import (
    get_openrouter_embeddings,
    get_model_token_limit,
    DEFAULT_EMBEDDING_MODEL,
)
from src.common.vectorstore_qdrant import (
    create_qdrant_vectorstore,
    get_collection_name,
    get_qdrant_client,
)

logger = logging.getLogger(__name__)

# Reranker selection:
#   "none"   (DEFAULT) — skip reranking. The embedding model is already
#            strong enough for hotel-knowledge recall and reranking was
#            adding ~1-2 seconds of CPU-bound latency per query AND
#            blocking the FastAPI event loop, hurting concurrent-user
#            throughput. We fetch top_k_retrieval directly from Qdrant
#            and return the top N.
#   "qwen"   — local CPU CrossEncoder (legacy — very slow, single-threaded)
#   "nvidia" — NVIDIA NIM reranker API (legacy — requires NVIDIA_API_KEY)
RERANKER_BACKEND = os.getenv("RERANKER_BACKEND", "none").lower()


def get_reranker(top_n: int = 4):
    """
    Get the configured reranker or None if reranking is disabled.

    Returns None when RERANKER_BACKEND=none (default), which signals
    document_search() to use vector-search results directly without a
    second reranking pass.
    """
    if RERANKER_BACKEND == "none" or RERANKER_BACKEND == "":
        logger.info("Reranker disabled (RERANKER_BACKEND=none) — using vector search directly")
        return None
    if RERANKER_BACKEND == "qwen":
        from src.common.reranker_qwen import get_qwen_reranker

        device = os.getenv("RERANKER_DEVICE", "cpu")
        model_name = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        logger.info(
            f"Loading cross-encoder reranker: model={model_name} device={device}"
        )
        return get_qwen_reranker(top_n=top_n, device=device)
    if RERANKER_BACKEND == "nvidia":
        from src.common.reranker_nvidia import get_nvidia_reranker

        logger.info("Using NVIDIA NIM reranker (API-based)")
        return get_nvidia_reranker(top_n=top_n)
    logger.warning(f"Unknown RERANKER_BACKEND={RERANKER_BACKEND}, disabling reranker")
    return None

# Import audit logger
try:
    from src.common.audit_logger import get_audit_logger
except ImportError:
    get_audit_logger = None


def calculate_optimal_chunk_size(
    model: str = DEFAULT_EMBEDDING_MODEL,
    overlap_ratio: float = 0.2,
    safety_margin: float = 0.8,  # Use 80% of limit for safety
    chars_per_token: float = 4.0,  # Estimate: ~4 chars per token for mixed Thai/English
) -> tuple:
    """
    Calculate optimal chunk size based on embedding model token limit.

    This auto-normalizes chunk size to stay within the embedding model's
    context window while maximizing information per chunk.

    Args:
        model: Embedding model name
        overlap_ratio: Ratio of chunk to use for overlap (0.0-0.5)
        safety_margin: Safety margin to avoid hitting token limit (0.5-1.0)
        chars_per_token: Estimated characters per token

    Returns:
        Tuple of (chunk_size, chunk_overlap) in characters
    """
    token_limit = get_model_token_limit(model)
    safe_tokens = int(token_limit * safety_margin)

    # Convert tokens to characters
    chunk_size = int(safe_tokens * chars_per_token)
    chunk_overlap = int(chunk_size * overlap_ratio)

    logger.info(
        f"Auto chunk size: model={model}, tokens={token_limit}, "
        f"chunk_size={chunk_size}, overlap={chunk_overlap}"
    )

    return chunk_size, chunk_overlap


# Auto-calculate optimal chunk size based on embedding model
_embedding_model = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
_auto_chunk_size, _auto_chunk_overlap = calculate_optimal_chunk_size(_embedding_model)

# Configuration - Use auto-calculated values unless explicitly overridden
# Environment variables take precedence for backward compatibility
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", _auto_chunk_size))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", _auto_chunk_overlap))
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", 30))
TOP_K_RERANK = int(os.getenv("TOP_K_RERANK", 5))

# Phase H.B — BM25 + vector hybrid via Reciprocal Rank Fusion.
# Pure dense retrieval (qwen3-embedding-8b) under-weights rare literal
# tokens (e.g. "HOTEL2024GUEST", "+66 2 245 7032"). BM25 over the same
# 49-chunk corpus catches them and is fused with vector results.
HYBRID_ENABLED = os.getenv("HYBRID_RETRIEVAL", "true").lower() == "true"
RRF_K = int(os.getenv("RRF_K", "60"))
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "30"))

# Module-level BM25 cache (lazy build; ~50ms for 49 chunks; reset by
# ingest/delete hooks below).
_bm25_lock = threading.Lock()
_bm25_state: Dict[str, Any] = {"index": None, "docs": None}


def _tokenize_bm25(text: str) -> List[str]:
    """Bilingual tokenizer for BM25. Lowercase + \\w+ split keeps Latin,
    Thai, and CJK as separate tokens. Sufficient for exact-keyword match
    (HOTEL2024GUEST, +66, อาหารเช้า, 早餐)."""
    return _re.findall(r"\w+", (text or "").lower(), flags=_re.UNICODE)


def _build_bm25_index() -> None:
    """Scroll Qdrant once and build an in-memory BM25Okapi index. Idempotent."""
    if BM25Okapi is None:
        logger.warning("rank_bm25 not installed — hybrid retrieval disabled")
        return
    try:
        client = get_qdrant_client()
        collection = get_collection_name()
        docs: List[Dict[str, Any]] = []
        offset = None
        while True:
            results, offset = client.scroll(
                collection_name=collection,
                limit=256,
                offset=offset,
                with_payload=True,
            )
            for p in results:
                payload = p.payload or {}
                content = (
                    payload.get("page_content")
                    or payload.get("content")
                    or (payload.get("metadata") or {}).get("page_content", "")
                )
                if content:
                    src = (
                        (payload.get("metadata") or {}).get("source")
                        or payload.get("source", "unknown")
                    )
                    docs.append({"content": content, "source": src})
            if offset is None:
                break
        tokenized = [_tokenize_bm25(d["content"]) for d in docs]
        index = BM25Okapi(tokenized) if tokenized else None
        _bm25_state["index"] = index
        _bm25_state["docs"] = docs
        logger.info(f"BM25 index built: {len(docs)} chunks")
    except Exception as e:
        logger.error(f"BM25 index build failed: {e}")
        _bm25_state["index"] = None
        _bm25_state["docs"] = None


def _get_bm25() -> Dict[str, Any]:
    """Lazy-init guard around _build_bm25_index."""
    if _bm25_state["index"] is None:
        with _bm25_lock:
            if _bm25_state["index"] is None:
                _build_bm25_index()
    return _bm25_state


def _invalidate_bm25() -> None:
    """Called by ingest/delete hooks so the next query rebuilds."""
    with _bm25_lock:
        _bm25_state["index"] = None
        _bm25_state["docs"] = None


class HotelKnowledgeRetriever(BaseExample):
    """
    RAG retriever for hotel knowledge base.

    Uses:
    - OpenRouter qwen-3-embedding-8b for embeddings
    - Qdrant (Railway) for vector storage
    - Configurable reranker: NVIDIA NIM (fast) or Qwen (local CPU)

    Supports bilingual Thai/English queries and documents.

    Example:
        ```python
        retriever = HotelKnowledgeRetriever()

        # Ingest documents
        retriever.ingest_docs("data/hotel/hotel_faq.pdf", "hotel_faq.pdf")

        # Search in English
        results = retriever.document_search("What time is breakfast?")

        # Search in Thai
        results = retriever.document_search("อาหารเช้ากี่โมง")
        ```
    """

    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        top_k_retrieval: int = TOP_K_RETRIEVAL,
        top_k_rerank: int = TOP_K_RERANK,
    ):
        """
        Initialize Hotel Knowledge Retriever.

        Args:
            chunk_size: Size of text chunks for splitting
            chunk_overlap: Overlap between chunks
            top_k_retrieval: Number of documents to retrieve initially
            top_k_rerank: Number of documents to return after reranking
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k_retrieval = top_k_retrieval
        self.top_k_rerank = top_k_rerank

        # Initialize components
        logger.info("Initializing Hotel Knowledge Retriever")
        self.embeddings = get_openrouter_embeddings()
        self.reranker = get_reranker(top_n=top_k_rerank)
        self.vectorstore = create_qdrant_vectorstore(self.embeddings)
        self.text_splitter = self._get_text_splitter()

    def _get_text_splitter(self):
        """Get text splitter for document chunking."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        # Use markdown-aware separators to keep sections together
        # Priority: section breaks > paragraphs > sentences > words
        return RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=[
                "\n## ",      # H2 headers - major sections
                "\n### ",     # H3 headers - subsections
                "\n\n",       # Paragraphs
                "\n",         # Lines
                ". ",         # Sentences (English)
                "。",          # Sentences (Thai period alternative)
                " ",          # Words
                "",           # Characters
            ],
            length_function=len,
        )

    def ingest_docs(self, filepath: str, filename: str) -> int:
        """
        Ingest hotel knowledge document into Qdrant.

        Args:
            filepath: Full path to the document file
            filename: Name of the document file (used as source)

        Returns:
            Number of chunks ingested

        Raises:
            ValueError: If file format is not supported
        """
        if not filename.endswith((".txt", ".pdf", ".md")):
            raise ValueError(
                f"{filename} is not a valid document. "
                "Supported formats: .txt, .pdf, .md"
            )

        try:
            logger.info(f"Loading document: {filepath}")

            # Use simple text loading for markdown/txt files
            if filename.endswith((".md", ".txt")):
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                raw_docs = [Document(page_content=content, metadata={"source": filename})]
            elif filename.endswith(".pdf"):
                # Use UnstructuredFileLoader only for PDFs
                try:
                    from langchain_community.document_loaders import UnstructuredFileLoader
                    loader = UnstructuredFileLoader(filepath)
                    raw_docs = loader.load()
                except ImportError:
                    raise ImportError(
                        "For PDF files, install: pip install langchain-community unstructured"
                    )
            else:
                raise ValueError(f"Unsupported file format: {filename}")

            if not raw_docs:
                logger.warning(f"No content found in {filename}")
                return 0

            # Split into chunks
            chunks = self.text_splitter.split_documents(raw_docs)

            # Add source metadata
            for chunk in chunks:
                chunk.metadata["source"] = filename

            # Add to Qdrant
            self.vectorstore.add_documents(chunks)

            logger.info(f"Ingested {len(chunks)} chunks from {filename}")
            _invalidate_bm25()  # Phase H.B: corpus changed
            return len(chunks)

        except Exception as e:
            logger.error(f"Failed to ingest {filename}: {e}")
            raise

    def ingest_text(self, text: str, source: str = "direct_input") -> int:
        """
        Ingest text directly into the knowledge base.

        Args:
            text: Text content to ingest
            source: Source identifier for the text

        Returns:
            Number of chunks ingested
        """
        try:
            # Create document from text
            doc = Document(page_content=text, metadata={"source": source})

            # Split into chunks
            chunks = self.text_splitter.split_documents([doc])

            # Add to Qdrant
            self.vectorstore.add_documents(chunks)

            logger.info(f"Ingested {len(chunks)} chunks from {source}")
            _invalidate_bm25()  # Phase H.B: corpus changed
            return len(chunks)

        except Exception as e:
            logger.error(f"Failed to ingest text from {source}: {e}")
            raise

    def document_search(
        self,
        content: str,
        num_docs: int = None,
        conv_history: Dict[str, str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search hotel knowledge base with reranking.

        Args:
            content: Search query (Thai or English)
            num_docs: Number of results to return (default: top_k_rerank)
            conv_history: Conversation history (optional, for future use)

        Returns:
            List of relevant document chunks with scores:
            [{"source": str, "content": str, "score": float}, ...]
        """
        if num_docs is None:
            num_docs = self.top_k_rerank

        logger.info(f"Hotel knowledge search: {content[:50]}...")

        # Timing for audit
        total_start = time.time()
        embedding_time = 0
        retrieval_time = 0
        reranking_time = 0

        try:
            # Get retriever with initial top_k
            retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": self.top_k_retrieval}
            )

            # Retrieve initial candidates
            retrieval_start = time.time()
            docs = retriever.invoke(content)
            retrieval_time = (time.time() - retrieval_start) * 1000

            if not docs:
                logger.info("No documents found")
                # Log retrieval with no results
                if get_audit_logger is not None:
                    try:
                        audit_logger = get_audit_logger()
                        audit_logger.log_retrieval(
                            query=content,
                            collection=get_collection_name(),
                            top_k=self.top_k_retrieval,
                            results=[],
                            latency_ms=retrieval_time,
                            success=True,
                        )
                    except Exception:
                        pass
                return []

            logger.info(f"Retrieved {len(docs)} initial candidates")

            # Log retrieval results before reranking
            retrieval_results = [
                {"source": doc.metadata.get("source", "unknown"), "score": 0.0, "content": doc.page_content}
                for doc in docs
            ]
            if get_audit_logger is not None:
                try:
                    audit_logger = get_audit_logger()
                    audit_logger.log_retrieval(
                        query=content,
                        collection=get_collection_name(),
                        top_k=self.top_k_retrieval,
                        results=retrieval_results,
                        latency_ms=retrieval_time,
                        success=True,
                    )
                except Exception as log_error:
                    logger.debug(f"Audit logging failed: {log_error}")

            # Optional reranking step. When RERANKER_BACKEND=none (default),
            # self.reranker is None and we return the top-N vector-search
            # results directly. This keeps the hot path fast and
            # non-blocking. Reranking was adding ~1-2s of CPU-bound work
            # inside an async tool, stalling the FastAPI event loop.
            reranking_time = 0
            if self.reranker is not None:
                reranking_start = time.time()
                self.reranker.top_n = num_docs
                reranked_docs = self.reranker.compress_documents(
                    documents=docs,
                    query=content
                )
                reranking_time = (time.time() - reranking_start) * 1000
                results = [
                    {
                        "source": doc.metadata.get("source", "unknown"),
                        "content": doc.page_content,
                        "score": doc.metadata.get("relevance_score", 0.0),
                    }
                    for doc in reranked_docs
                ]
                logger.info(f"Returning {len(results)} reranked results")
            elif HYBRID_ENABLED and BM25Okapi is not None:
                # Phase H.B: BM25 + vector hybrid via Reciprocal Rank Fusion.
                # Pure dense retrieval under-weights rare literal tokens
                # (HOTEL2024GUEST, +66 phone, 早餐 cross-lingual). BM25
                # over the same 49-chunk corpus catches them.
                bm25 = _get_bm25()
                if bm25["index"] is not None:
                    tokens = _tokenize_bm25(content)
                    scores = bm25["index"].get_scores(tokens)
                    bm25_ranked_idx = sorted(
                        range(len(scores)), key=lambda i: scores[i], reverse=True
                    )[:BM25_TOP_K]
                    bm25_docs = [bm25["docs"][i] for i in bm25_ranked_idx]
                    # Build rank lookups keyed by chunk content (LangChain
                    # doesn't expose point IDs at this layer; content
                    # equality is reliable for a 49-chunk corpus).
                    vec_rank = {d.page_content: r for r, d in enumerate(docs)}
                    bm25_rank = {d["content"]: r for r, d in enumerate(bm25_docs)}
                    fused: List[tuple] = []
                    for c in set(vec_rank) | set(bm25_rank):
                        score = 0.0
                        if c in vec_rank:
                            score += 1.0 / (RRF_K + vec_rank[c])
                        if c in bm25_rank:
                            score += 1.0 / (RRF_K + bm25_rank[c])
                        fused.append((c, score))
                    fused.sort(key=lambda x: x[1], reverse=True)
                    vec_content_to_doc = {d.page_content: d for d in docs}
                    bm25_content_to_doc = {d["content"]: d for d in bm25_docs}
                    results = []
                    for c, score in fused[:num_docs]:
                        if c in vec_content_to_doc:
                            d = vec_content_to_doc[c]
                            results.append({
                                "source": d.metadata.get("source", "unknown"),
                                "content": d.page_content,
                                "score": score,
                            })
                        else:
                            d = bm25_content_to_doc[c]
                            results.append({
                                "source": d["source"],
                                "content": d["content"],
                                "score": score,
                            })
                    logger.info(f"Returning {len(results)} hybrid (RRF) results")
                else:
                    # BM25 build failed — degrade to vector-only.
                    results = [
                        {
                            "source": doc.metadata.get("source", "unknown"),
                            "content": doc.page_content,
                            "score": 0.0,
                        }
                        for doc in docs[:num_docs]
                    ]
                    logger.info(
                        f"Returning {len(results)} results (vector only — "
                        "BM25 unavailable)"
                    )
            else:
                # No reranker: trim to num_docs from the vector search output
                results = [
                    {
                        "source": doc.metadata.get("source", "unknown"),
                        "content": doc.page_content,
                        "score": 0.0,  # vector score not propagated by LangChain
                    }
                    for doc in docs[:num_docs]
                ]
                logger.info(f"Returning {len(results)} results (no reranker)")

            # Log complete RAG pipeline
            total_time = (time.time() - total_start) * 1000
            if get_audit_logger is not None:
                try:
                    audit_logger = get_audit_logger()
                    audit_logger.log_rag_pipeline(
                        query=content,
                        embedding_ms=embedding_time,
                        retrieval_ms=retrieval_time,
                        reranking_ms=reranking_time,
                        total_ms=total_time,
                        results_count=len(results),
                        final_results=results,
                    )
                except Exception as log_error:
                    logger.debug(f"Audit logging failed: {log_error}")

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_documents(self) -> List[str]:
        """
        Get list of ingested documents.

        Returns:
            List of unique source filenames
        """
        try:
            from qdrant_client import models

            client = get_qdrant_client()
            collection = get_collection_name()

            # Scroll through all points to get unique sources
            sources = set()
            offset = None

            while True:
                results, offset = client.scroll(
                    collection_name=collection,
                    limit=100,
                    offset=offset,
                    with_payload=["source"]
                )

                for point in results:
                    if point.payload and "source" in point.payload:
                        sources.add(point.payload["source"])

                if offset is None:
                    break

            return sorted(list(sources))

        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            return []

    def delete_documents(self, filenames: List[str]) -> bool:
        """
        Delete documents by filename.

        Args:
            filenames: List of source filenames to delete

        Returns:
            True if deletion was successful
        """
        try:
            from qdrant_client import models

            client = get_qdrant_client()
            collection = get_collection_name()

            for filename in filenames:
                client.delete(
                    collection_name=collection,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="source",
                                    match=models.MatchValue(value=filename)
                                )
                            ]
                        )
                    )
                )
                logger.info(f"Deleted documents with source: {filename}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return False

    def clear_collection(self) -> bool:
        """
        Clear all documents from the collection.

        Returns:
            True if successful
        """
        try:
            from src.common.vectorstore_qdrant import delete_collection

            result = delete_collection()
            if result:
                # Recreate empty collection by re-initializing vectorstore
                self.vectorstore = create_qdrant_vectorstore(self.embeddings)
            return result

        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            return False
