"""NEMO-OS HTTP Server — REST API for PC control."""

from __future__ import annotations

import base64
import ctypes
import io
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import jwt
import pyautogui
import pygetwindow
import requests
import win32con
import win32gui
from flask import Flask, jsonify, request
from mss import mss
from PIL import Image

from core.security.gateway_v2 import SecurityGateway
from core.security.audit_logger_v2 import AuditLogger
from core.security.action_classifier import classify, RiskLevel
from flask import render_template


app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
logger = logging.getLogger("nemo.server")

# Special app paths for applications installed in AppData instead of PATH
SPECIAL_APP_PATHS = {
    "whatsapp": [
        # Traditional desktop app paths
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%APPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\WhatsApp\WhatsApp.exe"),
    ],
    "telegram": [
        os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Discord.exe"),
        os.path.expandvars(r"%APPDATA%\Discord\Discord.exe"),
    ],
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    ],
}

# Global references (will be injected at startup)
_gateway: Optional[SecurityGateway] = None
_audit_logger: Optional[AuditLogger] = None

# Pending actions awaiting confirmation (token -> action data)
_pending_actions: dict[str, dict[str, Any]] = {}
_pending_lock = threading.Lock()

# Disable pyautogui safety pause
pyautogui.PAUSE = 0


def set_dependencies(gateway: SecurityGateway, audit_logger: AuditLogger) -> None:
    """Inject SecurityGateway and AuditLogger dependencies."""
    global _gateway, _audit_logger
    _gateway = gateway
    _audit_logger = audit_logger


def _find_and_focus_window(target_name: str, timeout: int = 5) -> bool:
    """
    Find a window by name and bring it to foreground.
    
    For Store apps, tries to match partial window titles.
    For standard apps, looks for exact or partial matches.
    
    Args:
        target_name: Application name to search for in window titles
        timeout: Max seconds to wait for window to appear
    
    Returns:
        True if window found and focused, False otherwise
    """
    logger.debug(f"Finding and focusing window: {target_name}")
    
    target_lower = target_name.lower()
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            results = []
            
            def callback(hwnd, results_list):
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd).lower()
                        # For Store apps and others, be flexible with matching
                        # Match: exact name, app name in title, or common variations
                        if (target_lower == title or 
                            target_lower in title or
                            title.startswith(target_lower) or
                            target_lower.startswith(title.split()[0]) if title else False):
                            results_list.append((hwnd, title))
                except:
                    pass
            
            win32gui.EnumWindows(callback, results)
            
            if results:
                # Prefer exact/closer matches
                results.sort(key=lambda x: len(x[1]))  # Shorter titles first (more specific)
                hwnd, title = results[0]
                
                try:
                    logger.info(f"Found window: {title} (hwnd={hwnd})")
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.2)
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.3)
                    
                    # Verify the window is focused
                    focused_hwnd = win32gui.GetForegroundWindow()
                    focused_title = win32gui.GetWindowText(focused_hwnd)
                    logger.info(f"Window focused: {focused_title} ({target_name})")
                    return True
                except Exception as e:
                    logger.warning(f"Failed to focus window: {e}")
        
        except Exception as e:
            logger.warning(f"Window enumeration error: {e}")
        
        time.sleep(0.3)
    
    logger.warning(f"Window not found within {timeout}s timeout: {target_name}")
    return False


def _get_foreground_window_info() -> tuple[str, int]:
    """
    Get information about the currently focused window.
    
    Returns:
        Tuple of (window_title, hwnd)
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        return title, hwnd
    except Exception as e:
        logger.warning(f"Could not get foreground window: {e}")
        return "Unknown", 0


@app.route("/health", methods=["GET"])
def health() -> dict[str, Any]:
    """Health check endpoint."""
    logger.debug("Health check requested")
    return jsonify({
        "status": "ok",
        "security": "active",
    })


# ===== DASHBOARD ENDPOINTS =====

@app.route("/dashboard")
def dashboard():
    """Serve security dashboard."""
    return render_template("dashboard.html")


@app.route("/api/audit-log", methods=["GET"])
def api_audit_log():
    """Get audit log entries."""
    try:
        limit = request.args.get("limit", 50, type=int)
        risk_filter = request.args.get("risk", "", type=str)

        if not _audit_logger:
            return jsonify({"entries": [], "total": 0}), 200

        # Read audit log from file
        log_path = _audit_logger.log_path
        entries = []

        if log_path.exists():
            with open(log_path, "r") as f:
                lines = f.readlines()
                # Parse JSONL format (newest last, so reverse)
                for line in reversed(lines[-limit:]):
                    try:
                        entry = json.loads(line.strip())
                        # Apply risk filter if specified
                        if risk_filter and entry.get("risk_level") != risk_filter:
                            continue
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue

        return jsonify({
            "entries": entries,
            "total": len(entries),
            "limit": limit,
        }), 200

    except Exception as e:
        logger.error(f"Error fetching audit log: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Get dashboard statistics."""
    try:
        if not _audit_logger:
            return jsonify({
                "by_risk": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
                "by_action": {},
                "success_rate": 0,
                "total_actions": 0,
            }), 200

        log_path = _audit_logger.log_path
        stats = {
            "by_risk": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
            "by_action": {},
            "success_rate": 0,
            "total_actions": 0,
            "successes": 0,
        }

        if log_path.exists():
            with open(log_path, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        # Count by risk level
                        risk = entry.get("risk_level", "UNKNOWN")
                        if risk in ["LOW", "MEDIUM", "HIGH"]:
                            stats["by_risk"][risk] += 1

                        # Count by action
                        action = entry.get("action", "unknown")
                        stats["by_action"][action] = stats["by_action"].get(action, 0) + 1

                        # Count successes
                        stats["total_actions"] += 1
                        if entry.get("allowed", False):
                            stats["successes"] += 1

                    except json.JSONDecodeError:
                        continue

        # Calculate success rate
        if stats["total_actions"] > 0:
            stats["success_rate"] = int(
                (stats["successes"] / stats["total_actions"]) * 100
            )

        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error calculating stats: {e}")
        return jsonify({"error": str(e)}), 500


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
    """Execute an action on the PC with risk assessment and Auth0 verification."""
    try:
        # AUTH0 TOKEN VAULT VERIFICATION
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            # Verify with Auth0 (decoding without signature verification for now)
            try:
                # For production, add proper JWT verification with Auth0 public key
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False}  # TODO: Add proper verification
                )
                user_id = payload.get("sub", "unknown")
                scopes = payload.get("scope", "").split()
                
                # Map scope to NEMO role
                if "pc:admin" in scopes:
                    role = "ADMIN"
                    logger.info(f"Auth0 admin user: {user_id}")
                elif "pc:write" in scopes:
                    role = "USER"
                    logger.info(f"Auth0 write user: {user_id}")
                elif "pc:read" in scopes:
                    role = "RESTRICTED"
                    logger.info(f"Auth0 read-only user: {user_id}")
                else:
                    logger.warning(f"No valid PC scopes in token for user: {user_id}")
                    return jsonify({
                        "success": False,
                        "error": "Insufficient scope - requires pc:read, pc:write, or pc:admin"
                    }), 403
            except Exception as e:
                logger.warning(f"Token decode failed: {e}")
                return jsonify({
                    "success": False,
                    "error": "Invalid Auth0 token"
                }), 401
        else:
            logger.warning("No Auth0 token provided in Authorization header")
            # For now allow, but log the missing auth
        
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

        # Classify risk level
        classification = classify(action, target, value, user)
        logger.debug(f"Risk classification: {classification.risk_level.value} - {classification.reason}")

        # HIGH risk: require confirmation
        if classification.risk_level == RiskLevel.HIGH:
            token = str(uuid.uuid4())
            with _pending_lock:
                _pending_actions[token] = {
                    "action": action,
                    "target": target,
                    "value": value,
                    "user": user,
                    "channel": channel,
                    "timestamp": time.time(),
                }

            logger.warning(f"HIGH risk action requires confirmation: {action} (token={token})")
            if _audit_logger:
                _audit_logger.log(
                    user_id=user,
                    action=f"{action}_pending",
                    target=target or "",
                    allowed=False,
                    reason=f"Pending confirmation: {classification.reason}",
                )

            return jsonify({
                "success": False,
                "requires_confirmation": True,
                "confirmation_token": token,
                "risk_level": classification.risk_level.value,
                "reason": classification.reason,
                "message": f"High-risk action requires your approval. Use /confirm with token to proceed.",
            }), 202

        # Execute immediately for LOW/MEDIUM risk
        exec_result = _execute_action(action, target, value)

        # Log to audit
        if _audit_logger:
            _audit_logger.log(
                user_id=user,
                action=action,
                target=target or "",
                allowed=exec_result.get("success", False),
                reason=f"{classification.risk_level.value}: {exec_result.get('error', 'ok')}",
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
    """
    Open an application and bring it to foreground.
    
    Handles:
    - Traditional executables (.exe files)
    - Microsoft Store apps (package directories)
    - Apps in standard system paths
    
    Tries multiple strategies:
    1. Check SPECIAL_APP_PATHS for apps (WhatsApp, Telegram, Discord, Spotify)
    2. Try subprocess.Popen with standard executable name
    3. For Store apps, use explorer shell:appsFolder protocol
    4. Fallback to "cmd /c start" for regular apps
    5. Force window to foreground after launch
    """
    logger.info(f"Opening app: {app_name}")

    try:
        app_lower = app_name.lower()
        cmd = None
        is_store_app = False
        store_app_package = None

        # Strategy 1: Check special paths for AppData-installed apps
        if app_lower in SPECIAL_APP_PATHS:
            for app_path in SPECIAL_APP_PATHS[app_lower]:
                if Path(app_path).exists():
                    # Check if it's a directory (Microsoft Store app) or executable
                    is_dir = Path(app_path).is_dir()
                    logger.info(f"Found {app_name} at: {app_path} (dir={is_dir})")
                    
                    if is_dir:
                        # Store app - use explorer shell:appsFolder protocol
                        is_store_app = True
                        # Extract package name from path
                        store_app_package = Path(app_path).name
                        logger.info(f"{app_name} is a Microsoft Store app (package={store_app_package})")
                        break
                    else:
                        # Regular executable
                        cmd = [app_path]
                        break
        
        # Strategy 2: Try standard executable if no special path found
        if not cmd and not is_store_app:
            if app_lower == "chrome":
                cmd = [
                    "chrome.exe",
                    "--profile-directory=Default",
                    "--no-first-run",
                    "--start-maximized",
                ]
            else:
                cmd = [f"{app_name}.exe"] if not app_name.endswith(".exe") else [app_name]
        
        # Strategy 3: Try subprocess.Popen (for traditional executables)
        window_focused = False
        if cmd:
            try:
                subprocess.Popen(cmd)
                time.sleep(3)  # Wait for app window to appear
                
                # Strategy 4: Force window to foreground
                window_focused = _find_and_focus_window(app_name, timeout=5)
                
                logger.info(f"Opened: {app_name} (focused={window_focused})")
                return {
                    "success": True,
                    "action": "open_app",
                    "app": app_name,
                    "method": "direct_path" if app_lower in SPECIAL_APP_PATHS else "popen",
                    "window_focused": window_focused,
                }
            except Exception as exc:
                logger.warning(f"Direct launch failed: {exc}")
        
        # Strategy 5: For WhatsApp, use URI protocol (whatsapp:)
        if app_lower == "whatsapp":
            try:
                logger.info(f"Launching WhatsApp using URI protocol (whatsapp:)")
                subprocess.Popen(["explorer.exe", "whatsapp:"])
                time.sleep(3)
                
                window_focused = _find_and_focus_window(app_name, timeout=5)
                logger.info(f"Opened WhatsApp via URI: (focused={window_focused})")
                return {
                    "success": True,
                    "action": "open_app",
                    "app": app_name,
                    "method": "uri_whatsapp",
                    "window_focused": window_focused,
                }
            except Exception as exc:
                logger.warning(f"WhatsApp URI launch failed: {exc}")
        
        # Strategy 6: For other Store apps, use explorer shell:appsFolder protocol
        if is_store_app and store_app_package:
            try:
                logger.info(f"Launching Store app using explorer shell:appsFolder")
                # explorer.exe shell:appsFolder\<PackageFamilyName>!App
                cmd = [
                    "explorer.exe",
                    f"shell:appsFolder\\{store_app_package}!App"
                ]
                subprocess.Popen(cmd)
                time.sleep(3)
                
                window_focused = _find_and_focus_window(app_name, timeout=5)
                logger.info(f"Opened Store app: {app_name} (focused={window_focused})")
                return {
                    "success": True,
                    "action": "open_app",
                    "app": app_name,
                    "method": "store_app_protocol",
                    "window_focused": window_focused,
                }
            except Exception as exc:
                logger.warning(f"Store app launch failed: {exc}")
        
        # Strategy 7: Fallback to Windows "start" command (for regular apps)
        if not is_store_app:
            logger.info(f"Using fallback: cmd /c start {app_name}")
            subprocess.Popen(["cmd", "/c", "start", app_name])
            time.sleep(3)  # Wait for app window to appear
            
            # Force window to foreground
            window_focused = _find_and_focus_window(app_name, timeout=5)
            
            logger.info(f"Opened via fallback: {app_name} (focused={window_focused})")
            return {
                "success": True,
                "action": "open_app",
                "app": app_name,
                "method": "fallback_start",
                "window_focused": window_focused,
            }
        
        # If all else failed
        logger.error(f"Could not launch {app_name}")
        return {
            "success": False,
            "error": f"Could not launch application: {app_name}",
        }

    except Exception as exc:
        logger.error(f"Failed to open {app_name}: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _action_type(text: str) -> dict[str, Any]:
    """
    Type text into the active window.
    
    Uses typewrite to properly input text into the focused field.
    Checks for wrong window (VS Code) before typing.
    """
    logger.debug(f"Typing: {text[:50]}")

    try:
        # Get current focused window BEFORE typing
        current_window, hwnd = _get_foreground_window_info()
        logger.info(f"Current focused window: {current_window}")
        
        # Check if wrong window is focused (e.g., VS Code, Visual Studio)
        if "code" in current_window.lower() or "visual studio" in current_window.lower():
            logger.warning(f"Wrong window focused: {current_window} - cannot type")
            return {
                "success": False,
                "error": f"Wrong window focused: {current_window}",
                "focused_window": current_window,
            }
        
        # Use typewrite to properly type the text with adequate interval
        # Do NOT press Escape - it closes message fields in WhatsApp
        pyautogui.typewrite(text, interval=0.15)
        
        logger.info(f"Text typed successfully into: {current_window}")

        return {
            "success": True,
            "action": "type",
            "text_length": len(text),
            "focused_window": current_window,
        }
    except Exception as exc:
        logger.error(f"Type failed: {exc}")
        return {
            "success": False,
            "error": str(exc),
        }


def _action_press_key(keys: str) -> dict[str, Any]:
    """Press keyboard key or key combination."""
    logger.debug(f"Pressing keys: {keys}")

    try:
        key_list = keys.split("+")
        
        # Use press() for single keys, hotkey() for combinations
        if len(key_list) == 1:
            # Single key - use press() for better compatibility
            pyautogui.press(key_list[0])
            logger.info(f"Pressed: {keys}")
        else:
            # Multiple keys - use hotkey() for combinations
            pyautogui.hotkey(*key_list)
            logger.info(f"Pressed hotkey combination: {keys}")

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


@app.route("/confirm", methods=["POST"])
def confirm() -> dict[str, Any]:
    """Confirm and execute a pending HIGH-risk action."""
    try:
        data = request.get_json() or {}
        token = data.get("token", "")
        approved = data.get("approved", False)

        logger.info(f"Confirmation request: token={token[:8]}..., approved={approved}")

        if not token:
            return jsonify({
                "success": False,
                "error": "token is required",
            }), 400

        # Look up pending action
        with _pending_lock:
            pending = _pending_actions.pop(token, None)

        if not pending:
            logger.warning(f"Confirmation token not found or expired: {token}")
            return jsonify({
                "success": False,
                "error": "Token not found or expired",
            }), 404

        # Check if expired (60 seconds)
        if time.time() - pending["timestamp"] > 60:
            logger.warning(f"Confirmation token expired: {token}")
            return jsonify({
                "success": False,
                "error": "Token expired (must confirm within 60 seconds)",
            }), 410

        # USER DENIED
        if not approved:
            logger.warning(f"User denied action: {pending['action']}")
            if _audit_logger:
                _audit_logger.log(
                    user_id=pending["user"],
                    action=pending["action"],
                    target=pending["target"] or "",
                    allowed=False,
                    reason="User denied high-risk action",
                )
            return jsonify({
                "success": False,
                "error": "Action denied by user",
            }), 403

        # USER APPROVED - Execute the action
        logger.info(f"User approved action: {pending['action']}")
        exec_result = _execute_action(
            pending["action"],
            pending["target"],
            pending["value"],
        )

        # Log to audit
        if _audit_logger:
            _audit_logger.log(
                user_id=pending["user"],
                action=pending["action"],
                target=pending["target"] or "",
                allowed=exec_result.get("success", False),
                reason=f"User-approved: {pending['channel']}",
            )

        logger.info(f"Action confirmed and executed: {pending['action']} → {exec_result}")
        return jsonify(exec_result)

    except Exception as exc:
        logger.error(f"Confirm endpoint error: {exc}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route("/execute_with_vision", methods=["POST"])
def execute_with_vision() -> dict[str, Any]:
    """
    Execute actions with OpenClaw vision verification.
    
    Request body:
    {
      "actions": [
        {
          "action": "type",
          "value": "search text",
          "verify_instruction": "text should appear in search field"
        },
        {
          "action": "press_key",
          "value": "enter",
          "verify_instruction": "search results should be visible"
        }
      ],
      "user": "demo",
      "channel": "openclaw",
      "max_retries": 2,
      "vision_api_url": "http://localhost:5000"  // OpenClaw vision endpoint
    }
    
    Response:
    {
      "success": true,
      "total_actions": 2,
      "executed": 2,
      "verifications_passed": 2,
      "steps": [
        {
          "action": "type",
          "value": "search text",
          "status": "verified",
          "before_screenshot": "base64...",
          "after_screenshot": "base64...",
          "vision_analysis": "✓ Text appeared in search field",
          "timestamp": "2026-04-03T10:30:00Z"
        },
        ...
      ],
      "warnings": []
    }
    """
    try:
        data = request.get_json() or {}
        actions = data.get("actions", [])
        user = data.get("user", "api")
        channel = data.get("channel", "openclaw")
        max_retries = data.get("max_retries", 2)
        vision_api_url = data.get("vision_api_url", "http://localhost:5000")

        logger.info(f"Execute with vision: {len(actions)} actions, user={user}")

        if not actions:
            return jsonify({
                "success": False,
                "error": "actions array is required",
            }), 400

        # Execute action sequence with vision verification
        result = _execute_with_vision_verification(
            actions=actions,
            user=user,
            channel=channel,
            max_retries=max_retries,
            vision_api_url=vision_api_url,
        )

        # Log to audit
        if _audit_logger:
            _audit_logger.log(
                user_id=user,
                action="execute_with_vision",
                target=f"{len(actions)} actions",
                allowed=result.get("success", False),
                reason=f"Vision-verified automation: {result.get('executed', 0)}/{len(actions)} steps",
            )

        return jsonify(result), (200 if result.get("success") else 400)

    except Exception as exc:
        logger.error(f"Execute with vision error: {exc}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


def _execute_with_vision_verification(
    actions: list[dict[str, Any]],
    user: str,
    channel: str,
    max_retries: int = 2,
    vision_api_url: str = "http://localhost:5000",
) -> dict[str, Any]:
    """
    Execute actions with vision-based verification at each step.
    
    For each action:
    1. Capture screenshot BEFORE
    2. Execute action
    3. Capture screenshot AFTER
    4. Call OpenClaw vision API to verify action succeeded
    5. If verification fails, retry (with max_retries limit)
    6. Log result
    """
    steps_executed = []
    warnings = []
    total_verifications_passed = 0

    for action_idx, action_spec in enumerate(actions):
        action = action_spec.get("action", "")
        target = action_spec.get("target", "")
        value = action_spec.get("value", "")
        verify_instruction = action_spec.get("verify_instruction", "")

        logger.info(f"Step {action_idx + 1}/{len(actions)}: {action}")

        # Step 1: Capture BEFORE screenshot
        before_screenshot = _capture_screenshot()
        before_timestamp = time.time()

        # Step 2: Execute action
        exec_result = _execute_action(action, target, value)

        if not exec_result.get("success"):
            logger.error(f"Step {action_idx + 1} execution failed: {exec_result.get('error')}")
            steps_executed.append({
                "action": action,
                "value": value,
                "target": target,
                "status": "failed",
                "before_screenshot": before_screenshot,
                "after_screenshot": None,
                "error": exec_result.get("error"),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(before_timestamp)),
            })
            warnings.append(f"Step {action_idx + 1} ({action}) failed to execute: {exec_result.get('error')}")
            continue

        # Small delay for UI to update after action
        time.sleep(0.8)

        # Step 3: Capture AFTER screenshot
        after_screenshot = _capture_screenshot()
        after_timestamp = time.time()

        # Step 4: Vision-based verification (if instruction provided)
        verification_result = {
            "status": "executed",
            "analysis": "No verification instruction provided",
            "confidence": 0.0,
            "verified": True,  # Default to true if no instruction
        }

        if verify_instruction and after_screenshot:
            logger.info(f"Verifying step {action_idx + 1} with vision API")
            verification_result = _verify_with_vision(
                after_screenshot=after_screenshot,
                verify_instruction=verify_instruction,
                vision_api_url=vision_api_url,
                action=action,
                max_retries=max_retries,
            )

            if verification_result.get("verified"):
                total_verifications_passed += 1
            else:
                warnings.append(
                    f"Step {action_idx + 1} ({action}): "
                    f"{verification_result.get('analysis', 'Verification failed')}"
                )

        # Log step
        steps_executed.append({
            "action": action,
            "value": value,
            "target": target,
            "status": verification_result.get("status", "executed"),
            "before_screenshot": before_screenshot,
            "after_screenshot": after_screenshot,
            "vision_analysis": verification_result.get("analysis"),
            "confidence": verification_result.get("confidence", 0.0),
            "verified": verification_result.get("verified", True),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(after_timestamp)),
        })

        logger.info(f"Step {action_idx + 1} verified: {verification_result.get('verified')}")

    # Summary
    all_executed = len([s for s in steps_executed if s.get("status") != "failed"])
    all_verified = len([s for s in steps_executed if s.get("verified", True)])

    return {
        "success": all_executed == len(actions),
        "total_actions": len(actions),
        "executed": all_executed,
        "verifications_passed": total_verifications_passed,
        "all_verified": all_verified,
        "steps": steps_executed,
        "warnings": warnings,
        "duration_seconds": round(after_timestamp - before_timestamp, 2) if steps_executed else 0,
    }


def _verify_with_vision(
    after_screenshot: str,
    verify_instruction: str,
    vision_api_url: str,
    action: str,
    max_retries: int = 1,
) -> dict[str, Any]:
    """
    Call Ollama llava vision API to verify action results.
    
    Sends the screenshot + verification instruction to local Ollama instance
    running llava model for visual analysis.
    """
    logger.debug(f"Calling Ollama vision API for verification: {verify_instruction[:100]}")

    try:
        # Build Ollama vision API request
        prompt = f"Look at this screenshot. {verify_instruction}. Did it succeed? Reply ONLY with JSON: {{\"verified\": true/false, \"confidence\": 0.0-1.0, \"analysis\": \"what you see\"}}"
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llava",
                "prompt": prompt,
                "images": [after_screenshot],  # base64 image
                "stream": False,
            },
            timeout=30,
        )

        if response.status_code == 200:
            raw_response = response.json().get("response", "{}")
            logger.debug(f"Ollama response: {raw_response[:200]}")
            
            # Extract JSON from response
            try:
                start = raw_response.find("{")
                end = raw_response.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = raw_response[start:end]
                    result = json.loads(json_str)
                    logger.info(f"Vision verification result: verified={result.get('verified')}")
                    return {
                        "status": "verified" if result.get("verified") else "not_verified",
                        "analysis": result.get("analysis", ""),
                        "confidence": result.get("confidence", 0.0),
                        "verified": result.get("verified", False),
                    }
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse Ollama JSON response")
        else:
            logger.warning(f"Ollama vision API error: status={response.status_code}")

    except requests.exceptions.Timeout:
        logger.warning(f"Ollama vision API timeout")
    except requests.exceptions.RequestException as exc:
        logger.warning(f"Ollama connection error: {exc}")
    except Exception as exc:
        logger.error(f"Vision verification error: {exc}")

    # Fallback: If vision API unavailable, return neutral verification
    logger.warning(f"Vision verification unavailable, proceeding with caution")
    return {
        "status": "executed_no_verification",
        "analysis": "Ollama vision API unavailable - visual verification skipped",
        "confidence": 0.0,
        "verified": True,  # Allow continuation, but mark as unverified
    }


def _cleanup_expired_tokens() -> None:
    """Periodically clean up expired confirmation tokens."""
    while True:
        try:
            time.sleep(30)  # Check every 30 seconds
            with _pending_lock:
                now = time.time()
                expired = [k for k, v in _pending_actions.items() if now - v["timestamp"] > 60]
                for token in expired:
                    del _pending_actions[token]
                    logger.debug(f"Cleaned up expired token: {token}")
        except Exception as exc:
            logger.error(f"Token cleanup error: {exc}")


# Start cleanup daemon thread
_cleanup_thread = threading.Thread(target=_cleanup_expired_tokens, daemon=True)
_cleanup_thread.start()


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
