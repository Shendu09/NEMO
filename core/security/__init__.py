"""
NEMO Security Layer - Enterprise-grade security for AI Operating System agents.

Single entry point: SecurityGateway
- Role-Based Access Control (RBAC)
- Threat Detection & Pattern Matching
- Tamper-Evident Audit Logging
- Action Sandboxing

Usage:
    from core.security import SecurityGateway, Role
    
    gateway = SecurityGateway()
    gateway.add_user("alice", "Alice", Role.USER)
    result = gateway.run_command("alice", ["ls", "-la"])
"""

from .gateway_v2 import SecurityGateway
from .permissions_v2 import PermissionEngine, User, Role, ActionCategory
from .threat_detector_v2 import ThreatDetector, ThreatLevel, ThreatResult
from .audit_logger_v2 import AuditLogger, AuditEntry
from .sandbox_v2 import ActionSandbox, ExecutionResult

__all__ = [
    # Gateway
    "SecurityGateway",
    # Permissions
    "PermissionEngine",
    "User",
    "Role",
    "ActionCategory",
    # Threat Detection
    "ThreatDetector",
    "ThreatLevel",
    "ThreatResult",
    # Audit Logging
    "AuditLogger",
    "AuditEntry",
    # Sandbox
    "ActionSandbox",
    "ExecutionResult",
]

__version__ = "1.0.0"
