"""
Action Sandbox - Wraps all OS operations with security pipeline.
Nothing touches the OS without going through threat detection → permission check → execution → audit.
"""

import os
import subprocess
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
from pydantic import BaseModel

from .permissions_v2 import PermissionEngine, ActionCategory, PermissionResult
from .threat_detector_v2 import ThreatDetector, ThreatResult
from .audit_logger_v2 import AuditLogger


@dataclass(slots=True)
class ExecutionResult:
    """Result of a sandboxed action execution."""
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    perm_result: Optional[PermissionResult] = None
    threat_result: Optional[ThreatResult] = None


class ActionSandbox:
    """
    Sandbox for all OS operations.
    Pipeline: Threat Detection → Permission Check → Execute → Audit Log
    """

    def __init__(
        self,
        permission_engine: PermissionEngine,
        threat_detector: ThreatDetector,
        audit_logger: AuditLogger,
        dry_run: bool = False,
    ):
        """
        Initialize action sandbox with security components.
        
        Args:
            permission_engine: RBAC engine
            threat_detector: Threat detection engine
            audit_logger: Audit log
            dry_run: If True, logs but doesn't execute
        """
        self._perms = permission_engine
        self._detector = threat_detector
        self._audit = audit_logger
        self._dry_run = dry_run

    def read_file(self, user_id: str, path: str) -> ExecutionResult:
        """Read file with security checks."""
        def command():
            content = Path(path).read_text(errors="replace")
            return content, 0
        
        return self._execute(
            user_id,
            ActionCategory.FILE_READ,
            target=path,
            command=command,
        )

    def write_file(self, user_id: str, path: str, content: str) -> ExecutionResult:
        """Write file with security checks."""
        def command():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(content)
            return f"Written {len(content)} bytes to {path}", 0
        
        return self._execute(
            user_id,
            ActionCategory.FILE_WRITE,
            target=path,
            command=command,
            scan_text=content,
        )

    def delete_file(self, user_id: str, path: str) -> ExecutionResult:
        """Delete file with security checks."""
        def command():
            os.remove(path)
            return f"Deleted {path}", 0
        
        return self._execute(
            user_id,
            ActionCategory.FILE_DELETE,
            target=path,
            command=command,
        )

    def run_command(
        self,
        user_id: str,
        command: list[str],
        cwd: str = None,
        timeout: int = 30,
    ) -> ExecutionResult:
        """Run OS command with security checks."""
        cmd_str = " ".join(command)
        
        # Pre-scan command for threats
        threat_result = self._detector.scan(cmd_str)
        if not threat_result.safe:
            self._audit.log(
                user_id,
                ActionCategory.PROCESS_SPAWN.value,
                False,
                f"Threat: {threat_result.threat_type}",
                cmd_str,
            )
            return ExecutionResult(
                success=False,
                output=None,
                error=self._detector.explain(threat_result),
                exit_code=-1,
                threat_result=threat_result,
            )
        
        def cmd_exec():
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            return result.stdout or result.stderr, result.returncode
        
        return self._execute(
            user_id,
            ActionCategory.PROCESS_SPAWN,
            target=cmd_str,
            command=cmd_exec,
            threat_result=threat_result,
        )

    def take_screenshot(self, user_id: str, out_path: str) -> ExecutionResult:
        """Take screenshot with security checks."""
        def command():
            try:
                import pyautogui
                img = pyautogui.screenshot()
                img.save(out_path)
                return f"Screenshot saved to {out_path}", 0
            except ImportError:
                return "pyautogui not installed", 1
        
        return self._execute(
            user_id,
            ActionCategory.SCREENSHOT,
            target=out_path,
            command=command,
        )

    def type_text(self, user_id: str, text: str) -> ExecutionResult:
        """Type text via keyboard with security checks."""
        def command():
            try:
                import pyautogui
                pyautogui.typewrite(text, interval=0.05)
                return f"Typed {len(text)} characters", 0
            except ImportError:
                return "pyautogui not installed", 1
        
        return self._execute(
            user_id,
            ActionCategory.KEYBOARD_INPUT,
            target=None,
            command=command,
            scan_text=text,
        )

    def _execute(
        self,
        user_id: str,
        action: ActionCategory,
        target: Optional[str],
        command: Callable,
        scan_text: Optional[str] = None,
        threat_result: Optional[ThreatResult] = None,
    ) -> ExecutionResult:
        """
        Internal security pipeline for all actions.
        
        Pipeline:
        1. Threat scan (if scan_text provided)
        2. Permission check
        3. Dry run check
        4. Execute in try/except
        """
        # STEP 1 — Threat scan (only if not already scanned)
        if scan_text and threat_result is None:
            threat_result = self._detector.scan(scan_text)
            if not threat_result.safe:
                self._audit.log(
                    user_id,
                    str(action.value) if hasattr(action, 'value') else str(action),
                    False,
                    f"Threat: {threat_result.threat_type}",
                    target,
                )
                return ExecutionResult(
                    success=False,
                    output=None,
                    error=self._detector.explain(threat_result),
                    exit_code=-1,
                    threat_result=threat_result,
                )
        
        # STEP 2 — Permission check
        perm = self._perms.check(user_id, action, target)
        if not perm.allowed:
            self._audit.log(
                user_id,
                str(action.value) if hasattr(action, 'value') else str(action),
                False,
                perm.reason,
                target,
            )
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Permission denied: {perm.reason}",
                exit_code=-1,
                perm_result=perm,
            )
        
        # STEP 3 — Dry run check
        if self._dry_run:
            self._audit.log(
                user_id,
                str(action.value) if hasattr(action, 'value') else str(action),
                True,
                "DRY RUN",
                target,
            )
            return ExecutionResult(
                success=True,
                output="[DRY RUN] Would have executed.",
                error=None,
                exit_code=0,
                perm_result=perm,
                threat_result=threat_result,
            )
        
        # STEP 4 — Execute in try/except
        try:
            raw = command()
            if isinstance(raw, tuple):
                output, exit_code = raw
            else:
                output, exit_code = str(raw), 0
            
            self._audit.log(
                user_id,
                str(action.value) if hasattr(action, 'value') else str(action),
                True,
                "Executed successfully",
                target,
            )
            
            return ExecutionResult(
                success=True,
                output=output,
                error=None,
                exit_code=exit_code,
                perm_result=perm,
                threat_result=threat_result,
            )
        except Exception as exc:
            self._audit.log(
                user_id,
                str(action.value) if hasattr(action, 'value') else str(action),
                True,
                f"Execution error: {exc}",
                target,
            )
            return ExecutionResult(
                success=False,
                output=None,
                error=str(exc),
                exit_code=-1,
                perm_result=perm,
                threat_result=threat_result,
            )
