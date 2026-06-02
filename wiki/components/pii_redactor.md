---
type: component
status: active
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/pii_redactor.py
related:
  - concepts/pii_redaction_and_compliance
  - entities/Microsoft Presidio
  - modules/hotel_guardrails
tags: [component, pii, privacy, compliance, regex, redaction]
---

# Component: pii_redactor.py

## Purpose

`pii_redactor.py` is a lightweight regex-based PII scrubber that intercepts user messages **before** they are forwarded to a cloud LLM API. It replaces detected sensitive values with bracketed placeholder tokens such as `[CREDIT_CARD]` or `[PASSPORT]`, returning both the sanitized text and a dict of what was found. A second function, `check_output_pii()`, can be applied to bot responses to detect accidentally leaked PII.

This component resolves the gap noted in [[concepts/pii_redaction_and_compliance]]: a real PII scrubbing layer does exist in the codebase, implemented with pure regex rather than [[Microsoft Presidio]].

> [!key-insight] Regex-only, no Presidio
> Despite the concept page recommending Microsoft Presidio, the actual implementation uses six compiled `re` patterns with no ML-backed NER. This is faster and has no external dependency, but misses contextual PII — for example, a guest's full name embedded in a sentence would not be detected.

## PII types detected

| Type | Pattern | Example match |
|---|---|---|
| `CREDIT_CARD` | 16-digit groups with optional spaces/dashes | `4111-1111-1111-1111` |
| `THAI_NATIONAL_ID` | Thai ID format `D-DDDD-DDDDD-DD-D` | `1-2345-67890-12-3` |
| `PASSPORT` | 1–2 uppercase letters followed by 6–9 digits | `A1234567` |
| `PHONE_TH` | Thai mobile format starting with `06`, `08`, or `09` | `081-234-5678` |
| `PHONE_INTL` | International E.164-style numbers | `+44 20 7946 0958` |
| `EMAIL` | Standard email pattern | `guest@example.com` |

Patterns are applied in the order they appear in `PII_PATTERNS` (an ordered dict): credit card, Thai national ID, passport, Thai phone, international phone, email.

> [!gap] Pattern ordering risks
> The PASSPORT pattern `\b[A-Z]{1,2}\d{6,9}\b` is broad and could match things like product codes, room identifiers, or model names (e.g., `M1234567`). No false-positive suppression or allowlist is implemented. In a production setting this could silently redact non-PII values in messages.

## `redact_pii()` — main function

```python
def redact_pii(
    text: str,
    preserve_email: bool = False,
) -> Tuple[str, Dict[str, List[str]]]:
```

The `preserve_email` flag exists specifically for the booking flow, where the guest's email address must be passed to the LLM to create a reservation. When `preserve_email=True`, the EMAIL pattern is skipped. This is a context-aware redaction decision rather than blanket PII removal.

> [!note] Context-aware email handling
> Email redaction is skipped in the booking sub-agent path (`preserve_email=True`) because the LLM needs the email to fill the booking form. In all other sub-agents and in output checks, email is always redacted. This is the right tradeoff for functionality vs. compliance, but it means guest email addresses reach the cloud LLM during booking flows.

The function iterates over all found matches per type and performs a string `replace()` — it does not use regex substitution per match. If the same PII string appears multiple times in the text, all occurrences are replaced. However, because `replace()` is string-literal rather than regex-based for the replacement step, there is no risk of replacement string injection.

After redaction, if any PII was found, a single `logger.info()` line summarizes the types and counts: e.g., `"PII redacted: CREDIT_CARD(1), PHONE_TH(2)"`.

## `check_output_pii()` — output guard

```python
def check_output_pii(text: str) -> Tuple[bool, Dict[str, List[str]]]:
```

Delegates to `redact_pii(text, preserve_email=False)` and returns `(has_pii, found_dict)`. This function is intended to be applied to bot responses before they are sent to the guest, acting as an output rail catching accidentally leaked PII. Whether `server.py` actually calls this on every response is an integration concern — the function exists and is ready, but its wiring in the request pipeline is not guaranteed.

> [!gap] Output PII check wiring uncertain
> `check_output_pii()` is defined but this component page cannot confirm from `pii_redactor.py` alone that it is called on every LLM output path. Integration verification against `server.py` and `hotel_langgraph.py` is needed to confirm the output guard is active.

## Pipeline position

According to the `hotel_guardrails.md` module page: "PII scrubbing happens inside `/chat` before the message reaches LangGraph." This positions `redact_pii()` at the server layer, before the message enters the LangGraph state machine, protecting all four sub-agent paths with a single interception point.

## What is NOT detected

- Guest full names (no NER)
- Room numbers used as identifiers
- Booking reference numbers (unless they match the passport pattern by coincidence)
- Date-of-birth in common formats
- Physical address strings

> [!gap] No name redaction
> Hotel guests routinely include their names in chat messages. No name-detection pattern exists. Names entering the LLM are processed in plaintext. For GDPR compliance, name detection (likely requiring an NER model or Presidio's `PERSON` recognizer) would be needed.

## Related

- [[concepts/pii_redaction_and_compliance]] — regulatory context (GDPR, PCI-DSS, EU AI Act, Thai PDPA)
- [[entities/Microsoft Presidio]] — recommended tool that was not adopted; see gap above
- [[components/audit]] — audit records that may inadvertently contain PII in `details` JSONB
- [[modules/hotel_guardrails]] — where `redact_pii()` is called in the request pipeline
