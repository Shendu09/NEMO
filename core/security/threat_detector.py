"""
Threat Detector - Pattern-based threat analysis for NEMO Security Layer.
Scans AI-generated commands for dangerous patterns before execution.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ThreatLevel(str, Enum):
    """Threat severity levels."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Categories of threats."""
    PROMPT_INJECTION = "prompt_injection"
    DANGEROUS_COMMAND = "dangerous_command"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"


@dataclass
class ThreatRule:
    """A pattern rule for threat detection."""
    pattern: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    description: str


@dataclass
class ThreatResult:
    """Result of threat analysis."""
    safe: bool
    level: ThreatLevel
    threat_type: Optional[ThreatType]
    matched_rule: Optional[str]
    input_text: str


class ThreatDetector:
    """
    Scans text for dangerous patterns and threats.
    Uses regex-based pattern matching compiled with IGNORECASE and DOTALL flags.
    """

    def __init__(self):
        """Initialize with default threat patterns."""
        self.rules: List[ThreatRule] = []
        self._compiled_rules: List[tuple] = []
        
        # Initialize default dangerous patterns
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """Initialize default threat detection rules."""
        
        # PROMPT INJECTION patterns
        prompt_injection_patterns = [
            (
                r"(?:ignore|disregard)\s+(?:the\s+)?(?:following\s+)?instructions",
                "ignore instructions",
            ),
            (r"you\s+are\s+now", "you are now"),
            (r"pretend\s+to\s+be", "pretend to be"),
            (r"DAN\s*mode|DAN\s*jailbreak", "DAN mode"),
            (r"(?:jailbreak|unlock|break)\s+(?:safety|restrictions|guidelines)",
             "jailbreak attempt"),
            (r"override\s+(?:safety|restrictions|guidelines)", "override safety"),
            (r"<!--.*?-->|\"\"?:\s*\"", "hidden instruction wrapper"),
            (r"<system>.*?</system>", "system tag injection"),
            (r"<<<.*?>>>", "hidden prompt markers"),
        ]
        
        for pattern, desc in prompt_injection_patterns:
            self.add_rule(
                pattern=pattern,
                threat_type=ThreatType.PROMPT_INJECTION,
                threat_level=ThreatLevel.CRITICAL,
                description=f"Prompt injection attempt: {desc}",
            )

        # DANGEROUS OS COMMANDS patterns
        dangerous_commands = [
            (r"rm\s+-rf\s+/\s*$", "rm -rf /"),
            (r":\(\)\s*{\s*:\|:\s*&\s*}\s*;:", "fork bomb"),
            (r"dd\s+(?:if|of)=/dev/", "dd to /dev/"),
            (r"del\s+/s\s+/q\s*C:", "del C: /s /q"),
            (r"format\s+C:|format\s+\*:", "format C: or *:"),
            (r"PowerShell\s+-(?:enc|encoded|e)\s+", "PowerShell encoded"),
            (r"curl\s+.*?\|\s*(?:bash|sh|zsh)", "curl pipe bash"),
            (r"wget\s+.*?\|\s*(?:bash|sh|zsh)", "wget pipe bash"),
            (r"nc\s+-[lnve]+\s+.*?-e\s+(?:bash|sh)", "netcat reverse shell"),
            (r"/dev/tcp/", "/dev/tcp reverse shell"),
            (r"wmic\s+.*?delete", "wmic delete"),
            (r"bcdedit\s+/delete", "bcdedit delete"),
            (r"diskpart\s+/s\s+.*\.txt", "diskpart script"),
            (r"(?:chkdsk|fsutil)\s+.*?/F\s+C:", "force disk check C:"),
        ]
        
        for pattern, desc in dangerous_commands:
            self.add_rule(
                pattern=pattern,
                threat_type=ThreatType.DANGEROUS_COMMAND,
                threat_level=ThreatLevel.CRITICAL,
                description=f"Dangerous OS command: {desc}",
            )

        # DATA EXFILTRATION patterns
        exfiltration_patterns = [
            (
                r"(?:curl|wget)\s+.*?(?:passwd|shadow|\.ssh|credentials|\.env|\.git)",
                "exfil via curl/wget",
            ),
            (r"cat\s+(?:/etc)?/?(?:passwd|shadow|hosts)", "cat passwd/shadow"),
            (
                r"base64\s+.*?(?:passwd|shadow|ssh|env).*?\|\s*(?:curl|wget|nc)",
                "base64 exfil",
            ),
            (r"scp\s+.*?(?:\.ssh|\.env|credentials)", "scp credential files"),
            (r"rsync\s+.*?(?:\.ssh|\.env|credentials)", "rsync credential files"),
            (r"send.*?(?:/etc/passwd|\.ssh/id_rsa|\.env)", "socket send credentials"),
        ]
        
        for pattern, desc in exfiltration_patterns:
            self.add_rule(
                pattern=pattern,
                threat_type=ThreatType.DATA_EXFILTRATION,
                threat_level=ThreatLevel.HIGH,
                description=f"Data exfiltration: {desc}",
            )

        # PRIVILEGE ESCALATION patterns
        escalation_patterns = [
            (r"sudo\s+(?:su|bash|sh|dash)\s*$", "sudo su/bash"),
            (r"sudo\s+-[a-z]*s", "sudo shell escalation"),
            (r"pkexec\s+(?:bash|sh|systemctl)", "pkexec escalation"),
            (r"runas\s+/user:administrator", "runas admin"),
            (r"psexec\s+-s\s+-i", "psexec SYSTEM"),
            (r"chmod\s+\+s\s+", "setuid SUID"),
            (r"chown\s+root:\s*\s+.*?-s", "chown root setuid"),
            (r"sudo\s+-l", "sudo -l probe"),
        ]
        
        for pattern, desc in escalation_patterns:
            self.add_rule(
                pattern=pattern,
                threat_type=ThreatType.PRIVILEGE_ESCALATION,
                threat_level=ThreatLevel.HIGH,
                description=f"Privilege escalation: {desc}",
            )

    def add_rule(
        self,
        pattern: str,
        threat_type: ThreatType,
        threat_level: ThreatLevel,
        description: str,
    ) -> None:
        """
        Add a custom threat detection rule.
        
        Args:
            pattern: Regex pattern to match
            threat_type: Type of threat (from ThreatType enum)
            threat_level: Severity level (from ThreatLevel enum)
            description: Human-readable description of the threat
        """
        rule = ThreatRule(
            pattern=pattern,
            threat_type=threat_type,
            threat_level=threat_level,
            description=description,
        )
        self.rules.append(rule)
        
        # Compile pattern with flags
        try:
            compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
            self._compiled_rules.append((compiled, rule))
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {pattern}") from e

    def scan(self, text: str) -> ThreatResult:
        """
        Scan text for threats.
        
        Args:
            text: Text to scan
            
        Returns:
            ThreatResult indicating safety and any detected threats
        """
        if not text or not text.strip():
            return ThreatResult(
                safe=True,
                level=ThreatLevel.SAFE,
                threat_type=None,
                matched_rule=None,
                input_text=text,
            )

        # Check all compiled rules
        highest_threat_level = ThreatLevel.SAFE
        matched_threat_type = None
        matched_description = None

        for compiled_pattern, rule in self._compiled_rules:
            if compiled_pattern.search(text):
                # Found a match - determine if this is the highest threat
                threat_order = [
                    ThreatLevel.SAFE,
                    ThreatLevel.LOW,
                    ThreatLevel.MEDIUM,
                    ThreatLevel.HIGH,
                    ThreatLevel.CRITICAL,
                ]
                
                if threat_order.index(rule.threat_level) > threat_order.index(
                    highest_threat_level
                ):
                    highest_threat_level = rule.threat_level
                    matched_threat_type = rule.threat_type
                    matched_description = rule.description

        # Determine if safe
        is_safe = highest_threat_level == ThreatLevel.SAFE

        return ThreatResult(
            safe=is_safe,
            level=highest_threat_level,
            threat_type=matched_threat_type,
            matched_rule=matched_description,
            input_text=text,
        )

    def scan_command(self, command: str) -> ThreatResult:
        """
        Scan an OS command for threats. Alias for scan().
        
        Args:
            command: Command to scan
            
        Returns:
            ThreatResult
        """
        return self.scan(command)

    def get_rules(self) -> List[ThreatRule]:
        """Get all threat rules."""
        return self.rules.copy()

    def clear_custom_rules(self) -> None:
        """Clear only custom rules, keeping defaults."""
        self.rules = []
        self._compiled_rules = []
        self._init_default_rules()
