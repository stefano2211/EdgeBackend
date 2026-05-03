"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging import configure_logging
from src.ia.llm_client import init_llm_client
from src.ia.memory import init_memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    try:
        client = await init_llm_client()
        app.state.llm_client = client
    except RuntimeError as exc:
        # Log but don't crash — backend can start without LLM if needed
        import logging
        logging.getLogger(__name__).warning("LLM client not available: %s", exc)
    try:
        await init_memory()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Memory layer not available: %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="EdgeBackend",
        description="Edge AI Monolith with Digital Optimus Architecture",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_dev else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    from src.api.v1.router import router as api_v1_router
    app.include_router(api_v1_router)

    return app


app = create_app()
