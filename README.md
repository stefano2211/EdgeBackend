# AuraAI

Event-Driven AIOps Platform — Unified Backend + Frontend in a single Docker Compose.

## Architecture

Monorepo with clear separation:
- **Frontend** — Vue 3 + Vite + Tailwind CSS (served as static files by FastAPI)
- **Backend** — FastAPI + SQLAlchemy + LangGraph + DeepAgents
- **Infra** — PostgreSQL, Qdrant (vectors), Redis (Pub/Sub), MinIO (objects)
- **LLM** — vLLM or Ollama (mutually exclusive GPU profiles)

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd auraai

# 2. Configure
cp .env.example .env
# Edit .env with your secrets (at minimum SECRET_KEY)

# 3. Start everything
docker compose up -d

# 4. Open http://localhost:8000
```

That's it. The frontend SPA and backend API run from the same container on port `8000`.

## Development

### Frontend hot-reload (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Vite proxy forwards `/api/v1` and `/webhooks` to `http://localhost:8000`.

### Backend only (API at :8000)

```bash
# Infrastructure
docker compose up -d postgres qdrant redis minio

# Local backend
uv sync
uvicorn backend.main:app --reload
```

## LLM Backends

| Provider | Docker Profile | Default Model | When to use |
|----------|---------------|---------------|-------------|
| **vLLM** | `--profile vllm` | `Qwen/Qwen3.5-9B-Instruct` | Production: LoRA, tool calling, high throughput |
| **Ollama** | `--profile ollama` | `qwen3.5:9b` | Quick testing, fast model swaps |

> ⚠️ **Only one can run at a time** — they share the same GPU.

```bash
# With vLLM
docker compose --profile vllm up -d

# With Ollama
docker compose --profile ollama up -d
```

## Optional: Nginx Reverse Proxy

For production with gzip and caching:

```bash
docker compose --profile proxy up -d
```

Access at `http://localhost` (port 80).

## Environment Variables

See `.env.example` for all available options.

## Tech Stack

- **Frontend:** Vue 3, Vite, Tailwind CSS, Axios, markdown-it
- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2.0 (async), LangChain, DeepAgents
- **Vector DB:** Qdrant
- **Object Storage:** MinIO (S3-compatible)
- **Cache/Queue:** Redis
- **Automation:** MCP integrations for external system actions
