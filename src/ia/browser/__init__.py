"""VL-Agent Browser Automation — SOLID Architecture.

Fase 1: Percepción Visual + Acciones + Controlador

Packages:
  - models: Pure domain data classes
  - protocols: Abstract interfaces (ports)
  - perception: VisualPerceptionService (captura + SoM)
  - actions: Implementaciones de acciones del navegador
  - controller: BrowserController (orquestador)
"""

from src.ia.browser.models import (
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

from src.ia.browser.protocols import (
    VisualPerceptionPort,
    BrowserActionPort,
    BrowserActionRegistryPort,
    HumanLoopPort,
    BrowserControllerPort,
)

from src.ia.browser.perception import VisualPerceptionService
from src.ia.browser.actions import BrowserActionRegistry
from src.ia.browser.controller import BrowserController
from src.ia.browser.human_loop import HumanLoopService

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
