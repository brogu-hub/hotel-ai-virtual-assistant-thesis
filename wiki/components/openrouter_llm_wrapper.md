---
type: component
path: "src/hotel_guardrails/openrouter_llm.py"
status: active
parent_module: hotel_guardrails
tags: [component, llm, openrouter, ollama, wrapper]
created: 2026-04-19
updated: 2026-04-19
---

# openrouter_llm_wrapper — LLM Factory

## Purpose

Thin factory function that creates a `ChatOpenAI` instance pointing at either [[OpenRouter]] or a local Ollama endpoint, based on the active `RuntimeLLMConfig` singleton. Provides a single call-site abstraction so the rest of the codebase does not need to know which backend is active.

## Function: `get_openrouter_llm()`

**Module:** `src/hotel_guardrails/openrouter_llm.py`

**Signature:**

```
get_openrouter_llm(
    model: str = "qwen/qwen3-max",
    temperature: float = 0.3,
    max_tokens: int = 1024,
    streaming: bool = True,
) -> ChatOpenAI
```

**Logic:**

1. Read `RuntimeLLMConfig.backend`.
2. If `LLMBackend.OLLAMA` → return `ChatOpenAI` with `openai_api_base=ollama_base_url` and dummy key `"sk-ollama-not-needed"`. Model name comes from `runtime_config.ollama_model`.
3. If `LLMBackend.OPENROUTER` → return `ChatOpenAI` with `openai_api_base="https://openrouter.ai/api/v1"`, real API key from env, and HTTP headers `HTTP-Referer` + `X-Title`.

## Relationship to `get_llm()` in `hotel_langgraph.py`

`hotel_langgraph.py` has its own `get_llm()` function which is the one actually called by sub-agent nodes. That function has additional logic for:

- OpenRouter rate-limiter (`runtime_config.rate_limiter.wait_and_acquire()`)
- `reasoning` body param for thinking models (`runtime_config.thinking`)
- Per-call temperature/max_tokens from `config.configurable.llm_settings`

`get_openrouter_llm()` in `openrouter_llm.py` is used by `server.py` as the fallback LLM (for non-graph paths) and is the simpler of the two factories.

## Available Models Catalog

Defined in `config.py` as `AVAILABLE_MODELS` list. Each entry has:

- `id` — model string passed to `ChatOpenAI`
- `backend` — `"ollama"` or `"openrouter"`
- `presets` — `temperature`, `max_tokens`, `thinking` (bool), `max_retries`

Notable models:

| ID | Notes |
|---|---|
| `fredrezones55/qwen3.5-opus:9b` | Local Ollama, 9B, max_retries=2 (flaky) |
| `qwen/qwen3-max` | Cloud, primary dev model |
| `qwen/qwen3-max-thinking` | Extended reasoning, temp=0.1 |
| `qwen/qwen3.5-397b-a17b` | MoE 397B (17B active), latest |
| `minimax/minimax-m2.7` | Budget option, strong agentic |

## Related

- [[entities/OpenRouter]]
- [[entities/Qwen3-max]]
- [[components/hotel_langgraph]] — uses the more complete `get_llm()` variant
- [[modules/hotel_guardrails]]
