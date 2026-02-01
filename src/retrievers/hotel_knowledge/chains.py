# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hotel Knowledge RAG Chain

Retrieves hotel information from Qdrant using OpenRouter embeddings
and Qwen3-0.6B reranker. Supports bilingual Thai/English queries.

Usage:
    from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever

    retriever = HotelKnowledgeRetriever()
    retriever.ingest_docs("data/hotel/hotel_faq.pdf", "hotel_faq.pdf")
    results = retriever.document_search("What time is breakfast?")
"""

import os
import logging
import time
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document

from src.retrievers.base import BaseExample
from src.common.embeddings_openrouter import (
    get_openrouter_embeddings,
    get_model_token_limit,
    DEFAULT_EMBEDDING_MODEL,
)
from src.common.reranker_qwen import get_qwen_reranker
from src.common.vectorstore_qdrant import (
    create_qdrant_vectorstore,
    get_collection_name,
    get_qdrant_client,
)

logger = logging.getLogger(__name__)

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


class HotelKnowledgeRetriever(BaseExample):
    """
    RAG retriever for hotel knowledge base.

    Uses:
    - OpenRouter qwen-3-embedding-8b for embeddings
    - Qdrant (Railway) for vector storage
    - Qwen3-0.6B for reranking

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
        self.reranker = get_qwen_reranker(top_n=top_k_rerank)
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

            # Rerank with Qwen3
            reranking_start = time.time()
            self.reranker.top_n = num_docs
            reranked_docs = self.reranker.compress_documents(
                documents=docs,
                query=content
            )
            reranking_time = (time.time() - reranking_start) * 1000

            # Format response
            results = []
            for doc in reranked_docs:
                results.append({
                    "source": doc.metadata.get("source", "unknown"),
                    "content": doc.page_content,
                    "score": doc.metadata.get("relevance_score", 0.0)
                })

            logger.info(f"Returning {len(results)} reranked results")

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
