#!/usr/bin/env python3
"""
Ingest hotel knowledge documents from data/hotel/ into Qdrant vector store.

Usage:
    python scripts/ingest_hotel_knowledge.py
"""
import os
import sys
import glob
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def main():
    # Find hotel knowledge docs
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "hotel")
    if not os.path.exists(data_dir):
        # Try Docker path
        data_dir = "/app/data/hotel"

    md_files = sorted(glob.glob(os.path.join(data_dir, "*.md")))
    if not md_files:
        logger.error(f"No .md files found in {data_dir}")
        sys.exit(1)

    logger.info(f"Found {len(md_files)} knowledge documents in {data_dir}")

    # Initialize retriever (connects to Qdrant + embeddings)
    from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever
    retriever = HotelKnowledgeRetriever()

    # Clear existing collection for fresh ingest
    logger.info("Clearing existing collection...")
    retriever.clear_collection()

    # Ingest each document
    total_chunks = 0
    for filepath in md_files:
        filename = os.path.basename(filepath)
        try:
            chunks = retriever.ingest_docs(filepath, filename)
            total_chunks += chunks
            logger.info(f"  {filename}: {chunks} chunks")
        except Exception as e:
            logger.error(f"  {filename}: FAILED - {e}")

    logger.info(f"\nIngestion complete: {total_chunks} total chunks from {len(md_files)} documents")

    # Quick search test
    logger.info("\nRunning test search: 'breakfast time'")
    results = retriever.document_search("What time is breakfast?")
    for r in results[:3]:
        logger.info(f"  [{r['score']:.3f}] {r['source']}: {r['content'][:80]}...")


if __name__ == "__main__":
    main()
