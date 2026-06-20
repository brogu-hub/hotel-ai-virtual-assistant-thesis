# Archived: `src/ingest_service/` (NVIDIA blueprint)

This directory contains code from the original [NVIDIA AI Blueprint for AI Virtual Assistant](https://github.com/NVIDIA-AI-Blueprints/ai-virtual-assistant) that the Hotel AI Virtual Assistant thesis project forked from but does **NOT** actively use.

## Why preserved

1. **Attribution to upstream** — document/CSV ingestion is part of the NVIDIA reference architecture.
2. **Reproducibility** — preserved so anyone running the full NVIDIA stack can ingest gear-store CSVs and the original FAQ PDF.
3. **Thesis defense clarity** — clarifies that hotel ingestion runs through a dedicated thesis script, not the blueprint's microservice.

## What is still active (NOT archived)

Hotel knowledge ingestion is done via `scripts/ingest_hotel_knowledge.py` → `src/retrievers/hotel_knowledge/`. No standalone ingest microservice is deployed.

## Contents

| File | Original purpose |
|---|---|
| `Dockerfile` | Ingest service container build |
| `docker-compose.yaml` | Compose stack for the ingest microservice |
| `import_csv_to_sql.py` | CSV-to-Postgres importer for gear-store / orders data |
| `ingest_doc.py` | Document ingester into the Milvus vector store |
| `proxy_server.py` | HTTP proxy for ingestion endpoints |
| `requirements.txt` | Ingest service pip deps |
