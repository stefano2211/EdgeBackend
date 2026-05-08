# AGENTS.md — EdgeBackend

## Quick Start

```bash
cp .env.example .env   # if .env missing
uv sync
docker compose up -d postgres qdrant redis minio
uvicorn src.main:app --reload
```

- Requires **Python 3.13** (see `.python-version`). Use `uv` for all package operations.
- No GPU needed for local dev; the backend warns if no LLM is reachable.

## Architecture

- **Entrypoint**: `src/main.py` → `uvicorn src.main:app`.
- **DB init**: `python -m src.init_db` creates SQLAlchemy tables. The Docker entrypoint runs this before starting uvicorn; for local dev run it manually once before the app.
- **Config**: `src/core/config.py` uses Pydantic Settings, reads `.env`, `extra="ignore"`.

## LLM Providers (mutually exclusive)

The backend auto-detects the running LLM engine unless `DEFAULT_LLM_PROVIDER` is forced.

| Provider | Docker Profile | Default Model | Base URL |
|----------|---------------|---------------|----------|
| vLLM | `--profile vllm` | `Qwen/Qwen3.5-9B-Instruct` | `http://vllm:8000/v1` |
| Ollama | `--profile ollama` | `qwen3.5:9b` | `http://ollama:11434/v1` |

- **Only one can run at a time** (they share the same GPU).
- `DEFAULT_LLM_PROVIDER=auto` prefers vLLM, then falls back to Ollama.
- For local dev without GPU, leave both disabled; the app starts but chat features will warn.

## Docker Compose Services

```bash
# Core infrastructure (always needed)
docker compose up -d postgres qdrant redis minio

# Add ONE LLM backend
docker compose --profile vllm up -d vllm
# OR
docker compose --profile ollama up -d ollama
```

## Testing

- `pytest` and `pytest-asyncio` are configured in `pyproject.toml` (`asyncio_mode = auto`, `testpaths = ["tests"]`).
- **No `tests/` directory exists yet.**

## Code Style & Tooling

- **No lint, format, or type-check tools are currently configured** (no `ruff`, `mypy`, `pre-commit` config found).

## Important Conventions

- **CORS**: `allow_origins=["*"]` with `allow_credentials=False` (wildcard + credentials is a browser violation).
- **Playwright**: Browsers are installed inside the Docker image (`playwright install chromium`). Local Playwright usage may require `playwright install` if running outside Docker.
- **Package boundaries**: `src/api/` (routes/schemas), `src/core/` (config, DB, security), `src/ia/` (LLM clients, prompts, tools, browser automation), `src/persistencia/` (SQLAlchemy models, vector store), `src/services/` (business logic), `src/workers/` (background jobs).
