# Chapter 1: Introduction

## 1.1 Background and Motivation

The global hospitality industry serves over 1.4 billion international tourist arrivals annually, with Thailand ranking among the top ten most visited countries worldwide. As hotels compete for guest satisfaction, the quality and speed of customer service have become critical differentiators. Traditional front-desk operations rely on human staff working in shifts, creating bottlenecks during peak hours and leaving guests without support during late-night periods.

Artificial intelligence has begun to transform hospitality operations. Buhalis and Moldavska (2022) demonstrated that voice and text-based AI assistants can handle routine guest inquiries — from breakfast hours to WiFi passwords — with response times measured in seconds rather than minutes. Buhalis, O'Connor, and Leung (2023) further argued that "smart hospitality" ecosystems, where AI agents integrate with property management systems (PMS), represent the next evolution in hotel technology.

However, most deployed hotel chatbots remain **rule-based** or **FAQ-retrieval** systems with rigid decision trees. They cannot handle natural language variations, multi-step booking workflows, or bilingual conversations. A guest asking *"มีห้องว่างวันจันทร์หน้าไหม"* (Is there a room available next Monday?) receives no useful response from a keyword-matching system.

Recent advances in **Large Language Models (LLMs)** and **agentic AI frameworks** make it possible to build chatbots that understand natural language, reason about multi-step tasks, retrieve factual information from knowledge bases, and interact with databases — all while maintaining context across a conversation. This thesis explores this opportunity by building a production-grade AI virtual assistant for a luxury hotel.

## 1.2 Problem Statement

Existing hotel chatbot solutions face three core limitations:

1. **Rigid intent classification** — Rule-based systems fail on paraphrased or bilingual queries. A guest saying "I'd like to cancel" and "ยกเลิกการจอง" must both route to the cancellation handler.
2. **No database integration** — Most chatbots answer from static FAQ documents but cannot check room availability, create reservations, or modify bookings in real time.
3. **No scalability consideration** — Single-threaded chatbot deployments cannot serve multiple concurrent guests, and lack security measures (authentication, audit logging) required for hotel staff operations.

## 1.3 Objectives

This thesis aims to design, implement, and evaluate a hotel AI virtual assistant that addresses these limitations:

1. **Design a multi-agent AI system** using LangGraph state machines to route guest requests to specialized sub-agents (booking, service, knowledge, general conversation).
2. **Implement Retrieval-Augmented Generation (RAG)** over a hotel knowledge base using vector embeddings and Qdrant, enabling accurate answers about facilities, policies, and services.
3. **Build a production-grade full-stack system** with FastAPI backend, Next.js frontend, JWT authentication, admin dashboard, audit logging, and Docker deployment.
4. **Compare local and cloud LLM performance** by evaluating a 9-billion-parameter local model (Qwen3.5 Opus 9B on Ollama) against a cloud-hosted flagship model (Qwen3 Max on OpenRouter) across 25 hotel-domain test cases.

## 1.4 Scope and Limitations

**In scope:**
- Bilingual Thai and English conversation
- Four specialized sub-agents: booking operations, hotel services, knowledge retrieval, and general conversation
- Room availability checking, reservation CRUD, check-in/check-out workflows
- RAG over 10 hotel knowledge documents (dining, spa, policies, facilities, FAQ)
- JWT authentication with user and admin roles
- Admin dashboard for session monitoring, chat intervention, and audit logging
- Concurrent-user scaling with LLM semaphore, session locks, and knowledge caching
- Runtime switching between local Ollama and cloud OpenRouter LLM backends
- Automated evaluation with 25 test cases and 193 infrastructure tests

**Out of scope:**
- Real payment gateway integration (mock payment links only)
- Voice interaction (text-only)
- Multi-property support (single hotel)
- Production deployment under real guest traffic

## 1.5 Expected Contributions

1. A reproducible reference architecture for building hotel AI assistants using LangGraph and RAG
2. Empirical comparison of local 9B vs. cloud LLM for hotel-domain tasks (accuracy, latency, cost)
3. A set of scaling primitives (LLM concurrency limiter, session lock manager, knowledge cache) applicable to any LLM-backed service
4. Complete test suite (193 infrastructure tests + 25 model evaluation cases) as a benchmark for future hotel chatbot research

## 1.6 Thesis Organization

| Chapter | Title | Content |
|---------|-------|---------|
| 1 | Introduction | Background, objectives, scope |
| 2 | Literature Review | AI in hospitality, LLMs, LangGraph, RAG, web technologies |
| 3 | System Design | Architecture, agent design, database, RAG pipeline, auth, deployment |
| 4 | Implementation | Code-level details of backend, frontend, security, scaling |
| 5 | Testing and Evaluation | Model comparison, infrastructure tests, performance benchmarks |
| 6 | Discussion | Trade-offs, limitations, architectural decisions |
| 7 | Conclusion | Contributions summary and future work |
| A | Appendix: Test Results | Full evaluation data, Gantt timeline, repository structure |
| B | Appendix: User Manual | Installation, configuration, usage guide |

[Figure 1.1: System context diagram — guest interacts with the chatbot on the hotel website; the chatbot connects to LangGraph agent, PostgreSQL database, Qdrant vector store, and Ollama/OpenRouter LLM backends. Hotel staff access the admin dashboard for monitoring and intervention.]
