# AuraAI Monorepo Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify EdgeBackend and IndustrialFrontend into a single monorepo (`AuraAI`) with one `docker compose up` deployment.

**Architecture:** Multi-stage Dockerfile builds Vue frontend and embeds it into FastAPI backend static files. FastAPI serves API at `/api/v1/*` and webhooks at `/webhooks/*`, with SPA fallback for all other routes. Optional nginx reverse proxy for production.

**Tech Stack:** Vue 3 + Vite (frontend), FastAPI + Python 3.13 (backend), Docker + Docker Compose, PostgreSQL, Qdrant, Redis, MinIO

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/main.py` | Modify | Add `StaticFiles` mount for built SPA |
| `frontend/.env.production` | Modify | Set `VITE_API_URL=''` for relative URLs |
| `Dockerfile` | Create | Multi-stage: Node build → Python runtime |
| `docker-compose.yml` | Modify | Add unified `app` service, keep infra services |
| `nginx/nginx.conf` | Create | Reverse proxy for production profile |
| `docker/entrypoint.sh` | Modify | Update module path to `backend.main:app` |
| `pyproject.toml` | Modify | Update package find directory to `backend` |
| `.env.example` | Create | Template with all required env vars |
| `README.md` | Modify | Quick start: `git clone → cp .env.example .env → docker compose up` |

---

## Task 1: Restructure Backend Directory

**Files:**
- Create: `backend/` (move from `src/`)
- Modify: `pyproject.toml`
- Modify: `docker/entrypoint.sh`

**Context:** Move all backend source from `src/` to `backend/` so the monorepo root can hold both `backend/` and `frontend/`.

- [ ] **Step 1.1: Move backend source files**

Move all directories and files from `src/` to `backend/`:
- `src/main.py` → `backend/main.py`
- `src/core/` → `backend/core/`
- `src/api/` → `backend/api/`
- `src/ia/` → `backend/ia/`
- `src/services/` → `backend/services/`
- `src/persistencia/` → `backend/persistencia/`
- `src/integrations/` → `backend/integrations/`
- `src/workers/` → `backend/workers/`
- `src/init_db.py` → `backend/init_db.py`

Then remove the empty `src/` directory.

- [ ] **Step 1.2: Update pyproject.toml package discovery**

Change:
```toml
[tool.setuptools.packages.find]
where = ["src"]
```
to:
```toml
[tool.setuptools.packages.find]
where = ["backend"]
```

- [ ] **Step 1.3: Update docker/entrypoint.sh module path**

Change:
```bash
python -m src.init_db
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
```
to:
```bash
python -m backend.init_db
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## Task 2: Add Frontend Static Files Mount to FastAPI

**Files:**
- Modify: `backend/main.py`

**Context:** After all API routers are registered, mount the built frontend SPA so unknown routes fall through to `index.html`.

- [ ] **Step 2.1: Import StaticFiles and Path**

Add at the top of `backend/main.py`:
```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles
```

- [ ] **Step 2.2: Add static files mount before returning app**

After:
```python
app.include_router(webhook_public_router)
```

Add:
```python
    # Serve built frontend SPA (Vue Router history mode)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
```

---

## Task 3: Copy Frontend into Monorepo

**Files:**
- Create: `frontend/` (copy from IndustrialFrontend)

**Context:** Copy all frontend source files into the monorepo root under `frontend/`.

- [ ] **Step 3.1: Create frontend directory and copy all files**

Copy from `IndustrialFrontend/` to `frontend/`:
- `src/` (all Vue components, views, services, stores)
- `package.json`
- `package-lock.json`
- `vite.config.ts`
- `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`
- `index.html`
- `env.d.ts`
- `public/`
- `.gitignore`

- [ ] **Step 3.2: Update frontend/.env.production**

Set content to:
```bash
VITE_API_URL=''
VITE_DEMO_MODE=false
```

This forces relative URLs so the frontend calls the same origin as itself.

---

## Task 4: Create Multi-Stage Dockerfile

**Files:**
- Create: `Dockerfile`

**Context:** Single Dockerfile that builds the frontend with Node.js, then packages it into the Python runtime.

- [ ] **Step 4.1: Write the multi-stage Dockerfile**

```dockerfile
# syntax=docker/dockerfile:1

# ═══════════════════════════════════════════════════════════════════
# Stage 1: Build Frontend
# ═══════════════════════════════════════════════════════════════════
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit
COPY frontend/ ./
RUN npm run build-only

# ═══════════════════════════════════════════════════════════════════
# Stage 2: Build Backend Dependencies
# ═══════════════════════════════════════════════════════════════════
FROM python:3.13-slim AS backend-build

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml ./
RUN mkdir -p backend/edgebackend && touch backend/edgebackend/__init__.py
RUN uv pip install --system .

# ═══════════════════════════════════════════════════════════════════
# Stage 3: Production Runtime
# ═══════════════════════════════════════════════════════════════════
FROM python:3.13-slim AS production

WORKDIR /app
RUN groupadd -r edge && useradd -r -g edge edge

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl libglib2.0-0 libnss3 libnspr4 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libxcb1 \
    libxkbcommon0 libx11-6 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-build /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=backend-build /usr/local/bin /usr/local/bin
COPY --from=frontend-build /app/frontend/dist /app/backend/static
COPY --chown=edge:edge backend/ ./backend/
COPY --chown=edge:edge docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

RUN mkdir -p /app/uploads /app/.cache/huggingface /home/edge/.cache/ms-playwright \
    && chown -R edge:edge /app /home/edge

ENV HF_HOME=/app/.cache/huggingface
ENV PLAYWRIGHT_BROWSERS_PATH=/home/edge/.cache/ms-playwright

USER edge
RUN playwright install chromium

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/app/docker/entrypoint.sh"]
```

---

## Task 5: Update Docker Compose

**Files:**
- Modify: `docker-compose.yml`

**Context:** Replace the old `backend` service with a unified `app` service that builds from the monorepo Dockerfile. Keep all infrastructure services unchanged. Add optional `nginx` service with Docker profile.

- [ ] **Step 5.1: Replace backend service with unified app service**

Replace the `backend:` service block with:

```yaml
  # ── AuraAI Unified App ─────────────────────────────────────────
  app:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    container_name: aura-app
    restart: unless-stopped
    user: root
    depends_on:
      - postgres
      - qdrant
      - redis
      - minio
    ports:
      - "8000:8000"
    environment:
      APP_ENV: ${APP_ENV:-production}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-edge}:${POSTGRES_PASSWORD:-edge}@postgres:5432/${POSTGRES_DB:-edgebackend}
      DATABASE_POOL_SIZE: 20
      QDRANT_URL: http://qdrant:6333
      QDRANT_API_KEY: ${QDRANT_API_KEY:-}
      # vLLM
      VLLM_ENABLED: ${VLLM_ENABLED:-False}
      VLLM_BASE_URL: http://vllm:8000/v1
      VLLM_API_KEY: ${VLLM_API_KEY:-}
      VLLM_MODEL: ${VLLM_MODEL_NAME:-Qwen/Qwen3.5-9B-Instruct}
      VLLM_MAX_TOKENS: 8192
      # Ollama
      OLLAMA_ENABLED: ${OLLAMA_ENABLED:-True}
      OLLAMA_BASE_URL: http://ollama:11434/v1
      OLLAMA_MODEL: ${OLLAMA_MODEL:-llama3.1:8b}
      OLLAMA_MAX_TOKENS: 8192
      # Default provider
      DEFAULT_LLM_PROVIDER: ${DEFAULT_LLM_PROVIDER:-ollama}
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      JWT_ALGORITHM: HS256
      ACCESS_TOKEN_EXPIRE_MINUTES: 30
      # MinIO / S3 Object Storage
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY:-minioadmin}
      MINIO_BUCKET: ${MINIO_BUCKET:-documents}
      MINIO_SECURE: "false"
      MINIO_REGION: us-east-1
      MAX_UPLOAD_SIZE: 104857600
      # OAuth
      OAUTH_REDIRECT_URL: ${OAUTH_REDIRECT_URL:-http://localhost:8000/api/v1/integrations/oauth/callback}
      GMAIL_CLIENT_ID: ${GMAIL_CLIENT_ID:-}
      GMAIL_CLIENT_SECRET: ${GMAIL_CLIENT_SECRET:-}
      # Maquinaria API
      MAQUINARIA_API_URL: ${MAQUINARIA_API_URL:-http://apiejemplo-api-1:7000}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - edge-network
      - apiejemplo_default
    deploy:
      resources:
        limits:
          memory: 8G
```

- [ ] **Step 5.2: Update nginx service dependency**

Change the `nginx` service `depends_on` from `backend` to `app`.

---

## Task 6: Create nginx Reverse Proxy Config

**Files:**
- Create: `nginx/nginx.conf`

**Context:** nginx sits in front of the app for production deployments (optional profile). It proxies API and webhook routes, and forwards everything else to the SPA.

- [ ] **Step 6.1: Write nginx.conf**

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Enable gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # API, webhooks, docs, health → backend
    location ~ ^/(api|webhooks|docs|health|openapi\.json)/ {
        proxy_pass http://app:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA fallback (Vue Router history mode)
    location / {
        proxy_pass http://app:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

---

## Task 7: Create Environment Template

**Files:**
- Create: `.env.example`

**Context:** Single template file documenting all environment variables needed to run the stack.

- [ ] **Step 7.1: Write .env.example**

```bash
# ═══════════════════════════════════════════════════════════════════
# AuraAI — Environment Configuration Template
# Copy this file to .env and fill in your values
# ═══════════════════════════════════════════════════════════════════

# ── Core ──
APP_ENV=production
LOG_LEVEL=INFO

# ── PostgreSQL ──
POSTGRES_USER=edge
POSTGRES_PASSWORD=edge
POSTGRES_DB=edgebackend

# ── Qdrant ──
QDRANT_API_KEY=

# ── Redis ──
# (no additional config needed — uses defaults)

# ── MinIO ──
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents

# ── LLM Provider ──
# "auto" | "vllm" | "ollama"
DEFAULT_LLM_PROVIDER=ollama

# vLLM (only if using --profile vllm)
VLLM_ENABLED=False
VLLM_API_KEY=
VLLM_MODEL_NAME=Qwen/Qwen3.5-9B-Instruct

# Ollama (only if using --profile ollama)
OLLAMA_ENABLED=True
OLLAMA_MODEL=llama3.1:8b

# ── Security ──
# Generate a strong secret key for JWT signing
SECRET_KEY=change-me-to-a-random-secret-key-min-32-chars
EVENT_INGEST_API_KEY=change-me-event-ingest-key

# ── OAuth (Gmail integration) ──
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
OAUTH_REDIRECT_URL=http://localhost:8000/api/v1/integrations/oauth/callback

# ── External APIs ──
MAQUINARIA_API_URL=http://apiejemplo-api-1:7000
```

---

## Task 8: Update README.md

**Files:**
- Modify: `README.md`

**Context:** Clear quick-start instructions for the monorepo.

- [ ] **Step 8.1: Write README quick start**

Replace the existing README with:

```markdown
# AuraAI

Event-Driven AIOps Platform — Unified Backend + Frontend

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd auraai

# 2. Configure
cp .env.example .env
# Edit .env with your secrets

# 3. Start infrastructure + app
docker compose up -d

# 4. Open http://localhost:8000
```

## Development

```bash
# Frontend hot-reload (separate terminal)
cd frontend
npm install
npm run dev

# Backend only (API at :8000)
docker compose up -d postgres qdrant redis minio
uvicorn backend.main:app --reload
```

## Architecture

- **Frontend:** Vue 3 + Vite + Tailwind CSS
- **Backend:** FastAPI + SQLAlchemy + LangGraph
- **Infra:** PostgreSQL, Qdrant (vectors), Redis (Pub/Sub), MinIO (objects)
- **LLM:** vLLM or Ollama (mutually exclusive GPU profiles)
```

---

## Task 9: Verify Build

**Files:**
- N/A (integration test)

**Context:** Ensure the Docker image builds successfully and the app starts.

- [ ] **Step 9.1: Build Docker image**

```bash
docker build -t auraai:test .
```

Expected: Image builds without errors. Frontend dist is copied into `/app/backend/static`.

- [ ] **Step 9.2: Start infrastructure**

```bash
docker compose up -d postgres qdrant redis minio
```

- [ ] **Step 9.3: Start app and test endpoints**

```bash
docker compose up -d app
```

Test:
- `curl http://localhost:8000/health` → `{"status":"ok"}`
- `curl http://localhost:8000/` → Returns `index.html` (Vue SPA)
- `curl http://localhost:8000/api/v1/auth/me` → 401 (expected — no token)

---

## Task 10: Cleanup Old Artifacts

**Files:**
- Delete: `src/` (after confirming move to `backend/`)
- Delete: Old `Dockerfile` (replaced by root-level multi-stage)

**Context:** Remove duplicate/outdated files after migration.

- [ ] **Step 10.1: Remove old src/ directory**

```bash
rm -rf src/
```

- [ ] **Step 10.2: Remove old backend Dockerfile**

The old `Dockerfile` at repo root is replaced by the new multi-stage `Dockerfile`.

---

## Spec Coverage Checklist

| Spec Requirement | Plan Task |
|------------------|-----------|
| Monorepo folder structure | Tasks 1, 3 |
| Frontend builds inside Docker | Task 4 (Stage 1) |
| Backend serves static files | Task 2 |
| Relative API URLs (no hardcoded IP) | Task 3.2 |
| Single `docker compose up` | Tasks 4, 5 |
| Optional nginx reverse proxy | Tasks 5.1, 6 |
| `.env.example` template | Task 7 |
| Updated README | Task 8 |
| Build verification | Task 9 |
| Cleanup | Task 10 |

---

## Self-Review

**Placeholder scan:** No TBD, TODO, or vague instructions. Every step has exact file paths, exact code, and exact commands.

**Type consistency:** Module references updated consistently (`src.main:app` → `backend.main:app`, `src.init_db` → `backend.init_db`).

**No gaps:** All spec requirements mapped to tasks. No missing pieces.
