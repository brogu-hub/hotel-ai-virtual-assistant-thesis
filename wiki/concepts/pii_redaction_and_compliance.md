---
type: concept
status: developing
related:
  - concepts/human_in_the_loop
  - entities/microsoft_presidio
tags: [concept, privacy, compliance, GDPR, PII, EU-AI-Act, security]
created: 2026-04-19
updated: 2026-04-19
---

# PII Redaction and Compliance

## Definition

PII (Personally Identifiable Information) redaction is the process of intercepting sensitive guest data — passport numbers, credit card numbers, names — and replacing them with placeholders (e.g., `[CREDIT_CARD]`) **before** the data is forwarded to a cloud LLM provider. This is a legal and ethical requirement when handling hotel guest data.

## Regulatory context

- **GDPR:** EU data protection regulation applying to any system that handles EU guest data.
- **PCI-DSS:** Payment card industry standard — payment data must never be processed raw through LLM APIs.
- **EU AI Act (enforced 2026):** AI systems used in "essential services" (travel/housing classified here) fall under specific risk tiers. Organizations must maintain an **AI System Inventory** and document risk mitigation measures.

## Implementation approach

1. Intercept all messages before LLM API call
2. Apply a PII detection layer (regex + ML-based NER)
3. Replace sensitive fields with placeholders
4. Forward sanitized prompt to the LLM
5. Never process payments directly in chat — generate a **Secure Payment Link** or call a PCI-compliant gateway via function call

**Recommended tools:** Microsoft Presidio, custom regex Python layer

## Variants & related concepts

- [[concepts/human_in_the_loop]] — escalation protocols also reduce accidental PII exposure
- [[entities/microsoft_presidio]] — recommended open-source PII redaction tool

## How it shows up in this project

The `hotel_guardrails` NeMo Guardrails config (`src/hotel_guardrails/config/`) includes input/output rails that can be configured for PII filtering. Whether a dedicated Presidio integration exists in the codebase is a gap to verify.

> [!gap] Verify whether `src/hotel_guardrails/` includes an actual Presidio or regex-based PII scrubbing layer, or if this is a future compliance requirement.

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[entities/microsoft_presidio]]
- [[papers/eu_ai_act_2026]]

## Open questions

- Does the thesis chapter on compliance address EU AI Act risk-tier classification?
- Is there a PII test in the evaluation suite (`scripts/eval/`)?
