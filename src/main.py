"""FastAPI application factory."""

import asyncio
import logging as std_logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
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
    # Initialize durable job tracker for reactive event pipeline
    try:
        from src.services.event_job_tracker import init_job_tracker, get_job_tracker
        from src.services.event_service import (
            _build_analysis_coro,
            _build_execution_coro,
        )

        await init_job_tracker()
        tracker = get_job_tracker()
        tracker.register_recovery_factory("analysis", _build_analysis_coro)
        tracker.register_recovery_factory("execution", _build_execution_coro)
        await tracker.recover_on_startup()
        logger.info("Event job tracker initialized and recovery completed")
    except Exception as exc:
        logger.warning("Event job tracker not started: %s", exc)
    # Keep strong references to background tasks so they are not GC'd
    app.state._background_tasks: set[asyncio.Task] = set()

    def _spawn_bg(coro, name: str) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        app.state._background_tasks.add(task)
        task.add_done_callback(app.state._background_tasks.discard)
        return task

    # Start Redis-backed SSE subscriber for multi-worker broadcast
    try:
        broadcast = get_event_broadcast()
        _spawn_bg(broadcast.start_subscriber(), "broadcast_subscriber")
    except Exception as exc:
        logger.warning("SSE broadcast subscriber not started: %s", exc)

    # Auto-seed integration catalog if empty
    try:
        from src.core.database import AsyncSessionLocal
        from src.integrations.catalog_seed import seed_integration_catalog

        async with AsyncSessionLocal() as session:
            created, _ = await seed_integration_catalog(session)
            if created:
                logger.info("Auto-seeded %d integration catalog entries on startup", created)
    except Exception as exc:
        logger.warning("Integration catalog auto-seed skipped: %s", exc)

    # Start correlation worker (periodic event dedup/grouping)
    try:
        from src.workers.correlation_worker import correlation_worker

        _spawn_bg(correlation_worker(), "correlation_worker")
        logger.info("Correlation worker started")
    except Exception as exc:
        logger.warning("Correlation worker not started: %s", exc)

    # Cleanup any orphaned stdio processes on shutdown
    try:
        from src.integrations.stdio_runner import StdioRunner
        app.state.stdio_runner = StdioRunner()
    except Exception as exc:
        logger.warning("Stdio runner init skipped: %s", exc)

    # Periodic stdio health-check / auto-restart
    async def _stdio_health_loop():
        while True:
            await asyncio.sleep(60)
            try:
                runner = getattr(app.state, "stdio_runner", None)
                if not runner:
                    continue
                from src.core.database import AsyncSessionLocal
                from src.integrations.repositories.integration_repository import IntegrationInstanceRepository
                async with AsyncSessionLocal() as session:
                    repo = IntegrationInstanceRepository(session)
                    instances = await repo.list_all()  # type: ignore[attr-defined]
                    for inst in instances:
                        if inst.process_pid and inst.process_status == "running":
                            if not runner.health_check(inst.process_pid):
                                logger.warning(
                                    "Stdio process for instance %s (pid=%s) unhealthy — restarting",
                                    inst.id,
                                    inst.process_pid,
                                )
                                result = runner.restart(inst.process_pid)
                                if result.status == "running":
                                    inst.process_pid = result.pid
                                    inst.process_status = "running"
                                else:
                                    inst.process_status = "error"
                                await session.commit()
            except Exception:
                logger.exception("Stdio health loop error")

    _spawn_bg(_stdio_health_loop(), "stdio_health_loop")

    yield
    try:
        await get_event_broadcast().stop_subscriber()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="EdgeBackend",
        description="Aura AI — Event-Driven AIOps Backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    if settings.is_dev:
        logger = std_logging.getLogger(__name__)
    # ── CORS ──
    # Allow all origins unconditionally.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # wildcard + credentials is a browser violation
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Authorization", "X-Request-ID"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger = std_logging.getLogger(__name__)
        body = await request.body()
        logger.error(f"422 Validation Error: {exc.errors()} - Body: {body}")
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    from src.api.v1.router import router as api_v1_router
    from src.api.v1.routers.webhooks import public_router as webhook_public_router
    app.include_router(api_v1_router)
    app.include_router(webhook_public_router)

    return app


app = create_app()
