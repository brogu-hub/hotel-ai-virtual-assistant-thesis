---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, post-processing, llm-quality, local-model, regex, novel-contribution]
date_ingested: 2026-04-20
---

# tool_call_post_processor — Tool-Call Leak Stripping

> [!note]
> Function-level view. For the concept-level write-up (why this exists, the three observed leak shapes, thesis framing) see [[concepts/tool_call_codeblock_leak]].

## Scope

`strip_tool_call_codeblocks(text)` at `src/hotel_guardrails/hotel_langgraph.py:1249`, plus three compiled regexes and `has_tool_leak(text)` at line 1202.

## Regexes

| Name | Purpose |
|---|---|
| `_TOOL_NAMES_RE` | Union of known hotel tool names — the gate that makes stripping tool-aware |
| `_FENCED_BLOCK_RE` | Matches triple-backtick fenced Markdown blocks |
| `_XML_TOOLCALL_RE` | Matches `<call_TOOL(...)>`, `<tool_call>…</tool_call>`, `<function=NAME>…</function>` |
| `_LEAK_PREAMBLE_RE` | Leading hand-off sentences ("I'll search our knowledge base…") that become orphaned after a leak is stripped |

## Algorithm

Three passes over the response text:

1. **Fenced block pass** — runs only if `"```"` in text. Replaces any fenced block whose body matches `_TOOL_NAMES_RE` with empty string. Preserves blocks that don't mention a real tool (legitimate code examples survive).
2. **XML tag pass** — runs if `"<call_"`, `"<tool_call"`, or `"<function="` is present. Same tool-name gate.
3. **Dangling truncation pass** — runs if `<call_\w{5,}` is present. Catches responses cut mid-leak by `max_tokens` — the regex accepts partial tool-name prefixes (5+ word characters after `<call_`) because the closing characters may be truncated.

After any pass modifies the text, a final cleanup:

- `_LEAK_PREAMBLE_RE.sub("", cleaned, count=1)` — removes a single leading hand-off sentence orphaned above blank space.
- `re.sub(r"\n{3,}", "\n\n", cleaned)` — collapses 3+ blank lines.
- `.strip()`.

If no pass fires, original text is returned unchanged (no allocation overhead on clean responses).

## Integration

Called inside `invoke_hotel_agent()` at line 1315:

```
response_text = last_ai_message.content
has_leak, sample = has_tool_leak(response_text)
if has_leak and retries_remaining:
    # re-invoke with same session; checkpointer provides history
else:
    response_text = strip_tool_call_codeblocks(response_text)
    return response_text
```

The retry-then-strip order is deliberate: retrying first gives the model a chance to produce a clean response (which is visually better than a stripped one); stripping is the safety net.

## Retry budget

- 2 retries for local backends (Ollama/Qwen3.5-Opus-9B)
- 1 retry for cloud backends (OpenRouter/Qwen3-max)

Reflects the higher leak rate on local inference while keeping cloud latency low. Counters (`had_leak`, `retries`) are returned in the response dict for observability.

## Why tool-name-aware

A blanket "strip all fenced blocks" regex would delete legitimate code snippets — a user asking about an API, or the LLM explaining Python. Gating on `_TOOL_NAMES_RE` reduces false-positive rate to near zero: a block is only stripped if it mentions an actual hotel tool (`search_hotel_knowledge`, `create_reservation`, etc.).

## Verification

No leaks reported across the 27-case [[memory-test-suite-2026-04-20]] on local Qwen3.5-Opus-9B — a useful secondary signal that the combined retry + strip strategy works for the memory-heavy workload.

## Related

- [[concepts/tool_call_codeblock_leak]] — the concept page (why, the three shapes, thesis framing)
- [[components/hotel_langgraph]] — hosts the function and the retry loop
- [[Qwen3.5-Opus-9B]], [[Ollama]] — the runtime that exhibits these leaks
- [[experiments/model-eval-local-vs-cloud-2026-04-06]]
- [[experiments/memory-test-suite-2026-04-20]]
