"""Visual Perception Service — Captura screenshots con Set-of-Mark dibujado sobre la imagen.

En lugar de inyectar overlays DOM (CSS) que pueden fallar con z-index agresivos,
este servicio dibuja las cajas directamente sobre el screenshot usando Pillow.
Esto garantiza que el modelo multimodal vea EXACTAMENTE lo mismo que el texto AOM describe.

SOLID: Implementa VisualPerceptionPort.
"""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src.core.logging import logging
from src.ia.browser.models import (
    AOMElement,
    AOMResult,
    Bounds,
    BrowserState,
    ScreenshotResult,
    SOMConfig,
)

logger = logging.getLogger(__name__)

# Script JS para extraer el AOM (sin overlays visuales)
# Nota: eliminamos la creación de divs .ai-bbox; solo extraemos datos.
AOM_SCRIPT = """
() => {
    let idCounter = 1;
    const elementsList = [];
    
    const interactableSelectors = 'button, a, input, select, textarea, [role="button"], [role="link"], [tabindex]:not([tabindex="-1"])';
    const elements = document.querySelectorAll(interactableSelectors);
    
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
            const id = idCounter++;
            const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 50);
            
            elementsList.push({
                id: id,
                tag: el.tagName.toLowerCase(),
                text: text,
                bounds: {
                    x: Math.round(rect.x + window.scrollX),
                    y: Math.round(rect.y + window.scrollY),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                },
                element_type: el.type || el.getAttribute('role') || el.tagName.toLowerCase(),
                state: el.disabled ? 'disabled' : 'enabled',
                placeholder: el.placeholder || null,
                value: el.value || null,
                aria_label: el.getAttribute('aria-label') || null
            });
        }
    });
    
    return {
        elements: elementsList,
        viewport: { width: window.innerWidth, height: window.innerHeight },
        scroll: { x: window.scrollX, y: window.scrollY }
    };
}
"""


class VisualPerceptionService:
    """Captura screenshots y dibuja Set-of-Mark sobre la imagen con Pillow."""

    def __init__(self, config: SOMConfig | None = None):
        self.config = config or SOMConfig()
        self._font: ImageFont.FreeTypeFont | None = None
        self._try_load_font()

    def _try_load_font(self) -> None:
        """Intenta cargar una fuente TTF; fallback a fuente por defecto."""
        try:
            # En Windows: usa la fuente del sistema
            import sys
            if sys.platform == "win32":
                self._font = ImageFont.truetype("arial.ttf", self.config.label_font_size)
            else:
                self._font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", self.config.label_font_size)
        except Exception:
            logger.warning("No se pudo cargar fuente TTF, usando fuente por defecto")
            self._font = ImageFont.load_default()

    async def extract_aom(self, page: Any) -> AOMResult:
        """Extrae el Accessibility Object Model sin modificar el DOM."""
        raw = await page.evaluate(AOM_SCRIPT)
        elements = []
        elements_map = {}
        lines = []

        for data in raw.get("elements", []):
            bounds = Bounds(
                x=data["bounds"]["x"],
                y=data["bounds"]["y"],
                width=data["bounds"]["width"],
                height=data["bounds"]["height"],
            )
            el = AOMElement(
                id=data["id"],
                tag=data["tag"],
                text=data["text"],
                bounds=bounds,
                element_type=data.get("element_type", "unknown"),
                state=data.get("state", "enabled"),
                placeholder=data.get("placeholder"),
                value=data.get("value"),
                aria_label=data.get("aria_label"),
            )
            elements.append(el)
            elements_map[str(el.id)] = el
            lines.append(el.to_line())

        aom = AOMResult(
            elements=elements,
            elements_map=elements_map,
            text_description="Current Page Interactive Elements (AOM):\n" + "\n".join(lines),
        )
        logger.info("[VisualPerception] AOM extraído: %d elementos", len(elements))
        return aom

    async def capture_screenshot(
        self,
        page: Any,
        draw_som: bool = True,
        aom: AOMResult | None = None,
    ) -> ScreenshotResult:
        """Captura screenshot y opcionalmente dibuja SoM sobre la imagen."""
        # 1. Capturar screenshot crudo
        screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
        image = Image.open(io.BytesIO(screenshot_bytes))
        width, height = image.size

        if draw_som and aom:
            image = self._draw_som_on_image(image, aom)
            # Convertir de vuelta a RGB para JPEG (JPEG no soporta transparencia)
            if image.mode == "RGBA":
                # Crear fondo blanco para composición
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])  # Usar canal alpha como máscara
                image = background
            # Re-encodear como JPEG con las cajas dibujadas
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=60)
            screenshot_bytes = buf.getvalue()

        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

        return ScreenshotResult(
            base64_image=b64,
            width=width,
            height=height,
            has_som=draw_som and aom is not None,
        )

    def _draw_som_on_image(
        self,
        image: Image.Image,
        aom: AOMResult,
    ) -> Image.Image:
        """Dibuja cajas rojas numeradas sobre la imagen PIL."""
        # Convertir a RGBA para soportar transparencia en las cajas
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        draw = ImageDraw.Draw(image, "RGBA")
        cfg = self.config

        for el in aom.elements:
            b = el.bounds
            # Filtrar elementos fuera del viewport (solo dibujamos los visibles)
            if b.y + b.height < 0 or b.y > cfg.viewport_height:
                continue
            if b.x + b.width < 0 or b.x > cfg.viewport_width:
                continue

            # 1. Rectángulo de fondo semitransparente
            fill_rgba = (*cfg.box_color, cfg.opacity)
            draw.rectangle(
                [(b.x, b.y), (b.x + b.width, b.y + b.height)],
                outline=cfg.box_color,
                width=cfg.box_width,
                fill=fill_rgba,
            )

            # 2. Label con el ID
            label_text = f"[{el.id}]"
            bbox = draw.textbbox((0, 0), label_text, font=self._font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            label_x = b.x
            label_y = max(0, b.y - text_h - cfg.label_padding * 2)

            # Fondo del label
            draw.rectangle(
                [
                    (label_x, label_y),
                    (label_x + text_w + cfg.label_padding * 2, label_y + text_h + cfg.label_padding * 2),
                ],
                fill=cfg.label_bg_color,
            )
            # Texto del label
            draw.text(
                (label_x + cfg.label_padding, label_y + cfg.label_padding),
                label_text,
                fill=cfg.label_text_color,
                font=self._font,
            )

        return image

    async def get_full_state(
        self,
        page: Any,
        draw_som: bool = True,
    ) -> BrowserState:
        """Captura estado completo: screenshot + AOM + metadatos."""
        # Extraer AOM primero (no modifica DOM)
        aom = await self.extract_aom(page)

        # Capturar screenshot con SoM dibujado
        screenshot = await self.capture_screenshot(
            page=page,
            draw_som=draw_som,
            aom=aom,
        )

        return BrowserState(
            url=page.url,
            title=await page.title(),
            screenshot=screenshot,
            aom=aom,
        )
