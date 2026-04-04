# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Qdrant Vector Store Integration for Hotel Knowledge RAG

Connects to Railway-hosted Qdrant instance for vector storage and retrieval.
Provides LangChain-compatible vector store interface.

Usage:
    from src.common.vectorstore_qdrant import create_qdrant_vectorstore
    from src.common.embeddings_openrouter import get_openrouter_embeddings

    embeddings = get_openrouter_embeddings()
    vectorstore = create_qdrant_vectorstore(embeddings)
    vectorstore.add_documents(documents)
"""

import os
import logging
from typing import Optional, List
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_QDRANT_URL = "https://qdrant-production-8938.up.railway.app"
DEFAULT_COLLECTION_NAME = "hotel_knowledge"


def get_qdrant_url() -> str:
    """Get Qdrant URL from environment or default."""
    return os.getenv("QDRANT_URL", DEFAULT_QDRANT_URL)


def get_collection_name() -> str:
    """Get collection name from environment or default."""
    return os.getenv("QDRANT_COLLECTION", DEFAULT_COLLECTION_NAME)


def get_qdrant_client():
    """
    Create Qdrant client — auto-detects local (HTTP) vs Railway (HTTPS).

    Returns:
        QdrantClient instance
    """
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        raise ImportError(
            "qdrant-client is required. Install with: pip install qdrant-client"
        )

    qdrant_url = get_qdrant_url()
    api_key = os.getenv("QDRANT_API_KEY", None)
    is_local = qdrant_url.startswith("http://")

    logger.info(f"Connecting to Qdrant at: {qdrant_url} (local={is_local})")

    if is_local:
        # Local Docker Qdrant — HTTP, no auth
        return QdrantClient(
            url=qdrant_url,
            prefer_grpc=False,
        )
    else:
        # Railway / remote HTTPS Qdrant
        return QdrantClient(
            url=qdrant_url,
            api_key=api_key,
            port=443,
            https=True,
            grpc_port=None,
            prefer_grpc=False,
        )


def create_qdrant_vectorstore(
    embeddings: Embeddings,
    collection_name: Optional[str] = None,
    vector_size: int = None,
):
    """
    Create or connect to Qdrant vector store.

    Args:
        embeddings: Embedding model instance
        collection_name: Name of the collection (default from env)
        vector_size: Size of embedding vectors (default 4096 for qwen3-embedding-8b)

    Returns:
        QdrantVectorStore instance

    Raises:
        ImportError: If langchain-qdrant is not installed

    Example:
        ```python
        from src.common.embeddings_openrouter import get_openrouter_embeddings

        embeddings = get_openrouter_embeddings()
        vectorstore = create_qdrant_vectorstore(embeddings)

        # Add documents
        vectorstore.add_documents([
            Document(page_content="Breakfast: 6:30 AM - 10:30 AM"),
            Document(page_content="WiFi: HOTEL2024GUEST"),
        ])

        # Search
        results = vectorstore.similarity_search("breakfast time", k=3)
        ```
    """
    try:
        from langchain_qdrant import QdrantVectorStore
        from qdrant_client.models import Distance, VectorParams
    except ImportError:
        raise ImportError(
            "langchain-qdrant is required. Install with: pip install langchain-qdrant"
        )

    # Auto-detect vector size from env (qwen3-embedding:4b=2560, qwen3-embedding-8b=4096)
    if vector_size is None:
        vector_size = int(os.getenv("EMBEDDING_VECTOR_SIZE", "4096"))

    collection = collection_name or get_collection_name()
    client = get_qdrant_client()

    logger.info(f"Creating/connecting to Qdrant collection: {collection}")

    # Check if collection exists, create if not
    try:
        client.get_collection(collection_name=collection)
        logger.info(f"Collection '{collection}' already exists")
    except Exception:
        logger.info(f"Creating new collection '{collection}' with vector_size={vector_size}")
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )

    return QdrantVectorStore(
        client=client,
        collection_name=collection,
        embedding=embeddings,
    )


def get_qdrant_retriever(
    embeddings: Embeddings,
    collection_name: Optional[str] = None,
    top_k: int = 10,
):
    """
    Get a retriever from Qdrant vector store.

    Args:
        embeddings: Embedding model
        collection_name: Collection name (default from env)
        top_k: Number of documents to retrieve

    Returns:
        LangChain retriever

    Example:
        ```python
        retriever = get_qdrant_retriever(embeddings, top_k=5)
        docs = retriever.invoke("What time is checkout?")
        ```
    """
    vectorstore = create_qdrant_vectorstore(embeddings, collection_name)
    return vectorstore.as_retriever(search_kwargs={"k": top_k})


def delete_collection(collection_name: Optional[str] = None) -> bool:
    """
    Delete a Qdrant collection.

    Args:
        collection_name: Name of collection to delete

    Returns:
        True if deleted successfully
    """
    collection = collection_name or get_collection_name()
    client = get_qdrant_client()

    try:
        client.delete_collection(collection_name=collection)
        logger.info(f"Deleted collection: {collection}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete collection {collection}: {e}")
        return False


def get_collection_info(collection_name: Optional[str] = None) -> dict:
    """
    Get information about a Qdrant collection.

    Args:
        collection_name: Name of collection

    Returns:
        Dictionary with collection info (vectors_count, status, etc.)
    """
    collection = collection_name or get_collection_name()
    client = get_qdrant_client()

    try:
        info = client.get_collection(collection_name=collection)
        return {
            "name": collection,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "status": info.status.name,
            "config": {
                "vector_size": info.config.params.vectors.size if hasattr(info.config.params.vectors, 'size') else None,
                "distance": info.config.params.vectors.distance.name if hasattr(info.config.params.vectors, 'distance') else None,
            }
        }
    except Exception as e:
        logger.error(f"Failed to get collection info for {collection}: {e}")
        return {"name": collection, "error": str(e)}


def list_collections() -> List[str]:
    """
    List all Qdrant collections.

    Returns:
        List of collection names
    """
    client = get_qdrant_client()

    try:
        collections = client.get_collections()
        return [c.name for c in collections.collections]
    except Exception as e:
        logger.error(f"Failed to list collections: {e}")
        return []


def health_check() -> dict:
    """
    Check Qdrant connection health.

    Returns:
        Dictionary with health status
    """
    try:
        client = get_qdrant_client()
        # Try to list collections as a health check
        collections = client.get_collections()
        return {
            "status": "healthy",
            "url": get_qdrant_url(),
            "collections_count": len(collections.collections),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "url": get_qdrant_url(),
            "error": str(e),
        }
