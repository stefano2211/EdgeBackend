"""Global ContextVars for the application."""

import asyncio
from contextvars import ContextVar

# Queue to multiplex SSE events (like screenshots) from tools directly into the chat stream.
chat_stream_queue: ContextVar[asyncio.Queue | None] = ContextVar("chat_stream_queue", default=None)

# Active thread ID during agent execution (used by tools to know current conversation context).
active_thread_id: ContextVar[str | None] = ContextVar("active_thread_id", default=None)
