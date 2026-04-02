"""Screen Vision — captures and analyzes screen with Ollama vision model."""

from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import mss
import pygetwindow
import requests

from core.bus import BusClient, BusMessage, MessageType, Topics


logger = logging.getLogger("nemo.vision")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_VISION_MODEL = "llava"  # Vision model for screen analysis
VISION_PROMPT = """Analyze this screenshot of a computer screen. What app is open? 
List all visible buttons, text fields, and clickable elements with their approximate 
locations. Also list all visible text on screen.

Return ONLY valid JSON (no markdown, no explanations):
{
  "app": "application name",
  "elements": [
    {"name": "button/field label", "type": "button|field|link|text", "description": "what it does"}
  ],
  "visible_text": ["text", "snippets", "visible"],
  "screen_size": {"width": 0, "height": 0}
}"""


@dataclass
class ScreenAnalysis:
    """Result of screen vision analysis."""

    app: str
    elements: list[dict]
    visible_text: list[str]
    screen_size: dict
    screenshot_b64: str = ""


class ScreenVision:
    """Captures and analyzes screen content using Ollama vision model."""

    def __init__(self, bus_client: BusClient) -> None:
        """Initialize screen vision."""
        self.bus = bus_client
        self.logger = logging.getLogger("nemo.vision")
        self._stop = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._ollama_available = False
        self._check_ollama()

    def _check_ollama(self) -> None:
        """Check if Ollama is available."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            self._ollama_available = resp.status_code == 200
            if self._ollama_available:
                self.logger.info("Ollama is available")
            else:
                self.logger.warning("Ollama not responding properly")
        except Exception as exc:
            self.logger.warning(f"Ollama not available: {exc}")
            self._ollama_available = False

    def start(self) -> None:
        """Start listening for vision screenshot requests."""
        if self._listener_thread is not None:
            self.logger.warning("ScreenVision already started")
            return

        self.logger.info("ScreenVision starting...")
        self._stop.clear()
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
        )
        self._listener_thread.start()
        self.logger.info("ScreenVision listening on %s", Topics.VISION_SCREENSHOT)

    def stop(self) -> None:
        """Stop listening."""
        self.logger.info("ScreenVision stopping...")
        self._stop.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=5)

    def _listen_loop(self) -> None:
        """Listen for screenshot requests and process them."""
        def handler(msg: BusMessage) -> None:
            try:
                if msg.type != MessageType.PUBLISH:
                    return
                self.logger.info("Screenshot request received")
                result = self.analyze_screen()
                # Publish context
                self.bus.publish(
                    Topics.VISION_CONTEXT,
                    result,
                    sender="vision",
                )
            except Exception as exc:
                self.logger.error(f"Vision processing error: {exc}")
                self.bus.publish(
                    Topics.VISION_CONTEXT,
                    {
                        "success": False,
                        "error": str(exc),
                    },
                    sender="vision",
                )

        self.bus.subscribe(Topics.VISION_SCREENSHOT, handler)

    def analyze_screen(self) -> dict[str, Any]:
        """Capture and analyze the active window."""
        self.logger.info("Analyzing screen...")

        try:
            # Get active window
            active_window = pygetwindow.getActiveWindow()
            if not active_window:
                self.logger.warning("No active window found")
                return {
                    "success": False,
                    "error": "No active window found",
                }

            # Capture window screenshot
            screenshot_b64 = self._capture_window(active_window)
            if not screenshot_b64:
                return {
                    "success": False,
                    "error": "Failed to capture window",
                }

            # Analyze with Ollama
            if not self._ollama_available:
                self.logger.warning("Ollama not available, returning basic info")
                return {
                    "success": True,
                    "app": active_window.title,
                    "elements": [],
                    "visible_text": [],
                    "screen_size": {
                        "width": active_window.width,
                        "height": active_window.height,
                    },
                    "screenshot": screenshot_b64[:100],
                }

            analysis = self._analyze_with_ollama(screenshot_b64)
            analysis["success"] = True
            analysis["screenshot"] = screenshot_b64[:100]  # First 100 chars for logging

            self.logger.info(f"Screen analysis complete: {analysis['app']}")
            return analysis

        except Exception as exc:
            self.logger.error(f"Screen analysis failed: {exc}")
            raise

    def _capture_window(self, window: pygetwindow.Window) -> Optional[str]:
        """Capture window and return as base64."""
        try:
            region = {
                "left": max(0, window.left),
                "top": max(0, window.top),
                "width": max(1, window.width),
                "height": max(1, window.height),
            }

            with mss.mss() as sct:
                img = sct.grab(region)

                # Convert to PNG bytes
                from PIL import Image

                pil_img = Image.frombytes("RGB", img.size, img.rgb)
                img_bytes = io.BytesIO()
                pil_img.save(img_bytes, format="PNG")

                # Encode to base64
                b64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
                self.logger.debug(
                    f"Captured window: {region['width']}x{region['height']}"
                )
                return b64

        except Exception as exc:
            self.logger.error(f"Window capture failed: {exc}")
            return None

    def _analyze_with_ollama(self, screenshot_b64: str) -> dict[str, Any]:
        """Send screenshot to Ollama for visual analysis."""
        try:
            payload = {
                "model": OLLAMA_VISION_MODEL,
                "prompt": VISION_PROMPT,
                "images": [screenshot_b64],
                "stream": False,
            }

            self.logger.debug(f"Sending to Ollama {OLLAMA_VISION_MODEL}...")
            resp = requests.post(OLLAMA_URL, json=payload, timeout=30)
            resp.raise_for_status()

            response_text = resp.json().get("response", "")
            self.logger.debug(f"Ollama response: {response_text[:200]}")

            # Parse JSON response
            analysis = self._parse_vision_response(response_text)
            return analysis

        except Exception as exc:
            self.logger.error(f"Ollama analysis failed: {exc}")
            return {
                "app": "Unknown",
                "elements": [],
                "visible_text": [],
                "screen_size": {},
                "error": str(exc),
            }

    def _parse_vision_response(self, response_text: str) -> dict[str, Any]:
        """Parse Ollama vision response JSON."""
        try:
            # Try to extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                self.logger.warning("No JSON found in response")
                return {
                    "app": "Unknown",
                    "elements": [],
                    "visible_text": [],
                    "screen_size": {},
                }

            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)

            return {
                "app": data.get("app", "Unknown"),
                "elements": data.get("elements", []),
                "visible_text": data.get("visible_text", []),
                "screen_size": data.get("screen_size", {}),
            }

        except json.JSONDecodeError as exc:
            self.logger.error(f"Failed to parse JSON response: {exc}")
            self.logger.debug(f"Response was: {response_text[:200]}")
            return {
                "app": "Unknown",
                "elements": [],
                "visible_text": [],
                "screen_size": {},
                "parse_error": str(exc),
            }
