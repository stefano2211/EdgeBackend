"""Browser Controller — Orquestador principal del navegador.

Responsabilidades:
  1. Ciclo de vida del navegador (start/stop)
  2. Navegación a URLs
  3. Ejecución de acciones con pre/post-screenshot
  4. Emisión de eventos SSE al frontend (screenshots, pensamientos)
  5. Integración con Human-in-the-Loop (Fase 3)

SOLID: Implementa BrowserControllerPort.
Depreca progresivamente a BrowserManager.
"""

from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.core.logging import logging
from src.ia.browser.models import (
    ActionResult,
    ActionSpec,
    BrowserState,
    SOMConfig,
    TakeoverRequest,
)
from src.ia.browser.perception import VisualPerceptionService
from src.ia.browser.actions import BrowserActionRegistry
from src.ia.browser.human_loop import HumanLoopService

logger = logging.getLogger(__name__)


class BrowserController:
    """Orquesta navegación, percepción y acciones con eventos SSE."""

    def __init__(
        self,
        perception: VisualPerceptionService | None = None,
        registry: BrowserActionRegistry | None = None,
        human_loop: HumanLoopService | None = None,
        som_config: SOMConfig | None = None,
    ):
        self.perception = perception or VisualPerceptionService(som_config)
        self.registry = registry or BrowserActionRegistry()
        self.human_loop = human_loop or HumanLoopService()
        self.som_config = som_config or SOMConfig()

        # Playwright state
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._started = False

        # SSE event emitter callback (inyectado desde fuera)
        self._event_emitter: Any | None = None

        # Thread ID activo para human-in-the-loop
        self._active_thread_id: str | None = None

    # ── Propiedades ──

    @property
    def is_started(self) -> bool:
        return self._started

    def set_active_thread_id(self, thread_id: str) -> None:
        """Establece el thread ID activo para HITL."""
        self._active_thread_id = thread_id

    @property
    def active_thread_id(self) -> str | None:
        return self._active_thread_id

    @property
    def current_url(self) -> str:
        if self._page:
            return self._page.url
        return ""

    @property
    def page(self) -> Page | None:
        return self._page

    # ── Ciclo de vida ──

    async def start(self) -> None:
        if self._started:
            return
        logger.info("[BrowserController] Starting Playwright...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context(
            viewport={
                "width": self.som_config.viewport_width,
                "height": self.som_config.viewport_height,
            },
            device_scale_factor=1,
        )
        self._page = await self._context.new_page()
        self._started = True
        logger.info("[BrowserController] Browser ready")

    async def stop(self) -> None:
        if not self._started:
            return
        logger.info("[BrowserController] Stopping...")
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._started = False
        logger.info("[BrowserController] Stopped")

    async def _ensure_started(self) -> None:
        if not self._started:
            await self.start()

    # ── Navegación ──

    async def navigate(self, url: str) -> BrowserState:
        await self._ensure_started()
        logger.info("[BrowserController] Navigating to: %s", url)
        await self._page.goto(url, wait_until="networkidle")
        await self._page.wait_for_timeout(1000)
        state = await self.perception.get_full_state(self._page, draw_som=True)
        await self._emit_state(state, action_msg="Page loaded")
        return state

    async def get_current_state(self) -> BrowserState:
        await self._ensure_started()
        return await self.perception.get_full_state(self._page, draw_som=True)

    # ── Acciones ──

    async def execute_action(self, spec: ActionSpec) -> ActionResult:
        await self._ensure_started()
        logger.info("[BrowserController] Action: %s params=%s", spec.name, spec.params)

        # Pre-action: pensamiento + captura de estado
        await self.emit_thought(f"Ejecutando: {spec.name} — {spec.params}")
        pre_state = await self.perception.get_full_state(self._page, draw_som=True)
        await self._emit_state(pre_state, action_msg=f"Before: {spec.name}")

        # Ejecutar acción
        result = await self.registry.execute(
            page=self._page,
            spec=spec,
            aom=pre_state.aom,
        )

        # Post-action: pensamiento + captura de estado
        await self.emit_thought(f"Resultado: {result.message}")

        if result.state_changed or spec.name in ("screenshot",):
            await self._page.wait_for_timeout(800)
            post_state = await self.perception.get_full_state(self._page, draw_som=True)
            await self._emit_state(post_state, action_msg=result.message)
        else:
            await self._emit_state(pre_state, action_msg=result.message)

        return result

    # ── SSE Event Emission ──

    def set_event_emitter(self, emitter: Any) -> None:
        """Establece el callback para emitir eventos SSE.
        
        emitter debe ser una función async o sync con firma:
            async def emitter(payload: dict) -> None
        """
        self._event_emitter = emitter

    async def _emit_state(self, state: BrowserState, action_msg: str = "") -> None:
        """Emite un evento SSE con screenshot al frontend."""
        if not self._event_emitter:
            return

        payload = {
            "b64": state.screenshot.base64_image,
            "step": 1,
            "has_omniparser": state.screenshot.has_som,
            "action": action_msg,
            "url": state.url,
            "title": state.title,
        }

        try:
            if asyncio.iscoroutinefunction(self._event_emitter):
                await self._event_emitter({"screenshot": payload})
            else:
                self._event_emitter({"screenshot": payload})
        except Exception:
            logger.debug("[BrowserController] Event emitter failed, ignoring")

    async def emit_thought(self, thought: str) -> None:
        """Emite el 'pensamiento' del agente al frontend (Modo Cinema)."""
        if not self._event_emitter:
            return
        try:
            payload = {"thought": thought}
            if asyncio.iscoroutinefunction(self._event_emitter):
                await self._event_emitter(payload)
            else:
                self._event_emitter(payload)
        except Exception:
            logger.debug("[BrowserController] Thought emitter failed, ignoring")

    # ── Human-in-the-Loop (Fase 3) ──

    async def ask_user(self, prompt: str, thread_id: str, action_type: str = "general") -> str:
        """Pausa ejecución y espera respuesta del usuario vía HumanLoopService."""
        # Usar el thread_id activo del controller si está disponible
        effective_thread_id = self._active_thread_id or thread_id or "default"
        logger.info("[BrowserController] Takeover requested for thread=%s: %s", effective_thread_id, prompt)

        # 1. Emitir evento SSE al frontend para que muestre el takeover
        if self._event_emitter:
            try:
                takeover_payload = {
                    "type": "takeover",
                    "message": prompt,
                    "thread_id": effective_thread_id,
                    "action_type": action_type,
                }
                if asyncio.iscoroutinefunction(self._event_emitter):
                    await self._event_emitter(takeover_payload)
                else:
                    self._event_emitter(takeover_payload)
            except Exception:
                logger.debug("[BrowserController] Takeover emitter failed, ignoring")

        # 2. Bloquear esperando respuesta del usuario
        request = TakeoverRequest(
            thread_id=effective_thread_id,
            prompt=prompt,
            action_type=action_type,
        )
        response = await self.human_loop.ask_user(request)
        return response.response

    # ── Compatibilidad con BrowserManager (transición) ──

    async def navigate_legacy(self, url: str) -> str:
        """Wrapper compatible con la firma antigua de BrowserManager.navigate()."""
        state = await self.navigate(url)
        return state.aom.text_description

    async def get_screenshot_legacy(self) -> str:
        """Wrapper compatible con BrowserManager.get_screenshot()."""
        state = await self.get_current_state()
        return state.screenshot.base64_image

    async def extract_aom_legacy(self) -> str:
        """Wrapper compatible con BrowserManager.extract_aom()."""
        state = await self.get_current_state()
        return state.aom.text_description

    async def computer_action_legacy(
        self,
        action: str,
        coordinate: list[int] | None = None,
        text: str | None = None,
        element_id: int | None = None,
    ) -> str:
        """Wrapper compatible con BrowserManager.computer_action().
        
        Mapea nombres de acciones antiguos a nuevos.
        """
        name_map = {
            "mouse_move": "hover",
            "left_click": "click",
        }
        spec_name = name_map.get(action, action)

        params: dict[str, Any] = {}
        if coordinate:
            params["coordinate"] = coordinate
        if text:
            params["text"] = text
        if element_id is not None:
            params["element_id"] = element_id

        spec = ActionSpec(name=spec_name, params=params)
        result = await self.execute_action(spec)
        return result.message
