"""Web browser tools for DeepAgents — Phase 2: Playwright Computer Use.

Implements Anthropic's 2026 Computer Use standard:
- Unified `computer` tool (action, coordinate, text).
- Extended for local LLMs via `element_id` and Accessibility Object Model (AOM).
- NEW (Fase 1): scroll, wait, hover, double_click, right_click, ask_user.
- NEW (Fase 2): Supports screenshot + AOM as multimodal input for VL-agent.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from typing import Optional, List

from src.core.logging import logging
from src.ia.browser import ActionSpec
from src.services.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

# Obtener controller del singleton BrowserManager para compartir estado SSE
_controller = BrowserManager.get_instance().get_controller()


async def _async_navigate(url: str) -> str:
    """Navigate to a URL and return the Accessibility Object Model (AOM)."""
    logger.info("Browser Navigating to: %s", url)
    state = await _controller.navigate(url)
    return state.aom.text_description


async def _async_get_dom() -> str:
    """Extracts and returns the interactive elements map of the current page."""
    logger.info("Browser Extracting DOM/AOM")
    state = await _controller.get_current_state()
    return state.aom.text_description


class ComputerToolArgs(BaseModel):
    action: str = Field(
        description=(
            "The action to perform. "
            "Available: 'click', 'double_click', 'right_click', 'hover', 'type', 'key', "
            "'scroll', 'wait', 'screenshot', 'ask_user'."
        )
    )
    coordinate: Optional[List[int]] = Field(
        default=None,
        description="(x, y) coordinates for click/hover. Optional if using element_id.",
    )
    text: Optional[str] = Field(
        default=None,
        description=(
            "The text to type (for 'type' action), the key to press (for 'key' action), "
            "or the prompt message (for 'ask_user' action)."
        ),
    )
    element_id: Optional[int] = Field(
        default=None,
        description="The numeric [ID] of the element to interact with, obtained from browser_navigate/browser_dom.",
    )
    direction: Optional[str] = Field(
        default=None,
        description="For 'scroll' action: 'up' or 'down'.",
    )
    amount: Optional[int] = Field(
        default=None,
        description="For 'scroll' action: pixels to scroll (default 500).",
    )
    seconds: Optional[int] = Field(
        default=None,
        description="For 'wait' action: seconds to wait.",
    )
    thread_id: Optional[str] = Field(
        default="default",
        description="Thread ID for human-in-the-loop (ask_user action).",
    )


async def _async_computer(
    action: str,
    coordinate: Optional[List[int]] = None,
    text: Optional[str] = None,
    element_id: Optional[int] = None,
    direction: Optional[str] = None,
    amount: Optional[int] = None,
    seconds: Optional[int] = None,
    thread_id: Optional[str] = "default",
) -> str:
    """Unified Computer Use Tool with extended action set."""
    logger.info("Computer Action: %s (id=%s, coord=%s)", action, element_id, coordinate)

    # Caso especial: ask_user bloquea esperando respuesta del humano
    if action == "ask_user":
        prompt = text or "Necesito tu ayuda."
        # Obtener thread_id del contexto de ejecución (más confiable que el LLM)
        from src.core.context import active_thread_id
        ctx_thread_id = active_thread_id.get()
        response = await _controller.ask_user(
            prompt=prompt,
            thread_id=ctx_thread_id or thread_id or "default",
            action_type="general",
        )
        return f"User response: {response}"

    params: dict = {}
    if coordinate:
        params["coordinate"] = coordinate
    if text:
        params["text"] = text
    if element_id is not None:
        params["element_id"] = element_id
    if direction:
        params["direction"] = direction
    if amount is not None:
        params["amount"] = amount
    if seconds is not None:
        params["seconds"] = seconds

    spec = ActionSpec(name=action, params=params)
    result = await _controller.execute_action(spec)
    return result.message


# ── Register async tools with DeepAgents/LangChain ──

browser_navigate = StructuredTool.from_function(
    coroutine=_async_navigate,
    name="browser_navigate",
    description=(
        "Navigate to a URL using a real headless Chrome browser. "
        "Returns a numbered list of interactive elements (AOM) on the page. "
        "Call this FIRST to load a page."
    ),
)

browser_dom = StructuredTool.from_function(
    coroutine=_async_get_dom,
    name="browser_dom",
    description=(
        "Re-scans the current page and returns a numbered list of interactive elements. "
        "Use this if the page changes dynamically after a click to get updated element IDs."
    ),
)

computer = StructuredTool.from_function(
    coroutine=_async_computer,
    name="computer",
    description=(
        "Standard Computer Use tool to interact with the browser. "
        "You MUST specify an 'action'.\n"
        "Actions: click, double_click, right_click, hover, type, key, scroll, wait, screenshot, ask_user.\n"
        "To target an element, provide its 'element_id' (from browser_navigate/browser_dom) OR its 'coordinate' [x, y]."
    ),
    args_schema=ComputerToolArgs,
)
