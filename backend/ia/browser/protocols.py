"""Protocols (interfaces) for the browser automation subsystem.

Defines contracts that implementations must satisfy.
Follows Dependency Inversion Principle: higher-level modules depend
on these abstractions, not concrete implementations.
"""

from __future__ import annotations

from typing import Protocol, Any

from backend.ia.browser.models import (
    AOMResult,
    ScreenshotResult,
    BrowserState,
    ActionResult,
    ActionSpec,
    SOMConfig,
    TakeoverRequest,
    TakeoverResponse,
)


class VisualPerceptionPort(Protocol):
    """Extract visual information from the browser page."""

    async def capture_screenshot(
        self,
        draw_som: bool = True,
        config: SOMConfig | None = None,
    ) -> ScreenshotResult:
        """Capture screenshot. Optionally draw Set-of-Mark boxes."""
        ...

    async def extract_aom(self) -> AOMResult:
        """Extract Accessibility Object Model (interactive elements)."""
        ...

    async def get_full_state(
        self,
        draw_som: bool = True,
    ) -> BrowserState:
        """Capture complete browser state: screenshot + AOM."""
        ...


class BrowserActionPort(Protocol):
    """Single browser action implementation."""

    name: str

    async def execute(
        self,
        page: Any,  # Playwright Page
        params: dict[str, Any],
    ) -> ActionResult:
        """Execute the action on the given page."""
        ...


class BrowserActionRegistryPort(Protocol):
    """Registry of available browser actions."""

    def register(self, action: BrowserActionPort) -> None:
        """Register an action implementation."""
        ...

    def get(self, name: str) -> BrowserActionPort | None:
        """Get action by name."""
        ...

    def list_actions(self) -> list[str]:
        """List all available action names."""
        ...

    async def execute(
        self,
        page: Any,
        spec: ActionSpec,
    ) -> ActionResult:
        """Execute an action by name with given params."""
        ...


class HumanLoopPort(Protocol):
    """Human-in-the-loop interaction handler."""

    async def ask_user(self, request: TakeoverRequest) -> TakeoverResponse:
        """Pause execution and wait for human input."""
        ...

    async def notify(self, message: str, thread_id: str) -> None:
        """Send a non-blocking notification to the user."""
        ...

    def can_resume(self, thread_id: str) -> bool:
        """Check if a thread has a pending human response."""
        ...

    async def resume(self, response: TakeoverResponse) -> None:
        """Resume a paused thread with human response."""
        ...


class BrowserControllerPort(Protocol):
    """High-level browser orchestrator."""

    # ── Lifecycle ──
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    # ── Navigation ──
    async def navigate(self, url: str) -> BrowserState: ...
    async def get_current_state(self) -> BrowserState: ...

    # ── Actions ──
    async def execute_action(
        self,
        spec: ActionSpec,
    ) -> ActionResult: ...

    # ── Human Loop ──
    async def ask_user(
        self,
        prompt: str,
        thread_id: str,
        action_type: str = "general",
    ) -> str: ...

    # ── Properties ──
    @property
    def is_started(self) -> bool: ...

    @property
    def current_url(self) -> str: ...
