"""Reactive web browser tools for DeepAgents — uses isolated reactive browser instance.

Implements Anthropic's 2026 Computer Use standard with an isolated
BrowserController from BrowserManager("reactive"), completely separate
from the chat browser.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from typing import Optional, List

from src.core.logging import logging
from src.ia.browser import ActionSpec
from src.services.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

# Obtener controller del BrowserManager "reactive" (instancia aislada)
_reactive_controller = BrowserManager.get_instance("reactive").get_controller()


async def _async_reactive_navigate(url: str) -> str:
    """Navigate to a URL using the reactive browser and return the AOM."""
    logger.info("[Reactive Browser] Navigating to: %s", url)
    state = await _reactive_controller.navigate(url)
    return state.aom.text_description


async def _async_reactive_get_dom() -> str:
    """Extracts and returns the interactive elements map of the current page."""
    logger.info("[Reactive Browser] Extracting DOM/AOM")
    state = await _reactive_controller.get_current_state()
    return state.aom.text_description


class ReactiveComputerToolArgs(BaseModel):
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


async def _async_reactive_computer(
    action: str,
    coordinate: Optional[List[int]] = None,
    text: Optional[str] = None,
    element_id: Optional[int] = None,
    direction: Optional[str] = None,
    amount: Optional[int] = None,
    seconds: Optional[int] = None,
    thread_id: Optional[str] = "default",
) -> str:
    """Unified Computer Use Tool with extended action set (reactive browser)."""
    logger.info("[Reactive Computer] Action: %s (id=%s, coord=%s, text=%s)", action, element_id, coordinate, text)

    if action == "ask_user":
        prompt = text or "Necesito tu ayuda."
        ctrl_thread_id = _reactive_controller.active_thread_id
        effective_thread_id = ctrl_thread_id or thread_id or "default"
        response = await _reactive_controller.ask_user(
            prompt=prompt,
            thread_id=effective_thread_id,
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
    result = await _reactive_controller.execute_action(spec)
    return result.message


# ── Register async tools with DeepAgents/LangChain ──

reactive_browser_navigate = StructuredTool.from_function(
    coroutine=_async_reactive_navigate,
    name="reactive_browser_navigate",
    description=(
        "Navigate to a URL using the REACTIVE isolated headless Chrome browser. "
        "Returns a numbered list of interactive elements (AOM) on the page. "
        "Call this FIRST to load a page for the reactive event pipeline."
    ),
)

reactive_browser_dom = StructuredTool.from_function(
    coroutine=_async_reactive_get_dom,
    name="reactive_browser_dom",
    description=(
        "Re-scans the current page using the reactive browser and returns a numbered list of interactive elements. "
        "Use this if the page changes dynamically after a click to get updated element IDs."
    ),
)

reactive_computer = StructuredTool.from_function(
    coroutine=_async_reactive_computer,
    name="reactive_computer",
    description=(
        "Standard Computer Use tool to interact with the REACTIVE browser. "
        "You MUST specify an 'action'.\n"
        "Actions: click, double_click, right_click, hover, type, key, scroll, wait, screenshot, ask_user.\n"
        "To target an element, provide its 'element_id' (from reactive_browser_navigate/reactive_browser_dom) OR its 'coordinate' [x, y]."
    ),
    args_schema=ReactiveComputerToolArgs,
)
