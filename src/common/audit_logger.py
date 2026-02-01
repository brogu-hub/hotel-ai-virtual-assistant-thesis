# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Audit Logger for RAG Pipeline

Logs all tool calls, vector retrieval operations, and reranker scoring
for debugging, compliance, and performance analysis.

Usage:
    from src.common.audit_logger import get_audit_logger

    logger = get_audit_logger()
    logger.log_embedding_request(texts, model, response_time)
    logger.log_retrieval(query, results, latency_ms)
    logger.log_reranking(query, documents, scores, top_n)
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from functools import lru_cache
import uuid

# Configure audit logger
AUDIT_LOG_DIR = os.getenv("AUDIT_LOG_DIR", "logs/audit")
AUDIT_LOG_LEVEL = os.getenv("AUDIT_LOG_LEVEL", "INFO")
ENABLE_AUDIT_LOG = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"

# Standard logger for console output
logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Structured audit logger for RAG pipeline operations.

    Records:
    - Embedding requests and responses
    - Vector store retrieval operations
    - Reranker scoring details
    - Tool call metadata (timing, parameters, results)
    """

    def __init__(self, log_dir: str = AUDIT_LOG_DIR, enabled: bool = ENABLE_AUDIT_LOG):
        """
        Initialize audit logger.

        Args:
            log_dir: Directory to store audit logs
            enabled: Whether audit logging is enabled
        """
        self.enabled = enabled
        self.log_dir = Path(log_dir)
        self.session_id = str(uuid.uuid4())[:8]

        if self.enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self._setup_file_handlers()
            logger.info(f"Audit logger initialized: {self.log_dir} (session: {self.session_id})")

    def _setup_file_handlers(self):
        """Setup file handlers for different log types."""
        self.log_files = {
            "embeddings": self.log_dir / "embeddings.jsonl",
            "retrieval": self.log_dir / "retrieval.jsonl",
            "reranking": self.log_dir / "reranking.jsonl",
            "tool_calls": self.log_dir / "tool_calls.jsonl",
            "routing": self.log_dir / "routing.jsonl",
        }

    def _write_log(self, log_type: str, entry: Dict[str, Any]):
        """Write a log entry to the appropriate file."""
        if not self.enabled:
            return

        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        entry["session_id"] = self.session_id

        log_file = self.log_files.get(log_type)
        if log_file:
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

    def log_embedding_request(
        self,
        texts: List[str],
        model: str,
        response_time_ms: float,
        dimensions: int,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """
        Log an embedding request.

        Args:
            texts: Input texts that were embedded
            model: Embedding model name
            response_time_ms: Time taken for the request
            dimensions: Dimension of output embeddings
            success: Whether the request succeeded
            error: Error message if failed
        """
        entry = {
            "operation": "embedding",
            "model": model,
            "input_count": len(texts),
            "input_preview": [t[:100] + "..." if len(t) > 100 else t for t in texts[:3]],
            "dimensions": dimensions,
            "response_time_ms": response_time_ms,
            "success": success,
            "error": error,
        }
        self._write_log("embeddings", entry)

        # Also log to console
        status = "SUCCESS" if success else f"FAILED: {error}"
        logger.debug(
            f"[EMBED] {model} | {len(texts)} texts | {response_time_ms:.0f}ms | {status}"
        )

    def log_retrieval(
        self,
        query: str,
        collection: str,
        top_k: int,
        results: List[Dict[str, Any]],
        latency_ms: float,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """
        Log a vector retrieval operation.

        Args:
            query: Search query
            collection: Vector store collection name
            top_k: Number of results requested
            results: Retrieved documents with scores
            latency_ms: Time taken for retrieval
            success: Whether the operation succeeded
            error: Error message if failed
        """
        # Prepare results summary
        results_summary = []
        for i, r in enumerate(results[:10]):  # Log up to 10 results
            results_summary.append({
                "rank": i + 1,
                "source": r.get("source", "unknown"),
                "score": r.get("score", 0.0),
                "content_preview": r.get("content", "")[:150],
            })

        entry = {
            "operation": "retrieval",
            "query": query,
            "query_language": self._detect_language(query),
            "collection": collection,
            "top_k": top_k,
            "results_count": len(results),
            "results": results_summary,
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
        }
        self._write_log("retrieval", entry)

        logger.debug(
            f"[RETRIEVE] '{query[:50]}...' | {len(results)} results | {latency_ms:.0f}ms"
        )

    def log_reranking(
        self,
        query: str,
        model: str,
        input_documents: List[Dict[str, Any]],
        reranked_documents: List[Dict[str, Any]],
        top_n: int,
        latency_ms: float,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """
        Log a reranking operation with detailed scoring.

        Args:
            query: Original search query
            model: Reranker model name
            input_documents: Documents before reranking
            reranked_documents: Documents after reranking with scores
            top_n: Number of documents returned
            latency_ms: Time taken for reranking
            success: Whether the operation succeeded
            error: Error message if failed
        """
        # Document score mapping
        scores_before = []
        for i, doc in enumerate(input_documents[:20]):
            scores_before.append({
                "rank": i + 1,
                "source": doc.get("source", "unknown"),
                "initial_score": doc.get("score", 0.0),
            })

        scores_after = []
        for i, doc in enumerate(reranked_documents):
            scores_after.append({
                "rank": i + 1,
                "source": doc.get("source", "unknown"),
                "relevance_score": doc.get("score", 0.0),
                "content_preview": doc.get("content", "")[:100],
            })

        entry = {
            "operation": "reranking",
            "query": query,
            "query_language": self._detect_language(query),
            "model": model,
            "input_count": len(input_documents),
            "output_count": len(reranked_documents),
            "top_n": top_n,
            "scores_before": scores_before,
            "scores_after": scores_after,
            "score_range": {
                "min": min([d["relevance_score"] for d in scores_after], default=0),
                "max": max([d["relevance_score"] for d in scores_after], default=0),
            },
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
        }
        self._write_log("reranking", entry)

        if scores_after:
            score_str = ", ".join([f"{d['relevance_score']:.3f}" for d in scores_after])
            logger.debug(f"[RERANK] '{query[:50]}...' | scores: [{score_str}] | {latency_ms:.0f}ms")

    def log_tool_call(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        latency_ms: float,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """
        Log a tool call (for hotel_tools, search_hotel_knowledge, etc.).

        Args:
            tool_name: Name of the tool called
            parameters: Input parameters
            result: Tool output/result
            latency_ms: Time taken
            success: Whether the call succeeded
            error: Error message if failed
        """
        # Truncate large results
        result_preview = str(result)[:500] if result else None

        entry = {
            "operation": "tool_call",
            "tool_name": tool_name,
            "parameters": parameters,
            "result_preview": result_preview,
            "result_length": len(str(result)) if result else 0,
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
        }
        self._write_log("tool_calls", entry)

        status = "SUCCESS" if success else f"FAILED: {error}"
        logger.debug(f"[TOOL] {tool_name} | {latency_ms:.0f}ms | {status}")

    def log_rag_pipeline(
        self,
        query: str,
        embedding_ms: float,
        retrieval_ms: float,
        reranking_ms: float,
        total_ms: float,
        results_count: int,
        final_results: List[Dict[str, Any]],
    ):
        """
        Log complete RAG pipeline execution.

        Args:
            query: User query
            embedding_ms: Embedding time
            retrieval_ms: Retrieval time
            reranking_ms: Reranking time
            total_ms: Total pipeline time
            results_count: Number of final results
            final_results: Final documents returned
        """
        entry = {
            "operation": "rag_pipeline",
            "query": query,
            "query_language": self._detect_language(query),
            "timing": {
                "embedding_ms": embedding_ms,
                "retrieval_ms": retrieval_ms,
                "reranking_ms": reranking_ms,
                "total_ms": total_ms,
            },
            "results_count": results_count,
            "final_results": [
                {
                    "rank": i + 1,
                    "source": r.get("source", "unknown"),
                    "score": r.get("score", 0.0),
                }
                for i, r in enumerate(final_results)
            ],
        }
        self._write_log("tool_calls", entry)

        logger.info(
            f"[RAG] '{query[:50]}...' | "
            f"embed:{embedding_ms:.0f}ms + retrieve:{retrieval_ms:.0f}ms + "
            f"rerank:{reranking_ms:.0f}ms = {total_ms:.0f}ms | {results_count} results"
        )

    def log_routing_decision(
        self,
        request_id: str,
        query: str,
        routing_path: str,
        complexity: str,
        latency_ms: float,
        confidence: Optional[float] = None,
        historical_score: Optional[float] = None,
        reason: Optional[str] = None,
    ):
        """
        Log hybrid routing decision for analysis and optimization.

        Args:
            request_id: Unique request identifier
            query: User query
            routing_path: Which path was chosen (nemo/langgraph/blocked)
            complexity: Query complexity (simple/moderate/complex)
            latency_ms: Total response latency
            confidence: Confidence score for the routing decision
            historical_score: Historical performance score that influenced decision
            reason: Human-readable reason for the routing decision
        """
        entry = {
            "operation": "routing_decision",
            "request_id": request_id,
            "query": query[:200],  # Truncate long queries
            "query_language": self._detect_language(query),
            "routing_path": routing_path,
            "complexity": complexity,
            "confidence": confidence,
            "historical_score": historical_score,
            "reason": reason,
            "latency_ms": latency_ms,
        }
        self._write_log("routing", entry)

        logger.info(
            f"[ROUTE] {routing_path} | complexity={complexity} | "
            f"confidence={confidence:.2f if confidence else 'N/A'} | {latency_ms:.0f}ms"
        )

    def _detect_language(self, text: str) -> str:
        """Simple language detection based on Thai character presence."""
        thai_chars = sum(1 for c in text if "\u0e00" <= c <= "\u0e7f")
        if thai_chars > len(text) * 0.2:
            return "th"
        return "en"


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


@lru_cache(maxsize=1)
def get_audit_logger() -> AuditLogger:
    """Get the singleton audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
