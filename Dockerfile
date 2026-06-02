# syntax=docker/dockerfile:1

# ═══════════════════════════════════════════════════════════════════
# Stage 1: Build Frontend
# ═══════════════════════════════════════════════════════════════════
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package*.json ./
# Usar caché de BuildKit para descargas de dependencias de NPM
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline --no-audit
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

# Configurar variables de entorno optimizadas de uv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copiar configuración de dependencias de python
COPY pyproject.toml uv.lock ./

# Instalar dependencias utilizando la caché de BuildKit y uv sync
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ═══════════════════════════════════════════════════════════════════
# Stage 3: Production Runtime
# ═══════════════════════════════════════════════════════════════════
FROM python:3.13-slim AS production

WORKDIR /app
RUN groupadd -r edge && useradd -m -r -g edge edge

# Instalar dependencias necesarias limpiando cachés en la misma capa
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl nodejs npm \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Copiar ejecutables globales de uv/uvx requeridos para MCP
COPY --from=backend-build /bin/uv /bin/uvx /bin/

# Copiar el entorno virtual asilado de Python
COPY --from=backend-build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copiar la aplicación frontend compilada de forma estática
COPY --from=frontend-build /app/frontend/dist /app/backend/static

# Copiar código fuente y entrypoint
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
