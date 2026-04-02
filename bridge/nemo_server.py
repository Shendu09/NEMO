"""NEMO-OS HTTP Server — REST API for PC control."""

from __future__ import annotations

import base64
import io
import json
import logging
import subprocess
import time
from typing import Any, Optional

import pyautogui
import pygetwindow
from flask import Flask, jsonify, request
from mss import mss
from PIL import Image

from core.security.gateway_v2 import SecurityGateway
from core.security.audit_logger_v2 import AuditLogger


app = Flask(__name__)
logger = logging.getLogger("nemo.server")

# Global references (will be injected at startup)
_gateway: Optional[SecurityGateway] = None
_audit_logger: Optional[AuditLogger] = None

# Disable pyautogui safety pause
pyautogui.PAUSE = 0


def set_dependencies(gateway: SecurityGateway, audit_logger: AuditLogger) -> None:
    """Inject SecurityGateway and AuditLogger dependencies."""
    global _gateway, _audit_logger
    _gateway = gateway
    _audit_logger = audit_logger


@app.route("/health", methods=["GET"])
def health() -> dict[str, Any]:
    """Health check endpoint."""
    logger.debug("Health check requested")
    return jsonify({
        "status": "ok",
        "security": "active",
    })


@app.route("/screenshot", methods=["GET"])
def screenshot() -> dict[str, Any]:
    """Capture active window screenshot."""
    logger.info("Screenshot requested via GET /screenshot")

    try:
        screenshot_b64 = _capture_screenshot()
        if not screenshot_b64:
            return jsonify({
                "success": False,
                "error": "Failed to capture screenshot",
            }), 400

        # Log to audit
        if _audit_logger:
            _audit_logger.log(
                user_id="api",
                action="screenshot",
                target="screen",
                allowed=True,
                reason="GET /screenshot",
            )

        return jsonify({
            "success": True,
            "screenshot": screenshot_b64,
        })

    except Exception as exc:
        logger.error(f"Screenshot failed: {exc}")
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route("/execute", methods=["POST"])
def execute() -> dict[str, Any]:
    """Execute an action on the PC."""
    try:
        data = request.get_json() or {}
        action = data.get("action", "")
        target = data.get("target", "")
        value = data.get("value", "")
        user = data.get("user", "api")
        channel = data.get("channel", "api")

        logger.info(f"Execute request: action={action}, user={user}, channel={channel}")

        if not action:
            return jsonify({
                "success": False,
                "error": "action is required",
            }), 400

        # Execute the action
        exec_result = _execute_action(action, target, value)

        # Log to audit
        if _audit_logger:
            _audit_logger.log(
                user_id=user,
                action=action,
                target=target or "",
                allowed=exec_result.get("success", False),
                reason=f"{channel}: {exec_result.get('error', 'ok')}",
            )

        logger.info(f"Action completed: {action} → {exec_result}")
        return jsonify(exec_result)

    except Exception as exc:
        logger.error(f"Execute endpoint error: {exc}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


def _execute_action(action: str, target: str, value: str) -> dict[str, Any]:
    """Execute a single action."""
    logger.debug(f"Executing: {action}")

    if action == "open_app":
        return _action_open_app(target, value)
    elif action == "type":
        return _action_type(value)
    elif action == "press_key":
        return _action_press_key(value)
    elif action == "click":
        return _action_click(value)
    elif action == "screenshot":
        return _action_screenshot()
    elif action == "wait":
        return _action_wait(value)
    else:
        return {
            "success": False,
            "error": f"Unknown action: {action}",
        }


def _action_open_app(app_name: str, args: str = "") -> dict[str, Any]:
    """Open an application."""
    logger.info(f"Opening app: {app_name}")

    try:
        if app_name.lower() == "chrome":
            cmd = [
                "chrome.exe",
                "--profile-directory=Default",
                "--no-first-run",
                "--start-maximized",
            ]
        else:
            cmd = [app_name]

        subprocess.Popen(cmd)
        time.sleep(2)

        logger.info(f"Opened: {app_name}")
        return {
            "success": True,
            "action": "open_app",
            "app": app_name,
        }
    except Exception as exc:
        logger.error(f"Failed to open {app_name}: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _action_type(text: str) -> dict[str, Any]:
    """Type text into active window."""
    logger.debug(f"Typing: {text[:50]}")

    try:
        # Press escape to clear focus
        pyautogui.press("escape")
        time.sleep(0.4)

        # Type with interval
        pyautogui.write(text, interval=0.05)
        logger.info("Text typed successfully")

        return {
            "success": True,
            "action": "type",
            "text_length": len(text),
        }
    except Exception as exc:
        logger.error(f"Type failed: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _action_press_key(keys: str) -> dict[str, Any]:
    """Press keyboard hotkey combination."""
    logger.debug(f"Pressing keys: {keys}")

    try:
        key_list = keys.split("+")
        pyautogui.hotkey(*key_list)
        logger.info(f"Pressed: {keys}")

        return {
            "success": True,
            "action": "press_key",
            "keys": keys,
        }
    except Exception as exc:
        logger.error(f"Press key failed: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _action_click(coords: str) -> dict[str, Any]:
    """Click at coordinates."""
    logger.debug(f"Clicking: {coords}")

    try:
        x, y = map(int, coords.split(","))
        pyautogui.click(x, y)
        logger.info(f"Clicked at ({x}, {y})")

        return {
            "success": True,
            "action": "click",
            "x": x,
            "y": y,
        }
    except Exception as exc:
        logger.error(f"Click failed: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _action_screenshot() -> dict[str, Any]:
    """Capture active window screenshot."""
    logger.debug("Taking screenshot")

    try:
        screenshot_b64 = _capture_screenshot()
        if not screenshot_b64:
            return {
                "success": False,
                "error": "Failed to capture screenshot",
            }

        return {
            "success": True,
            "action": "screenshot",
            "screenshot": screenshot_b64,
        }
    except Exception as exc:
        logger.error(f"Screenshot failed: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _action_wait(seconds: str) -> dict[str, Any]:
    """Wait for specified seconds."""
    logger.debug(f"Waiting: {seconds}s")

    try:
        duration = float(seconds)
        time.sleep(duration)
        logger.info(f"Wait completed: {duration}s")

        return {
            "success": True,
            "action": "wait",
            "seconds": duration,
        }
    except Exception as exc:
        logger.error(f"Wait failed: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _capture_screenshot() -> Optional[str]:
    """Capture active window and return base64."""
    try:
        # Get active window
        active_window = pygetwindow.getActiveWindow()
        if not active_window:
            logger.warning("No active window found")
            return None

        # Capture window region
        region = {
            "left": max(0, active_window.left),
            "top": max(0, active_window.top),
            "width": max(1, active_window.width),
            "height": max(1, active_window.height),
        }

        with mss() as sct:
            img = sct.grab(region)
            pil_img = Image.frombytes("RGB", img.size, img.rgb)

            # Convert to PNG bytes
            img_bytes = io.BytesIO()
            pil_img.save(img_bytes, format="PNG")
            img_b64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        logger.debug(f"Screenshot: {region['width']}x{region['height']}")
        return img_b64

    except Exception as exc:
        logger.error(f"Screenshot capture failed: {exc}")
        return None


def start_server(
    gateway: SecurityGateway,
    audit_logger: AuditLogger,
    host: str = "0.0.0.0",
    port: int = 8765,
) -> None:
    """Start the NEMO HTTP server."""
    set_dependencies(gateway, audit_logger)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info(f"Starting NEMO HTTP Server on {host}:{port}")
    app.run(host=host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    # For direct testing
    from core.security.gateway_v2 import SecurityGateway as GW
    from core.security.audit_logger_v2 import AuditLogger as AL

    gateway = GW()
    audit_logger = AL()

    start_server(gateway, audit_logger)
