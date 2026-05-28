"""Human-in-the-Loop Service — Pausa ejecución y espera input del usuario.

Usa un diccionario en memoria con asyncio.Event para señalización.
Para deployment multi-worker, reemplazar por Redis pub/sub.

SOLID: Implementa HumanLoopPort.
"""

from __future__ import annotations

import asyncio
from typing import Any

from backend.core.logging import logging
from backend.ia.browser.models import TakeoverRequest, TakeoverResponse

logger = logging.getLogger(__name__)


class HumanLoopService:
    """Gestiona pausas para input del usuario durante ejecución del agente."""

    def __init__(self):
        # thread_id -> {"event": asyncio.Event, "response": str|None, "prompt": str}
        self._pending: dict[str, dict[str, Any]] = {}

    async def ask_user(self, request: TakeoverRequest) -> TakeoverResponse:
        """Bloquea hasta que el usuario responda vía resume().
        
        Flujo:
          1. Crea un asyncio.Event para este thread_id
          2. Emite evento SSE type=takeover (vía callback externo)
          3. Espera (con timeout) a que resume() establezca la respuesta
          4. Devuelve la respuesta
        """
        event = asyncio.Event()
        self._pending[request.thread_id] = {
            "event": event,
            "response": None,
            "prompt": request.prompt,
        }

        logger.info("[HumanLoop] Takeover started for thread=%s: %s", request.thread_id, request.prompt)

        # Esperar respuesta (timeout: 10 minutos)
        try:
            await asyncio.wait_for(event.wait(), timeout=600)
        except asyncio.TimeoutError:
            logger.warning("[HumanLoop] Takeover timeout for thread=%s", request.thread_id)
            self._cleanup(request.thread_id)
            return TakeoverResponse(
                thread_id=request.thread_id,
                response="[TIMEOUT: No user response received]",
            )

        data = self._pending.get(request.thread_id)
        response_text = data["response"] if data else "[ERROR: Response lost]"
        self._cleanup(request.thread_id)

        logger.info("[HumanLoop] Takeover completed for thread=%s", request.thread_id)
        return TakeoverResponse(
            thread_id=request.thread_id,
            response=response_text,
        )

    def can_resume(self, thread_id: str) -> bool:
        """¿Hay un takeover pendiente para este thread?"""
        return thread_id in self._pending

    async def resume(self, response: TakeoverResponse) -> None:
        """Reanuda un thread pausado con la respuesta del usuario."""
        data = self._pending.get(response.thread_id)
        if not data:
            logger.warning("[HumanLoop] No pending takeover for thread=%s", response.thread_id)
            return

        data["response"] = response.response
        data["event"].set()
        logger.info("[HumanLoop] Resume signal sent for thread=%s", response.thread_id)

    def _cleanup(self, thread_id: str) -> None:
        self._pending.pop(thread_id, None)

    async def notify(self, message: str, thread_id: str) -> None:
        """Notificación no bloqueante (para información al usuario)."""
        logger.info("[HumanLoop] Notify thread=%s: %s", thread_id, message)
        # En Fase 4 se emitirá como SSE type=thought
