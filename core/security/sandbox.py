"""
Action Sandbox - Wraps all OS calls in NEMO Security Layer.
All OS operations go through threat detection → permissions → execution → audit.
"""

import subprocess
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from .permissions import PermissionEngine, ActionCategory, PermissionResult
from .threat_detector import ThreatDetector, ThreatResult
from .audit_logger import AuditLogger, AuditEntry


@dataclass
class ExecutionResult:
    """Result of a sandboxed action execution."""
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0
    perm_result: Optional[PermissionResult] = None
    threat_result: Optional[ThreatResult] = None


class ActionSandbox:
    """
    Sandboxes all OS operations.
    Pipeline: ThreatDetector → PermissionEngine → Execute → AuditLogger
    """

    def __init__(
        self,
        data_dir: Path = None,
        dry_run: bool = False,
    ):
        """
        Initialize action sandbox.
        
        Args:
            data_dir: Directory for logs and data. Defaults to ./clevrr_data
            dry_run: If True, logs but doesn't execute (for testing)
        """
        self.data_dir = Path(data_dir) if data_dir else Path("./clevrr_data")
        self.data_dir.mkdir(exist_ok=True)
        
        self.dry_run = dry_run
        self.threat_detector = ThreatDetector()
        self.permission_engine = PermissionEngine(self.data_dir)
        self.audit_logger = AuditLogger(self.data_dir)
        
        self.os_type = platform.system()  # "Windows", "Linux", "Darwin"

    def _execute_pipeline(
        self,
        user_id: str,
        action: ActionCategory,
        action_text: str,
        target: str = "",
        executor=None,
    ) -> ExecutionResult:
        """
        Execute the complete security pipeline.
        
        Args:
            user_id: User performing action
            action: Action category
            action_text: Full action text/command
            target: Target (file path, etc.) for permission checks
            executor: Callable that performs the actual action
            
        Returns:
            ExecutionResult with all details
        """
        # Step 1: Threat Detection
        threat_result = self.threat_detector.scan(action_text)
        
        if not threat_result.safe:
            # Threat detected - block even before permission check
            self.audit_logger.log(
                user_id=user_id,
                action=action.value,
                target=target or action_text[:100],
                allowed=False,
                reason=f"Threat detected: {threat_result.matched_rule}",
            )
            return ExecutionResult(
                success=False,
                error=f"Security threat detected: {threat_result.matched_rule}",
                exit_code=1,
                threat_result=threat_result,
            )
        
        # Step 2: Permission Check
        perm_result = self.permission_engine.check(user_id, action, target)
        
        if not perm_result.allowed:
            # Permission denied
            self.audit_logger.log(
                user_id=user_id,
                action=action.value,
                target=target or action_text[:100],
                allowed=False,
                reason=perm_result.reason,
            )
            return ExecutionResult(
                success=False,
                error=f"Permission denied: {perm_result.reason}",
                exit_code=1,
                perm_result=perm_result,
                threat_result=threat_result,
            )
        
        # Step 3: Execute (if not dry_run)
        output = ""
        error = ""
        exit_code = 0
        success = False
        
        if not self.dry_run and executor:
            try:
                output, error, exit_code = executor()
                success = exit_code == 0
            except Exception as e:
                success = False
                error = str(e)
                exit_code = 1
        elif self.dry_run:
            success = True
            output = "[DRY RUN - Not executed]"
        
        # Step 4: Audit Log
        self.audit_logger.log(
            user_id=user_id,
            action=action.value,
            target=target or action_text[:100],
            allowed=True,
            reason="Executed successfully" if success else f"Execution failed: {error}",
        )
        
        return ExecutionResult(
            success=success,
            output=output,
            error=error,
            exit_code=exit_code,
            perm_result=perm_result,
            threat_result=threat_result,
        )

    def read_file(
        self,
        user_id: str,
        filepath: str,
    ) -> ExecutionResult:
        """
        Read file with security checks.
        
        Args:
            user_id: User requesting file read
            filepath: Path to file
            
        Returns:
            ExecutionResult with file contents or error
        """
        def executor():
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return content, "", 0
        
        result = self._execute_pipeline(
            user_id=user_id,
            action=ActionCategory.FILE_READ,
            action_text=f"read {filepath}",
            target=filepath,
            executor=executor if not self.dry_run else None,
        )
        
        return result

    def write_file(
        self,
        user_id: str,
        filepath: str,
        content: str,
    ) -> ExecutionResult:
        """
        Write file with security checks.
        
        Args:
            user_id: User requesting file write
            filepath: Path to file
            content: Content to write
            
        Returns:
            ExecutionResult
        """
        action_text = f"write to {filepath}"
        
        def executor():
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return "", "", 0
        
        result = self._execute_pipeline(
            user_id=user_id,
            action=ActionCategory.FILE_WRITE,
            action_text=action_text,
            target=filepath,
            executor=executor if not self.dry_run else None,
        )
        
        return result

    def delete_file(
        self,
        user_id: str,
        filepath: str,
    ) -> ExecutionResult:
        """
        Delete file with security checks.
        
        Args:
            user_id: User requesting file delete
            filepath: Path to file
            
        Returns:
            ExecutionResult
        """
        action_text = f"delete {filepath}"
        
        def executor():
            Path(filepath).unlink()
            return "", "", 0
        
        result = self._execute_pipeline(
            user_id=user_id,
            action=ActionCategory.FILE_DELETE,
            action_text=action_text,
            target=filepath,
            executor=executor if not self.dry_run else None,
        )
        
        return result

    def run_command(
        self,
        user_id: str,
        command: str,
        timeout: int = 30,
    ) -> ExecutionResult:
        """
        Run OS command with security checks.
        
        Args:
            user_id: User running command
            command: Shell command to execute
            timeout: Command timeout in seconds
            
        Returns:
            ExecutionResult with stdout/stderr
        """
        def executor():
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    timeout=timeout,
                    text=True,
                )
                return result.stdout, result.stderr, result.returncode
            except subprocess.TimeoutExpired:
                return "", f"Command timed out after {timeout}s", 124
        
        result = self._execute_pipeline(
            user_id=user_id,
            action=ActionCategory.PROCESS_SPAWN,
            action_text=command,
            target=command[:100],
            executor=executor if not self.dry_run else None,
        )
        
        return result

    def take_screenshot(
        self,
        user_id: str,
    ) -> ExecutionResult:
        """
        Take screenshot with security checks.
        
        Args:
            user_id: User requesting screenshot
            
        Returns:
            ExecutionResult with screenshot data path or error
        """
        def executor():
            try:
                import pyautogui
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                filepath = self.data_dir / f"screenshot_{timestamp}.png"
                pyautogui.screenshot(str(filepath))
                return str(filepath), "", 0
            except ImportError:
                return "", "pyautogui not available", 1
        
        result = self._execute_pipeline(
            user_id=user_id,
            action=ActionCategory.SCREENSHOT,
            action_text="take_screenshot",
            executor=executor if not self.dry_run else None,
        )
        
        return result

    def type_text(
        self,
        user_id: str,
        text: str,
        interval: float = 0.05,
    ) -> ExecutionResult:
        """
        Type text via keyboard with security checks.
        
        Args:
            user_id: User requesting keyboard input
            text: Text to type
            interval: Delay between keystrokes (seconds)
            
        Returns:
            ExecutionResult
        """
        def executor():
            try:
                import pyautogui
                pyautogui.typewrite(text, interval=interval)
                return "", "", 0
            except ImportError:
                return "", "pyautogui not available", 1
        
        result = self._execute_pipeline(
            user_id=user_id,
            action=ActionCategory.KEYBOARD_INPUT,
            action_text=f"type_text({len(text)} chars)",
            executor=executor if not self.dry_run else None,
        )
        
        return result

    def get_threat_detector(self) -> ThreatDetector:
        """Get threat detector instance."""
        return self.threat_detector

    def get_permission_engine(self) -> PermissionEngine:
        """Get permission engine instance."""
        return self.permission_engine

    def get_audit_logger(self) -> AuditLogger:
        """Get audit logger instance."""
        return self.audit_logger
