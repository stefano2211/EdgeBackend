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
RUN groupadd -r edge && useradd -m -r -g edge edge

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=backend-build /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=backend-build /usr/local/bin /usr/local/bin
COPY --from=frontend-build /app/frontend/dist /app/backend/static
COPY --chown=edge:edge backend/ ./backend/
COPY --chown=edge:edge docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

RUN mkdir -p /app/uploads /app/.cache/huggingface \
    && chown -R edge:edge /app /home/edge

ENV HF_HOME=/app/.cache/huggingface

USER edge

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/app/docker/entrypoint.sh"]
