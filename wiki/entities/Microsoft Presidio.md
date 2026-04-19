---
type: entity
category: library
url: "https://github.com/microsoft/presidio"
tags: [entity, library, microsoft, privacy, PII, compliance, security]
created: 2026-04-19
updated: 2026-04-19
---

# Microsoft Presidio

## What it is

Microsoft Presidio is an open-source Python library for PII (Personally Identifiable Information) detection and anonymization. It uses NER models and regex patterns to identify sensitive data and replace it with placeholders before data leaves a secure perimeter.

## Role in this project

Presidio is recommended as the PII redaction layer for the hotel chatbot, to intercept guest passport numbers, credit card details, and other sensitive data before they are forwarded to cloud LLM APIs (OpenRouter, NVIDIA NIM). Required for GDPR and EU AI Act (2026) compliance.

## Key facts

- Replaces sensitive fields with placeholders: `[CREDIT_CARD]`, `[PASSPORT_NUMBER]`, etc.
- Works as a Python middleware layer inserted before any LLM API call
- Recommended in combination with a custom regex layer for hotel-specific PII patterns
- Satisfies PCI-DSS requirements for avoiding raw payment data in LLM calls
- Complements payment link generation (never process payments directly in chat)

## Related

- [[pii_redaction_and_compliance]]
- [[human_in_the_loop]]
- [[OpenRouter]]
- [[NVIDIA]]
