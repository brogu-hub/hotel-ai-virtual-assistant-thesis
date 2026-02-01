# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
RAG Evaluation Package for Hotel AI Assistant

Uses DeepEval with OpenRouter (qwen/qwen3-max) as LLM judge
to evaluate the RAG pipeline quality.

Usage:
    # Generate golden dataset from hotel markdown files
    python -m scripts.eval.run_evaluation --generate-dataset

    # Run full evaluation
    python -m scripts.eval.run_evaluation

    # Custom settings
    python -m scripts.eval.run_evaluation \\
        --endpoint http://localhost:8081 \\
        --output results.html \\
        --threshold 0.7
"""

from .config import EvalConfig, get_config
from .models import (
    GoldenQAPair,
    GoldenDataset,
    EvaluationResult,
    EvaluationSummary,
    Language,
    Category,
    Difficulty,
)
from .golden_dataset import generate_golden_dataset, load_golden_dataset
from .metrics import OpenRouterJudge, create_metrics
from .evaluation import HotelRAGEvaluator, run_evaluation
from .report import generate_html_report, generate_json_report

__all__ = [
    # Config
    "EvalConfig",
    "get_config",
    # Models
    "GoldenQAPair",
    "GoldenDataset",
    "EvaluationResult",
    "EvaluationSummary",
    "Language",
    "Category",
    "Difficulty",
    # Dataset
    "generate_golden_dataset",
    "load_golden_dataset",
    # Metrics
    "OpenRouterJudge",
    "create_metrics",
    # Evaluation
    "HotelRAGEvaluator",
    "run_evaluation",
    # Report
    "generate_html_report",
    "generate_json_report",
]

__version__ = "1.0.0"
