---
type: entity
category: library
url: https://vanna.ai
tags: [entity, library, text-to-sql, structured-data]
created: 2026-04-19
updated: 2026-04-19
---

# Vanna.AI

## What it is

Vanna.AI is an open-source Python library for natural-language-to-SQL query generation, using RAG over a schema and example query store.

## Role in this project

Vanna.AI powers the **structured data retriever** (`src/retrievers/structured_data/`) to translate natural-language user queries into SQL against the PostgreSQL database.

## Key facts

- Used in `src/retrievers/structured_data/`
- Works in tandem with [[PostgreSQL]] and the hotel database schema (`deploy/compose/init-scripts/init-hotel.sql`)
- Enables queries like "what rooms are available next weekend?" to be translated to SQL
- Port: 8087 (structured retriever service)

## Related

- [[retrievers]]
- [[PostgreSQL]]
- [[RAG]]
