"""
Action Classifier - Risk assessment for PC automation actions.

Classifies every action into 3 risk levels and requires step-up
authentication (confirmation) for HIGH-risk actions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple


class RiskLevel(Enum):
    """Risk classification levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class ClassificationResult:
    """Result of action classification."""
    risk_level: RiskLevel
    reason: str
    requires_confirmation: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
        }


class ActionClassifier:
    """Classify PC automation actions by risk level."""

    # LOW-risk actions (execute immediately)
    LOW_RISK_ACTIONS = {
        "screenshot",
        "wait",
    }

    # Browser apps (safe to open)
    SAFE_APPS = {
        "chrome", "chromium", "firefox", "edge",
        "opera", "brave", "safari",
        "google-chrome", "firefox-esr",
    }

    # System tools (MEDIUM/HIGH risk when opened)
    SYSTEM_TOOLS = {
        "cmd", "cmd.exe", "powershell", "powershell.exe",
        "terminal", "bash", "sh", "zsh", "git-bash",
        "tasklist", "taskkill", "regedit", "services",
        "devmgmt.msc", "diskmgmt.msc",
    }

    # Dangerous patterns (HIGH risk)
    DANGEROUS_KEYWORDS = {
        "delete", "remove", "format", "wipe",
        "shutdown", "restart", "halt", "poweroff",
        "rm", "rmdir", "del", "erase",
        "kill", "pkill", "taskkill",
        "admin", "password", "credential", "token",
        "registry", "regedit", "system32", "hosts",
        "boot", "mbr", "partition", "disk",
        "encryption", "ransomware", "virus",
        ".exe", ".bat", ".ps1", ".cmd", ".scr",
        ".dmg", ".app", ".deb", ".rpm",
    }

    # System folder patterns (HIGH risk when accessed)
    SYSTEM_FOLDERS = {
        "system32", "windows", "program files", "c:\\windows",
        "c:\\program files", "/system", "/usr/bin", "/usr/sbin",
        "/etc", "/root", "/home", "/var/log", "/etc/passwd",
        "registry", "regedit",
    }

    # Safe keyboard shortcuts (don't elevate risk)
    SAFE_HOTKEYS = {
        "enter", "tab", "escape", "space",
        "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+a",
        "alt+tab", "alt+f4",  # These are still medium
        "backspace", "delete",
        "home", "end", "pageup", "pagedown",
        "up", "down", "left", "right",
    }

    # Medium-risk hotkeys
    MEDIUM_HOTKEYS = {
        "alt+f4", "win+r", "win+x", "alt+tab",
        "ctrl+alt+delete", "ctrl+shift+esc",
    }

    def __init__(self):
        """Initialize action classifier."""
        self.logger = logging.getLogger("nemo.classifier")

    def classify(
        self,
        action: str,
        target: str = "",
        value: str = "",
        user: str = "",
    ) -> ClassificationResult:
        """
        Classify an action by risk level.

        Args:
            action: Action type (open_app, type, press_key, click, screenshot, wait)
            target: Action target (app name, coordinates, etc.)
            value: Action value (text, key name, etc.)
            user: User ID (for logging context)

        Returns:
            ClassificationResult with risk level and reason
        """
        self.logger.debug(f"Classifying {action} by {user}: target={target}, value={value}")

        # Route to specific classifier
        if action == "screenshot":
            return self._classify_screenshot()
        elif action == "wait":
            return self._classify_wait()
        elif action == "open_app":
            return self._classify_open_app(target)
        elif action == "type":
            return self._classify_type(value)
        elif action == "press_key":
            return self._classify_press_key(value)
        elif action == "click":
            return self._classify_click(target, value)
        else:
            return ClassificationResult(
                risk_level=RiskLevel.MEDIUM,
                reason=f"Unknown action type: {action}",
                requires_confirmation=True,
            )

    def _classify_screenshot(self) -> ClassificationResult:
        """Screenshot is always LOW risk."""
        return ClassificationResult(
            risk_level=RiskLevel.LOW,
            reason="Screenshot capture is non-destructive",
            requires_confirmation=False,
        )

    def _classify_wait(self) -> ClassificationResult:
        """Wait is always LOW risk."""
        return ClassificationResult(
            risk_level=RiskLevel.LOW,
            reason="Wait action has no side effects",
            requires_confirmation=False,
        )

    def _classify_open_app(self, target: str) -> ClassificationResult:
        """Classify opening an application."""
        if not target:
            return ClassificationResult(
                risk_level=RiskLevel.MEDIUM,
                reason="open_app without target is risky",
                requires_confirmation=True,
            )

        target_lower = target.lower().strip()

        # Check if it's a safe browser
        if target_lower in self.SAFE_APPS:
            return ClassificationResult(
                risk_level=RiskLevel.LOW,
                reason=f"Opening safe browser: {target}",
                requires_confirmation=False,
            )

        # Check for system tools (HIGH risk)
        if target_lower in self.SYSTEM_TOOLS:
            return ClassificationResult(
                risk_level=RiskLevel.HIGH,
                reason=f"Opening system tool: {target}",
                requires_confirmation=True,
            )

        # Check for dangerous keywords in app name
        for keyword in self.DANGEROUS_KEYWORDS:
            if keyword in target_lower:
                return ClassificationResult(
                    risk_level=RiskLevel.HIGH,
                    reason=f"App name contains dangerous keyword: {keyword}",
                    requires_confirmation=True,
                )

        # Check for system folder paths
        for folder in self.SYSTEM_FOLDERS:
            if folder in target_lower:
                return ClassificationResult(
                    risk_level=RiskLevel.HIGH,
                    reason=f"App path contains system folder: {folder}",
                    requires_confirmation=True,
                )

        # Default to MEDIUM risk for unknown apps
        return ClassificationResult(
            risk_level=RiskLevel.MEDIUM,
            reason=f"Unknown application: {target}",
            requires_confirmation=True,
        )

    def _classify_type(self, value: str) -> ClassificationResult:
        """Classify typing text."""
        if not value:
            return ClassificationResult(
                risk_level=RiskLevel.LOW,
                reason="Typing empty string",
                requires_confirmation=False,
            )

        # Very long text might be suspicious
        if len(value) > 200:
            return ClassificationResult(
                risk_level=RiskLevel.MEDIUM,
                reason=f"Text is very long ({len(value)} chars), could be script injection",
                requires_confirmation=True,
            )

        # Check for dangerous patterns in text
        for keyword in ["password", "credential", "token", "admin", "delete", "remove"]:
            if keyword in value.lower():
                return ClassificationResult(
                    risk_level=RiskLevel.MEDIUM,
                    reason=f"Text contains keyword: {keyword}",
                    requires_confirmation=True,
                )

        # Default: typing is LOW risk
        return ClassificationResult(
            risk_level=RiskLevel.LOW,
            reason="Typing text is generally safe",
            requires_confirmation=False,
        )

    def _classify_press_key(self, keys: str) -> ClassificationResult:
        """Classify pressing keyboard keys."""
        if not keys:
            return ClassificationResult(
                risk_level=RiskLevel.LOW,
                reason="No keys pressed",
                requires_confirmation=False,
            )

        keys_lower = keys.lower().strip()

        # Check if it's a medium-risk hotkey
        if keys_lower in self.MEDIUM_HOTKEYS:
            return ClassificationResult(
                risk_level=RiskLevel.MEDIUM,
                reason=f"Medium-risk hotkey: {keys}",
                requires_confirmation=True,
            )

        # Check if it's a safe hotkey
        if keys_lower in self.SAFE_HOTKEYS:
            return ClassificationResult(
                risk_level=RiskLevel.LOW,
                reason=f"Safe hotkey: {keys}",
                requires_confirmation=False,
            )

        # Any other hotkey is potentially risky
        return ClassificationResult(
            risk_level=RiskLevel.MEDIUM,
            reason=f"Unknown hotkey: {keys}",
            requires_confirmation=True,
        )

    def _classify_click(self, target: str, value: str) -> ClassificationResult:
        """Classify mouse clicks."""
        # Clicking on coordinates is generally MEDIUM risk
        # (we don't know what's at those coordinates)
        return ClassificationResult(
            risk_level=RiskLevel.MEDIUM,
            reason="Click on unknown coordinates requires confirmation",
            requires_confirmation=True,
        )


# Singleton instance
_classifier = ActionClassifier()


def classify(
    action: str,
    target: str = "",
    value: str = "",
    user: str = "",
) -> ClassificationResult:
    """
    Classify an action by risk level (module-level convenience function).

    Args:
        action: Action type
        target: Action target
        value: Action value
        user: User performing action

    Returns:
        ClassificationResult
    """
    return _classifier.classify(action, target, value, user)
