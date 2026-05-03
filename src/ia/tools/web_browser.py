"""Web browser tools for DeepAgents — Phase 1: async HTTP + BeautifulSoup.

Phase 2 will add Playwright for JS-heavy pages and login flows.

All tools are async-registered via StructuredTool.from_function(coroutine=...)
to avoid blocking the event loop when DeepAgents invokes them.
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import StructuredTool

from src.core.logging import logging

logger = logging.getLogger(__name__)

# Simple session-scoped browser state
_browser_state: dict = {"current_url": None, "last_html": None}

# Shared async client (lifecycle-managed externally if needed)
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    return _client


async def _async_navigate(url: str) -> str:
    """Navigate to a URL and return the page text content."""
    try:
        client = _get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style/nav/footer tags
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        _browser_state["current_url"] = url
        _browser_state["last_html"] = resp.text

        max_len = 8000
        if len(text) > max_len:
            text = text[:max_len] + f"\n\n[... truncated, {len(text) - max_len} chars remaining]"

        title = soup.title.string if soup.title else "N/A"
        return f"URL: {url}\nTitle: {title}\n\n{text}"
    except Exception as e:
        logger.exception("Browser navigate failed: %s", e)
        return f"[Failed to navigate to {url}: {e}]"


async def _async_click(selector: str) -> str:
    """Click an element on the current page (Phase 1 stub)."""
    url = _browser_state.get("current_url", "none")
    return (
        f"[Note: Click on '{selector}' requires Phase 2 Playwright implementation. "
        f"Current page: {url}]"
    )


async def _async_type(selector: str, text: str) -> str:
    """Type text into an input field on the current page (Phase 1 stub)."""
    url = _browser_state.get("current_url", "none")
    return (
        f"[Note: Type '{text}' into '{selector}' requires Phase 2 Playwright. "
        f"Current page: {url}]"
    )


async def _async_screenshot() -> str:
    """Take a screenshot of the current page (Phase 1 stub)."""
    url = _browser_state.get("current_url", "none")
    return (
        f"[Note: Screenshots require Phase 2 Playwright implementation. "
        f"Current page: {url}]"
    )


async def _async_extract_text() -> str:
    """Extract all visible text from the current page."""
    html = _browser_state.get("last_html")
    if not html:
        return "[No page loaded. Call browser_navigate first.]"

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:8000]


# ── Register async tools with DeepAgents/LangChain ──

browser_navigate = StructuredTool.from_function(
    coroutine=_async_navigate,
    name="browser_navigate",
    description=(
        "Navigate to a URL and return the page text content. "
        "Use for loading a web page before clicking, typing, or extracting text. "
        "Returns visible text truncated to 8000 chars. "
        "If the page requires JavaScript, note it for Phase 2 Playwright."
    ),
)

browser_click = StructuredTool.from_function(
    coroutine=_async_click,
    name="browser_click",
    description=(
        "Click an element on the current page by CSS selector. "
        "Phase 1 stub: returns a note. Phase 2 will use Playwright for real interaction."
    ),
)

browser_type = StructuredTool.from_function(
    coroutine=_async_type,
    name="browser_type",
    description=(
        "Type text into an input field on the current page by CSS selector. "
        "Phase 1 stub: returns a note. Phase 2 will use Playwright for real interaction."
    ),
)

browser_screenshot = StructuredTool.from_function(
    coroutine=_async_screenshot,
    name="browser_screenshot",
    description=(
        "Take a screenshot of the current page. "
        "Phase 1 stub: returns a note. Phase 2 will use Playwright for real screenshots."
    ),
)

browser_extract_text = StructuredTool.from_function(
    coroutine=_async_extract_text,
    name="browser_extract_text",
    description=(
        "Extract all visible text from the current page. "
        "Uses the HTML cached by the last browser_navigate call."
    ),
)
