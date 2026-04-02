"""
Threat Detector - Pattern-based threat analysis for NEMO Security Layer.
Scans AI commands for dangerous threats before execution.
"""

import re
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class ThreatLevel(str, Enum):
    """Threat severity levels."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatResult(BaseModel):
    """Result of threat analysis."""
    safe: bool
    level: ThreatLevel
    threat_type: Optional[str] = None
    matched_rule: Optional[str] = None
    input_text: str
    sanitized: Optional[str] = None

    class Config:
        use_enum_values = True


class ThreatDetector:
    """Pattern-based threat detection engine."""

    def __init__(self, custom_rules: Optional[dict] = None):
        """
        Initialize threat detector with default + custom rules.
        
        Args:
            custom_rules: dict of {name: pattern} for custom threat patterns
        """
        self._rules: List[tuple[str, str, ThreatLevel, re.Pattern]] = []
        
        # Compile default patterns by category
        self._add_category("prompt_injection", ThreatLevel.HIGH, [
            r"ignore\s+(all\s+)?(previous|prior|your|the)?\s*(instructions|rules|guidelines|constraints|system)",
            r"you are now",
            r"pretend (you are|to be|you're)",
            r"your new (instructions|role|purpose|task) (is|are)",
            r"forget (everything|all|your)",
            r"act as (if )?you (have no|don't have) (restrictions|limits|rules)",
            r"DAN mode",
            r"jailbreak",
            r"override (safety|security|restrictions|guidelines)",
            r"system prompt",
            r"\[\[.*?\]\]",
            r"<\|.*?\|>",
        ])
        
        # Linux dangerous commands
        self._add_category("dangerous_command_linux", ThreatLevel.CRITICAL, [
            r"rm\s+-rf\s+[/~]",
            r"rm\s+--no-preserve-root",
            r":\(\)\{.*\};:",
            r"dd\s+if=.*of=/dev/",
            r"mkfs\.",
            r"shred\s+",
            r"wipefs",
            r"chmod\s+-R\s+777\s+/",
            r"curl.*\|\s*(bash|sh|python)",
            r"wget.*\|\s*(bash|sh|python)",
            r"nc\s+-e",
            r"/dev/tcp/",
        ])
        
        # Windows dangerous commands
        self._add_category("dangerous_command_windows", ThreatLevel.CRITICAL, [
            r"format\s+[a-zA-Z]:",
            r"del\s+/[sq].*\*",
            r"rd\s+/[sq]\s+[a-zA-Z]:\\",
            r"reg\s+(delete|add).*HKLM\\SYSTEM",
            r"bcdedit",
            r"wmic\s+.*delete",
            r"net\s+user\s+.*\s+/delete",
            r"powershell.*-enc",
            r"powershell.*bypass",
            r"invoke-expression",
            r"iex\(",
        ])
        
        # Data exfiltration
        self._add_category("data_exfiltration", ThreatLevel.CRITICAL, [
            r"(curl|wget|nc|ncat)\s+.*\s+(passwd|shadow|\.ssh|credentials|secrets|\.env|api.?key)",
            r"cat\s+.*(passwd|shadow|authorized_keys|\.ssh|\.aws|credentials)",
            r"type\s+.*\.(env|credentials|config|key|pem|pfx)",
            r"copy\s+.*\.(key|pem|pfx|p12)\s+",
            r"base64.*\/etc\/(passwd|shadow)",
            r"python.*socket.*send",
        ])
        
        # Privilege escalation
        self._add_category("privilege_escalation", ThreatLevel.HIGH, [
            r"sudo\s+su",
            r"sudo\s+bash",
            r"sudo\s+python.*-c",
            r"sudo\s+chmod.*\+s",
            r"pkexec",
            r"doas\s+",
            r"runas\s+/user:.*administrator",
            r"psexec.*-s",
        ])
        
        # Add custom rules if provided
        if custom_rules:
            for name, pattern in custom_rules.items():
                self.add_rule(name, pattern)

    def _add_category(
        self,
        category: str,
        level: ThreatLevel,
        patterns: List[str],
    ) -> None:
        """Compile and add a category of patterns."""
        for pattern in patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
                self._rules.append((category, pattern, level, compiled))
            except re.error:
                pass  # Skip invalid patterns

    def scan(self, text: str) -> ThreatResult:
        """
        Scan text for threats.
        
        Returns first matching threat found, or SAFE if none match.
        """
        if not text or not text.strip():
            return ThreatResult(
                safe=True,
                level=ThreatLevel.SAFE,
                input_text=text,
                sanitized=text,
            )

        # Check all rules in order
        for category, pattern, level, compiled_pattern in self._rules:
            if compiled_pattern.search(text):
                return ThreatResult(
                    safe=False,
                    level=level,
                    threat_type=category,
                    matched_rule=pattern,
                    input_text=text,
                    sanitized=None,
                )

        # No threats found
        return ThreatResult(
            safe=True,
            level=ThreatLevel.SAFE,
            input_text=text,
            sanitized=text,
        )

    def scan_batch(self, texts: List[str]) -> List[ThreatResult]:
        """Scan multiple texts and return results."""
        return [self.scan(text) for text in texts]

    def add_rule(self, name: str, pattern: str) -> None:
        """Add a custom threat rule at runtime."""
        try:
            compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
            self._rules.append((name, pattern, ThreatLevel.HIGH, compiled))
        except re.error:
            raise ValueError(f"Invalid regex pattern: {pattern}")

    def explain(self, result: ThreatResult) -> str:
        """Return human-readable explanation of threat result."""
        if result.safe:
            return "Input is safe."
        
        return (
            f"Blocked [{result.level.upper()}] — "
            f"ThreatType: {result.threat_type} "
            f"matched pattern `{result.matched_rule}`"
        )
