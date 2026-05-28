# AuraAI Monorepo Design Spec

**Date:** 2026-05-28
**Status:** Approved
**Goal:** Unify EdgeBackend (FastAPI) and IndustrialFrontend (Vue 3) into a single monorepo with one `docker compose up` command.

---

## 1. Problem Statement

Currently, the project consists of two separate repositories:
- `EdgeBackend`: FastAPI backend with PostgreSQL, Qdrant, Redis, MinIO, vLLM/Ollama
- `IndustrialFrontend`: Vue 3 + Vite frontend served by nginx

Users must clone both, configure separate `.env` files, and manage multiple Docker containers. The goal is a single-repository, single-command deployment model similar to OpenWebUI.

---

## 2. Target Architecture

### 2.1 Folder Structure

```
AuraAI/
├── docker-compose.yml          # All services (infra + app + optional nginx)
├── Dockerfile                  # Multi-stage: Node build → Python runtime
├── .env.example                # Template for environment variables
├── README.md                   # Quick start guide
├── .gitignore
│
├── frontend/                   # Vue 3 SPA (was IndustrialFrontend)
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── .env.production         # VITE_API_URL=''
│   └── public/
│
├── backend/                    # FastAPI app (was EdgeBackend/src/)
│   ├── main.py                 # App factory + StaticFiles mount
│   ├── core/
│   ├── api/
│   ├── ia/
│   ├── services/
│   ├── persistencia/
│   ├── integrations/
│   ├── workers/
│   └── init_db.py
│
├── nginx/
│   └── nginx.conf              # Reverse proxy (production profile)
│
└── docker/
    └── entrypoint.sh           # DB wait + migrate + uvicorn startup
```

### 2.2 Request Routing (Single Origin)

| Path | Handler | Purpose |
|------|---------|---------|
| `/api/v1/*` | FastAPI router | Authenticated API endpoints |
| `/webhooks/*` | FastAPI public_router | Public webhook reception |
| `/docs`, `/openapi.json` | FastAPI auto-generated | API documentation |
| `/health` | FastAPI health check | Health probe |
| `/*` | `StaticFiles` fallback | Vue 3 SPA (index.html) |

**Key insight:** FastAPI resolves exact paths first (`/api/v1/...`) before falling through to the `StaticFiles` wildcard mount. The SPA handles client-side routing (Vue Router history mode).

### 2.3 Build Pipeline

```
Stage 1: node:20-alpine (frontend-builder)
  1. COPY frontend/package*.json
  2. npm ci
  3. COPY frontend/src/ frontend/index.html frontend/vite.config.ts ...
  4. npm run build-only  →  outputs frontend/dist/

Stage 2: python:3.13-slim (backend-builder)
  1. COPY backend/ pyproject.toml
  2. uv pip install --system .

Stage 3: python:3.13-slim (production)
  1. COPY --from=Stage 1 /frontend/dist → /app/backend/static/
  2. COPY --from=Stage 2 /site-packages
  3. COPY backend/
  4. playwright install chromium
  5. CMD: /app/docker/entrypoint.sh
```

---

## 3. Changes by File

### 3.1 Backend (`backend/main.py`)

Add at the bottom of `create_app()`, **after** all API router includes:

```python
from fastapi.staticfiles import StaticFiles

# Serve built frontend SPA — must be last mount
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
```

### 3.2 Frontend (`frontend/.env.production`)

```bash
VITE_API_URL=''
VITE_DEMO_MODE=false
```

The frontend's `api.ts` already falls back to relative URLs when `baseURL` is empty:
```javascript
baseURL: import.meta.env.PROD ? (import.meta.env.VITE_API_URL || '') : '',
```

This means Axios requests like `api.post('/api/v1/auth/login', ...)` resolve to the same origin and port, eliminating CORS concerns entirely.

### 3.3 Docker Compose (`docker-compose.yml`)

Services:
1. `postgres` — unchanged
2. `qdrant` — unchanged
3. `redis` — unchanged
4. `minio` — unchanged
5. `app` — **new unified service** (replaces old `backend`)
   - Build context: `.` (monorepo root)
   - Dockerfile: `./Dockerfile`
   - Port: `8000:8000`
   - Depends on: postgres, qdrant, redis, minio
6. `nginx` — **optional**, profile `proxy`
   - Port: `80:80`
   - Reverse proxies `/api/*`, `/webhooks/*` to `app:8000`
   - Everything else to `app:8000` (StaticFiles)

### 3.4 Dockerfile (Multi-Stage)

```dockerfile
# syntax=docker/dockerfile:1

# ═══════════════════════════════════════════════════════════════════
# Stage 1: Build Frontend
# ═══════════════════════════════════════════════════════════════════
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline
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

### 3.5 nginx (`nginx/nginx.conf`)

```nginx
server {
    listen 80;
    server_name _;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # API & webhooks → backend
    location ~ ^/(api|webhooks|docs|health|openapi\.json)/ {
        proxy_pass http://app:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SPA static + fallback
    location / {
        proxy_pass http://app:8000;
    }
}
```

---

## 4. Development Workflow

### 4.1 First-Time Setup

```bash
git clone https://github.com/stefa/auraai.git
cd auraai
cp .env.example .env
docker compose up -d
```

Access: `http://localhost:8000`

### 4.2 With nginx (Production)

```bash
docker compose --profile proxy up -d
```

Access: `http://localhost`

### 4.3 Frontend Development (Hot Reload)

For frontend-only development without Docker rebuilds:

```bash
cd frontend
npm install
npm run dev
```

Vite proxy config forwards `/api/v1` and `/webhooks` to `http://localhost:8000`.

---

## 5. Data Flow

### User → Backend (API)
```
Browser → http://localhost:8000/api/v1/auth/login
          → FastAPI router (exact match)
```

### User → Frontend (SPA)
```
Browser → http://localhost:8000/chat
          → StaticFiles → /backend/static/index.html
          → Vue Router history mode loads ChatView
```

### Frontend → Backend (XHR/SSE)
```
Vue App → axios.get('/api/v1/events')  // relative URL
          → Same origin :8000
          → FastAPI
```

---

## 6. Error Handling & Edge Cases

| Case | Handling |
|------|----------|
| `static/` directory missing | `main.py` checks `static_dir.exists()` before mounting. If missing, API-only mode. |
| 404 on API endpoint | FastAPI returns JSON 404 (not SPA fallback) |
| 404 on unknown frontend route | StaticFiles serves `index.html` (Vue Router handles 404 client-side) |
| CORS | Not needed — same origin. CORS middleware can stay for dev safety. |
| Webhook public endpoint | Still works at `/webhooks/{slug}/receive` — no auth required |

---

## 7. Migration Notes

1. `EdgeBackend/src/` → `AuraAI/backend/`
2. `IndustrialFrontend/src/` → `AuraAI/frontend/src/`
3. `IndustrialFrontend/package.json` → `AuraAI/frontend/package.json`
4. `EdgeBackend/docker-compose.yml` services (postgres, qdrant, redis, minio) → preserved
5. `EdgeBackend/Dockerfile` → replaced by multi-stage `AuraAI/Dockerfile`
6. `EdgeBackend/src/main.py` → add StaticFiles mount
7. Git history: recommend archiving old repos and starting fresh, or using `git subtree` if history preservation is critical.

---

## 8. Approval

Design approved by user on 2026-05-28.
