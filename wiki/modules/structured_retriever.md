---
type: module
path: "src/retrievers/structured_data/"
status: active
language: python
purpose: "NL-to-SQL retriever — translates natural language questions into validated SQL and executes against PostgreSQL via Vanna.AI"
maintainer: Mangakorian
created: 2026-04-19
updated: 2026-04-19
port: 8087
depends_on: [common, retrievers, Vanna.AI, PostgreSQL, Milvus]
used_by: [agent]
tags: [module, retriever, structured-data, nl-to-sql, vanna, postgresql]
---

# structured_retriever

Sub-service of [[retrievers]]. Translates natural language questions into SQL, executes them against [[PostgreSQL]], and returns results as text. Runs on **port 8087**.

## Responsibility

- Accept a natural language question and a `user_id`.
- Generate a SQL query using [[Vanna.AI]]'s LLM + vector-similarity training mechanism.
- Validate the generated SQL (SELECT-only, must filter on `customer_id = user_id`).
- Execute the query and return results as a stringified pandas DataFrame.

> [!note] Ingest not supported
> `CSVChatbot.ingest_docs()` raises `NotImplementedError`. Data enters PostgreSQL via the separate [[ingest_service]] (CSV-to-SQL import), not via the `/documents` endpoint.

## Key classes

| Class | File | Role |
| --- | --- | --- |
| `CSVChatbot` | `structured_data/chains.py` | `BaseExample` impl, orchestrates VannaWrapper |
| `VannaWrapper` | `vaanaai/vaana_base.py` | Vanna + Milvus store + NvidiaLLM; SQL safety checks |
| `NvidiaLLM` | `vaanaai/vaana_llm.py` | Vanna `VannaBase` LLM adapter wrapping `get_llm()` |
| `NVIDIAEmbeddingsWrapper` | `vaanaai/utils.py` | Converts LangChain embeddings to numpy arrays for Vanna |

See [[retriever_vanna_wrapper]] for detail on `VannaWrapper`.

## Search pipeline

```text
POST /search {query, user_id}
  → CSVChatbot.document_search()
       → vaana_client.ask_query(question, user_id)
            → generate_sql()          # Vanna: vector-search training data + LLM
            → is_sql_valid()          # SELECT-only + WHERE customer_id = user_id
            → run_sql()               # psycopg2 read-only connection
            → return DataFrame as str
```

`user_id` is **mandatory** — the method returns an early error string if absent. This enforces row-level data isolation: every generated SQL must contain `WHERE customer_id = <user_id>`.

## SQL safety guardrails

`VannaWrapper.is_sql_valid()` enforces two rules:

1. The statement type must be `SELECT` (via sqlparse).
2. The WHERE clause must contain exactly one `customer_id = <user_id>` condition (via regex).

Any query failing these checks returns the sentinel string `"not valid sql"`, causing `document_search` to raise an exception upstream.

## Training mechanism

[[Vanna.AI]] uses in-context training stored in [[Milvus]]:

- **`do_training(method="schema")`** — called at startup. Loads the static `CREATE TABLE` DDL from `prompt.yaml` (`static_db_schema` key) and trains Vanna if the training collection is empty.
- **`do_training(method="ddl")`** — called on each search. Introspects live PostgreSQL `information_schema` and trains if empty (fallback).

The static schema covers the `customer_data` table (orders, returns data from the original NVIDIA Blueprint).

## Schema (static)

```sql
CREATE TABLE customer_data (
  customer_id INTEGER, order_id INTEGER, product_name VARCHAR,
  order_amount NUMERIC, order_date DATE, order_status VARCHAR,
  return_status VARCHAR, return_reason VARCHAR, ...
);
```

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `DATABASE_URL` | — | PostgreSQL connection (parsed to host/port) |
| `POSTGRES_DB` | `customer_data` | Database name |
| `POSTGRES_USER` | `postgres_readonly` | DB user (read-only) |
| `POSTGRES_PASSWORD` | `readonly_password` | DB password |
| `APP_VECTORSTORE_NAME` | `milvus` | Must be `milvus` for VannaWrapper |
| `APP_VECTORSTORE_URL` | — | Milvus URI for Vanna training store |

> [!contradiction]
> `VannaWrapper.__init__` hard-codes a check for `settings.vector_store.name == "milvus"` and only sets `milvus_db_url` in that branch, but `CLAUDE.md` lists [[Qdrant]] as the dev vector store. The structured retriever cannot run in dev mode without Milvus available or a code change to handle Qdrant.

## Related

- [[retrievers]] — parent module
- [[retriever_base_example]] — interface contract
- [[retriever_vanna_wrapper]] — component detail
- [[Vanna.AI]], [[PostgreSQL]], [[Milvus]]
- [[ingest_service]] — populates the `customer_data` table
- [[RAG]]
