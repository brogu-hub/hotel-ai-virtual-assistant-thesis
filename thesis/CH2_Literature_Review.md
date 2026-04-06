# Chapter 2: Literature Review

## 2.1 Artificial Intelligence in the Hospitality Industry

### 2.1.1 Property Management Systems and Digital Transformation

Hotel Property Management Systems (PMS) form the operational backbone of modern hotels, managing reservations, room status, guest profiles, billing, and housekeeping. Oracle OPERA, the market-leading PMS, defines a canonical room status lifecycle: *Vacant Clean → Occupied → Vacant Dirty → Cleaning → Inspected → Vacant Clean* (Oracle, 2023). This lifecycle, documented across industry resources (SetupMyHotel, 2023; Cloudbeds, 2023), is the foundation for the room status state machine implemented in this project.

Academic research on hotel management systems (Atlantis Press, ICETIS '13; JETIR, 2023) has established the core functional requirements: reservation management, guest registration, check-in/check-out, and billing. The AltexSoft (2023) comprehensive guide and DDI Development (2023) analysis further detail how modern PMS platforms are evolving from on-premise monoliths to cloud-based microservices — a transition this thesis mirrors by implementing the hotel backend as a microservice architecture.

### 2.1.2 AI Chatbots in Hotels: From Rule-Based to Generative

The evolution of chatbots in hospitality can be categorized into four generations:

[Figure 2.1: Chatbot generation taxonomy — (1) Rule-based: keyword matching and decision trees; (2) Retrieval-based: FAQ lookup with intent classification; (3) Generative: LLM-powered free-form responses; (4) Agentic: multi-agent systems with tool calling, memory, and database integration. This project implements Generation 4.]

A comprehensive bibliometric analysis of 398 chatbot papers from 2003–2023 (Taylor & Francis, 2025) reveals that research shifted dramatically toward generative AI after 2022. A subsequent review of 71 articles on conversational AI in hospitality (Taylor & Francis, 2026) confirms that LLM-based systems are now the dominant research direction, replacing the intent-classification paradigm that characterized the 2018–2022 period.

**Buhalis and Moldavska (2022)** conducted the canonical study on AI assistants in hospitality, demonstrating that voice and text assistants can handle routine guest inquiries with high satisfaction scores. They identified key requirements: **natural language understanding**, **context retention across turns**, and **integration with hotel operational systems**. Buhalis, O'Connor, and Leung (2023) extended this to propose "smart hospitality ecosystems" where AI agents interact with PMS, housekeeping, and revenue management systems in real time — precisely the architecture this thesis implements.

Experimental studies further validate the approach: research on AI in the hotel booking process (MDPI Tourism & Hospitality, 2023) found that chatbot-assisted booking increased conversion rates, while studies on personalizing guest experience with generative AI (Taylor & Francis, 2024) demonstrated that LLM-powered concierges can dynamically adapt responses based on guest preferences and context.

## 2.2 Large Language Models

### 2.2.1 Transformer Architecture and Instruction Tuning

The Transformer architecture (Vaswani et al., 2017) introduced the self-attention mechanism that enables models to process sequences in parallel rather than sequentially. Modern LLMs build on this foundation with instruction tuning — fine-tuning on human-curated instruction–response pairs — which transforms a raw language model into a helpful assistant. The Qwen model family used in this project employs dense Transformer architectures with Rotary Position Embeddings (RoPE) for extended context handling.

### 2.2.2 Small vs. Large Models

A central question in deploying LLM-based systems is the trade-off between model size and capability. This thesis directly compares:

- **Qwen3.5 Opus 9B** — a 9-billion-parameter dense model running locally on a single GPU (NVIDIA RTX 5080, 16 GB VRAM). Quantized to Q5_K_M (6.5 GB) for deployment.
- **Qwen3 Max** — a cloud-hosted flagship model with significantly more parameters, accessed via the OpenRouter API.

The 9B model represents the practical ceiling for single-GPU local deployment in a hotel setting (no cloud dependency, no per-query API cost, data stays on-premise). The cloud model represents unconstrained capability at the cost of latency, cost, and data privacy.

### 2.2.3 Thinking Models and Reasoning

Recent LLMs incorporate explicit "thinking" or "chain-of-thought" mechanisms where the model generates internal reasoning tokens (enclosed in `<think>` tags) before producing the final response. Qwen3.5 models emit these tokens natively. This thesis evaluates the impact of this reasoning capability on hotel task accuracy and finds that disabling explicit thinking mode on the 9B local model (which already reasons natively) reduces latency without measurable accuracy loss (Section 5.4).

## 2.3 Agentic AI and Orchestration

### 2.3.1 LangGraph State Machines

LangGraph, an extension of the LangChain ecosystem, provides a framework for building **stateful, multi-step AI agents** as directed graphs. Each node represents an agent action (LLM call, tool execution, routing decision), and edges define the flow between actions with conditional branching.

**Liu et al. (2024)** presented the most citable academic source on LangGraph for multi-agent systems (arXiv:2411.18241), exploring how LangGraph combined with other frameworks can implement complex agent orchestration patterns. Their work validates the "hybrid router → LangGraph → sub-agents" architecture used in this project.

[Figure 2.2: LangGraph concept — a directed graph where the primary assistant node routes to specialized sub-agent nodes (booking, service, knowledge, general) based on tool-call dispatch. Each sub-agent has its own tool loop with conditional exit.]

### 2.3.2 Multi-Agent Routing Patterns

The **ReAct** (Reasoning + Acting) pattern, where an LLM alternates between reasoning about the task and taking actions (tool calls), is the foundational pattern for agentic AI. LangGraph implements ReAct through its tool-calling loop: the LLM generates a tool call, the tool node executes it, and the result is fed back to the LLM for the next reasoning step.

This project extends ReAct with **sub-agent routing**: the primary assistant LLM does not directly execute tools but instead dispatches to specialized sub-agents, each with their own tool sets and prompts. This separation of concerns mirrors the microservice pattern — each sub-agent is an expert in its domain (booking, knowledge, service).

### 2.3.3 Tool Calling and Function Invocation

Modern LLMs support structured tool calling where the model outputs a JSON-formatted function call (name + arguments) instead of free text. The LangGraph `ToolNode` intercepts these calls, executes the corresponding Python function, and returns the result as a message. This thesis implements 15 hotel-specific tools including `check_room_availability`, `create_reservation`, `search_hotel_knowledge`, and `generate_payment_link`.

## 2.4 Retrieval-Augmented Generation

### 2.4.1 The RAG Pipeline

Retrieval-Augmented Generation (RAG) addresses the LLM's knowledge cutoff and hallucination problems by retrieving relevant documents from an external knowledge base before generating a response. The pipeline consists of:

1. **Chunking** — splitting documents into overlapping segments
2. **Embedding** — converting chunks into dense vector representations
3. **Indexing** — storing vectors in a vector database
4. **Retrieval** — finding the most similar chunks to the user's query
5. **Generation** — feeding the retrieved context to the LLM with the original query

[Figure 2.3: RAG pipeline — hotel knowledge markdown documents are chunked, embedded via OpenRouter qwen3-embedding-8b (4096 dimensions), and stored in Qdrant. At query time, the user's message is embedded, top-k similar chunks are retrieved, and the LLM generates a response grounded in the retrieved context.]

### 2.4.2 Vector Databases

Vector databases are purpose-built for similarity search over high-dimensional embeddings. This project uses **Qdrant**, an open-source vector database written in Rust, selected for its performance on cosine similarity search and its Docker-native deployment model. Alternative vector databases include Milvus (used in the original NVIDIA blueprint), Pinecone (cloud-only), and ChromaDB (in-process).

### 2.4.3 Reranking and the Decision to Remove It

Cross-encoder rerankers (e.g., BAAI/bge-reranker-v2-m3) can improve retrieval precision by re-scoring the top-k results using a more expensive model. However, this project found that the reranker added ~1–2 seconds of CPU-bound latency per query and **blocked the FastAPI async event loop**, stalling all concurrent requests. Given that the embedding-based search from Qdrant was already achieving 100% accuracy on knowledge retrieval tests (8/8), the reranker was disabled by default — a trade-off documented in Section 5.4.

## 2.5 Web Application Technologies

### 2.5.1 FastAPI and Asynchronous Python

FastAPI is a modern Python web framework built on Starlette and Pydantic, providing automatic OpenAPI documentation, request validation, and async support. Its async capabilities are critical for this project: LLM inference calls take 3–50 seconds, and the server must handle other requests (health checks, admin queries, concurrent chats) without blocking.

### 2.5.2 Next.js App Router and React Server Components

The frontend uses **Next.js 15** with the App Router, which leverages React Server Components (RSC) for server-side rendering with minimal client JavaScript bundles (Next.js, 2024; Osmani, 2024). The chat interface uses Server-Sent Events (SSE) for real-time token streaming, while the admin dashboard uses client-side rendering with SWR for data fetching.

### 2.5.3 State Management: Zustand and SWR

**Zustand** was selected over Redux for global state management based on the comparative analysis by Salah (2024), which demonstrates Zustand's smaller bundle size, simpler API (no boilerplate reducers/actions), and equivalent functionality for medium-complexity applications.

**SWR** (stale-while-revalidate) implements the caching strategy defined in **RFC 5861** (Nottingham, 2010): serve cached data immediately while revalidating in the background. This pattern is ideal for the admin dashboard, where statistics should display instantly but update as fresh data arrives.

### 2.5.4 TypeScript

Gao, Bird, and Barr (2017) found that TypeScript could have prevented **15% of public bugs** in JavaScript projects on GitHub. Fischer and Hanenberg (2015) demonstrated a "large positive effect" of static typing on API usability. This project uses TypeScript throughout the frontend for type-safe API contracts between the backend's Pydantic models and the frontend's data fetching layer.

### 2.5.5 Ant Design

The UI component library is **Ant Design 5**, an enterprise-grade React component library providing 60+ components (Table, Form, Modal, Descriptions, etc.) with a consistent design language. The `antd-style` CSS-in-JS library integrates with Ant Design's theme tokens for consistent styling (Ant Design, 2024).

## 2.6 Security and Compliance

### 2.6.1 JWT Authentication and RBAC

JSON Web Tokens (JWT) provide stateless authentication by encoding user identity and role claims in a cryptographically signed token. This project implements role-based access control (RBAC) with two roles: `user` (registered guests) and `admin` (hotel staff). Admin routes require a valid JWT with `role=admin`, while guest chat endpoints remain public.

### 2.6.2 PII Redaction

Guest conversations may contain personally identifiable information (PII) such as credit card numbers, passport numbers, and phone numbers. Before sending messages to the LLM, a regex-based PII redactor scrubs sensitive data, replacing it with category tokens (e.g., `[CREDIT_CARD]`). This prevents the LLM from memorizing or echoing sensitive information.

## 2.7 Model Evaluation Methods

### 2.7.1 RAG Evaluation Metrics

DeepEval provides automated evaluation metrics for RAG systems including:
- **Faithfulness** — does the response only contain information from the retrieved context?
- **Answer Relevancy** — is the response relevant to the user's question?
- **Context Recall** — does the retrieved context contain the information needed to answer?

### 2.7.2 Cohen's Kappa for Inter-Model Agreement

Cohen's Kappa (κ) measures the agreement between two raters (in this case, two models) beyond what would be expected by chance. The formula is:

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

where $p_o$ is the observed agreement rate and $p_e$ is the expected agreement by chance. A κ of 0.0 indicates chance agreement, while 1.0 indicates perfect agreement. In this thesis, κ is computed between the local 9B model's pass/fail decisions and the cloud model's pass/fail decisions across 25 test cases.
