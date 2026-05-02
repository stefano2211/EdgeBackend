# EdgeBackend

Edge AI Monolith Backend — FastAPI + vLLM (Qwen3.5) + PostgreSQL + Qdrant.

## Architecture

Modular monolith (modulith) with clear separation of business layers:
- **Auth** — JWT authentication
- **Chat/Proactive** — AI chat with RAG, MCP, and System 1/2 agents
- **Events/Reactive** — Event ingestion, analysis, and agentic orchestration
- **Knowledge** — Document collections and vector search
- **Models** — LLM configuration and discovery
- **Tools** — MCP sources and tool management
- **Admin** — User management, analytics, settings

## LLM Backends

The backend supports **two mutually-exclusive LLM inference engines**. The backend auto-detects which one is running — no `.env` edits needed.

| Provider | Docker Profile | Default Model | When to use |
|----------|---------------|---------------|-------------|
| **vLLM** | `--profile vllm` | `Qwen/Qwen3.5-9B-Instruct` | Production: LoRA, tool calling, high throughput |
| **Ollama** | `--profile ollama` | `qwen3.5:9b` | Quick testing, fast model swaps |

> ⚠️ **Only one can run at a time** — they share the same GPU. Use the appropriate Docker profile.

### Quick Start — vLLM (recommended for production)

```bash
cp .env.example .env

# Start infrastructure + vLLM
docker compose up -d postgres qdrant redis
docker compose --profile vllm up -d vllm

# Backend auto-detects vLLM at http://vllm:8000/v1
```

### Quick Start — Ollama

```bash
cp .env.example .env

# Stop vLLM if running
docker compose --profile vllm down vllm

# Start Ollama
docker compose up -d postgres qdrant redis
docker compose --profile ollama up -d ollama

# Backend auto-detects Ollama at http://ollama:11434/v1
```

### Local development (no GPU)

```bash
uv sync

# Infrastructure only
docker compose up -d postgres qdrant redis

# Backend starts and warns that no LLM is available
uvicorn src.main:app --reload
```
