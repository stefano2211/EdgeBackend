"""Web browser tools for DeepAgents — Phase 1: HTTP requests + BeautifulSoup.

Phase 2 will add Playwright for JS-heavy pages and login flows.
"""

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from src.core.logging import logging

logger = logging.getLogger(__name__)

# Simple session-scoped browser state
_browser_state: dict = {"current_url": None, "last_html": None}


@tool
def browser_navigate(url: str) -> str:
    """Navigate to a URL and return the page text content.

    Args:
        url: The full URL to navigate to (e.g. "https://example.com").

    Returns:
        Extracted visible text from the page, truncated to 8000 chars.
        If the page requires JavaScript, returns a note to use screenshots (Phase 2).
    """
    try:
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
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


@tool
def browser_click(selector: str) -> str:
    """Click an element on the current page.

    Phase 1: returns a note. Phase 2 will use Playwright for real interaction.

    Args:
        selector: CSS selector of the element to click.

    Returns:
        Note about the action and current page state.
    """
    url = _browser_state.get("current_url", "none")
    return (
        f"[Note: Click on '{selector}' requires Phase 2 Playwright implementation. "
        f"Current page: {url}]"
    )


@tool
def browser_type(selector: str, text: str) -> str:
    """Type text into an input field on the current page.

    Phase 1: returns a note. Phase 2 will use Playwright for real interaction.

    Args:
        selector: CSS selector of the input field.
        text: Text to type into the field.

    Returns:
        Note about the action and current page state.
    """
    url = _browser_state.get("current_url", "none")
    return (
        f"[Note: Type '{text}' into '{selector}' requires Phase 2 Playwright. "
        f"Current page: {url}]"
    )


@tool
def browser_screenshot() -> str:
    """Take a screenshot of the current page.

    Phase 1: returns a note. Phase 2 will use Playwright for real screenshots.

    Returns:
        Note about screenshot capability and current page state.
    """
    url = _browser_state.get("current_url", "none")
    return (
        f"[Note: Screenshots require Phase 2 Playwright implementation. "
        f"Current page: {url}]"
    )


@tool
def browser_extract_text() -> str:
    """Extract all visible text from the current page.

    Returns cached text from the last browser_navigate call.

    Returns:
        Extracted text, or a note if no page has been loaded.
    """
    html = _browser_state.get("last_html")
    if not html:
        return "[No page loaded. Call browser_navigate first.]"

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return text[:8000]
