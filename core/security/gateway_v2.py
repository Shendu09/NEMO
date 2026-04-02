"""
Security Gateway - Single entry point for NEMO Security Layer.
The ONLY class the AI agent should import.
Wires together all security components: PermissionEngine, ThreatDetector,
AuditLogger, and ActionSandbox into a unified security interface.
"""

from pathlib import Path
from typing import Optional

from .permissions_v2 import PermissionEngine, User, Role, ActionCategory
from .threat_detector_v2 import ThreatDetector, ThreatResult
from .audit_logger_v2 import AuditLogger
from .sandbox_v2 import ActionSandbox, ExecutionResult


class SecurityGateway:
    """
    Single entry point for all security operations.
    Delegates to internal components: PermissionEngine, ThreatDetector,
    AuditLogger, ActionSandbox. Zero logic — pure delegation.
    """

    def __init__(
        self,
        data_dir: Path = Path("./clevrr_data"),
        dry_run: bool = False,
        custom_rules: Optional[dict] = None,
    ) -> None:
        """
        Initialize Security Gateway.
        
        Args:
            data_dir: Directory for users.json and audit.log
            dry_run: If True, logs but doesn't execute
            custom_rules: Optional dict of {name: pattern} custom threat rules
        """
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Wire internal components
        self._perms = PermissionEngine(data_dir / "users.json")
        self._detector = ThreatDetector(custom_rules)
        self._audit = AuditLogger(data_dir / "audit.log")
        self._sandbox = ActionSandbox(
            permission_engine=self._perms,
            threat_detector=self._detector,
            audit_logger=self._audit,
            dry_run=dry_run,
        )

    # ==================== USER MANAGEMENT ====================

    def add_user(
        self,
        user_id: str,
        username: str,
        role: Role,
        allowed_paths: list[str] = None,
    ) -> User:
        """Add a new user."""
        return self._perms.add_user(user_id, username, role, allowed_paths)

    def remove_user(self, user_id: str) -> None:
        """Remove a user."""
        self._perms.remove_user(user_id)

    def update_role(self, user_id: str, role: Role) -> Optional[User]:
        """Update user's role."""
        return self._perms.update_role(user_id, role)

    def deactivate_user(self, user_id: str) -> Optional[User]:
        """Deactivate a user."""
        return self._perms.deactivate_user(user_id)

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._perms.get_user(user_id)

    def list_permissions(self, user_id: str) -> set[ActionCategory]:
        """Get all permissions for a user."""
        return self._perms.list_permissions(user_id)

    # ==================== FILE OPERATIONS ====================

    def read_file(self, user_id: str, path: str) -> ExecutionResult:
        """Read file with security checks."""
        return self._sandbox.read_file(user_id, path)

    def write_file(self, user_id: str, path: str, content: str) -> ExecutionResult:
        """Write file with security checks."""
        return self._sandbox.write_file(user_id, path, content)

    def delete_file(self, user_id: str, path: str) -> ExecutionResult:
        """Delete file with security checks."""
        return self._sandbox.delete_file(user_id, path)

    # ==================== COMMAND EXECUTION ====================

    def run_command(
        self,
        user_id: str,
        command: list[str],
        cwd: Optional[str] = None,
        timeout: int = 30,
    ) -> ExecutionResult:
        """Run OS command with security checks."""
        return self._sandbox.run_command(user_id, command, cwd, timeout)

    # ==================== DESKTOP OPERATIONS ====================

    def take_screenshot(self, user_id: str, out_path: str) -> ExecutionResult:
        """Take screenshot with security checks."""
        return self._sandbox.take_screenshot(user_id, out_path)

    def type_text(self, user_id: str, text: str) -> ExecutionResult:
        """Type text via keyboard with security checks."""
        return self._sandbox.type_text(user_id, text)

    # ==================== AUDIT & VERIFICATION ====================

    def verify_audit_chain(self) -> tuple[bool, str]:
        """Verify integrity of audit log chain."""
        return self._audit.verify()

    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """Get audit log with optional filtering."""
        return self._audit.query(user_id=user_id, limit=limit)

    def export_audit(self, out_path: Path) -> None:
        """Export audit log to JSON file."""
        self._audit.export_json(out_path)

    # ==================== THREAT SCANNING ====================

    def scan_text(self, text: str) -> ThreatResult:
        """Scan text for threats without executing anything."""
        return self._detector.scan(text)
