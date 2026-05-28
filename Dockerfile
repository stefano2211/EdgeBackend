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
