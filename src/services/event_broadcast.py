"""Global SSE broadcast manager for event updates.

Shared across all EventService instances so that events created in one
request are broadcast to all connected SSE clients, regardless of which
worker handled the connection.
"""

import asyncio
import json
from typing import AsyncIterator


class EventBroadcastManager:
    """Singleton that manages asyncio.Queue listeners for SSE streams."""

    def __init__(self) -> None:
        self._listeners: list[asyncio.Queue] = []

    def connect(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._listeners.append(queue)
        return queue

    def disconnect(self, queue: asyncio.Queue) -> None:
        if queue in self._listeners:
            self._listeners.remove(queue)

    async def broadcast(self, payload: dict) -> None:
        data = f"data: {json.dumps(payload)}\n\n"
        dead: list[asyncio.Queue] = []
        for queue in self._listeners:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(queue)
        for q in dead:
            self.disconnect(q)

    def broadcast_nowait(self, payload: dict) -> None:
        """Fire-and-forget broadcast (safe to call from sync contexts)."""
        data = f"data: {json.dumps(payload)}\n\n"
        dead: list[asyncio.Queue] = []
        for queue in self._listeners:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(queue)
        for q in dead:
            self.disconnect(q)


# Global singleton instance
_broadcast_manager = EventBroadcastManager()


def get_event_broadcast() -> EventBroadcastManager:
    return _broadcast_manager
