"""Domain models for the browser automation subsystem.

Pure data classes with no external dependencies — can be imported anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Point:
    """2D coordinate."""

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Bounds:
    """Element bounding rectangle."""

    x: int
    y: int
    width: int
    height: int

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2


@dataclass(frozen=True, slots=True)
class AOMElement:
    """Single interactive element from the Accessibility Object Model."""

    id: int
    tag: str
    text: str
    bounds: Bounds
    element_type: str = "unknown"  # button, input, link, select, etc.
    state: str = "enabled"  # enabled, disabled, checked, etc.
    placeholder: str | None = None
    value: str | None = None
    aria_label: str | None = None

    def to_line(self) -> str:
        """Format as a single line for LLM text consumption."""
        extra = ""
        if self.placeholder:
            extra += f' placeholder="{self.placeholder}"'
        if self.value:
            extra += f' value="{self.value}"'
        if self.aria_label:
            extra += f' aria="{self.aria_label}"'
        return f"[{self.id}] {self.tag.upper()} - \"{self.text}\"{extra}"


@dataclass(frozen=True, slots=True)
class AOMResult:
    """Complete AOM extraction result."""

    elements: list[AOMElement]
    elements_map: dict[str, AOMElement] = field(repr=False)
    text_description: str  # Formatted string for LLM

    def get_by_id(self, element_id: int) -> AOMElement | None:
        return self.elements_map.get(str(element_id))


@dataclass(frozen=True, slots=True)
class ScreenshotResult:
    """Screenshot with optional Set-of-Mark annotation."""

    base64_image: str
    width: int
    height: int
    has_som: bool  # True if bounding boxes are drawn on the image


@dataclass(frozen=True, slots=True)
class BrowserState:
    """Complete snapshot of the browser at a point in time."""

    url: str
    title: str
    screenshot: ScreenshotResult
    aom: AOMResult


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Result of executing a browser action."""

    success: bool
    message: str
    state_changed: bool = False  # True if page content changed
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """Specification for a browser action (name + params)."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)


# ── Human-in-the-Loop models ──

@dataclass(frozen=True, slots=True)
class TakeoverRequest:
    """Request for human input during agent execution."""

    thread_id: str
    prompt: str
    action_type: str  # "login", "confirmation", "captcha", "general"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TakeoverResponse:
    """Human response to a takeover request."""

    thread_id: str
    response: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Perception configuration ──

@dataclass(frozen=True, slots=True)
class SOMConfig:
    """Configuration for Set-of-Mark visual annotation."""

    box_color: tuple[int, int, int] = (255, 0, 0)  # Red
    box_width: int = 2
    label_bg_color: tuple[int, int, int] = (255, 0, 0)
    label_text_color: tuple[int, int, int] = (255, 255, 255)
    label_font_size: int = 12
    label_padding: int = 2
    opacity: int = 30  # 0-255, background fill opacity

    # Viewport size
    viewport_width: int = 1280
    viewport_height: int = 800
