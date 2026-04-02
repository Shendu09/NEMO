"""
Security Gateway - Single entry point for NEMO Security Layer.
The ONLY class the AI agent should import.
Wires together all security components.
"""

from pathlib import Path
from typing import List, Optional, Dict

from .permissions import PermissionEngine, Role, ActionCategory, NemoUser
from .threat_detector import ThreatDetector, ThreatResult
from .audit_logger import AuditLogger, AuditEntry
from .sandbox import ActionSandbox, ExecutionResult


class SecurityGateway:
    """
    Single entry point for all NEMO security operations.
    Integrates: ThreatDetector → PermissionEngine → ActionSandbox → AuditLogger
    
    This is the ONLY class that should be imported by the AI agent.
    """

    def __init__(
        self,
        data_dir: Path = None,
        dry_run: bool = False,
        custom_rules: List[tuple] = None,
    ):
        """
        Initialize security gateway.
        
        Args:
            data_dir: Directory for logs and data. Defaults to ./clevrr_data
            dry_run: If True, logs but doesn't execute (for testing)
            custom_rules: List of custom threat rules to add
                         Format: (pattern, threat_type, threat_level, description)
        """
        self.data_dir = Path(data_dir) if data_dir else Path("./clevrr_data")
        self.dry_run = dry_run
        
        # Initialize sandbox (which contains all other components)
        self.sandbox = ActionSandbox(self.data_dir, dry_run)
        
        # Get references to components
        self.permission_engine = self.sandbox.permission_engine
        self.threat_detector = self.sandbox.threat_detector
        self.audit_logger = self.sandbox.audit_logger
        
        # Add custom rules if provided
        if custom_rules:
            for rule in custom_rules:
                pattern, threat_type, threat_level, description = rule
                self.threat_detector.add_rule(
                    pattern=pattern,
                    threat_type=threat_type,
                    threat_level=threat_level,
                    description=description,
                )

    # ==================== User Management ====================

    def add_user(
        self,
        user_id: str,
        username: str,
        role: Role,
        allowed_paths: List[str] = None,
    ) -> NemoUser:
        """Add a new user to the system."""
        return self.permission_engine.add_user(
            user_id=user_id,
            username=username,
            role=role,
            allowed_paths=allowed_paths,
        )

    def remove_user(self, user_id: str) -> bool:
        """Remove a user from the system."""
        return self.permission_engine.remove_user(user_id)

    def update_role(self, user_id: str, new_role: Role) -> Optional[NemoUser]:
        """Update a user's role."""
        return self.permission_engine.update_role(user_id, new_role)

    def deactivate_user(self, user_id: str) -> Optional[NemoUser]:
        """Deactivate a user (prevent future access)."""
        return self.permission_engine.deactivate_user(user_id)

    def get_user(self, user_id: str) -> Optional[NemoUser]:
        """Get user by ID."""
        return self.permission_engine.get_user(user_id)

    def list_users(self) -> List[NemoUser]:
        """List all users."""
        return self.permission_engine.list_users()

    # ==================== File Operations ====================

    def read_file(
        self,
        user_id: str,
        filepath: str,
    ) -> ExecutionResult:
        """
        Read file with full security checks.
        
        Args:
            user_id: User requesting read
            filepath: Path to file
            
        Returns:
            ExecutionResult with contents or error
        """
        return self.sandbox.read_file(user_id, filepath)

    def write_file(
        self,
        user_id: str,
        filepath: str,
        content: str,
    ) -> ExecutionResult:
        """
        Write file with full security checks.
        
        Args:
            user_id: User requesting write
            filepath: Path to file
            content: Content to write
            
        Returns:
            ExecutionResult
        """
        return self.sandbox.write_file(user_id, filepath, content)

    def delete_file(
        self,
        user_id: str,
        filepath: str,
    ) -> ExecutionResult:
        """
        Delete file with full security checks.
        
        Args:
            user_id: User requesting delete
            filepath: Path to file
            
        Returns:
            ExecutionResult
        """
        return self.sandbox.delete_file(user_id, filepath)

    # ==================== Command Execution ====================

    def run_command(
        self,
        user_id: str,
        command: str,
        timeout: int = 30,
    ) -> ExecutionResult:
        """
        Run OS command with full security checks.
        
        Args:
            user_id: User running command
            command: Shell command to execute
            timeout: Command timeout in seconds
            
        Returns:
            ExecutionResult with output/error
        """
        return self.sandbox.run_command(user_id, command, timeout)

    # ==================== Desktop Operations ====================

    def take_screenshot(self, user_id: str) -> ExecutionResult:
        """
        Take screenshot with full security checks.
        
        Args:
            user_id: User requesting screenshot
            
        Returns:
            ExecutionResult with screenshot file path or error
        """
        return self.sandbox.take_screenshot(user_id)

    def type_text(
        self,
        user_id: str,
        text: str,
        interval: float = 0.05,
    ) -> ExecutionResult:
        """
        Type text via keyboard with full security checks.
        
        Args:
            user_id: User requesting input
            text: Text to type
            interval: Delay between keystrokes
            
        Returns:
            ExecutionResult
        """
        return self.sandbox.type_text(user_id, text, interval)

    # ==================== Threat Analysis ====================

    def scan_text(self, text: str) -> ThreatResult:
        """
        Scan text for security threats without executing anything.
        Useful for analyzing commands before running them.
        
        Args:
            text: Text to scan
            
        Returns:
            ThreatResult indicating threat level and details
        """
        return self.threat_detector.scan(text)

    # ==================== Audit & Verification ====================

    def verify_audit_chain(self) -> tuple[bool, Optional[str]]:
        """
        Verify integrity of audit log chain.
        Detects any tampering with the log.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.audit_logger.verify()

    def get_audit_log(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        allowed: Optional[bool] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AuditEntry]:
        """
        Query audit log with filtering.
        
        Args:
            user_id: Filter by user
            action: Filter by action type
            allowed: Filter by permission result
            since: Filter since ISO timestamp
            until: Filter until ISO timestamp
            limit: Max results
            
        Returns:
            List of AuditEntry objects
        """
        return self.audit_logger.query(
            user_id=user_id,
            action=action,
            allowed=allowed,
            since=since,
            until=until,
            limit=limit,
        )

    def export_audit(self, filepath: Path) -> None:
        """
        Export audit log to JSON file.
        
        Args:
            filepath: Path to export to
        """
        self.audit_logger.export_json(filepath)

    def get_audit_chain_integrity(self) -> Dict:
        """Get detailed audit chain integrity report."""
        return self.audit_logger.get_chain_integrity()

    # ==================== Permissions & Discovery ====================

    def list_permissions(self) -> Dict:
        """
        List all role-action permissions.
        
        Returns:
            Dictionary mapping roles to allowed actions
        """
        from .permissions import ROLE_PERMISSIONS
        return {
            role.value: [action.value for action in actions]
            for role, actions in ROLE_PERMISSIONS.items()
        }

    def get_threat_rules(self) -> List[Dict]:
        """
        Get all threat detection rules.
        
        Returns:
            List of rule dictionaries
        """
        rules = self.threat_detector.get_rules()
        return [
            {
                "pattern": rule.pattern,
                "threat_type": rule.threat_type.value,
                "threat_level": rule.threat_level.value,
                "description": rule.description,
            }
            for rule in rules
        ]

    # ==================== Configuration ====================

    def set_dry_run(self, enabled: bool) -> None:
        """Enable/disable dry-run mode (logs without executing)."""
        self.sandbox.dry_run = enabled

    def get_config(self) -> Dict:
        """Get current gateway configuration."""
        return {
            "data_dir": str(self.data_dir),
            "dry_run": self.dry_run,
            "user_count": len(self.permission_engine.users),
            "audit_entries": self.audit_logger.get_entry_count(),
            "threat_rules": len(self.threat_detector.rules),
            "os_type": self.sandbox.os_type,
        }
