# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
PII Redactor — scrubs personally identifiable information before sending to LLM.

Detects and replaces: credit card numbers, Thai national IDs, passport numbers,
phone numbers. Email is context-aware (preserved for booking, redacted otherwise).

Usage:
    from src.hotel_guardrails.pii_redactor import redact_pii

    text, found = redact_pii("My card is 4111-1111-1111-1111")
    # text = "My card is [CREDIT_CARD]"
    # found = {"CREDIT_CARD": ["4111-1111-1111-1111"]}
"""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# Patterns ordered by specificity (most specific first to avoid partial matches)
PII_PATTERNS = {
    "CREDIT_CARD": re.compile(
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b"
    ),
    "THAI_NATIONAL_ID": re.compile(
        r"\b\d{1}-\d{4}-\d{5}-\d{2}-\d{1}\b"
    ),
    "PASSPORT": re.compile(
        r"\b[A-Z]{1,2}\d{6,9}\b"
    ),
    "PHONE_TH": re.compile(
        r"\b0[689]\d[-\s]?\d{3}[-\s]?\d{4}\b"
    ),
    "PHONE_INTL": re.compile(
        r"\b\+\d{1,3}[-\s]?\d{1,4}[-\s]?\d{3,4}[-\s]?\d{3,4}\b"
    ),
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
}


def redact_pii(
    text: str,
    preserve_email: bool = False,
) -> Tuple[str, Dict[str, List[str]]]:
    """
    Redact PII from text before sending to LLM.

    Args:
        text: Input text to scan
        preserve_email: If True, skip email redaction (needed for booking flow)

    Returns:
        Tuple of (redacted_text, found_pii_dict)
        found_pii_dict maps PII type to list of found values
    """
    found: Dict[str, List[str]] = {}
    redacted = text

    for pii_type, pattern in PII_PATTERNS.items():
        if pii_type == "EMAIL" and preserve_email:
            continue

        matches = pattern.findall(redacted)
        if matches:
            found[pii_type] = matches
            for match in matches:
                redacted = redacted.replace(match, f"[{pii_type}]")

    if found:
        logger.info(f"PII redacted: {', '.join(f'{k}({len(v)})' for k, v in found.items())}")

    return redacted, found


def check_output_pii(text: str) -> Tuple[bool, Dict[str, List[str]]]:
    """
    Check bot output for accidentally leaked PII.
    Returns (has_pii, found_dict). Never preserves email in output check.
    """
    _, found = redact_pii(text, preserve_email=False)
    return bool(found), found
