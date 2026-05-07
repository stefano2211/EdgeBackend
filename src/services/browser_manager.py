"""Browser Manager — Legacy singleton wrapper around BrowserController.

Mantiene compatibilidad con código existente (web_browser.py tools)
mientras delega toda la lógica al nuevo BrowserController (SOLID).

TODO: Deprecar este archivo una vez que web_browser.py use BrowserController directamente.
"""

from __future__ import annotations

from typing import Optional

from src.core.logging import logging
from src.ia.browser import BrowserController

logger = logging.getLogger(__name__)


class BrowserManager:
    """Singleton backward-compatible wrapper."""
    _instance = None
    
    def __init__(self):
        self._controller: Optional[BrowserController] = None
    
    @classmethod
    def get_instance(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_controller(self) -> BrowserController:
        """Obtiene el BrowserController compartido (singleton)."""
        if self._controller is None:
            self._controller = BrowserController()
            # Conectar el emitter SSE al callback antiguo
            self._controller.set_event_emitter(self._legacy_emitter)
        return self._controller

    def _get_controller(self) -> BrowserController:
        """Backward-compatible alias."""
        return self.get_controller()

    async def start(self):
        await self._get_controller().start()

    async def get_page(self):
        ctrl = self._get_controller()
        await ctrl._ensure_started()
        return ctrl.page
        
    async def navigate(self, url: str) -> str:
        """Legacy: returns AOM text description."""
        return await self._get_controller().navigate_legacy(url)
        
    async def extract_aom(self) -> str:
        """Legacy: returns AOM text description."""
        return await self._get_controller().extract_aom_legacy()
        
    async def get_screenshot(self) -> str:
        """Legacy: returns base64 screenshot."""
        return await self._get_controller().get_screenshot_legacy()
            
    async def _emit_screenshot_event(self, action_msg: str, click_coords: tuple[int, int] = None):
        """Legacy SSE emitter — ahora delegado al controller."""
        # El controller ya emite automáticamente vía _legacy_emitter
        pass
        
    async def computer_action(
        self, 
        action: str, 
        coordinate: list[int] = None, 
        text: str = None, 
        element_id: int = None
    ) -> str:
        """Legacy computer action wrapper."""
        return await self._get_controller().computer_action_legacy(
            action=action,
            coordinate=coordinate,
            text=text,
            element_id=element_id,
        )

    # ── Emitter compatible con el código antiguo ──

    def _legacy_emitter(self, payload: dict) -> None:
        """Adapta eventos del nuevo controller al formato SSE antiguo."""
        from src.core.context import chat_stream_queue
        import asyncio

        q = chat_stream_queue.get()
        if not q:
            return

        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass
