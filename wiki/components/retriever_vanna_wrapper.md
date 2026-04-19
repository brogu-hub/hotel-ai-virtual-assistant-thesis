---
type: component
path: "src/retrievers/structured_data/vaanaai/vaana_base.py"
parent_module: structured_retriever
status: active
language: python
purpose: "Vanna.AI wrapper adding PostgreSQL connectivity, SQL safety validation, dynamic DDL training, and NL-to-SQL query execution"
created: 2026-04-19
updated: 2026-04-19
tags: [component, retriever, vanna, nl-to-sql, postgresql, milvus, sql-safety]
---

# retriever_vanna_wrapper

`VannaWrapper` in `src/retrievers/structured_data/vaanaai/vaana_base.py`. Inherits from both `Milvus_VectorStore` (Vanna's Milvus training store) and `NvidiaLLM` (the LLM adapter). This is the core engine of [[structured_retriever]].

## Inheritance chain

```text
VannaWrapper
  ├─ Milvus_VectorStore   (vanna.milvus) — stores/retrieves training examples in Milvus
  └─ NvidiaLLM            (vaana_llm.py) — delegates to get_llm() from common; wraps submit_prompt()
       └─ VannaBase        (vanna.base)
```

`NVIDIAEmbeddingsWrapper` (`vaanaai/utils.py`) adapts LangChain embeddings to numpy arrays so Vanna's Milvus store can use them. It wraps `embed_query` and `embed_documents` from `get_embedding_model()`.

## Key methods

### `connect_to_postgres(host, dbname, user, password, port)`

Establishes a **read-only** psycopg2 connection. Sets `self.run_sql` to a closure that opens a fresh read-only connection per query and handles `InterfaceError` reconnection.

### `is_sql_valid(sql, customer_id) -> bool`

Two-stage safety check:

1. Parse with sqlparse — statement type must be `SELECT`.
2. Regex match — must find `WHERE … customer_id = <user_id>` with exactly one `customer_id` condition.

Returns `False` for any mutation statements, missing WHERE clause, or mismatched customer ID.

### `do_training(method)`

- `"schema"` — reads `static_db_schema` from `prompt.yaml`; used at startup for fast deterministic training.
- `"ddl"` — introspects live `information_schema.columns` for all public tables; used as fallback.

Training is skipped if `get_training_data()` is non-empty (idempotent).

### `ask_query(question, user_id) -> DataFrame | str`

Full NL-to-SQL execution:

```text
question + ", for user_id: {user_id}"
  → generate_sql()   (Vanna: training vector similarity + LLM call)
  → is_sql_valid()   (safety gate)
  → run_sql()        (psycopg2 read-only)
  → pd.DataFrame
```

Returns `"not valid sql"` sentinel string if validation fails.

## SQL generation detail

`NvidiaLLM.generate_sql()` calls `super().generate_sql()` (Vanna's base implementation), then strips escaped underscores (`\_` → `_`) which some LLMs emit.

`NvidiaLLM.submit_prompt()` calls `self.model.invoke(prompt)` where `self.model` is the LangChain LLM from `get_llm()` — meaning it transparently supports NVIDIA NIM (prod) or OpenRouter (dev) depending on configuration.

## Milvus dependency

`VannaWrapper.__init__` always initialises `MilvusClient` and passes it to `Milvus_VectorStore`. The structured retriever therefore requires [[Milvus]] regardless of the global `APP_VECTORSTORE_NAME` setting. This is a known gap — see [[structured_retriever]] for the contradiction callout.

## Related

- [[structured_retriever]] — parent module
- [[Vanna.AI]], [[Milvus]], [[PostgreSQL]]
- [[common]] — `get_llm()`, `get_embedding_model()`, `get_config()`
