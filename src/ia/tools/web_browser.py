"""Web browser tools for DeepAgents — Phase 2: Playwright Computer Use.

Implements Anthropic's 2026 Computer Use standard:
- Unified `computer` tool (action, coordinate, text).
- Extended for local LLMs via `element_id` and Accessibility Object Model (AOM).
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from typing import Optional, List

from src.core.logging import logging
from src.services.browser_manager import BrowserManager

logger = logging.getLogger(__name__)

# Single persistent manager instance
_manager = BrowserManager.get_instance()


async def _async_navigate(url: str) -> str:
    """Navigate to a URL and return the Accessibility Object Model (AOM)."""
    logger.info("Browser Navigating to: %s", url)
    return await _manager.navigate(url)


async def _async_get_dom() -> str:
    """Extracts and returns the interactive elements map of the current page."""
    logger.info("Browser Extracting DOM/AOM")
    return await _manager.extract_aom()


class ComputerToolArgs(BaseModel):
    action: str = Field(
        description="The action to perform: 'mouse_move', 'left_click', 'type', 'key', 'screenshot'."
    )
    coordinate: Optional[List[int]] = Field(
        default=None,
        description="(x, y) coordinates for mouse_move or left_click. Optional if using element_id.",
    )
    text: Optional[str] = Field(
        default=None,
        description="The text to type (for 'type' action) or the key to press (for 'key' action).",
    )
    element_id: Optional[int] = Field(
        default=None,
        description="Fallback for local LLMs: The numeric [ID] of the element to interact with, obtained from browser_dom.",
    )


async def _async_computer(action: str, coordinate: Optional[List[int]] = None, text: Optional[str] = None, element_id: Optional[int] = None) -> str:
    """Unified Anthropic-style Computer Use Tool."""
    logger.info("Computer Action: %s (id=%s, coord=%s)", action, element_id, coordinate)
    return await _manager.computer_action(
        action=action,
        coordinate=coordinate,
        text=text,
        element_id=element_id
    )


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
        "You MUST specify an 'action' ('mouse_move', 'left_click', 'type', 'key', 'screenshot'). "
        "To target an element, provide its 'element_id' (from browser_navigate/browser_dom) OR its 'coordinate' [x, y]."
    ),
    args_schema=ComputerToolArgs,
)
