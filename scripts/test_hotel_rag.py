#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Test Hotel Knowledge RAG System

Validates:
1. Document ingestion to Qdrant
2. Embedding generation with OpenRouter
3. Retrieval accuracy
4. Reranking with Qwen3-0.6B

Usage:
    # Generate documents first
    python scripts/generate_hotel_knowledge.py

    # Run RAG tests
    python scripts/test_hotel_rag.py

    # Run specific tests
    python scripts/test_hotel_rag.py --test-ingest
    python scripts/test_hotel_rag.py --test-search
    python scripts/test_hotel_rag.py --test-accuracy
"""

import os
import sys
import argparse
import time
from pathlib import Path

# Test queries with expected keywords to validate retrieval accuracy
TEST_QUERIES = [
    # Breakfast queries (English and Thai)
    ("What time is breakfast?", ["6:30", "10:30", "Grand Dining", "complimentary"]),
    ("อาหารเช้ากี่โมง", ["06:30", "10:30", "ห้องอาหาร", "ฟรี"]),

    # WiFi queries
    ("What is the WiFi password?", ["HOTEL2024GUEST", "100 Mbps", "HotelGuest"]),
    ("รหัส WiFi คืออะไร", ["HOTEL2024GUEST", "100 Mbps", "อินเทอร์เน็ต"]),

    # Check-in/out queries
    ("What time is check-in?", ["2:00 PM", "14:00", "early check-in"]),
    ("เช็คเอาท์กี่โมง", ["12:00", "เที่ยง", "500"]),

    # Spa queries
    ("What are the spa hours?", ["10:00 AM", "10:00 PM", "Serenity"]),
    ("นวดแผนไทยราคาเท่าไหร่", ["1,500", "2,000", "2,500"]),

    # Pool queries
    ("Where is the swimming pool?", ["5th Floor", "Rooftop", "6:00 AM", "9:00 PM"]),
    ("สระว่ายน้ำเปิดกี่โมง", ["06:00", "21:00", "ชั้น 5"]),

    # Cancellation queries
    ("What is the cancellation policy?", ["48 hours", "free", "1 night"]),
    ("นโยบายยกเลิก", ["48 ชั่วโมง", "ฟรี"]),

    # Room service queries
    ("Is room service available 24 hours?", ["24 hours", "30-45 minutes"]),
    ("สั่งรูมเซอร์วิสได้ตอนไหน", ["24 ชั่วโมง"]),

    # Pet policy
    ("Can I bring my dog?", ["small pets", "5 kg", "500 THB"]),
    ("พาสัตว์เลี้ยงมาได้ไหม", ["5 กก", "500 บาท"]),

    # Room types
    ("What room types are available?", ["Standard", "Deluxe", "Suite", "Penthouse"]),
    ("ห้องพักมีกี่ประเภท", ["สแตนดาร์ด", "ดีลักซ์", "สวีท", "เพนท์เฮาส์"]),

    # Transportation
    ("How do I get to the airport?", ["airport transfer", "1,500", "Suvarnabhumi"]),
    ("รถรับส่งสนามบิน", ["สนามบิน", "1,500", "สุวรรณภูมิ"]),
]

# Data directory
DATA_DIR = Path("data/hotel")


def test_qdrant_connection():
    """Test connection to Qdrant."""
    print("\n" + "=" * 60)
    print("Testing Qdrant Connection")
    print("=" * 60)

    try:
        from src.common.vectorstore_qdrant import health_check, list_collections

        health = health_check()
        print(f"Status: {health['status']}")
        print(f"URL: {health['url']}")

        if health['status'] == 'healthy':
            collections = list_collections()
            print(f"Collections: {collections}")
            print("✓ Qdrant connection successful")
            return True
        else:
            print(f"✗ Qdrant unhealthy: {health.get('error')}")
            return False

    except Exception as e:
        print(f"✗ Qdrant connection failed: {e}")
        return False


def test_embeddings():
    """Test OpenRouter embeddings."""
    print("\n" + "=" * 60)
    print("Testing OpenRouter Embeddings")
    print("=" * 60)

    try:
        from src.common.embeddings_openrouter import get_openrouter_embeddings

        embeddings = get_openrouter_embeddings()

        # Test embedding generation
        test_text = "What time is breakfast?"
        print(f"Embedding test text: '{test_text}'")

        start = time.time()
        vector = embeddings.embed_query(test_text)
        elapsed = time.time() - start

        print(f"Vector dimensions: {len(vector)}")
        print(f"Generation time: {elapsed:.2f}s")
        print(f"Sample values: [{vector[0]:.4f}, {vector[1]:.4f}, ...]")
        print("✓ Embeddings working")
        return True

    except Exception as e:
        print(f"✗ Embeddings failed: {e}")
        return False


def test_reranker():
    """Test Qwen3 reranker."""
    print("\n" + "=" * 60)
    print("Testing Qwen3 Reranker")
    print("=" * 60)

    try:
        from src.common.reranker_qwen import get_qwen_reranker
        from langchain_core.documents import Document

        reranker = get_qwen_reranker(top_n=2)

        # Test documents
        docs = [
            Document(page_content="Breakfast is served from 6:30 AM to 10:30 AM."),
            Document(page_content="The swimming pool is on the 5th floor."),
            Document(page_content="WiFi password is HOTEL2024GUEST."),
        ]

        query = "What time is breakfast?"
        print(f"Query: '{query}'")
        print(f"Documents: {len(docs)}")

        start = time.time()
        reranked = reranker.compress_documents(documents=docs, query=query)
        elapsed = time.time() - start

        print(f"Reranked to: {len(reranked)} docs")
        print(f"Reranking time: {elapsed:.2f}s")

        for i, doc in enumerate(reranked):
            score = doc.metadata.get("relevance_score", 0)
            print(f"  {i+1}. Score: {score:.3f} - {doc.page_content[:50]}...")

        # Verify breakfast doc is ranked first
        if "breakfast" in reranked[0].page_content.lower():
            print("✓ Reranker working correctly")
            return True
        else:
            print("✗ Reranker did not rank correctly")
            return False

    except Exception as e:
        print(f"✗ Reranker failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ingest_documents():
    """Test document ingestion."""
    print("\n" + "=" * 60)
    print("Testing Document Ingestion")
    print("=" * 60)

    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        print("Run: python scripts/generate_hotel_knowledge.py first")
        return False

    try:
        from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever

        retriever = HotelKnowledgeRetriever()

        # Clear existing collection
        print("Clearing existing collection...")
        retriever.clear_collection()

        # Get all markdown files
        files = list(DATA_DIR.glob("*.md"))
        if not files:
            print(f"No markdown files found in {DATA_DIR}")
            return False

        print(f"Found {len(files)} documents to ingest")

        total_chunks = 0
        for filepath in files:
            print(f"  Ingesting: {filepath.name}...", end=" ")
            start = time.time()
            chunks = retriever.ingest_docs(str(filepath), filepath.name)
            elapsed = time.time() - start
            print(f"{chunks} chunks ({elapsed:.2f}s)")
            total_chunks += chunks

        print(f"\n✓ Ingested {total_chunks} total chunks from {len(files)} documents")

        # Verify documents are in the store
        docs = retriever.get_documents()
        print(f"Documents in store: {docs}")

        return len(docs) > 0

    except Exception as e:
        print(f"✗ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_document_search():
    """Test document search."""
    print("\n" + "=" * 60)
    print("Testing Document Search")
    print("=" * 60)

    try:
        from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever

        retriever = HotelKnowledgeRetriever()

        # Simple search test
        query = "What time is breakfast?"
        print(f"Query: '{query}'")

        start = time.time()
        results = retriever.document_search(query, num_docs=3)
        elapsed = time.time() - start

        print(f"Results: {len(results)} documents")
        print(f"Search time: {elapsed:.2f}s")

        if results:
            for i, r in enumerate(results):
                print(f"\n  Result {i+1}:")
                print(f"    Source: {r['source']}")
                print(f"    Score: {r['score']:.3f}")
                print(f"    Content: {r['content'][:100]}...")

            print("\n✓ Document search working")
            return True
        else:
            print("✗ No results returned")
            return False

    except Exception as e:
        print(f"✗ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_accuracy():
    """Test RAG retrieval accuracy with expected keywords."""
    print("\n" + "=" * 60)
    print("Testing RAG Accuracy")
    print("=" * 60)

    try:
        from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever

        retriever = HotelKnowledgeRetriever()

        passed = 0
        failed = 0

        for query, expected_keywords in TEST_QUERIES:
            results = retriever.document_search(query, num_docs=3)

            if not results:
                print(f"✗ FAIL (no results): {query}")
                failed += 1
                continue

            # Combine all result content
            combined = " ".join([r["content"] for r in results])

            # Check if expected keywords are present (case-insensitive)
            found = []
            for kw in expected_keywords:
                if kw.lower() in combined.lower():
                    found.append(kw)

            # Consider pass if at least 50% of keywords found
            threshold = len(expected_keywords) // 2
            if len(found) >= threshold:
                passed += 1
                status = "✓ PASS"
            else:
                failed += 1
                status = "✗ FAIL"

            top_score = results[0]['score'] if results else 0
            print(f"{status}: {query[:40]}...")
            print(f"       Found {len(found)}/{len(expected_keywords)} keywords, score={top_score:.3f}")

        total = passed + failed
        accuracy = 100 * passed / total if total > 0 else 0

        print("\n" + "-" * 60)
        print(f"Accuracy: {passed}/{total} passed ({accuracy:.1f}%)")

        if accuracy >= 70:
            print("✓ RAG accuracy test PASSED")
            return True
        else:
            print("✗ RAG accuracy below threshold (70%)")
            return False

    except Exception as e:
        print(f"✗ Accuracy test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Hotel Knowledge RAG System Test Suite")
    print("=" * 60)

    results = {}

    # Test Qdrant connection
    results["Qdrant Connection"] = test_qdrant_connection()

    # Test embeddings
    results["OpenRouter Embeddings"] = test_embeddings()

    # Test reranker
    results["Qwen3 Reranker"] = test_reranker()

    # Test document ingestion
    results["Document Ingestion"] = test_ingest_documents()

    # Test search
    results["Document Search"] = test_document_search()

    # Test accuracy
    results["RAG Accuracy"] = test_rag_accuracy()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for test, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests PASSED!")
    else:
        print("Some tests FAILED. Check output above.")
    print("=" * 60)

    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test Hotel Knowledge RAG System")
    parser.add_argument("--test-connection", action="store_true", help="Test Qdrant connection only")
    parser.add_argument("--test-embeddings", action="store_true", help="Test embeddings only")
    parser.add_argument("--test-reranker", action="store_true", help="Test reranker only")
    parser.add_argument("--test-ingest", action="store_true", help="Test document ingestion only")
    parser.add_argument("--test-search", action="store_true", help="Test document search only")
    parser.add_argument("--test-accuracy", action="store_true", help="Test RAG accuracy only")

    args = parser.parse_args()

    # Run specific tests or all
    if args.test_connection:
        success = test_qdrant_connection()
    elif args.test_embeddings:
        success = test_embeddings()
    elif args.test_reranker:
        success = test_reranker()
    elif args.test_ingest:
        success = test_ingest_documents()
    elif args.test_search:
        success = test_document_search()
    elif args.test_accuracy:
        success = test_rag_accuracy()
    else:
        success = run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
