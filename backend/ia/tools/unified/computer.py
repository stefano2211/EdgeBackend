"""Unified Computer Use tool factory.

Replaces: web_browser.py + reactive_web_browser.py
"""

from __future__ import annotations

from typing import Optional, List

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from backend.core.logging import logging
from backend.ia.browser import ActionSpec
from backend.services.browser_manager import BrowserManager

logger = logging.getLogger(__name__)


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
        description="Text to type, key to press, or prompt message for ask_user.",
    )
    element_id: Optional[int] = Field(
        default=None,
        description="Numeric [ID] of the element from browser_navigate/browser_dom.",
    )
    direction: Optional[str] = Field(
        default=None,
        description="For 'scroll': 'up' or 'down'.",
    )
    amount: Optional[int] = Field(
        default=None,
        description="For 'scroll': pixels to scroll (default 500).",
    )
    seconds: Optional[int] = Field(
        default=None,
        description="For 'wait': seconds to wait.",
    )
    thread_id: Optional[str] = Field(
        default="default",
        description="Thread ID for human-in-the-loop (ask_user).",
    )


def create_computer_tool(instance: str = "chat") -> StructuredTool:
    """Create a Computer Use tool bound to a BrowserManager instance.

    Args:
        instance: BrowserManager key — "chat" for proactive, "reactive" for events.

    Returns:
        StructuredTool with navigate, dom, and computer actions.
    """
    controller = BrowserManager.get_instance(instance).get_controller()

    async def _async_navigate(url: str) -> str:
        logger.info("[%s Browser] Navigating to: %s", instance, url)
        state = await controller.navigate(url)
        return state.aom.text_description

    async def _async_get_dom() -> str:
        logger.info("[%s Browser] Extracting DOM/AOM", instance)
        state = await controller.get_current_state()
        return state.aom.text_description

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
        logger.info(
            "[%s Computer] Action: %s (id=%s, coord=%s, text=%s)",
            instance,
            action,
            element_id,
            coordinate,
            text,
        )

        if action == "ask_user":
            prompt = text or "Necesito tu ayuda."
            ctrl_thread_id = controller.active_thread_id
            effective = ctrl_thread_id or thread_id or "default"
            response = await controller.ask_user(
                prompt=prompt,
                thread_id=effective,
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
        result = await controller.execute_action(spec)
        return result.message

    # We return a dict of tools or a single tool? DeepAgents expects individual tools.
    # The orchestrator factory registers them separately. For convenience, we return the
    # computer tool as the primary interface, and callers can also create navigate/dom.
    # But to keep compatibility, we return a single StructuredTool named "computer".

    return StructuredTool.from_function(
        coroutine=_async_computer,
        name="computer",
        description=(
            "Standard Computer Use tool to interact with the browser. "
            "Actions: click, double_click, right_click, hover, type, key, scroll, wait, screenshot, ask_user.\n"
            "Target by element_id (from browser_navigate/browser_dom) OR coordinate [x, y]."
        ),
        args_schema=ComputerToolArgs,
    )


def create_browser_navigate_tool(instance: str = "chat") -> StructuredTool:
    """Create a browser_navigate tool for a named instance."""
    controller = BrowserManager.get_instance(instance).get_controller()

    async def _navigate(url: str) -> str:
        logger.info("[%s Browser] Navigating to: %s", instance, url)
        state = await controller.navigate(url)
        return state.aom.text_description

    return StructuredTool.from_function(
        coroutine=_navigate,
        name="browser_navigate",
        description="Navigate to a URL and return the AOM of interactive elements.",
    )


def create_browser_dom_tool(instance: str = "chat") -> StructuredTool:
    """Create a browser_dom tool for a named instance."""
    controller = BrowserManager.get_instance(instance).get_controller()

    async def _get_dom() -> str:
        logger.info("[%s Browser] Extracting DOM/AOM", instance)
        state = await controller.get_current_state()
        return state.aom.text_description

    return StructuredTool.from_function(
        coroutine=_get_dom,
        name="browser_dom",
        description="Re-scan the current page and return updated interactive elements.",
    )
