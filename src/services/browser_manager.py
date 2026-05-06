"""Browser Manager — Persistent Playwright session for Anthropic-style Computer Use."""

import base64
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from src.core.logging import logging

logger = logging.getLogger(__name__)

# Script to inject for DOM Accessibility Tree mapping (Set-of-Mark)
AOM_SCRIPT = """
() => {
    let idCounter = 1;
    const elementsMap = {};
    
    // Cleanup previous boxes
    document.querySelectorAll('.ai-bbox').forEach(el => el.remove());
    
    const interactableSelectors = 'button, a, input, select, textarea, [role="button"], [role="link"], [tabindex]:not([tabindex="-1"])';
    const elements = document.querySelectorAll(interactableSelectors);
    
    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        // Only visible elements
        if (rect.width > 0 && rect.height > 0) {
            const id = idCounter++;
            const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().substring(0, 50);
            
            elementsMap[id] = {
                tag: el.tagName.toLowerCase(),
                text: text,
                bounds: {
                    x: rect.x + window.scrollX,
                    y: rect.y + window.scrollY,
                    width: rect.width,
                    height: rect.height,
                    center_x: rect.x + window.scrollX + (rect.width / 2),
                    center_y: rect.y + window.scrollY + (rect.height / 2)
                }
            };
            
            // Draw visual box with ID for the screenshot
            const box = document.createElement('div');
            box.className = 'ai-bbox';
            box.style.position = 'absolute';
            box.style.left = `${rect.x + window.scrollX}px`;
            box.style.top = `${rect.y + window.scrollY}px`;
            box.style.width = `${rect.width}px`;
            box.style.height = `${rect.height}px`;
            box.style.border = '2px solid red';
            box.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
            box.style.zIndex = '999999';
            box.style.pointerEvents = 'none';
            
            const label = document.createElement('span');
            label.innerText = `[${id}]`;
            label.style.position = 'absolute';
            label.style.top = '-15px';
            label.style.left = '0';
            label.style.background = 'red';
            label.style.color = 'white';
            label.style.fontSize = '12px';
            label.style.padding = '2px';
            label.style.fontWeight = 'bold';
            
            box.appendChild(label);
            document.body.appendChild(box);
        }
    });
    
    return elementsMap;
}
"""

class BrowserManager:
    """Singleton to manage persistent browser state across LLM tool calls."""
    _instance = None
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._elements_map: dict = {}
    
    @classmethod
    def get_instance(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self):
        if self._playwright is None:
            logger.info("[BrowserManager] Starting Playwright engine")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                device_scale_factor=1,
            )
            self._page = await self._context.new_page()

    async def get_page(self) -> Page:
        if self._page is None:
            await self.start()
        return self._page
        
    async def navigate(self, url: str) -> str:
        try:
            page = await self.get_page()
            await page.goto(url, wait_until="networkidle")
            return await self.extract_aom()
        except Exception as e:
            logger.error("Navigation failed: %s", e)
            return f"Error navigating to {url}: {e}"
        
    async def extract_aom(self) -> str:
        """Extracts Accessibility Object Model (DOM mapping) and draws boxes."""
        try:
            page = await self.get_page()
            # Wait for network to settle before parsing DOM
            await page.wait_for_timeout(1000)
            self._elements_map = await page.evaluate(AOM_SCRIPT)
            
            # Format for LLM consumption
            lines = []
            for id_str, data in self._elements_map.items():
                tag = data['tag'].upper()
                text = data['text']
                lines.append(f"[{id_str}] {tag} - \"{text}\"")
                
            return "Current Page Interactive Elements (AOM):\n" + "\n".join(lines)
        except Exception as e:
            logger.error("AOM extraction failed: %s", e)
            return f"Error extracting elements: {e}"
        
    async def get_screenshot(self) -> str:
        """Returns base64 encoded screenshot of current viewport."""
        try:
            page = await self.get_page()
            screenshot_bytes = await page.screenshot(type="jpeg", quality=60)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        except Exception as e:
            logger.error("Screenshot failed: %s", e)
            return ""
            
    async def _emit_screenshot_event(self, action_msg: str, click_coords: tuple[int, int] = None):
        """Emits a live screenshot event to the active chat SSE stream."""
        from src.core.context import chat_stream_queue
        import asyncio
        
        q = chat_stream_queue.get()
        if not q:
            return
            
        b64 = await self.get_screenshot()
        if not b64:
            return
            
        payload = {
            "b64": b64,
            "step": 1,  # LangGraph checkpoint logic could supply this
            "has_omniparser": True,
            "action": action_msg
        }
        
        if click_coords:
            # Convert pixel coordinates to percentages for the frontend UI (viewport is 1280x800)
            payload["click"] = {
                "x": round((click_coords[0] / 1280) * 100, 2),
                "y": round((click_coords[1] / 800) * 100, 2),
                "type": "click"
            }
            
        try:
            q.put_nowait({"screenshot": payload})
        except asyncio.QueueFull:
            pass
        
    async def computer_action(
        self, 
        action: str, 
        coordinate: list[int] = None, 
        text: str = None, 
        element_id: int = None
    ) -> str:
        """Executes Anthropic-style computer actions.
        
        Supports both native X,Y coordinates and fallback element_id (from AOM).
        """
        page = await self.get_page()
        
        x, y = None, None
        
        if element_id is not None:
            el_data = self._elements_map.get(str(element_id))
            if not el_data:
                return f"Error: Element ID [{element_id}] not found on screen."
            x = el_data['bounds']['center_x']
            y = el_data['bounds']['center_y']
        elif coordinate and len(coordinate) == 2:
            x, y = coordinate
            
        try:
            # Pre-action screenshot for visual feedback
            if action not in ("screenshot",):
                await self._emit_screenshot_event(f"Executing: {action}")
                
            if action == "mouse_move" and x is not None:
                await page.mouse.move(x, y)
                await self._emit_screenshot_event("Cursor Moved", click_coords=(x, y))
                return f"Moved cursor to [{x}, {y}]"
                
            elif action == "left_click" and x is not None:
                await self._emit_screenshot_event("Clicking Element...", click_coords=(x, y))
                await page.mouse.click(x, y)
                # Let animations and navigation settle
                await page.wait_for_timeout(1000) 
                await self._emit_screenshot_event(f"Clicked [{x}, {y}]")
                return f"Clicked at [{x}, {y}]. Current URL: {page.url}"
                
            elif action == "type":
                if x is not None:
                    await self._emit_screenshot_event("Clicking Input...", click_coords=(x, y))
                    await page.mouse.click(x, y)
                if text:
                    await page.keyboard.type(text, delay=20)
                    await self._emit_screenshot_event(f"Typed: {text}")
                    return f"Typed '{text}'"
                return "Error: No text provided to type."
                
            elif action == "key":
                if text:
                    await page.keyboard.press(text)
                    await page.wait_for_timeout(500)
                    await self._emit_screenshot_event(f"Pressed Key: {text}")
                    return f"Pressed key '{text}'"
                return "Error: No key provided."
                
            elif action == "screenshot":
                await self._emit_screenshot_event("Screenshot Request")
                return "Screenshot taken. (Check image payload if supported by UI)"
                
            else:
                return f"Error: Unsupported action '{action}' or missing coordinates/element_id."
                
        except Exception as e:
            logger.exception("Computer action failed")
            return f"Action failed: {e}"
