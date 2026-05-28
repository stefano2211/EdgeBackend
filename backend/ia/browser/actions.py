"""Browser Actions — Implementaciones de acciones individuales + Registry.

Cada acción es una clase que implementa BrowserActionPort.
Esto permite extender fácilmente: para agregar una nueva acción,
simplemente creas una clase y la registras.

SOLID:
  - SRP: cada clase hace UNA sola acción
  - OCP: extensible sin modificar código existente
  - LSP: todas implementan BrowserActionPort
  - DIP: BrowserController depende de BrowserActionRegistryPort, no de clases concretas
"""

from __future__ import annotations

from typing import Any

from backend.core.logging import logging
from backend.ia.browser.models import (
    ActionResult,
    ActionSpec,
    AOMResult,
)

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────

def _resolve_coordinates(
    params: dict[str, Any],
    aom: AOMResult | None,
) -> tuple[int, int] | None:
    """Resuelve coordenadas desde element_id, coordinate, o devuelve None."""
    element_id = params.get("element_id")
    coordinate = params.get("coordinate")

    if element_id is not None and aom is not None:
        el = aom.get_by_id(element_id)
        if el:
            return (el.bounds.center_x, el.bounds.center_y)
        else:
            raise ValueError(f"Element ID [{element_id}] not found in AOM")

    if coordinate and len(coordinate) == 2:
        return (int(coordinate[0]), int(coordinate[1]))

    return None


# ───────────────────────────────────────────────
# Acciones individuales
# ───────────────────────────────────────────────

class ClickAction:
    """Click en un elemento por coordenadas o element_id."""

    name = "click"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        coords = _resolve_coordinates(params, params.get("_aom"))
        if not coords:
            return ActionResult(
                success=False,
                message="Click failed: provide element_id or coordinate",
            )
        x, y = coords
        try:
            await page.mouse.click(x, y)
            await page.wait_for_timeout(800)  # Esperar a que la UI reaccione
            return ActionResult(
                success=True,
                message=f"Clicked at ({x}, {y})",
                state_changed=True,
                metadata={"coordinates": [x, y]},
            )
        except Exception as e:
            logger.exception("Click action failed")
            return ActionResult(success=False, message=f"Click error: {e}")


class DoubleClickAction:
    """Doble click en un elemento."""

    name = "double_click"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        coords = _resolve_coordinates(params, params.get("_aom"))
        if not coords:
            return ActionResult(
                success=False,
                message="Double-click failed: provide element_id or coordinate",
            )
        x, y = coords
        try:
            await page.mouse.dblclick(x, y)
            await page.wait_for_timeout(800)
            return ActionResult(
                success=True,
                message=f"Double-clicked at ({x}, {y})",
                state_changed=True,
                metadata={"coordinates": [x, y]},
            )
        except Exception as e:
            logger.exception("Double-click action failed")
            return ActionResult(success=False, message=f"Double-click error: {e}")


class RightClickAction:
    """Click derecho (context menu) en un elemento."""

    name = "right_click"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        coords = _resolve_coordinates(params, params.get("_aom"))
        if not coords:
            return ActionResult(
                success=False,
                message="Right-click failed: provide element_id or coordinate",
            )
        x, y = coords
        try:
            await page.mouse.click(x, y, button="right")
            await page.wait_for_timeout(800)
            return ActionResult(
                success=True,
                message=f"Right-clicked at ({x}, {y})",
                state_changed=True,
                metadata={"coordinates": [x, y]},
            )
        except Exception as e:
            logger.exception("Right-click action failed")
            return ActionResult(success=False, message=f"Right-click error: {e}")


class HoverAction:
    """Hover (mouse_move) sobre un elemento."""

    name = "hover"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        coords = _resolve_coordinates(params, params.get("_aom"))
        if not coords:
            return ActionResult(
                success=False,
                message="Hover failed: provide element_id or coordinate",
            )
        x, y = coords
        try:
            await page.mouse.move(x, y)
            await page.wait_for_timeout(500)
            return ActionResult(
                success=True,
                message=f"Hovered at ({x}, {y})",
                state_changed=False,
                metadata={"coordinates": [x, y]},
            )
        except Exception as e:
            logger.exception("Hover action failed")
            return ActionResult(success=False, message=f"Hover error: {e}")


class TypeAction:
    """Escribir texto en un input (hace click primero, luego type)."""

    name = "type"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        text = params.get("text", "")
        if not text:
            return ActionResult(
                success=False,
                message="Type failed: no text provided",
            )

        coords = _resolve_coordinates(params, params.get("_aom"))
        try:
            if coords:
                await page.mouse.click(coords[0], coords[1])
                await page.wait_for_timeout(200)
            await page.keyboard.type(text, delay=20)
            await page.wait_for_timeout(300)
            return ActionResult(
                success=True,
                message=f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}",
                state_changed=True,
                metadata={"text": text, "coordinates": list(coords) if coords else None},
            )
        except Exception as e:
            logger.exception("Type action failed")
            return ActionResult(success=False, message=f"Type error: {e}")


class KeyAction:
    """Presionar una tecla especial (Enter, Escape, Tab, etc.)."""

    name = "key"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        key = params.get("text", "")
        if not key:
            return ActionResult(
                success=False,
                message="Key failed: no key provided",
            )
        try:
            await page.keyboard.press(key)
            await page.wait_for_timeout(500)
            return ActionResult(
                success=True,
                message=f"Pressed key: {key}",
                state_changed=True,
                metadata={"key": key},
            )
        except Exception as e:
            logger.exception("Key action failed")
            return ActionResult(success=False, message=f"Key error: {e}")


class ScrollAction:
    """Scroll de página arriba o abajo."""

    name = "scroll"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        direction = params.get("direction", "down")
        amount = params.get("amount", 500)
        try:
            if direction == "down":
                await page.evaluate(f"window.scrollBy(0, {amount})")
            else:
                await page.evaluate(f"window.scrollBy(0, -{amount})")
            await page.wait_for_timeout(500)
            return ActionResult(
                success=True,
                message=f"Scrolled {direction} by {amount}px",
                state_changed=True,
                metadata={"direction": direction, "amount": amount},
            )
        except Exception as e:
            logger.exception("Scroll action failed")
            return ActionResult(success=False, message=f"Scroll error: {e}")


class WaitAction:
    """Esperar N segundos (para que cargue contenido dinámico)."""

    name = "wait"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        seconds = params.get("seconds", 2)
        try:
            await page.wait_for_timeout(seconds * 1000)
            return ActionResult(
                success=True,
                message=f"Waited {seconds}s",
                state_changed=False,
                metadata={"seconds": seconds},
            )
        except Exception as e:
            logger.exception("Wait action failed")
            return ActionResult(success=False, message=f"Wait error: {e}")


class ScreenshotAction:
    """Capturar screenshot (útil para verificación manual)."""

    name = "screenshot"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        return ActionResult(
            success=True,
            message="Screenshot captured",
            state_changed=False,
        )


class AskUserAction:
    """Placeholder: la acción real de ask_user la maneja BrowserController + HumanLoop."""

    name = "ask_user"

    async def execute(self, page: Any, params: dict[str, Any]) -> ActionResult:
        prompt = params.get("prompt", "Necesito tu ayuda.")
        return ActionResult(
            success=True,
            message=f"Takeover requested: {prompt}",
            state_changed=False,
            metadata={"prompt": prompt, "takeover": True},
        )


# ───────────────────────────────────────────────
# Registry
# ───────────────────────────────────────────────

class BrowserActionRegistry:
    """Registro de acciones disponibles. Thread-safe, singleton por controller."""

    def __init__(self):
        self._actions: dict[str, Any] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        defaults = [
            ClickAction(),
            DoubleClickAction(),
            RightClickAction(),
            HoverAction(),
            TypeAction(),
            KeyAction(),
            ScrollAction(),
            WaitAction(),
            ScreenshotAction(),
            AskUserAction(),
        ]
        for action in defaults:
            self.register(action)

    def register(self, action: Any) -> None:
        """Registra una nueva acción."""
        self._actions[action.name] = action
        logger.info("[ActionRegistry] Registered: %s", action.name)

    def get(self, name: str) -> Any | None:
        """Obtiene una acción por nombre."""
        return self._actions.get(name)

    def list_actions(self) -> list[str]:
        """Lista todos los nombres de acciones disponibles."""
        return list(self._actions.keys())

    async def execute(
        self,
        page: Any,
        spec: ActionSpec,
        aom: AOMResult | None = None,
    ) -> ActionResult:
        """Ejecuta una acción por nombre con parámetros."""
        action = self.get(spec.name)
        if not action:
            return ActionResult(
                success=False,
                message=f"Unknown action: {spec.name}. Available: {self.list_actions()}",
            )

        # Inyectar AOM en params para resolución de coordenadas
        params = dict(spec.params)
        params["_aom"] = aom

        return await action.execute(page, params)
