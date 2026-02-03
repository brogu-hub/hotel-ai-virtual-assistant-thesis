# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Pydantic Models for RAG Evaluation

Defines schemas for:
- Golden Q&A pairs (test data)
- Evaluation results
- Report data structures
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    """Supported languages for evaluation."""
    ENGLISH = "en"
    THAI = "th"


class Category(str, Enum):
    """Hotel knowledge categories."""
    DINING = "dining"
    FACILITIES = "facilities"
    SPA = "spa"
    ROOM = "room"
    POLICY = "policy"
    TRANSPORTATION = "transportation"
    EMERGENCY = "emergency"
    FAQ = "faq"
    BOOKING = "booking"  # CRUD operations for reservations


class Difficulty(str, Enum):
    """Question difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class GoldenQAPair(BaseModel):
    """
    Single Q&A pair for evaluation.

    Represents a test case with expected answer and context.
    """
    id: str = Field(
        ...,
        description="Unique identifier, e.g., 'breakfast_en_01'",
    )
    question: str = Field(
        ...,
        description="User query in Thai or English",
    )
    expected_answer: str = Field(
        ...,
        description="Golden answer extracted from source document",
    )
    expected_context: List[str] = Field(
        ...,
        description="Source document filenames that should be retrieved",
    )
    expected_keywords: List[str] = Field(
        ...,
        description="Keywords that must appear in the response",
    )
    language: Language = Field(
        ...,
        description="Query language: 'en' or 'th'",
    )
    category: Category = Field(
        ...,
        description="Topic category",
    )
    difficulty: Difficulty = Field(
        default=Difficulty.MEDIUM,
        description="Question difficulty: easy/medium/hard",
    )


class GoldenDataset(BaseModel):
    """
    Complete evaluation dataset.

    Contains all Q&A pairs for RAG evaluation.
    """
    version: str = Field(
        default="1.0.0",
        description="Dataset version",
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Timestamp when dataset was generated",
    )
    total_pairs: int = Field(
        ...,
        description="Total number of Q&A pairs",
    )
    pairs: List[GoldenQAPair] = Field(
        ...,
        description="List of Q&A pairs",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "version": "1.0.0",
                "generated_at": "2024-01-15T10:30:00",
                "total_pairs": 24,
                "pairs": [
                    {
                        "id": "dining_en_01",
                        "question": "What time is breakfast?",
                        "expected_answer": "Breakfast is served from 6:30 AM to 10:30 AM...",
                        "expected_context": ["dining_services.md"],
                        "expected_keywords": ["6:30", "10:30", "Grand Dining"],
                        "language": "en",
                        "category": "dining",
                        "difficulty": "easy",
                    }
                ],
            }
        }


class MetricScore(BaseModel):
    """Score for a single metric."""
    name: str = Field(..., description="Metric name")
    score: float = Field(..., description="Score between 0 and 1")
    passed: bool = Field(..., description="Whether score meets threshold")
    reason: Optional[str] = Field(None, description="Explanation for score")


class EvaluationResult(BaseModel):
    """
    Result for a single test case evaluation.

    Contains all metrics and scores for one Q&A pair.
    """
    question_id: str = Field(..., description="Q&A pair ID")
    question: str = Field(..., description="Original question")
    language: Language = Field(..., description="Question language")
    category: Category = Field(..., description="Question category")

    # Response data
    actual_output: str = Field(..., description="AI response from endpoint")
    expected_output: str = Field(..., description="Expected golden answer")
    retrieval_context: List[str] = Field(
        default_factory=list,
        description="Sources returned by RAG",
    )
    expected_context: List[str] = Field(
        default_factory=list,
        description="Expected source documents",
    )

    # Performance
    latency_ms: float = Field(..., description="Response time in milliseconds")

    # Metric scores
    faithfulness_score: float = Field(
        default=0.0,
        description="Faithfulness metric score",
    )
    context_recall_score: float = Field(
        default=0.0,
        description="Context recall metric score",
    )
    answer_relevancy_score: float = Field(
        default=0.0,
        description="Answer relevancy metric score",
    )
    helpfulness_score: float = Field(
        default=0.0,
        description="Bilingual helpfulness GEval score",
    )

    # Overall result
    passed: bool = Field(..., description="Whether test case passed")
    failure_reasons: List[str] = Field(
        default_factory=list,
        description="Reasons for failure if any",
    )

    @property
    def average_score(self) -> float:
        """Calculate average of all metric scores."""
        scores = [
            self.faithfulness_score,
            self.context_recall_score,
            self.answer_relevancy_score,
            self.helpfulness_score,
        ]
        return sum(scores) / len(scores) if scores else 0.0


class EvaluationSummary(BaseModel):
    """
    Summary statistics for evaluation run.

    Used for report generation.
    """
    total_tests: int = Field(..., description="Total test cases run")
    passed_tests: int = Field(..., description="Number of passed tests")
    failed_tests: int = Field(..., description="Number of failed tests")
    pass_rate: float = Field(..., description="Pass rate as percentage")

    # Average metrics
    avg_faithfulness: float = Field(..., description="Average faithfulness score")
    avg_context_recall: float = Field(..., description="Average context recall score")
    avg_answer_relevancy: float = Field(..., description="Average answer relevancy score")
    avg_helpfulness: float = Field(..., description="Average helpfulness score")

    # Latency stats
    avg_latency_ms: float = Field(..., description="Average latency in ms")
    p95_latency_ms: float = Field(..., description="95th percentile latency in ms")
    min_latency_ms: float = Field(..., description="Minimum latency in ms")
    max_latency_ms: float = Field(..., description="Maximum latency in ms")

    # Breakdown by language
    english_pass_rate: float = Field(..., description="English queries pass rate")
    thai_pass_rate: float = Field(..., description="Thai queries pass rate")

    # Breakdown by category
    category_pass_rates: Dict[str, float] = Field(
        default_factory=dict,
        description="Pass rate by category",
    )

    # Timestamp
    evaluated_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Evaluation timestamp",
    )
