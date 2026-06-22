# Aura AI — Event-Driven AIOps Platform

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![DeepAgents](https://img.shields.io/badge/LangChain-DeepAgents-orange?logo=langchain&logoColor=white)](https://github.com/langchain-ai/deepagents)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant-FB8C00)](https://qdrant.tech)

> Autonomous multi-agent AIOps — ingest, correlate, analyze, and remediate events from any external system. Chat with your data using natural language.

---

## Table of Contents

1. [What is Aura AI?](#what-is-aura-ai)
2. [Core Concepts](#core-concepts)
3. [Architecture Overview](#architecture-overview)
4. [Quick Start](#quick-start)
5. [Prerequisites](#prerequisites)
6. [Local Development](#local-development)
7. [Production Deployment](#production-deployment)
8. [Environment Variables](#environment-variables)
9. [Project Structure](#project-structure)
10. [API Reference](#api-reference)
11. [Reactive Pipeline](#reactive-pipeline)
12. [Proactive Pipeline (Chat)](#proactive-pipeline-chat)
13. [Integrations & MCP](#integrations--mcp)
14. [Knowledge Bases & RAG](#knowledge-bases--rag)
15. [Database Connector](#database-connector)
16. [Testing](#testing)
17. [Contributing](#contributing)
18. [Roadmap](#roadmap)
19. [License](#license)

---

## What is Aura AI?

Aura AI is an **autonomous AIOps platform** that bridges two worlds:

| Mode | Trigger | Behavior | Use Case |
|------|---------|----------|----------|
| **Reactive** | External webhook / API event | Autonomous 3-phase analysis → diagnosis → email notification | Alert response, incident triage, monitoring |
| **Proactive** | User chat message | Multi-agent streaming chat with live data, docs, and integrations | Business queries, data exploration, root cause investigation |

Both modes are powered by the same **DeepAgents multi-agent engine** — a LangGraph-based orchestration layer that dispatches work to specialized sub-agents:

- **`db_analyst-agent`** — Queries your connected databases (PostgreSQL, MySQL), auto-generates SQL, returns insights
- **`rag-agent`** — Searches your document knowledge bases with hybrid search (dense + BM25 sparse + cross-encoder reranking)
- **`mcp-agent`** — Executes actions via external integrations (Gmail, APIs, messaging) through the Model Context Protocol

### Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI (Python 3.13), async/await |
| **Multi-Agent** | DeepAgents (LangGraph), LangChain |
| **LLM** | vLLM or Ollama (Qwen 3.5 9B) |
| **Database** | PostgreSQL 17 (SQLAlchemy 2.0 async) |
| **Vector DB** | Qdrant |
| **Cache/PubSub** | Redis (SSE broadcast, OAuth state, checkpointing) |
| **Object Storage** | MinIO (S3-compatible) |
| **Frontend** | Vue 3 + Vite + Tailwind CSS + ApexCharts |

---

## Core Concepts

### Dual-Mode Architecture

```
                    ┌──────────────────────┐
                    │      USER / SYSTEM    │
                    └──────┬───────┬───────┘
                           │       │
              Chat message │       │ Webhook / API event
                           ▼       ▼
              ┌────────────┴───────┴────────────┐
              │        SHARED FACTORY            │
              │  create_orchestrator(context=...) │
              │  context="proactive" | "reactive" │
              └────────────┬───────┬────────────┘
                           │       │
                           ▼       ▼
         ┌─────────────────┐   ┌─────────────────┐
         │ PROACTIVE CORE   │   │  REACTIVE CORE   │
         │ (Chat Interface)  │   │ (Event Pipeline)  │
         │                  │   │                  │
         │ Parallel dispatch│   │ Sequential 1→2→3 │
         │ SSE streaming    │   │ Director→Analyst │
         │ Multi-language   │   │ Structured JSON  │
         └────────┬─────────┘   └────────┬─────────┘
                  │                      │
                  └──────────┬───────────┘
                             ▼
         ┌─────────────────────────────────────┐
         │            SHARED SUB-AGENTS          │
         │                                      │
         │  db_analyst-agent   # SQL & schema   │
         │  rag-agent          # Document search │
         │  mcp-agent          # External actions│
         └─────────────────────────────────────┘
```

### Sub-Agent Capabilities

| Sub-Agent | Tools | When Used |
|-----------|-------|-----------|
| `db_analyst-agent` | `query_resource_data`, `execute_data_query`, `retrieve_relevant_schema`, `list_db_connections`, `db_schema`, `db_query`, `explain_sql_query` | Any data/metric/trend question |
| `rag-agent` | `rag_retrieve` | Document/manual/SOP search |
| `mcp-agent` | `mcp_execute` | External API calls, email, messaging |

### Director-Analyst Split (Reactive Only)

The reactive pipeline employs a two-stage architecture:

1. **Director** (DeepAgents orchestrator) — dispatches sub-agents in strict sequence (Phase 1→2→3), collects raw data only. Does NOT analyze or produce JSON.
2. **Synthesis Analyst** (separate LLM call) — receives the Director's raw findings, cross-checks event claims against real data, produces structured `ReactiveAnalysisOutput` JSON with source citations.

This separation prevents the Director from hallucinating analysis before all data is collected.

---

## Architecture Overview

```
                          EXTERNAL SYSTEMS
                                │
                    POST /webhooks/{slug}/receive
                                │
                                ▼
┌───────────────────────────────────────────────────────────┐
│                     NGINX (port 80)                        │
│                 Reverse Proxy + Gzip + Cache               │
└───────────────┬───────────────────────────────┬───────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────────┐  ┌────────────────────────┐
│    BACKEND (FastAPI :8000)     │  │   FRONTEND (Nginx SPA)  │
│                               │  │    Vue 3 + Vite          │
│  ┌─────────────────────────┐  │  └────────────────────────┘
│  │  api/v1/routers/         │  │
│  │  ├─ auth, users          │  │
│  │  ├─ chat, conversations   │  │
│  │  ├─ events, webhooks     │  │
│  │  ├─ knowledge, documents  │  │
│  │  ├─ integrations (MCP)   │  │
│  │  ├─ database-connector    │  │
│  │  ├─ reactive config       │  │
│  │  ├─ dashboard, metrics   │  │
│  │  └─ system, admin         │  │
│  └─────────────────────────┘  │
│                               │
│  ┌─────────────────────────┐  │
│  │  Application Layer       │  │
│  │  ├─ ChatOrchestrator     │  │
│  │  ├─ ReactiveOrchestrator │  │
│  │  ├─ DomainDetector       │  │
│  │  ├─ CorrelationEngine    │  │
│  │  └─ RetrievalPipeline    │  │
│  └─────────────────────────┘  │
│                               │
│  ┌─────────────────────────┐  │
│  │  DeepAgents Factory       │  │
│  │  ├─ SubagentRegistry     │  │
│  │  ├─ Prompt Templates     │  │
│  │  └─ Tool Factories       │  │
│  └─────────────────────────┘  │
└───────────┬───────────────────┘
            │
    ┌───────┼───────────┬──────────────┐
    ▼       ▼           ▼              ▼
┌────────┐┌────────┐┌────────┐┌────────────┐
│PostgreSQL││ Qdrant ││ Redis  ││   MinIO    │
│ :5432   ││ :6333  ││ :6379  ││ :9000/:9001│
└────────┘└────────┘└────────┘└────────────┘
         ▲                              ▲
         │                              │
    ┌────┴────┐                  ┌──────┴─────┐
    │  vLLM   │                  │   Ollama    │
    │  :8000  │                  │   :11434    │
    └─────────┘                  └────────────┘
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd EdgeBackend

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY to a random string

# 3. Start infrastructure (PostgreSQL, Qdrant, Redis, MinIO)
docker compose up -d postgres qdrant redis minio

# 4. Install Python dependencies
uv sync

# 5. Initialize database tables
python -m backend.init_db

# 6. Start the backend
uvicorn backend.main:app --reload
```

Open **http://localhost:8000** — the API is ready.

For the frontend, open a separate terminal:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

---

## Prerequisites

| Component | Version | Required | Notes |
|-----------|---------|----------|-------|
| **Python** | 3.13+ | Yes | See `.python-version` |
| **uv** | latest | Yes | Python package manager |
| **Docker** | 24+ | Yes | For PostgreSQL, Qdrant, Redis, MinIO |
| **Docker Compose** | v2 | Yes | |
| **Node.js** | 20.19+ or 22.12+ | For frontend | |
| **GPU (NVIDIA)** | — | Optional | For vLLM/Ollama. CPU-only dev is fine — app warns if no LLM is reachable |

### Port Allocation

| Port | Service | Purpose |
|------|---------|---------|
| `80` | Nginx | Production reverse proxy |
| `8000` | FastAPI | Backend API |
| `5173` | Vite | Frontend dev server |
| `5432` | PostgreSQL | Relational database |
| `6333` | Qdrant | Vector database (HTTP) |
| `6334` | Qdrant | Vector database (gRPC) |
| `6379` | Redis | Cache, pub/sub, checkpointing |
| `9000` | MinIO | Object storage (S3 API) |
| `9001` | MinIO | Web console |
| `8001` | vLLM (Docker) | LLM inference |
| `11434` | Ollama (Docker) | LLM inference |

---

## Local Development

### Backend

```bash
# Infrastructure only
docker compose up -d postgres qdrant redis minio

# Python environment
uv sync

# Initialize DB tables (run once, creates SQLAlchemy models)
python -m backend.init_db

# Start with auto-reload
uvicorn backend.main:app --reload --port 8000
```

### Frontend Hot-Reload

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api/v1` and `/webhooks` to `http://localhost:8000` automatically.

### LLM Backends

The app auto-detects which LLM engine is available. You can run exactly **one** at a time (they share the GPU):

```bash
# Option A: vLLM (production-grade — tool calling, LoRA, speculative decoding)
docker compose --profile vllm up -d vllm

# Option B: Ollama (quick testing, easy model switching)
docker compose --profile ollama up -d ollama
```

Configure via `.env`:

```env
DEFAULT_LLM_PROVIDER=auto    # auto-detect (prefers vLLM, falls back to Ollama)
# or force one:
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_LLM_PROVIDER=vllm
```

Without any LLM, the app starts but chat/analysis features will warn the user.

### Debugging

```bash
# Set log level
LOG_LEVEL=DEBUG uvicorn backend.main:app --reload

# Run specific test
pytest tests/test_smoke_pipeline.py -v

# Check health
curl http://localhost:8000/health
```

---

## Production Deployment

```bash
# 1. Configure .env for production
APP_ENV=production
LOG_LEVEL=INFO
SECRET_KEY=<random-64-char-string>

# 2. Start everything (includes Nginx reverse proxy)
docker compose --profile vllm up -d     # or --profile ollama
docker compose --profile proxy up -d

# 3. Access via Nginx at http://localhost:80
```

### Docker Compose Profiles

| Profile | Services | Use |
|---------|----------|-----|
| (none) | postgres, qdrant, redis, minio, backend, frontend | Core infra + app |
| `vllm` | vllm | GPU LLM inference |
| `ollama` | ollama | Alternative LLM |
| `proxy` | nginx | Reverse proxy with gzip/caching |

### Resource Limits (docker-compose.yml)

| Service | Memory Limit | Notes |
|---------|-------------|-------|
| PostgreSQL | 1 GB | 200 max connections |
| Qdrant | 4 GB | 8 search threads |
| Redis | 1 GB | AOF persistence, LRU eviction |
| MinIO | 1 GB | |
| Backend | 8 GB | HuggingFace model cache |
| vLLM | GPU (shared) | `gpu-memory-utilization: 0.88` |

---

## Environment Variables

Full reference of every `.env` variable:

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | `development` or `production` |
| `LOG_LEVEL` | `DEBUG` | Python logging level |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://edge:edge@localhost:5432/edgebackend` | PostgreSQL connection |
| `DATABASE_POOL_SIZE` | `20` | SQLAlchemy async pool size |

### Qdrant (Vector DB)

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP endpoint |
| `QDRANT_API_KEY` | — | Optional API key |

### vLLM

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_ENABLED` | `False` | Enable vLLM provider |
| `VLLM_BASE_URL` | `http://vllm:8000/v1` | vLLM endpoint |
| `VLLM_API_KEY` | — | Optional API key |
| `VLLM_MODEL` | `Qwen/Qwen3.5-9B-Instruct` | Model name |
| `VLLM_MAX_TOKENS` | `8192` | Max output tokens |

### Ollama

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_ENABLED` | `True` | Enable Ollama provider |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen3.5:9b` | Model name |
| `OLLAMA_MAX_TOKENS` | `8192` | Max output tokens |
| `OLLAMA_NUM_CTX` | `24576` | Context window size |

### LLM Provider Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_LLM_PROVIDER` | `ollama` | `auto`, `vllm`, or `ollama` |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-in-production` | JWT signing key — **change this** |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT token lifespan |
| `EVENT_INGEST_API_KEY` | `change-me-event-ingest-key` | API key for event ingestion |

### OAuth (Gmail Integration)

| Variable | Default | Description |
|----------|---------|-------------|
| `OAUTH_REDIRECT_URL` | `http://localhost/api/v1/integrations/oauth/callback` | OAuth callback URL (must match Google Cloud Console) |
| `GMAIL_CLIENT_ID` | — | Google OAuth 2.0 client ID |
| `GMAIL_CLIENT_SECRET` | — | Google OAuth 2.0 client secret |

### Credential Encryption

| Variable | Default | Description |
|----------|---------|-------------|
| `CREDENTIAL_ENCRYPTION_KEY` | — | Fernet encryption key (falls back to `SECRET_KEY`) |
| `CREDENTIAL_ENCRYPTION_KEY_PREVIOUS` | — | Previous key for rotation |

### MinIO / S3 Object Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO S3 endpoint |
| `MINIO_ACCESS_KEY` | `minioadmin` | Access key |
| `MINIO_SECRET_KEY` | `minioadmin` | Secret key |
| `MINIO_BUCKET` | `documents` | Bucket name |
| `MINIO_SECURE` | `False` | Use TLS |
| `MINIO_REGION` | `us-east-1` | Region |
| `MAX_UPLOAD_SIZE` | `104857600` | Max file upload (100 MB) |

### Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDINGS_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Dense embeddings model |
| `SPARSE_EMBEDDINGS_MODEL` | `Qdrant/bm25` | Sparse (BM25) embeddings model |

### RAG Pipeline

| Variable | Default | Description |
|----------|---------|-------------|
| `HYBRID_SEARCH_ENABLED` | `True` | Hybrid dense + sparse search |
| `RAG_PREFETCH_LIMIT` | `50` | Chunks to prefetch per query |
| `RAG_RERANK_TOP_K` | `5` | Chunks after reranking |
| `RAG_MIN_RELEVANCE_SCORE` | `0.01` | Minimum relevance threshold |

### Reranker

| Variable | Default | Description |
|----------|---------|-------------|
| `RERANKER_ENABLED` | `False` | Enable cross-encoder reranker |
| `RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Reranker model |

### Chunking & Query Enhancement

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTEXTUAL_CHUNKING_ENABLED` | `False` | LLM-based contextual chunk enrichment |
| `QUERY_ENHANCEMENT_ENABLED` | `False` | LLM-based multi-query + HyDE expansion |

### Reactive Pipeline

| Variable | Default | Description |
|----------|---------|-------------|
| `REACTIVE_NOTIFICATION_EMAIL` | — | Fallback email recipient for event notifications |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Frontend dev server origin |
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | Allowed CORS origins |
| `SHOW_REASONING_IN_CHAT` | `False` | Show LLM reasoning tokens in chat |

---

## Project Structure

```
EdgeBackend/
├── backend/
│   ├── main.py                     # FastAPI app factory, lifespan events
│   ├── init_db.py                  # SQLAlchemy table creation
│   │
│   ├── api/v1/
│   │   ├── router.py               # Aggregates all sub-routers under /api/v1
│   │   ├── routers/                # REST endpoint modules (one per domain)
│   │   │   ├── auth.py             # POST /login, /register, /logout
│   │   │   ├── chat.py             # POST /chat, /chat/stream (SSE)
│   │   │   ├── events.py           # CRUD + approve/reject + SSE stream
│   │   │   ├── webhooks.py         # Webhook CRUD + test mapping
│   │   │   ├── conversations.py    # Conversation lifecycle
│   │   │   ├── knowledge.py        # Knowledge base CRUD + toggle
│   │   │   ├── documents.py        # Document upload/list/delete
│   │   │   ├── integrations.py     # Integration instance lifecycle
│   │   │   ├── data_analyst.py     # NL2SQL interface
│   │   │   ├── domain_config.py    # Domain detection rules
│   │   │   ├── reactive_config.py  # Reactive mode toggles
│   │   │   ├── reactive_tools.py   # Reactive tool catalog
│   │   │   ├── reactive_credentials.py # Encrypted credentials
│   │   │   ├── tools.py            # Chat tool catalog
│   │   │   ├── prompts.py          # LLM prompt management
│   │   │   ├── models.py           # LLM model configs
│   │   │   ├── dashboard.py        # Unified summary endpoint
│   │   │   ├── metrics.py          # Event metrics (MTTD, MTTR)
│   │   │   ├── db_collector.py     # Scheduled DB collection
│   │   │   ├── system.py           # System stats
│   │   │   ├── admin.py            # User management, analytics
│   │   │   └── users.py            # User profile
│   │   └── schemas/                # Pydantic request/response models
│   │
│   ├── core/
│   │   ├── config.py               # Pydantic Settings — all env vars
│   │   ├── deps.py                 # FastAPI dependency injection
│   │   ├── context.py              # Async context management
│   │   ├── exceptions.py           # Custom exception classes
│   │   ├── base_service.py         # Generic CRUD service base class
│   │   └── _helpers.py             # commit_and_refresh, etc.
│   │
│   ├── ia/                         # Intelligence & Automation
│   │   ├── factory.py              # Unified DeepAgents orchestrator factory
│   │   ├── llm_client.py           # LLM client abstraction
│   │   ├── langchain_models.py     # LangChain model wrappers
│   │   ├── orchestrator_factory.py # (Legacy alias → factory.py)
│   │   ├── prompts/
│   │   │   ├── reactive.py         # Reactive pipeline prompts
│   │   │   ├── orchestrator.py     # Proactive chat orchestrator prompt
│   │   │   ├── subagents.py        # Sub-agent descriptions + prompts
│   │   │   ├── loader.py           # Jinja2 template loader
│   │   │   └── templates/         # Markdown prompt templates (.md)
│   │   ├── subagents/
│   │   │   ├── plugin_registry.py  # Sub-agent plugin registry
│   │   │   └── builders.py         # Sub-agent builder functions
│   │   ├── tools/
│   │   │   ├── data_analyst.py     # DB query + NL2SQL tools
│   │   │   ├── db.py               # Direct SQL + schema tools
│   │   │   ├── mcp.py              # MCP execution tool
│   │   │   ├── rag.py              # RAG retrieval tool
│   │   │   └── session.py          # Async session context managers
│   │   ├── schemas/
│   │   │   └── reactive.py         # ReactiveAnalysisOutput Pydantic model
│   │   └── memory/
│   │       └── __init__.py         # LangGraph checkpointer + store
│   │
│   ├── services/                   # Business logic
│   │   ├── chat_service.py         # Chat facade (conversations + orchestration)
│   │   ├── chat_orchestrator.py    # DeepAgents streaming + non-streaming
│   │   ├── reactive_orchestrator.py # Reactive event analysis pipeline
│   │   ├── event_service.py        # Event lifecycle + job enqueue
│   │   ├── event_job_tracker.py    # Durable job queue + retry + recovery
│   │   ├── webhook_service.py      # Webhook reception + mapping
│   │   ├── webhook_mapping_engine.py # JSONPath payload mapping + LLM auto-discover
│   │   ├── correlation_engine.py   # Dedup, flapping detection, grouping
│   │   ├── domain_detector.py      # Rule-based + LLM domain classification
│   │   ├── notification_service.py # Gmail notification delivery
│   │   ├── knowledge_service.py    # Knowledge base management
│   │   ├── document_service.py     # Document upload + processing
│   │   ├── document_processor.py   # PDF/TXT chunking + indexing
│   │   ├── embedding_service.py    # Dense embedding generation
│   │   ├── sparse_embedding_service.py # BM25 sparse embedding
│   │   ├── retrieval_pipeline.py   # Multi-stage: enhance → embed → retrieve → rerank
│   │   ├── query_enhancer.py       # Multi-query + HyDE expansion
│   │   ├── chunking_service.py     # Document chunking strategies
│   │   ├── schema_embedding_service.py # DB schema semantic indexing
│   │   ├── data_analyst_service.py # NL2SQL with auto-correction
│   │   ├── reactive_config_service.py # Reactive mode configuration
│   │   ├── event_metric_service.py # Event metric aggregation
│   │   ├── mcp_service.py          # MCP execution service
│   │   ├── credential_service.py   # Reactive credential management
│   │   ├── domain_config_service.py # Domain CRUD
│   │   ├── model_service.py        # LLM model config
│   │   ├── prompt_service.py       # Prompt management
│   │   ├── tool_registry_service.py # Tool discovery across contexts
│   │   └── ...
│   │
│   ├── integrations/               # MCP integrations layer
│   │   ├── integration_service.py  # Integration lifecycle + tool discovery
│   │   ├── catalog.py              # Integration catalog
│   │   ├── catalog_seed.py         # Seed data for built-in integrations
│   │   ├── credentials.py          # Credential management
│   │   ├── credential_vault.py     # Fernet encryption vault
│   │   ├── credential_audit.py     # Audit logging
│   │   ├── router.py               # /api/v1/integrations endpoints
│   │   ├── oauth/                  # OAuth2 state management (Redis)
│   │   ├── auth_strategies/        # Per-auth-type validation + mapping
│   │   ├── custom_mcp_servers/gmail/ # Gmail MCP server client
│   │   └── repositories/           # IntegrationInstance persistence
│   │
│   ├── database_connector/         # External DB connections
│   │   ├── service.py              # Connection lifecycle + schema discovery
│   │   ├── engine_factory.py       # SQLAlchemy async engine pool
│   │   ├── schema_intelligence.py  # FK inference, sample data, auto-describe
│   │   ├── repository.py           # Connection persistence
│   │   ├── router.py               # /api/v1/database endpoints
│   │   └── schemas.py              # Pydantic schemas
│   │
│   ├── persistencia/               # Persistence layer
│   │   ├── repositories/           # SQLAlchemy repositories (one per model)
│   │   ├── vector/                 # Qdrant client + vector repositories
│   │   └── storage/                # MinIO S3 client
│   │
│   └── workers/                    # Background async workers
│       └── correlation_worker.py   # Periodic event dedup/grouping (30s)
│
├── frontend/                       # Vue 3 SPA
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/               # ChatInput, MarkdownRenderer
│   │   │   ├── dashboard/          # KpiCard, SeverityDonut, SystemHealthPills
│   │   │   └── layout/             # Sidebar
│   │   ├── views/
│   │   │   ├── ChatView.vue        # Main chat interface
│   │   │   ├── DashboardView.vue   # KPI dashboard
│   │   │   ├── EventsView.vue      # Event listing + filtering
│   │   │   ├── reactive/           # Reactive pipelines UI
│   │   │   └── workspace/          # Knowledge base workspace
│   │   ├── services/               # Axios API clients
│   │   ├── stores/                 # Pinia state stores
│   │   ├── router/                 # Vue Router config
│   │   └── layouts/                # Page layouts
│   └── vite.config.ts
│
├── nginx/                          # Reverse proxy config
├── docker/                         # Docker init scripts + configs
├── scripts/                        # Migrations + utilities
├── tests/                          # pytest suite
├── docs/                           # Additional documentation
├── docker-compose.yml              # All services + profiles
├── pyproject.toml                   # Python dependencies + config
└── uv.lock                         # Locked dependency versions
```

---

## API Reference

The API exposes **123 endpoints** across 26 modules under `/api/v1`.

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/register` | No | Register new user |
| `POST` | `/api/v1/auth/login` | No | Login → JWT `access_token` |
| `GET` | `/api/v1/auth/me` | JWT | Current user profile |
| `POST` | `/api/v1/auth/logout` | JWT | Logout (stateless) |

### Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/users/me` | JWT | User profile |

### Chat

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/chat` | JWT | Chat message (non-streaming) |
| `POST` | `/api/v1/chat/stream` | JWT | Chat message (SSE streaming) |

**Chat Request Body:**
```json
{
  "query": "Cuales son los 5 productos mas vendidos?",
  "knowledge_base_id": "optional-uuid",
  "mcp_source_id": "optional-uuid",
  "db_connection_ids": ["optional-uuid"],
  "thread_id": "optional-uuid"
}
```

### Conversations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/conversations` | JWT | List conversations |
| `POST` | `/api/v1/conversations` | JWT | Create conversation |
| `GET` | `/api/v1/conversations/{thread_id}/messages` | JWT | Get messages |
| `DELETE` | `/api/v1/conversations/{thread_id}` | JWT | Delete conversation |
| `PATCH` | `/api/v1/conversations/{thread_id}/archive` | JWT | Archive/unarchive |

### Events

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/events` | JWT | List events (filters: severity, status, domain) |
| `GET` | `/api/v1/events/{event_id}` | JWT | Get event detail |
| `POST` | `/api/v1/events/{event_id}/approve` | JWT | Approve for execution |
| `POST` | `/api/v1/events/{event_id}/reject` | JWT | Reject event |
| `POST` | `/api/v1/events/{event_id}/feedback` | JWT | Submit feedback |
| `GET` | `/api/v1/events/stream` | Token | SSE real-time event stream |

### Webhooks (Public — no auth)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/webhooks/{slug}/receive` | No | Public webhook receiver |

### Webhooks (Authenticated)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/webhooks` | JWT | List webhook sources |
| `POST` | `/api/v1/webhooks` | JWT | Create webhook source |
| `GET` | `/api/v1/webhooks/{slug}` | JWT | Get webhook |
| `PATCH` | `/api/v1/webhooks/{slug}` | JWT | Update webhook |
| `DELETE` | `/api/v1/webhooks/{slug}` | JWT | Delete webhook |
| `POST` | `/api/v1/webhooks/{slug}/test` | JWT | Test mapping config |

### Database Connector

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/database/connections` | JWT | List connections |
| `POST` | `/api/v1/database/connections` | JWT | Create connection |
| `GET` | `/api/v1/database/connections/{id}` | JWT | Get connection |
| `PATCH` | `/api/v1/database/connections/{id}` | JWT | Update connection |
| `DELETE` | `/api/v1/database/connections/{id}` | JWT | Delete connection |
| `POST` | `/api/v1/database/connections/{id}/test` | JWT | Test connectivity |
| `POST` | `/api/v1/database/connections/{id}/discover-schema` | JWT | Auto-discover schema |
| `GET` | `/api/v1/database/connections/{id}/schema` | JWT | Get cached schema |
| `PATCH` | `/api/v1/database/connections/{id}/schema/enrich` | JWT | Enrich with descriptions |
| `POST` | `/api/v1/database/connections/{id}/query` | JWT | Execute read-only SQL |

### Data Analyst

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/data-analyst/ask` | JWT | NL question → SQL + results |
| `GET` | `/api/v1/data-analyst/connections` | JWT | List available DB connections |
| `POST` | `/api/v1/data-analyst/schema` | JWT | Semantic schema search |
| `POST` | `/api/v1/data-analyst/explain` | JWT | Explain SQL query |

### Integrations (MCP)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/integrations/catalog` | JWT | List integration catalog |
| `GET` | `/api/v1/integrations/catalog/{slug}` | JWT | Catalog detail |
| `POST` | `/api/v1/integrations/instances` | JWT | Create instance |
| `GET` | `/api/v1/integrations/instances` | JWT | List instances |
| `GET` | `/api/v1/integrations/instances/{id}` | JWT | Instance detail |
| `PATCH` | `/api/v1/integrations/instances/{id}` | JWT | Update instance |
| `DELETE` | `/api/v1/integrations/instances/{id}` | JWT | Delete instance |
| `GET` | `/api/v1/integrations/instances/{id}/setup-guide` | JWT | Auth setup guide |
| `POST` | `/api/v1/integrations/instances/{id}/credentials` | JWT | Submit credentials |
| `POST` | `/api/v1/integrations/instances/{id}/oauth/{provider}/start` | JWT | Start OAuth2 flow |
| `GET` | `/api/v1/integrations/oauth/callback` | No | OAuth2 callback |
| `POST` | `/api/v1/integrations/instances/{id}/sync` | JWT | Force tool re-discovery |
| `POST` | `/api/v1/integrations/instances/{id}/stop` | JWT | Stop MCP process |
| `GET` | `/api/v1/integrations/instances/{id}/status` | JWT | Runtime process status |

### Knowledge Bases

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/knowledge` | JWT | List knowledge bases |
| `POST` | `/api/v1/knowledge` | JWT | Create knowledge base |
| `GET` | `/api/v1/knowledge/{id}` | JWT | Get with nested documents |
| `PATCH` | `/api/v1/knowledge/{id}` | JWT | Update |
| `DELETE` | `/api/v1/knowledge/{id}` | JWT | Delete |
| `PATCH` | `/api/v1/knowledge/{id}/toggle-chat` | JWT | Toggle for chat |
| `PATCH` | `/api/v1/knowledge/{id}/toggle-reactive` | JWT | Toggle for reactive |

### Documents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/documents/upload` | JWT | Upload document (PDF/TXT) |
| `GET` | `/api/v1/documents` | JWT | List documents |
| `GET` | `/api/v1/documents/{id}` | JWT | Get document |
| `DELETE` | `/api/v1/documents/{id}` | JWT | Delete (DB + MinIO + Qdrant) |

### Reactive Configuration

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/reactive/tools` | JWT | List reactive-enabled tools |
| `PUT` | `/api/v1/reactive/tools/{tool_id}` | JWT | Toggle tool |
| `GET` | `/api/v1/reactive/knowledge` | JWT | List reactive-enabled KBs |
| `PUT` | `/api/v1/reactive/knowledge/{kb_id}` | JWT | Toggle KB |

### Metrics & Dashboard

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/dashboard/summary` | JWT | Unified dashboard summary |
| `GET` | `/api/v1/metrics/events` | JWT | Event metrics (MTTD, MTTR) |
| `GET` | `/api/v1/metrics/events/summary` | JWT | 7-day metrics summary |

### Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/admin/users` | Admin JWT | List users |
| `PATCH` | `/api/v1/admin/users/{id}` | Admin JWT | Update user role |
| `DELETE` | `/api/v1/admin/users/{id}` | Admin JWT | Delete user |
| `GET` | `/api/v1/admin/stats` | Admin JWT | Platform analytics |
| `GET` | `/api/v1/admin/settings` | Admin JWT | System configuration |

### System & Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check |
| `GET` | `/api/v1/system/stats` | JWT | System statistics |

### Domain Configuration

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/domains` | JWT | List domain configs |
| `POST` | `/api/v1/domains` | JWT | Create domain config |
| `GET` | `/api/v1/domains/{id}` | JWT | Get domain config |
| `PUT` | `/api/v1/domains/{id}` | JWT | Update domain config |
| `DELETE` | `/api/v1/domains/{id}` | JWT | Delete domain config |
| `POST` | `/api/v1/domains/detect` | JWT | Test domain detection |

### Models & Prompts

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/models` | JWT | List model configs |
| `POST` | `/api/v1/models` | JWT | Create model config |
| `GET` | `/api/v1/models/discovery/providers` | JWT | List LLM providers |
| `GET` | `/api/v1/models/discovery/models/{provider}` | JWT | List provider models |
| `GET` | `/api/v1/prompts` | No | List prompts |
| `POST` | `/api/v1/prompts` | JWT | Create prompt |
| `PATCH` | `/api/v1/prompts/{id}` | JWT | Update prompt |
| `DELETE` | `/api/v1/prompts/{id}` | JWT | Delete prompt |

---

## Reactive Pipeline

The reactive pipeline is the autonomous event-response system. It triggers automatically when an external system pushes a webhook payload.

### Lifecycle

```
Event Status: pending → analyzing → completed
                                ↘ failed
```

### Step-by-Step Flow

```
╔══════════════════════════════════════════════════════════════╗
║  PHASE 0: INGESTION & NORMALIZATION                         ║
╚══════════════════════════════════════════════════════════════╝
  
  External System
       │
       │  POST /webhooks/{slug}/receive  (any JSON payload)
       ▼
  ┌─────────────────────┐
  │ WebhookService       │
  │  1. Validate HMAC    │
  │  2. Rate limit check │
  │  3. Auto-discover    │
  │     mapping (LLM)    │
  └─────────┬───────────┘
            │
            ▼
  ┌─────────────────────┐
  │ WebhookMappingEngine │
  │  JSONPath extraction │
  │  Severity mapping    │
  │  Timestamp parsing   │
  └─────────┬───────────┘
            │
            ▼
  ┌─────────────────────┐
  │ DomainDetector       │
  │  1. Rule match       │
  │     (keywords,       │
  │      source glob)    │
  │  2. LLM inference    │
  │     (cached 5 min)   │
  └─────────┬───────────┘
            │
            ▼
  Event created: status="pending"

╔══════════════════════════════════════════════════════════════╗
║  PHASE A: CORRELATION (background worker, every 30s)        ║
╚══════════════════════════════════════════════════════════════╝

  ┌─────────────────────┐
  │ CorrelationEngine    │
  │  1. Dedup (5-min     │
  │     window)          │
  │  2. Flapping detect  │
  │     (>3 events from  │
  │      same source)    │
  │  3. Group by domain  │
  │  4. Suppress low-    │
  │     severity when    │
  │     critical active  │
  └─────────────────────┘

  Matched events → status="suppressed"
  Remaining events → status stays "pending"

╔══════════════════════════════════════════════════════════════╗
║  PHASE B: ANALYSIS (EventJobTracker durable queue)          ║
╚══════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────┐
  │ ReactiveOrchestrator.analyze()               │
  │                                              │
  │  event.status = "analyzing"                  │
  │                                              │
  │  Load user reactive config:                  │
  │    • Which KBs enabled?                      │
  │    • Which MCP tools enabled?                │
  │    • Which DB connections?                   │
  │                                              │
  │  ┌─────────────────────────────────────┐     │
  │  │  DEEPGENTS DIRECTOR                 │     │
  │  │  (Sequential 1→2→3)                 │     │
  │  │                                     │     │
  │  │  Phase 1: db_analyst-agent          │     │
  │  │    → query_resource_data()          │     │
  │  │    • Window by severity:            │     │
  │  │      info→1h, warn→6h, error→24h   │     │
  │  │    • Zero LLM, parameterized query  │     │
  │  │    • Returns markdown table         │     │
  │  │                                     │     │
  │  │  Phase 2: rag-agent                │     │
  │  │    → rag_retrieve()                │     │
  │  │    • Enriched query (event + DB)   │     │
  │  │    • Hybrid search + rerank        │     │
  │  │    • Returns citations + text      │     │
  │  │                                     │     │
  │  │  Phase 3: mcp-agent                │     │
  │  │    → mcp_execute()                 │     │
  │  │    • send_email (Gmail)            │     │
  │  │    • Other enabled integrations    │     │
  │  │    • Returns action results        │     │
  │  └─────────────────────────────────────┘     │
  │                                              │
  │  ┌─────────────────────────────────────┐     │
  │  │  SYNTHESIS ANALYST (separate LLM)   │     │
  │  │                                     │     │
  │  │  Receives:                          │     │
  │  │    • Raw sub-agent findings          │     │
  │  │    • Director summary                │     │
  │  │    • Event context                   │     │
  │  │                                     │     │
  │  │  Applies:                           │     │
  │  │    • Cross-check rules               │     │
  │  │    • Source attribution              │     │
  │  │    • Anti-hallucination protocol     │     │
  │  │                                     │     │
  │  │  Output:                            │     │
  │  │    {                                │     │
  │  │      "analysis": "...",              │     │
  │  │      "diagnosis": "...",             │     │
  │  │      "plan": "...",                  │     │
  │  │      "execute_instruction": "..."    │     │
  │  │    }                                │     │
  │  └─────────────────────────────────────┘     │
  │                                              │
  │  → Email analysis via Gmail MCP              │
  │  → event.status = "completed"                │
  └─────────────────────────────────────────────┘
```

### Event States

| Status | Meaning |
|--------|---------|
| `pending` | Event created, waiting for correlation/analysis |
| `analyzing` | Analysis pipeline is running |
| `completed` | Analysis done, email sent |
| `failed` | Pipeline error |
| `awaiting_approval` | Waiting for human approval before execution |
| `executing` | Remediation plan is being executed |
| `suppressed` | Deduplicated, flapping, or low-severity under critical |

### Durability

The `EventJobTracker` ensures no analysis job is lost:

- Jobs are **persisted in PostgreSQL** (`event_jobs` table)
- **Concurrency limited** via `asyncio.Semaphore` (max 5)
- **Automatic retry** with exponential backoff (2s → 4s → 8s, max 3 attempts)
- **Orphan recovery** on startup: any `running`/`queued` job older than 5 minutes is re-queued

### SSE Real-Time Updates

Connect to `GET /api/v1/events/stream` for live updates:

```json
// Status change
{"type": "status_update", "data": {"id": 42, "status": "analyzing", ...}}

// Phase results
{"type": "db_analyst_result", "data": {"id": 42, "result": "..."}}
{"type": "rag_result", "data": {"id": 42, "result": "..."}}
{"type": "mcp_result", "data": {"id": 42, "result": "..."}}

// Analysis output
{"type": "analysis_result", "data": {"id": 42, "result": "..."}}
{"type": "diagnosis_result", "data": {"id": 42, "diagnosis": "..."}}
{"type": "planner_result", "data": {"id": 42, "plan": "..."}}

// Log lines (real-time pipeline logging)
{"type": "log_line", "data": {"id": 42, "level": "info", "message": "..."}}
```

---

## Proactive Pipeline (Chat)

The proactive pipeline powers the conversational interface. Users chat naturally and the orchestrator dispatches to sub-agents automatically.

### Flow

```
User Message
     │
     ▼
┌────────────────────┐
│ ChatOrchestrator    │
│                     │
│ 1. Create/resolve   │
│    conversation     │
│ 2. Resolve toggles: │
│    • knowledge_base │
│    • mcp_source     │
│    • db_connections │
│ 3. Discover tools   │
│    dynamically      │
│ 4. Create DeepAgents│
│    orchestrator     │
└────────┬───────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ DEEPGENTS ORCHESTRATOR (Director)        │
│                                          │
│ System prompt rules:                     │
│ • Match user language                    │
│ • ALL data questions → db_analyst-agent  │
│ • Document questions → rag-agent         │
│ • API/external → mcp-agent               │
│ • Multi-domain → PARALLEL dispatch       │
│ • Pure reasoning → answer directly       │
│ • Max 2 delegation turns                 │
│ • NEVER answer data from memory          │
└────────┬────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ SSE STREAMING OUTPUT                    │
│                                         │
│ {"type": "token", "content": "...",     │
│  "agent": "orchestrator"}              │
│                                         │
│ {"type": "subagent", "name":            │
│  "db_analyst-agent", "status":"running"}│
│                                         │
│ {"type": "tool_call", "name":           │
│  "query_resource_data", ...}            │
│                                         │
│ {"type": "subagent", "name":            │
│  "db_analyst-agent","status":"complete"}│
│                                         │
│ {"type": "done", ...}                   │
└────────────────────────────────────────┘
```

### Streaming Events

| Event Type | Description |
|------------|-------------|
| `token` | AI-generated text token |
| `reasoning` | LLM reasoning traces (if `SHOW_REASONING_IN_CHAT=true`) |
| `subagent` | Sub-agent lifecycle (`running` / `complete`) |
| `tool_call` | Tool invocation with name + args |
| `tool_response` | Tool result (truncated to 200 chars) |
| `thought` | Sub-agent thinking (if `SHOW_REASONING_IN_CHAT=true`) |
| `done` | Stream complete, includes `full_content` |

### Anti-Hallucination Rules

The orchestrator system prompt enforces strict rules:

1. **Mandatory data rule**: Any question involving numbers, metrics, or data MUST be delegated to `db_analyst-agent` first. The orchestrator has NO direct database access tools.
2. **Parallel dispatch**: Multi-domain queries dispatch all needed sub-agents in a single turn.
3. **Max 2 turns**: Total delegation limited to prevent infinite tool-call loops.
4. **Error honesty**: If a sub-agent returns `no_data` or `error`, report it honestly — never fabricate.
5. **Language matching**: Always respond in the user's input language.

---

## Integrations & MCP

Integrations use the **Model Context Protocol (MCP)** to connect external services.

### Architecture

```
┌──────────────────────────────────┐
│          DATABASE                 │
│  IntegrationInstance              │
│  ├─ catalog_slug (e.g. "gmail")  │
│  ├─ credentials (encrypted)      │
│  ├─ available_in_chat (bool)     │
│  └─ available_in_reactive (bool) │
└────────────┬─────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌──────────┐   ┌──────────────┐
│ OAuth2    │   │ API Key /    │
│ (Gmail)  │   │ Custom Auth  │
└────┬─────┘   └──────┬───────┘
     │                │
     ▼                ▼
┌─────────────────────────────┐
│  MCP Stdio Server Process    │
│  (python -m custom_mcp)      │
│  Environment: credentials    │
│  injected as env vars        │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│  Tool Discovery (tools/list) │
│  → mcp_execute tool          │
│  Registered in DeepAgents    │
└─────────────────────────────┘
```

### Setting Up Gmail Integration

1. Create a Google Cloud Console project
2. Enable the Gmail API
3. Create OAuth 2.0 credentials (Web application type)
4. Add authorized redirect URI: `http://localhost:8000/api/v1/integrations/oauth/callback`
5. Set `.env`:
   ```env
   GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GMAIL_CLIENT_SECRET=your-client-secret
   OAUTH_REDIRECT_URL=http://localhost:8000/api/v1/integrations/oauth/callback
   ```
6. In the frontend: **Integrations → Create Instance → Gmail → Start OAuth Flow**

### Credential Security

- All credentials are encrypted at rest using **Fernet** (symmetric encryption)
- Encryption key: `CREDENTIAL_ENCRYPTION_KEY` or falls back to `SECRET_KEY`
- Supports **key rotation** via `CREDENTIAL_ENCRYPTION_KEY_PREVIOUS`
- Credentials are never returned in API responses
- OAuth tokens with expiry are auto-managed

### Tool Discovery

When credentials are submitted, the system:
1. Spawns the MCP stdio server as a child process
2. Calls `tools/list` via the MCP protocol
3. Normalizes tool metadata (name, description, parameter schema)
4. Caches schemas for 60 seconds to avoid repeated process spawns
5. Registers tools with the DeepAgents sub-agent registry

---

## Knowledge Bases & RAG

The RAG (Retrieval-Augmented Generation) system indexes your documents and provides semantic search to the LLM.

### Document Pipeline

```
Upload (PDF/TXT)
     │
     ▼
┌────────────────┐
│ MinIO Storage   │  ← Raw file persisted
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ DocumentProcessor│  ← Async background processing
│ 1. Extract text  │
│ 2. Chunk text    │
│ 3. Generate       │
│    embeddings     │
│ 4. Index in       │
│    Qdrant         │
└────────────────┘
```

### Retrieval Pipeline (5 Stages)

```
Query → ENHANCE → EMBED → RETRIEVE → RERANK → FORMAT → Context
```

| Stage | Technology | Config Toggle |
|-------|-----------|---------------|
| **1. Enhance** | Multi-query + HyDE expansion (LLM) | `QUERY_ENHANCEMENT_ENABLED` |
| **2. Embed** | Dense (`all-MiniLM-L6-v2`) + Sparse (`BM25`) | `HYBRID_SEARCH_ENABLED` |
| **3. Retrieve** | Qdrant hybrid RRF fusion | `RAG_PREFETCH_LIMIT=50` |
| **4. Rerank** | Cross-encoder (`bge-reranker-v2-m3`) | `RERANKER_ENABLED` |
| **5. Format** | XML-structured context with citations | `RAG_MIN_RELEVANCE_SCORE` |

### Contextual Chunking

When enabled (`CONTEXTUAL_CHUNKING_ENABLED=true`), each document chunk is enriched with document-level context (title, section headings) before embedding — improving retrieval precision.

### Multi-KB Search

Both the proactive and reactive pipelines support searching across multiple knowledge bases simultaneously. Results are deduplicated by document ID and ranked by composite score.

---

## Database Connector

Connect your own PostgreSQL or MySQL databases for natural-language querying.

### Supported Databases

| Database | Status | Features |
|----------|--------|----------|
| **PostgreSQL** | Full support | Schema discovery, FK inference, read-only mode, semantic indexing |
| **MySQL** | Full support | Schema discovery, FK inference, read-only mode |

### SQL Generation (NL2SQL)

```
User asks "Top 5 products by sales last month"
     │
     ▼
┌─────────────────────┐
│ 1. Schema RAG        │  Semantic search for relevant tables/columns
│    (Qdrant vector   │
│     search)          │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 2. SQL Generation    │  LLM generates SQL with schema context
│    (LLM prompt)     │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 3. Execute +         │  Run query, check for errors
│    Auto-Correct      │  Retry up to 3 times with error feedback
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ 4. Interpret Results │  Natural-language insights from results
└─────────────────────┘
```

### Security (4-Layer Defense)

| Layer | Method | Blocks |
|-------|--------|--------|
| **1** | Read-only transaction (`SET TRANSACTION READ ONLY`) | Write queries |
| **2** | SQLFluff parse validation | Syntax injection |
| **3** | Regex block list (`DROP`, `ALTER`, `INSERT`, `DELETE`, etc.) | DDL/DML statements |
| **4** | Row limit (`max_rows`) + query timeout | Resource exhaustion |

### Schema Semantic Indexing

After schema discovery, table and column metadata is embedded and indexed in Qdrant. This enables `retrieve_relevant_schema()` — semantic search across your entire database schema to find the right tables for any natural-language question.

---

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_smoke_pipeline.py -v

# Run with detailed output
pytest -v --tb=long
```

### Test Suite

| File | Coverage |
|------|----------|
| `test_smoke_pipeline.py` | Domain detection, event creation, repository filtering, correlation engine, metrics |
| `test_reactive_pipeline_fixes.py` | Reactive pipeline edge cases and fixes |
| `test_refactor_fixes.py` | Refactor regression tests |
| `test_additional_fixes.py` | Additional bug fix verification |
| `test_database_connector.py` | Database connection CRUD |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes following existing code patterns
4. Run tests: `pytest`
5. Submit a pull request

### Code Style

- Python: Follow existing SOLID patterns (Service → Repository → Model)
- Frontend: Vue 3 Composition API, Tailwind CSS
- Packages: `backend.api/` (routes/schemas), `backend.core/` (config/DB), `backend.ia/` (LLM), `backend.services/` (business logic), `backend.persistencia/` (models/repos)

### Architecture Conventions

- **Services** are injected via constructor, never use hardcoded imports
- **Repositories** abstract database access behind interfaces
- **Tools** are created via factory functions with closure-bound parameters
- **Prompts** are loaded from Jinja2 templates in `backend/ia/prompts/templates/`
- **Sub-agents** register via `SubagentRegistry.register()` in `backend/ia/subagents/builders.py`

---

## Roadmap

- [x] Multi-agent orchestration with DeepAgents
- [x] Reactive event pipeline (Director-Analyst split)
- [x] Hybrid search (dense + sparse + rerank)
- [x] NL2SQL with auto-correction
- [x] MCP integrations (stdio + REST)
- [x] OAuth2 Gmail integration
- [x] Credential encryption at rest
- [x] Durable event job queue with startup recovery
- [x] SSE real-time event streaming
- [x] Domain auto-detection (rules + LLM)
- [x] Event correlation (dedup, flapping, grouping, suppression)
- [ ] Multi-tenant isolation
- [ ] WebSocket transport for MCP
- [ ] Custom dashboard widgets
- [ ] Scheduled event analysis
- [ ] Multi-model routing
- [ ] Audit log dashboard
- [ ] RBAC (role-based access control)

---

## License

MIT License — see [LICENSE](./LICENSE) for details.

---

**Built with `langchain`, `deepagents`, `fastapi`, `qdrant-client`, `sqlalchemy`, and `redis`.**
