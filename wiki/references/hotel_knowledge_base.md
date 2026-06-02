---
type: reference
status: active
date_ingested: 2026-04-20
sources:
  - data/hotel/
tags: [reference, knowledge-base, rag, hotel-data, bilingual, thai-english]
---

# Hotel Knowledge Base — Catalog

> [!note]
> This is the corpus indexed by the `search_hotel_knowledge` tool in [[components/actions]]. All 10 files are hand-written, bilingual (English + Thai), and intentionally small so retrieval quality can be reasoned about without scraping noise. Used by [[components/knowledge_subagent]].

## Location

`data/hotel/*.md` — 10 Markdown files, ~2,645 lines total. Chunked and embedded into a [[Qdrant]] collection at ingest time via [[ingest_service]].

## Hotel identity

**Canonical name: "The Grand Horizon Hotel" / "โรงแรม เดอะ แกรนด์ ฮอไรซัน"**. The naming drift across CLAUDE.md, the OpenAPI spec, and the KB Thai names was resolved on 2026-04-20 — see the entry in [[log]].

## Catalog

| Filename | Topic | Lines | Key contents |
|---|---|---|---|
| `dining_services.md` | Restaurants & bars | 70 | Breakfast (6:30–10:30, complimentary), Thai/Western/Japanese stations, bakery, beverages |
| `emergency_contacts.md` | Safety & emergencies | 125 | Fire, medical, security phone numbers; on-site first-aid; police/hospital routes |
| `facilities_amenities.md` | Hotel facilities | 137 | Pool hours, fitness center, business center, laundry, concierge desk |
| `hotel_faq.md` | Frequently asked questions | 43 | Check-in/out, WiFi password process, pet policy, currency exchange |
| `local_attractions.md` | Nearby things to do | 88 | Walking-distance sights, distances, typical visit duration |
| `policies_rules.md` | House rules & policies | 87 | Smoking, pets, quiet hours, cancellation, payment methods |
| `room_guide.md` | In-room guide | 158 | TV channels, AC, in-room dining, housekeeping schedule |
| `room_types.md` | Room types & prices | 101 | Standard (28sqm, 2,500 THB), Deluxe, Suite, Grand Suite |
| `spa_wellness.md` | Spa & wellness | 97 | Massage types, pricing, reservation process, operating hours |
| `transportation.md` | Airport & transfer | 141 | Airport shuttle, taxi fares, car rental partners, public transport tips |

## Bilingual structure

Every file follows the same pattern: English headline → English body → Thai translation block (กฎหรือรายละเอียดภาษาไทย). This dual-layer makes the corpus equally retrievable in both languages when the embedding model is multilingual (Qwen3 embeddings and sentence-transformers both are). The [[bilingual_memory_extraction]] concept uses the same language-parallel structure for the rule-based keyword tables.

## Rooms (canonical from `room_types.md`)

Four room types, all with complimentary breakfast, free WiFi, minibar, 24h room service, daily housekeeping:

| Type | Size | Price/night | Max guests | Beds |
|---|---|---|---|---|
| Standard | 28 sqm | 2,500 THB | 2 | 1 king OR 2 twin |
| Deluxe | (see file) | (see file) | (see file) | (see file) |
| Suite | (see file) | (see file) | (see file) | (see file) |
| Grand Suite | (see file) | (see file) | (see file) | (see file) |

> [!gap]
> The full Deluxe / Suite / Grand Suite specs are in `room_types.md` but not transcribed here to avoid duplicating the source. Refer to the file directly when building the thesis appendix; a future ingest should lift the full table.

## Retrieval profile

- **Embedding model** (dev): sentence-transformers multilingual.
- **Vector store**: Qdrant single collection `hotel_knowledge`.
- **Chunk strategy**: per-heading; each `##` heading becomes one chunk.
- **Reranker**: Qwen3-0.6B reranker in dev; NVIDIA reranker in prod — or disabled per [[reranker_disabled]].

## Thesis uses

- **Chapter 4 (System Design)** — [[thesis/hotel_ai_chatbot_chapter]] §4.4.3 and §4.5.3 describe how the KB plugs into the knowledge sub-agent.
- **Chapter 5 (Implementation)** — `search_hotel_knowledge` tool integration.
- **Chapter 6 (Evaluation)** — the eval cases in `scripts/test_4_subagents.py` (knowledge suite) draw expected answers from this corpus; see [[experiments/model-eval-local-vs-cloud-2026-04-06]].

## Related

- [[components/knowledge_subagent]] — consumer
- [[components/actions]] — `search_hotel_knowledge` tool definition
- [[modules/hotel_knowledge_retriever]] — retriever microservice
- [[flows/rag_ingest_pipeline]] — ingestion flow
- [[concepts/RAG]], [[concepts/hybrid_rag_with_reranking]]
- [[entities/Qdrant]]
