# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hotel Knowledge RAG Retriever

Provides semantic search over hotel knowledge base including:
- Hotel FAQs
- Dining services and hours
- Spa and wellness information
- Facilities and amenities
- Hotel policies and rules
"""

from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever

__all__ = ["HotelKnowledgeRetriever"]
