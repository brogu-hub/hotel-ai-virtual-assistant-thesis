---
type: concept
status: implemented
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/hotel_langgraph.py
tags: [concept, llm-quality, local-model, post-processing, qwen, lessons-learned]
---

# Tool-Call Codeblock Leak

> [!key-insight]
> Local 9B models sometimes emit their tool-call syntax as prose instead of as a structured tool call. The hotel assistant detects three distinct leak shapes and strips them with a tool-name-aware post-processor so the user never sees them.

## Background

When a sub-agent wants to call a tool, the framework expects a well-formed `AIMessage.tool_calls` payload. Frontier models (GPT-4, Claude, Gemini) produce this reliably. Local 9B models — in this project, Qwen3.5-Opus-9B via [[Ollama]] — occasionally "leak": they describe the tool call in plain text as if explaining what they are about to do, instead of actually making the structured call.

The user sees raw `search_hotel_knowledge(query="…")` syntax in the chat — both confusing and a trust-breaking defect for a production concierge.

## The Three Leak Shapes

The hotel assistant has logged three distinct leak shapes from the 9B backend:

### 1. Fenced Markdown Code Block

````
I'll search our knowledge base for breakfast hours.

```search_hotel_knowledge(query="breakfast hours")```

The breakfast service runs from …
````

### 2. Qwen / Hermes-Style XML Tag

```
I'll look that up for you.
<call_search_hotel_knowledge(query="breakfast hours")>
The breakfast service runs from …
```

### 3. Dangling Truncation

Response was cut off by `max_tokens` mid-leak, leaving an open tag with no closer:

```
I'll look that up for you.
<call_search_hotel_knowl
```

## The Post-Processor: `strip_tool_call_codeblocks()`

Located at `src/hotel_guardrails/hotel_langgraph.py:1249`. Three-pass strategy, tool-name-aware:

1. **Pass 1 — fenced code blocks.** Only strips blocks whose body matches `_TOOL_NAMES_RE` (a union of known hotel tool names). A user asking "what does `search_hotel_knowledge` do?" in a code block is preserved; a leaked call is removed.
2. **Pass 2 — XML-style tags.** Handles `<call_TOOL(...)>`, `<tool_call>…</tool_call>`, and `<function=TOOL>…</function>`. Same tool-name gate.
3. **Pass 3 — dangling truncations.** Catches `<call_\w{5,}` with no closing tag when `max_tokens` cut the response mid-leak. The 5-char minimum keeps false positives low — "`<call_me`" as natural English is extremely rare.

After any pass fires, a leading hand-off sentence ("I'll search our knowledge base for …") is trimmed if it now orphans above blank space, and 3+ blank lines are collapsed. This is handled by `_LEAK_PREAMBLE_RE` and a final `\n{3,}` collapse.

## Why Tool-Name-Aware Matters

A naive regex that strips every fenced block would destroy legitimate code snippets (e.g., a user asking about an API, or the LLM producing sample code as part of an explanation). The `_TOOL_NAMES_RE` gate ensures only blocks mentioning an actual hotel tool name get stripped — reducing false positives to near zero.

## Integration Point

`strip_tool_call_codeblocks()` runs inside `invoke_hotel_agent()`'s quality retry loop alongside `has_tool_leak()`:

1. Invoke graph → extract last `AIMessage` content.
2. `has_tool_leak(text)` — regex check for any remaining leak.
3. If leaked and retries remain → re-invoke (checkpointer provides history).
4. Else → apply `strip_tool_call_codeblocks()` as final cleanup.

The retry budget is 2 for Ollama 9B models and 1 for cloud OpenRouter models — acknowledging the higher leak rate on local inference.

## Lessons for the Thesis

- **Local models need safety nets.** Frontier-model patterns (tool-call reliability taken for granted) break down at the 7B–9B scale; productionising a local-inference system requires explicit defensive post-processing.
- **Observed-shape catalog beats generic regex.** Three distinct leak shapes were catalogued from real traffic; a fourth would be a new entry, not a regex redesign.
- **Name-awareness > aggression.** Stripping only blocks that mention real tool names preserves legitimate code-in-chat while still cleaning leaks.

## Related

- [[components/hotel_langgraph]] — hosts `strip_tool_call_codeblocks()` and the retry loop
- [[components/tool_call_post_processor]] — component-level documentation
- [[Qwen3.5-Opus-9B]] — the model that exhibits these leaks
- [[Ollama]] — the runtime
- [[experiments/model-eval-local-vs-cloud-2026-04-06]] — quality comparison where these leaks affect local scores
- [[concepts/keyword-match-eval]] — the eval harness where retries are counted
