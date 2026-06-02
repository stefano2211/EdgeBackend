"""EventJobTracker — durable, backpressured background job queue.

Replaces fire-and-forget asyncio.create_task with:
- Persistent job state in PostgreSQL (survives restarts)
- Concurrency limiting via asyncio.Semaphore
- Automatic retry with exponential backoff
- Orphan recovery on startup

Usage:
    from backend.services.event_job_tracker import get_job_tracker
    await get_job_tracker().enqueue(event_id=42, job_type="analysis", coro_factory=my_coro_factory)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal
from backend.persistencia.models.event_job import EventJob

logger = logging.getLogger(__name__)

_MAX_CONCURRENT: int = 5
_RECOVERY_AGE_MINUTES: int = 5


class EventJobTracker:
    """Global singleton that manages background event jobs with backpressure."""

    def __init__(self, max_concurrent: int = _MAX_CONCURRENT) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._internal_queue: asyncio.Queue[_JobSpec] = asyncio.Queue()
        self._drain_task: asyncio.Task | None = None
        self._shutdown = False
        self._recovery_factories: dict[str, Callable[[int], Coroutine[Any, Any, None]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def enqueue(
        self,
        event_id: int,
        job_type: str,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> EventJob:
        """Persist a job and schedule it for execution.

        Args:
            event_id: FK to events.id.
            job_type: "analysis" or "execution".
            coro_factory: Zero-argument async callable that performs the work.
                          Invoked inside the tracker with retry logic.
        """
        job = await self._persist_job(event_id, job_type)
        spec = _JobSpec(job.id, event_id, job_type, coro_factory, attempt=0)

        # Try to acquire semaphore immediately
        if self._semaphore.locked():
            logger.info("Job %s for event %s queued (semaphore full)", job_type, event_id)
            await self._internal_queue.put(spec)
        else:
            # Spawn immediately; if semaphore is exhausted the task will block
            asyncio.create_task(self._run_with_acquisition(spec))

        return job

    async def cancel(self, event_id: int, job_type: str) -> bool:
        """Mark a job as cancelled so it won't be retried."""
        async with AsyncSessionLocal() as session:
            job = await self._get_job(session, event_id, job_type)
            if job and job.status in ("queued", "running"):
                job.status = "cancelled"
                job.completed_at = datetime.utcnow()
                await session.commit()
                logger.info("Cancelled job %s for event %s", job_type, event_id)
                return True
            return False

    def register_recovery_factory(
        self,
        job_type: str,
        factory: Callable[[int], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a factory that can rebuild a coroutine from an event_id.

        Used during ``recover_on_startup`` to re-queue durable jobs after a
        process restart.
        """
        self._recovery_factories[job_type] = factory
        logger.info("Registered recovery factory for job_type='%s'", job_type)

    async def recover_on_startup(self) -> None:
        """Re-queue orphaned jobs that were running/queued before a restart."""
        async with AsyncSessionLocal() as session:
            cutoff = datetime.utcnow() - timedelta(minutes=_RECOVERY_AGE_MINUTES)
            stmt = (
                select(EventJob)
                .where(EventJob.status.in_(["running", "queued"]))
                .where(EventJob.updated_at < cutoff)
            )
            result = await session.execute(stmt)
            orphans = list(result.scalars().all())

        if not orphans:
            logger.info("No orphaned jobs to recover")
            return

        logger.info("Recovering %d orphaned job(s)", len(orphans))
        recovered = 0
        failed = 0
        for job in orphans:
            await self._reset_job(job.id)
            factory = self._recovery_factories.get(job.job_type)
            if factory:
                try:
                    await self.enqueue(job.event_id, job.job_type, lambda: factory(job.event_id))
                    recovered += 1
                except Exception:
                    logger.exception(
                        "Failed to recover job %s for event %s", job.job_type, job.event_id
                    )
                    await self._mark_failed(
                        job.id, "Recovery failed — exception during re-enqueue"
                    )
                    failed += 1
            else:
                await self._mark_failed(
                    job.id, "Orphaned after restart — no recovery factory registered"
                )
                failed += 1

        logger.info(
            "Recovery complete: %d re-queued, %d marked failed", recovered, failed
        )

    async def start(self) -> None:
        """Start the background queue drain worker."""
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain_loop())
            logger.info("EventJobTracker drain loop started")

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._shutdown = True
        if self._drain_task and not self._drain_task.done():
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------

    async def _run_with_acquisition(self, spec: _JobSpec) -> None:
        async with self._semaphore:
            await self._run_job(spec)

    async def _run_job_and_release(self, spec: _JobSpec) -> None:
        try:
            await self._run_job(spec)
        finally:
            self._semaphore.release()

    async def _run_job(self, spec: _JobSpec) -> None:
        await self._mark_running(spec.job_id)
        logger.info(
            "Running job %s for event %s (attempt %d)",
            spec.job_type,
            spec.event_id,
            spec.attempt + 1,
        )

        try:
            await spec.coro_factory()
            await self._mark_completed(spec.job_id)
            logger.info("Job %s for event %s completed", spec.job_type, spec.event_id)
        except Exception as exc:
            logger.exception(
                "Job %s for event %s failed (attempt %d)",
                spec.job_type,
                spec.event_id,
                spec.attempt + 1,
            )
            next_attempt = spec.attempt + 1
            max_attempts = await self._get_max_attempts(spec.job_id)

            if next_attempt < max_attempts:
                delay = 2 ** next_attempt  # 2, 4, 8 seconds
                logger.warning(
                    "Retrying job %s for event %s in %ds (%d/%d)",
                    spec.job_type,
                    spec.event_id,
                    delay,
                    next_attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(delay)
                spec.attempt = next_attempt
                await self._internal_queue.put(spec)
            else:
                await self._mark_failed(spec.job_id, str(exc))
                logger.error(
                    "Job %s for event %s exhausted all %d attempts",
                    spec.job_type,
                    spec.event_id,
                    max_attempts,
                )

    async def _drain_loop(self) -> None:
        """Background loop that pulls from internal queue when slots free up."""
        while not self._shutdown:
            try:
                spec = await asyncio.wait_for(self._internal_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if self._shutdown:
                break

            # Block until a semaphore slot is available
            await self._semaphore.acquire()
            try:
                asyncio.create_task(self._run_job_and_release(spec))
            except Exception:
                self._semaphore.release()
                raise

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _persist_job(self, event_id: int, job_type: str) -> EventJob:
        async with AsyncSessionLocal() as session:
            existing = await self._get_job(session, event_id, job_type)
            if existing:
                # Re-enqueue of an existing job -> reset state
                existing.status = "queued"
                existing.attempt = 0
                existing.started_at = None
                existing.completed_at = None
                existing.error_message = None
                existing.updated_at = datetime.utcnow()
                await session.commit()
                return existing

            job = EventJob(
                event_id=event_id,
                job_type=job_type,
                status="queued",
                attempt=0,
                max_attempts=3,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    async def _get_job(
        self, session: AsyncSession, event_id: int, job_type: str
    ) -> EventJob | None:
        stmt = (
            select(EventJob)
            .where(EventJob.event_id == event_id)
            .where(EventJob.job_type == job_type)
            .order_by(EventJob.id.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _mark_running(self, job_id: int) -> None:
        async with AsyncSessionLocal() as session:
            job = await session.get(EventJob, job_id)
            if job:
                job.status = "running"
                job.attempt += 1
                job.started_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                await session.commit()

    async def _mark_completed(self, job_id: int) -> None:
        async with AsyncSessionLocal() as session:
            job = await session.get(EventJob, job_id)
            if job:
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                await session.commit()

    async def _mark_failed(self, job_id: int, error_message: str) -> None:
        async with AsyncSessionLocal() as session:
            job = await session.get(EventJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = error_message
                job.completed_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                await session.commit()

    async def _reset_job(self, job_id: int) -> None:
        async with AsyncSessionLocal() as session:
            job = await session.get(EventJob, job_id)
            if job:
                job.status = "queued"
                job.attempt = 0
                job.started_at = None
                job.completed_at = None
                job.error_message = None
                job.updated_at = datetime.utcnow()
                await session.commit()

    async def _get_max_attempts(self, job_id: int) -> int:
        async with AsyncSessionLocal() as session:
            job = await session.get(EventJob, job_id)
            return job.max_attempts if job else 3


class _JobSpec:
    __slots__ = ("job_id", "event_id", "job_type", "coro_factory", "attempt")

    def __init__(
        self,
        job_id: int,
        event_id: int,
        job_type: str,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
        attempt: int = 0,
    ) -> None:
        self.job_id = job_id
        self.event_id = event_id
        self.job_type = job_type
        self.coro_factory = coro_factory
        self.attempt = attempt


# ── Global singleton ──
_tracker: EventJobTracker | None = None


async def init_job_tracker(max_concurrent: int = _MAX_CONCURRENT) -> EventJobTracker:
    """Initialize and start the global job tracker."""
    global _tracker
    if _tracker is None:
        _tracker = EventJobTracker(max_concurrent=max_concurrent)
        await _tracker.start()
    return _tracker


def get_job_tracker() -> EventJobTracker:
    if _tracker is None:
        raise RuntimeError(
            "EventJobTracker not initialized. Call init_job_tracker() in lifespan first."
        )
    return _tracker
