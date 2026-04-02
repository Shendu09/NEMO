"""Action Executor — executes OS actions with security validation."""

from __future__ import annotations

import base64
import io
import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import mss
import pyautogui
import pygetwindow

from core.bus import BusClient, BusMessage, MessageType, Topics
from core.security import SecurityGateway


logger = logging.getLogger("nemo.executor")

# Disable pyautogui's built-in safety pause for faster execution
pyautogui.PAUSE = 0


@dataclass
class ActionStep:
    """Single action step from AI plan."""

    action: str  # open_app, type, click, press_key, screenshot
    target: str = ""  # app name or coordinates or key
    value: str = ""  # text to type or additional data


class ActionExecutor:
    """Executes OS actions on behalf of AI brain with security checks."""

    def __init__(
        self,
        bus_client: BusClient,
        security_gateway: SecurityGateway,
        user_id: str = "ai_executor",
    ) -> None:
        """Initialize action executor."""
        self.bus = bus_client
        self.gateway = security_gateway
        self.user_id = user_id
        self.logger = logging.getLogger("nemo.executor")
        self._stop = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start listening for AI decisions on the bus."""
        if self._listener_thread is not None:
            self.logger.warning("Executor already started")
            return

        self.logger.info("ActionExecutor starting...")
        self._stop.clear()
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
        )
        self._listener_thread.start()
        self.logger.info("ActionExecutor listening on %s", Topics.AI_DECISION)

    def stop(self) -> None:
        """Stop listening."""
        self.logger.info("ActionExecutor stopping...")
        self._stop.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=5)

    def _listen_loop(self) -> None:
        """Listen for AI decisions and execute them."""
        def handler(msg: BusMessage) -> None:
            try:
                if msg.type != MessageType.PUBLISH:
                    return
                plan = msg.payload.get("steps", [])
                if not plan:
                    self.logger.warning("Received empty plan")
                    return
                result = self.execute_plan(plan)
                # Publish result
                self.bus.publish(
                    Topics.ACTION_RESULT,
                    result,
                    sender=self.user_id,
                )
            except Exception as exc:
                self.logger.error(f"Plan execution error: {exc}")
                self.bus.publish(
                    Topics.ACTION_RESULT,
                    {
                        "success": False,
                        "error": str(exc),
                        "steps_completed": 0,
                    },
                    sender=self.user_id,
                )

        self.bus.subscribe(Topics.AI_DECISION, handler)

    def execute_plan(self, steps: list[dict]) -> dict[str, Any]:
        """Execute a sequence of action steps."""
        results = []
        completed = 0

        for i, step_data in enumerate(steps):
            try:
                step = ActionStep(**step_data)
                self.logger.info(
                    f"[{i + 1}/{len(steps)}] Executing: {step.action}"
                )

                # RBAC check
                try:
                    self.gateway.run_command(
                        user_id=self.user_id,
                        target=f"action.{step.action}",
                        args={"target": step.target, "value": step.value},
                    )
                except Exception as sec_exc:
                    self.logger.error(f"Security check failed: {sec_exc}")
                    return {
                        "success": False,
                        "error": f"Security check failed: {sec_exc}",
                        "steps_completed": completed,
                    }

                # Execute the action
                result = self._execute_action(step)
                results.append(result)
                completed += 1

                # Publish result for this step
                self.bus.publish(
                    Topics.ACTION_RESULT,
                    {
                        "success": True,
                        "step": i + 1,
                        "action": step.action,
                        "screenshot": result.get("screenshot"),
                    },
                    sender=self.user_id,
                )

            except Exception as exc:
                self.logger.error(f"Step {i + 1} failed: {exc}")
                return {
                    "success": False,
                    "error": str(exc),
                    "steps_completed": completed,
                }

        return {
            "success": True,
            "steps_completed": completed,
            "results": results,
        }

    def _execute_action(self, step: ActionStep) -> dict[str, Any]:
        """Execute a single action step."""
        if step.action == "open_app":
            return self._action_open_app(step.target, step.value)
        elif step.action == "type":
            return self._action_type(step.target)
        elif step.action == "click":
            return self._action_click(step.target)
        elif step.action == "press_key":
            return self._action_press_key(step.target)
        elif step.action == "screenshot":
            return self._action_screenshot()
        elif step.action == "wait":
            return self._action_wait(step.target)
        else:
            raise ValueError(f"Unknown action: {step.action}")

    def _action_open_app(self, app_name: str, args: str = "") -> dict[str, Any]:
        """Open an application."""
        self.logger.info(f"Opening app: {app_name}")

        cmd = app_name
        if app_name.lower() == "chrome":
            cmd = (
                "chrome"
                if subprocess.run(
                    ["which", "chrome"],
                    capture_output=True,
                ).returncode == 0
                else "google-chrome"
            )
            cmd += " --profile-directory=Default --no-first-run --start-maximized"

        try:
            subprocess.Popen(cmd, shell=True)
            self.logger.info(f"Opened: {app_name}")
            return {
                "action": "open_app",
                "app": app_name,
                "success": True,
            }
        except Exception as exc:
            self.logger.error(f"Failed to open {app_name}: {exc}")
            raise

    def _action_type(self, text: str) -> dict[str, Any]:
        """Type text into active window."""
        self.logger.info(f"Typing: {text[:50]}...")

        # Press Escape to cancel any dialogs
        pyautogui.press("escape")
        time.sleep(0.4)

        # Type with interval
        pyautogui.write(text, interval=0.05)
        self.logger.info("Typed successfully")

        return {
            "action": "type",
            "text": text[:50],
            "success": True,
        }

    def _action_click(self, coords: str) -> dict[str, Any]:
        """Click at coordinates."""
        try:
            x, y = map(int, coords.split(","))
            self.logger.info(f"Clicking at ({x}, {y})")
            pyautogui.click(x, y)
            self.logger.info("Click executed")
            return {
                "action": "click",
                "x": x,
                "y": y,
                "success": True,
            }
        except Exception as exc:
            self.logger.error(f"Click failed: {exc}")
            raise

    def _action_press_key(self, keys: str) -> dict[str, Any]:
        """Press keyboard hotkey combination."""
        self.logger.info(f"Pressing: {keys}")

        key_list = keys.split("+")
        pyautogui.hotkey(*key_list)
        self.logger.info(f"Key pressed: {keys}")

        return {
            "action": "press_key",
            "keys": keys,
            "success": True,
        }

    def _action_screenshot(self) -> dict[str, Any]:
        """Capture active window screenshot."""
        self.logger.info("Taking screenshot...")

        try:
            # Get active window
            active_window = pygetwindow.getActiveWindow()
            if not active_window:
                self.logger.warning("No active window found")
                return {
                    "action": "screenshot",
                    "success": False,
                    "error": "No active window",
                }

            # Capture window region
            region = {
                "left": max(0, active_window.left),
                "top": max(0, active_window.top),
                "width": max(1, active_window.width),
                "height": max(1, active_window.height),
            }

            with mss.mss() as sct:
                img = sct.grab(region)
                # Convert to base64
                img_bytes = io.BytesIO()
                from PIL import Image

                pil_img = Image.frombytes("RGB", img.size, img.rgb)
                pil_img.save(img_bytes, format="PNG")
                img_b64 = base64.b64encode(
                    img_bytes.getvalue()
                ).decode("utf-8")

            self.logger.info(f"Screenshot captured: {region['width']}x{region['height']}")
            return {
                "action": "screenshot",
                "success": True,
                "screenshot": img_b64[:100],  # First 100 chars for logging
                "window": {
                    "width": region["width"],
                    "height": region["height"],
                },
            }
        except Exception as exc:
            self.logger.error(f"Screenshot failed: {exc}")
            raise

    def _action_wait(self, seconds: str) -> dict[str, Any]:
        """Wait for specified seconds."""
        try:
            duration = float(seconds)
            self.logger.info(f"Waiting {duration}s...")
            time.sleep(duration)
            self.logger.info("Wait completed")
            return {
                "action": "wait",
                "seconds": duration,
                "success": True,
            }
        except Exception as exc:
            self.logger.error(f"Wait failed: {exc}")
            raise
