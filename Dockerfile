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

# Runtime deps (including Playwright system deps for Chromium)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create app dirs and set ownership BEFORE switching to edge
RUN mkdir -p /app/uploads /app/.cache/huggingface /home/edge/.cache/ms-playwright \
    && chown -R edge:edge /app /home/edge

ENV HF_HOME=/app/.cache/huggingface
ENV PLAYWRIGHT_BROWSERS_PATH=/home/edge/.cache/ms-playwright

# Copy app code as edge user
COPY --chown=edge:edge src/ ./src/
COPY --chown=edge:edge docker/backend-entrypoint.sh /app/docker/backend-entrypoint.sh
RUN chmod +x /app/docker/backend-entrypoint.sh

# Switch to edge and install Playwright browsers
USER edge
RUN playwright install chromium

# Verify browser installation
RUN python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()"

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/app/docker/backend-entrypoint.sh"]
