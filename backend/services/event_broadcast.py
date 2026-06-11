"""Global SSE broadcast manager for event updates.

Uses Redis Pub/Sub so events published by one worker/process are delivered
to all connected SSE clients across all workers.
"""

import asyncio
import json

from backend.core.config import settings
from backend.core.logging import logging

logger = logging.getLogger(__name__)


class EventBroadcastManager:
    """Manages local asyncio.Queue listeners and publishes/subscribes via Redis."""

    _redis_channel = "sse:events"

    def __init__(self) -> None:
        self._listeners: list[asyncio.Queue] = []
        self._redis_client = None
        self._pubsub = None
        self._subscribe_task: asyncio.Task | None = None

    def _ensure_redis(self):
        if self._redis_client is None:
            try:
                import redis.asyncio as redis_async
                self._redis_client = redis_async.from_url(
                    settings.REDIS_URL, decode_responses=True
                )
            except Exception as exc:
                logger.warning("Redis unavailable for SSE broadcast: %s", exc)
        return self._redis_client

    def connect(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._listeners.append(queue)
        return queue

    def disconnect(self, queue: asyncio.Queue) -> None:
        if queue in self._listeners:
            self._listeners.remove(queue)


    def _put_local(self, data: str) -> None:
        dead: list[asyncio.Queue] = []
        for queue in self._listeners:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(queue)
        for q in dead:
            self.disconnect(q)

    async def broadcast(self, payload: dict) -> None:
        data = f"data: {json.dumps(payload)}\n\n"
        # Always publish to Redis (other workers will pick it up)
        redis = self._ensure_redis()
        if redis:
            try:
                await redis.publish(self._redis_channel, data)
            except Exception as exc:
                logger.warning("Redis publish failed: %s", exc)
        # Also push to local listeners (same-worker optimisation)
        self._put_local(data)

    def broadcast_nowait(self, payload: dict) -> None:
        """Fire-and-forget broadcast (safe to call from sync contexts)."""
        data = f"data: {json.dumps(payload)}\n\n"
        redis = self._ensure_redis()
        if redis:
            try:
                asyncio.get_running_loop().create_task(
                    redis.publish(self._redis_channel, data)
                )
            except RuntimeError:
                pass  # no event loop in sync context; skip redis publish
        self._put_local(data)

    async def start_subscriber(self) -> None:
        """Start background Redis subscriber to feed local queues."""
        self._subscribe_task = asyncio.current_task()
        redis = self._ensure_redis()
        if not redis:
            logger.warning("Redis not available; SSE is limited to single-worker mode")
            return
        try:
            self._pubsub = redis.pubsub()
            await self._pubsub.subscribe(self._redis_channel)
            logger.info("Redis SSE subscriber started on channel %s", self._redis_channel)
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    self._put_local(message["data"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Redis SSE subscriber crashed: %s", exc)

    async def stop_subscriber(self) -> None:
        if self._subscribe_task and not self._subscribe_task.done():
            self._subscribe_task.cancel()
            try:
                await self._subscribe_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe(self._redis_channel)
        if self._redis_client:
            await self._redis_client.close()


# Global singleton instance
_broadcast_manager = EventBroadcastManager()


def get_event_broadcast() -> EventBroadcastManager:
    return _broadcast_manager
