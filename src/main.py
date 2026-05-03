"""FastAPI application factory."""

import asyncio
import logging as std_logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging import configure_logging
from src.ia.llm_client import init_llm_client
from src.ia.memory import init_memory
from src.services.event_broadcast import get_event_broadcast


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger = std_logging.getLogger(__name__)
    try:
        client = await init_llm_client()
        app.state.llm_client = client
    except RuntimeError as exc:
        logger.warning("LLM client not available: %s", exc)
    try:
        await init_memory()
    except Exception as exc:
        logger.warning("Memory layer not available: %s", exc)
    # Start Redis-backed SSE subscriber for multi-worker broadcast
    try:
        broadcast = get_event_broadcast()
        asyncio.create_task(broadcast.start_subscriber())
    except Exception as exc:
        logger.warning("SSE broadcast subscriber not started: %s", exc)
    yield
    try:
        await get_event_broadcast().stop_subscriber()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="EdgeBackend",
        description="Edge AI Monolith with Digital Optimus Architecture",
        version="0.1.0",
        lifespan=lifespan,
    )

    if settings.is_dev:
        logger = std_logging.getLogger(__name__)
    # ── CORS ──
    # In dev, allow common frontend ports; in prod, use configured origins only.
    origins = settings.CORS_ORIGINS
    if settings.is_dev:
        origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not settings.is_dev,  # wildcard + credentials is a browser violation
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Authorization", "X-Request-ID"],
    )

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    from src.api.v1.router import router as api_v1_router
    app.include_router(api_v1_router)

    return app


app = create_app()
