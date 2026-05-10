"""Browser Manager — Named-instance factory for isolated browser controllers.

Supports multiple isolated browser instances (e.g. "chat" vs "reactive")
so that concurrent pipelines do not share state, screenshots, or SSE queues.

Backward-compatible: get_instance() without args returns the legacy "chat" instance.
"""

from __future__ import annotations

import threading
from typing import Optional

from src.core.logging import logging
from src.ia.browser import BrowserController

logger = logging.getLogger(__name__)


class BrowserManager:
    """Thread-safe factory of named BrowserController wrappers."""

    _instances: dict[str, "BrowserManager"] = {}
    _lock = threading.Lock()

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._controller: Optional[BrowserController] = None
        self._controller_lock = threading.Lock()
        self._event_emitter = self._legacy_emitter

    @classmethod
    def get_instance(cls, name: str = "chat") -> "BrowserManager":
        """Retrieve or create a named BrowserManager instance.

        Args:
            name: Instance key. Use "chat" for the chat pipeline and
                  "reactive" for the reactive/event pipeline.
        """
        if name not in cls._instances:
            with cls._lock:
                if name not in cls._instances:
                    cls._instances[name] = cls(name)
                    logger.info("[BrowserManager] Created new instance: %s", name)
        return cls._instances[name]

    def get_controller(self) -> BrowserController:
        """Obtain the isolated BrowserController for this named instance."""
        if self._controller is None:
            with self._controller_lock:
                if self._controller is None:
                    self._controller = BrowserController()
                    self._controller.set_event_emitter(self._event_emitter)
        return self._controller

    def set_event_emitter(self, emitter) -> None:
        """Replace the SSE emitter callback for this instance.

        If the controller is already created, the emitter is updated live.
        """
        self._event_emitter = emitter
        if self._controller is not None:
            self._controller.set_event_emitter(emitter)

    # ── Backward-compatible aliases (delegate to "chat" instance) ──

    def _get_controller(self) -> BrowserController:
        return self.get_controller()

    async def start(self):
        await self._get_controller().start()

    async def get_page(self):
        ctrl = self._get_controller()
        await ctrl._ensure_started()
        return ctrl.page

    async def navigate(self, url: str) -> str:
        return await self._get_controller().navigate_legacy(url)

    async def extract_aom(self) -> str:
        return await self._get_controller().extract_aom_legacy()

    async def get_screenshot(self) -> str:
        return await self._get_controller().get_screenshot_legacy()

    async def computer_action(
        self,
        action: str,
        coordinate: list[int] = None,
        text: str = None,
        element_id: int = None,
    ) -> str:
        return await self._get_controller().computer_action_legacy(
            action=action,
            coordinate=coordinate,
            text=text,
            element_id=element_id,
        )

    # ── Legacy SSE emitter (used by the "chat" instance by default) ──

    def _legacy_emitter(self, payload: dict) -> None:
        """Adapta eventos del controller al formato SSE antiguo del chat."""
        from src.core.context import chat_stream_queue
        import asyncio

        q = chat_stream_queue.get()
        if not q:
            return

        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass
