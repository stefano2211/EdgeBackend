# ── Builder Stage ─────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Copiar solo pyproject.toml (capa cacheada mientras no cambien deps)
COPY pyproject.toml ./

# 2. Crear src/ dummy para que pip install pueda resolver el paquete
RUN mkdir -p src/edgebackend && touch src/edgebackend/__init__.py

# 3. Instalar dependencias (CAPA CACHEADA — solo se invalida si cambia pyproject.toml)
#    Usamos install normal (NO -e) para que Docker cachee esta capa correctamente.
RUN pip install --upgrade pip && \
    pip install .

# 4. Copiar codigo real (solo invalida esta capa cuando cambia src/)
COPY src/ ./src/

# ── Production Stage ────────────────────────────────────────────
FROM python:3.13-slim AS production

WORKDIR /app

# Non-root user
RUN groupadd -r edge && useradd -r -g edge edge

# Runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Install Playwright browsers and system dependencies
RUN playwright install-deps chromium && playwright install chromium

# Copy app code
COPY src/ ./src/

# Create uploads and cache dirs
RUN mkdir -p /app/uploads /app/.cache/huggingface && chown -R edge:edge /app

ENV HF_HOME=/app/.cache/huggingface

# Copy and make entrypoint executable
COPY docker/backend-entrypoint.sh /app/docker/backend-entrypoint.sh
RUN chmod +x /app/docker/backend-entrypoint.sh && chown edge:edge /app/docker/backend-entrypoint.sh

USER edge

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/app/docker/backend-entrypoint.sh"]
