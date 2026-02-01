# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Configuration for RAG Evaluation

Handles environment variables and default settings for the evaluation pipeline.

Environment Variables:
    OPENROUTER_API_KEY: OpenRouter API key (required)
    EVAL_ENDPOINT_URL: FastAPI endpoint URL (default: http://localhost:8081)
    DEEPEVAL_JUDGE_MODEL: LLM judge model (default: qwen/qwen3-max)
    EVAL_PASS_THRESHOLD: Metric pass threshold (default: 0.7)
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EvalConfig:
    """Configuration for RAG evaluation."""

    # Endpoint settings
    endpoint_url: str = field(
        default_factory=lambda: os.getenv("EVAL_ENDPOINT_URL", "http://localhost:8081")
    )

    # OpenRouter LLM Judge settings
    judge_model: str = field(
        default_factory=lambda: os.getenv("DEEPEVAL_JUDGE_MODEL", "qwen/qwen3-max")
    )
    openrouter_api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "")
    )
    openrouter_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
    )

    # Paths
    dataset_path: str = field(
        default_factory=lambda: os.getenv(
            "EVAL_DATASET_PATH", "scripts/eval/dataset.json"
        )
    )
    hotel_data_dir: str = field(
        default_factory=lambda: os.getenv("HOTEL_DATA_DIR", "data/hotel")
    )
    report_path: str = field(
        default_factory=lambda: os.getenv("EVAL_REPORT_PATH", "test_results.html")
    )

    # Thresholds
    pass_threshold: float = field(
        default_factory=lambda: float(os.getenv("EVAL_PASS_THRESHOLD", "0.7"))
    )

    # Request settings
    request_timeout: float = 60.0
    max_retries: int = 3

    # OpenRouter headers for Paid Tier compliance
    http_referer: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_REFERER", "https://siam-serenity-hotel.com"
        )
    )
    x_title: str = field(
        default_factory=lambda: os.getenv(
            "OPENROUTER_TITLE", "Hotel RAG Evaluation"
        )
    )

    def validate(self) -> bool:
        """
        Validate configuration.

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required. "
                "Set it with: export OPENROUTER_API_KEY=sk-or-v1-xxx"
            )

        if self.pass_threshold < 0 or self.pass_threshold > 1:
            raise ValueError(
                f"pass_threshold must be between 0 and 1, got {self.pass_threshold}"
            )

        return True

    def __post_init__(self):
        """Set OPENAI_API_KEY for DeepEval compatibility."""
        # DeepEval uses OPENAI_API_KEY internally for LLM calls
        # We set it to OpenRouter's key for compatibility
        if self.openrouter_api_key and not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = self.openrouter_api_key


def get_config(**overrides) -> EvalConfig:
    """
    Get evaluation configuration with optional overrides.

    Args:
        **overrides: Override specific config values

    Returns:
        EvalConfig instance
    """
    config = EvalConfig()

    for key, value in overrides.items():
        if hasattr(config, key) and value is not None:
            setattr(config, key, value)

    return config
