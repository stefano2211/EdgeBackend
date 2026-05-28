"""VL-Agent Browser Automation — SOLID Architecture.

Fase 1: Percepción Visual + Acciones + Controlador

Packages:
  - models: Pure domain data classes
  - protocols: Abstract interfaces (ports)
  - perception: VisualPerceptionService (captura + SoM)
  - actions: Implementaciones de acciones del navegador
  - controller: BrowserController (orquestador)
"""

from backend.ia.browser.models import (
    Point,
    Bounds,
    AOMElement,
    AOMResult,
    ScreenshotResult,
    BrowserState,
    ActionResult,
    ActionSpec,
    SOMConfig,
    TakeoverRequest,
    TakeoverResponse,
)

from backend.ia.browser.protocols import (
    VisualPerceptionPort,
    BrowserActionPort,
    BrowserActionRegistryPort,
    HumanLoopPort,
    BrowserControllerPort,
)

from backend.ia.browser.perception import VisualPerceptionService
from backend.ia.browser.actions import BrowserActionRegistry
from backend.ia.browser.controller import BrowserController
from backend.ia.browser.human_loop import HumanLoopService

__all__ = [
    # Models
    "Point",
    "Bounds",
    "AOMElement",
    "AOMResult",
    "ScreenshotResult",
    "BrowserState",
    "ActionResult",
    "ActionSpec",
    "SOMConfig",
    "TakeoverRequest",
    "TakeoverResponse",
    # Protocols
    "VisualPerceptionPort",
    "BrowserActionPort",
    "BrowserActionRegistryPort",
    "HumanLoopPort",
    "BrowserControllerPort",
    # Implementations
    "VisualPerceptionService",
    "BrowserActionRegistry",
    "BrowserController",
    "HumanLoopService",
]
