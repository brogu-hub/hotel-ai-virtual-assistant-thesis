# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Custom LLM Judge and Metrics for RAG Evaluation

Uses OpenRouter (qwen/qwen3-max) as the LLM judge instead of OpenAI.
Provides DeepEval-compatible metrics for evaluating RAG responses.

Metrics:
- Faithfulness: Does the answer follow retrieved context?
- Context Recall: Did retrieval find the right documents?
- Answer Relevancy: Is the answer helpful to the user?
- Bilingual Helpfulness: Custom GEval for Thai/English responses
"""

import os
import logging
from typing import Optional, List, Any

from deepeval.models import DeepEvalBaseLLM
from deepeval.metrics import (
    FaithfulnessMetric,
    ContextualRecallMetric,
    AnswerRelevancyMetric,
    GEval,
)
from deepeval.test_case import LLMTestCaseParams

logger = logging.getLogger(__name__)


class OpenRouterJudge(DeepEvalBaseLLM):
    """
    Custom LLM judge using OpenRouter API for DeepEval metrics.

    Uses OpenAI-compatible API with qwen/qwen3-max model.
    Includes required headers for OpenRouter Paid Tier compliance.
    """

    def __init__(
        self,
        model_name: str = "qwen/qwen3-max",
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        temperature: float = 0.0,
        http_referer: str = "https://grand-horizon-hotel.com",
        x_title: str = "Hotel RAG Evaluation",
    ):
        """
        Initialize OpenRouter judge.

        Args:
            model_name: OpenRouter model to use
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env)
            base_url: OpenRouter API base URL
            temperature: LLM temperature (0.0 for deterministic evaluation)
            http_referer: HTTP-Referer header for OpenRouter
            x_title: X-Title header for OpenRouter
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url
        self.temperature = temperature
        self.http_referer = http_referer
        self.x_title = x_title
        self._client = None

        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required. "
                "Set it with: export OPENROUTER_API_KEY=sk-or-v1-xxx"
            )

    def _get_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers={
                    "HTTP-Referer": self.http_referer,
                    "X-Title": self.x_title,
                },
            )
        return self._client

    def load_model(self):
        """Load the model (required by DeepEval interface)."""
        return self._get_client()

    def generate(self, prompt: str, schema: Optional[Any] = None) -> str:
        """
        Generate response from OpenRouter.

        Args:
            prompt: The prompt to send to the LLM
            schema: Optional Pydantic schema for structured output

        Returns:
            LLM response text
        """
        client = self._get_client()

        try:
            messages = [{"role": "user", "content": prompt}]

            # Handle structured output if schema provided
            if schema is not None:
                # For structured output, add JSON instruction to prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {schema.model_json_schema()}"
                )
                messages = [{"role": "user", "content": json_prompt}]

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.temperature,
                max_tokens=2048,
            )

            content = response.choices[0].message.content

            # If schema provided, validate and parse
            if schema is not None:
                import json

                # Try to extract JSON from response
                try:
                    # Handle markdown code blocks
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()

                    parsed = json.loads(content)
                    return schema(**parsed)
                except Exception as e:
                    logger.warning(f"Failed to parse structured output: {e}")
                    return content

            return content

        except Exception as e:
            logger.error(f"OpenRouter generation failed: {e}")
            raise

    async def a_generate(self, prompt: str, schema: Optional[Any] = None) -> str:
        """
        Async generate response from OpenRouter.

        Args:
            prompt: The prompt to send to the LLM
            schema: Optional Pydantic schema for structured output

        Returns:
            LLM response text
        """
        # Use sync version for now (OpenRouter supports async but simpler this way)
        return self.generate(prompt, schema)

    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model_name


def create_metrics(
    judge: OpenRouterJudge,
    pass_threshold: float = 0.7,
) -> tuple:
    """
    Create DeepEval metrics using OpenRouter as judge.

    Args:
        judge: OpenRouterJudge instance
        pass_threshold: Minimum score to pass (0.0 to 1.0)

    Returns:
        Tuple of (faithfulness, context_recall, answer_relevancy, bilingual_helpfulness)
    """
    # Faithfulness: Does the answer strictly follow retrieved context?
    faithfulness = FaithfulnessMetric(
        model=judge,
        threshold=pass_threshold,
        include_reason=True,
    )

    # Context Recall: Did retrieval find the right documents?
    context_recall = ContextualRecallMetric(
        model=judge,
        threshold=pass_threshold,
        include_reason=True,
    )

    # Answer Relevancy: Is the answer helpful to the user?
    answer_relevancy = AnswerRelevancyMetric(
        model=judge,
        threshold=pass_threshold,
        include_reason=True,
    )

    # Custom GEval for bilingual helpfulness
    bilingual_helpfulness = GEval(
        name="Bilingual Helpfulness",
        criteria="""
Evaluate if the hotel AI assistant's response is helpful for a guest.

Consider the following criteria:
1. **Accuracy**: Does the response contain correct information from the hotel knowledge base?
2. **Completeness**: Does it include all relevant details (times, prices, locations, procedures)?
3. **Language Appropriateness**: Is the response in the same language as the question (Thai or English)?
4. **Professionalism**: Is the tone polite and professional as expected from a hotel concierge?
5. **Actionability**: Can the guest take action based on this information?

Scoring:
- 0.0-0.3: Response is unhelpful, incorrect, or in wrong language
- 0.4-0.6: Response is partially helpful but missing key details
- 0.7-0.8: Response is helpful with minor issues
- 0.9-1.0: Response is excellent, complete, and perfectly appropriate
        """,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        model=judge,
        threshold=pass_threshold,
    )

    return faithfulness, context_recall, answer_relevancy, bilingual_helpfulness


def create_keyword_checker(expected_keywords: List[str]) -> callable:
    """
    Create a simple keyword checker for quick validation.

    Args:
        expected_keywords: List of keywords that should appear in response

    Returns:
        Function that checks if keywords are present
    """

    def check_keywords(response: str) -> tuple:
        """
        Check if expected keywords are present in response.

        Uses flexible matching to handle common variations:
        - Case insensitive
        - Hyphens/spaces interchangeable
        - Ordinals with or without suffix (5th = 5)

        Returns:
            Tuple of (score, found_keywords, missing_keywords)
        """
        import re

        def normalize(text: str) -> str:
            """Normalize text for flexible matching."""
            text = text.lower()
            # Replace hyphens with spaces
            text = text.replace("-", " ")
            # Remove ordinal suffixes for numbers (1st, 2nd, 3rd, 4th, 5th)
            text = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1', text)
            return text

        response_normalized = normalize(response)
        found = []
        missing = []

        for keyword in expected_keywords:
            keyword_normalized = normalize(keyword)
            if keyword_normalized in response_normalized:
                found.append(keyword)
            else:
                missing.append(keyword)

        # Score is percentage of keywords found
        score = len(found) / len(expected_keywords) if expected_keywords else 1.0

        return score, found, missing

    return check_keywords


class SimpleKeywordMetric:
    """
    Simple keyword-based metric for quick validation.

    Faster than LLM-based metrics, useful for pre-filtering.
    """

    def __init__(self, threshold: float = 0.5):
        """
        Initialize keyword metric.

        Args:
            threshold: Minimum percentage of keywords required to pass
        """
        self.threshold = threshold
        self.name = "Keyword Coverage"

    def evaluate(
        self,
        actual_output: str,
        expected_keywords: List[str],
    ) -> dict:
        """
        Evaluate keyword coverage in response.

        Args:
            actual_output: The AI's response
            expected_keywords: Keywords that should appear

        Returns:
            Dictionary with score, passed, and details
        """
        checker = create_keyword_checker(expected_keywords)
        score, found, missing = checker(actual_output)

        return {
            "name": self.name,
            "score": score,
            "passed": score >= self.threshold,
            "found_keywords": found,
            "missing_keywords": missing,
            "reason": (
                f"Found {len(found)}/{len(expected_keywords)} keywords. "
                f"Missing: {missing}" if missing else "All keywords found."
            ),
        }


if __name__ == "__main__":
    # Test the OpenRouter judge
    logging.basicConfig(level=logging.INFO)

    print("Testing OpenRouter Judge...")

    try:
        judge = OpenRouterJudge()
        response = judge.generate("What is 2 + 2? Reply with just the number.")
        print(f"Test response: {response}")
        print("OpenRouter Judge initialized successfully!")
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set OPENROUTER_API_KEY environment variable.")
