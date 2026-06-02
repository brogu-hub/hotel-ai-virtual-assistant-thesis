---
type: component
path: "src/hotel_guardrails/config.py"
status: active
parent_module: hotel_guardrails
tags: [component, configuration, settings, env-vars, pydantic-settings]
date_ingested: 2026-04-20
---

# config — Configuration & Runtime Settings

## Purpose

Single source of truth for all configurable values. Reads `APP_*` environment variables via Pydantic Settings, exposes typed accessors to the rest of the module, and provides a hot-reloadable `RuntimeLLMConfig` singleton so the LLM backend can be switched at runtime without restart.

## Setting classes

| Class | Purpose | Env prefix |
|---|---|---|
| `LLMSettings` (line 40) | Backend, model, temperature, max_tokens, OpenRouter/Ollama endpoints | `APP_LLM_` |
| `LangGraphSettings` (line 78) | Checkpointer / store selection, pool sizes, retry budget | `APP_LANGGRAPH_`, `APP_CHECKPOINTER_`, `APP_STORE_` |
| `RerankerSettings` (line 100) | Reranker model, threshold, disabled flag (see [[reranker_disabled]]) | `APP_RERANKER_` |
| `ServerSettings` (line 122) | Host, port, CORS, rate limits, stream connection caps | `APP_SERVER_` |

All use Pydantic v2 `BaseSettings`; unknown env vars are silently ignored. Missing required fields fail loudly at import time rather than first-use.

## Enums

- `LLMBackend` (line 34) — `OPENROUTER`, `OLLAMA`, `NVIDIA_AI_ENDPOINTS`.

## Cached accessors

| Function | Returns | Scope |
|---|---|---|
| `get_llm_settings()` (line 266) | `LLMSettings` | Process-wide, `@lru_cache` |
| `get_server_settings()` (line 271) | `ServerSettings` | Process-wide |
| `get_langgraph_settings()` (line 276) | `LangGraphSettings` | Process-wide |
| `get_reranker_settings()` (line 281) | `RerankerSettings` | Process-wide |

Cached so hot-path code can call them freely without re-parsing env.

## Model preset helpers

- `get_model_presets(model_id)` (line 219) — returns recommended temperature, max_tokens, and prompt style for known models (Qwen3-max, Qwen3.5-Opus-9B, Llama 3.3 70B, MiniMax-M2.7). Lets the sub-agents get model-appropriate defaults without hardcoding a table in each handler.
- `resolve_thinking_model(model_id, thinking_enabled)` (line 254) — maps a base model to its thinking-enabled variant when available (e.g., Qwen3-max → Qwen3-max:thinking).

## Runtime switchable config

`RuntimeLLMConfig` (line 340) wraps `LLMSettings` with runtime overrides accepted via the `/settings/llm` endpoint. Two modes:

- **Session-scoped** — override lives for a single `/chat` call via `config.configurable`.
- **Process-scoped** — override applied by an admin via `/settings/llm` PATCH; persists until restart.

`RateLimiter` (line 291) is a simple token-bucket used for `/settings/*` admin endpoints. (Chat rate limiting is in [[components/chat_scaling]].)

- `get_runtime_llm_config()` (line 502) — singleton accessor.

## Env variable surface

The complete `APP_*` surface is authoritative in `config.py`. The project CLAUDE.md env table is a curated subset. Key envs:

| Env var | Purpose | Default |
|---|---|---|
| `APP_LLM_MODELENGINE` | Backend switch | `openrouter` |
| `APP_LLM_MODELNAME` | Model ID | `qwen/qwen3-max` |
| `APP_LLM_MODEL_ID` | Alias | — |
| `APP_VECTORSTORE_NAME` | `qdrant` / `milvus` | `qdrant` |
| `APP_VECTORSTORE_URL` | Qdrant URL | — |
| `APP_CHECKPOINTER_NAME` | `postgres` / `memory` | `postgres` |
| `APP_STORE_NAME` | `postgres` / `memory` / `off` | `postgres` |
| `DATABASE_URL` | PostgreSQL URI (shared by both planes) | — |
| `APP_CACHE_URL` | Redis host:port | — |
| `OPENROUTER_API_KEY` | OpenRouter access | — |
| `NVIDIA_API_KEY` / `NGC_API_KEY` | NIM access | — |

## Thesis framing

Config is not just plumbing — it's the mechanism by which the same code ships to two fundamentally different deployment profiles (cloud [[Qwen3-max]] via OpenRouter, local [[Qwen3.5-Opus-9B]] via [[Ollama]]) without code changes. That the switch is a single env var (`APP_LLM_MODELENGINE`) is a direct consequence of the layered architecture described in [[thesis/hotel_ai_chatbot_chapter]] §4.2.

## Related

- [[modules/hotel_guardrails]]
- [[components/server]] — consumer
- [[components/hotel_langgraph]] — consumer
- [[components/openrouter_llm_wrapper]] — consumer
- [[modules/common]] — has its own `configuration_wizard` / `configclass` pattern this file mirrors
