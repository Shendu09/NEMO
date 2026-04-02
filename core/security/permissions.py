"""
Permission Engine - Role-Based Access Control (RBAC) for NEMO Security Layer.
Manages user roles, action permissions, and enforces access control.
"""

import json
import threading
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Set, Dict, Optional, List
from datetime import datetime


class Role(str, Enum):
    """Role definitions for RBAC."""
    ADMIN = "admin"
    USER = "user"
    RESTRICTED = "restricted"
    GUEST = "guest"


class ActionCategory(str, Enum):
    """All action categories that can be controlled."""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    PROCESS_SPAWN = "process_spawn"
    PROCESS_KILL = "process_kill"
    NETWORK_REQUEST = "network_request"
    SYSTEM_CONFIG = "system_config"
    CLIPBOARD = "clipboard"
    SCREENSHOT = "screenshot"
    KEYBOARD_INPUT = "keyboard_input"
    MOUSE_INPUT = "mouse_input"
    REGISTRY_READ = "registry_read"
    REGISTRY_WRITE = "registry_write"
    SERVICE_CONTROL = "service_control"
    PACKAGE_INSTALL = "package_install"
    SUDO_ESCALATE = "sudo_escalate"


# Define role-action mappings
ROLE_PERMISSIONS: Dict[Role, Set[ActionCategory]] = {
    Role.ADMIN: set(ActionCategory),  # All permissions
    Role.USER: {
        ActionCategory.FILE_READ,
        ActionCategory.FILE_WRITE,
        ActionCategory.FILE_DELETE,
        ActionCategory.PROCESS_SPAWN,
        ActionCategory.NETWORK_REQUEST,
        ActionCategory.CLIPBOARD,
        ActionCategory.SCREENSHOT,
        ActionCategory.KEYBOARD_INPUT,
        ActionCategory.MOUSE_INPUT,
    },
    Role.RESTRICTED: {
        ActionCategory.FILE_READ,
        ActionCategory.CLIPBOARD,
        ActionCategory.SCREENSHOT,
        ActionCategory.KEYBOARD_INPUT,
    },
    Role.GUEST: {
        ActionCategory.FILE_READ,
        ActionCategory.CLIPBOARD,
        ActionCategory.SCREENSHOT,
    },
}


@dataclass
class PermissionResult:
    """Result of a permission check."""
    allowed: bool
    reason: str
    role: str
    action: str
    timestamp: str


@dataclass
class NemoUser:
    """User model with role and permissions."""
    user_id: str
    username: str
    role: Role
    created_at: str
    active: bool = True
    allowed_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "created_at": self.created_at,
            "active": self.active,
            "allowed_paths": self.allowed_paths,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "NemoUser":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            role=Role(data["role"]),
            created_at=data["created_at"],
            active=data.get("active", True),
            allowed_paths=data.get("allowed_paths", []),
        )


class PermissionEngine:
    """
    Role-Based Access Control engine for NEMO.
    Thread-safe permission checking and user management.
    """

    def __init__(self, data_dir: Path = None):
        """
        Initialize permission engine.
        
        Args:
            data_dir: Directory to persist user data. Defaults to ./clevrr_data
        """
        self.data_dir = Path(data_dir) if data_dir else Path("./clevrr_data")
        self.data_dir.mkdir(exist_ok=True)
        self.users_file = self.data_dir / "users.json"
        
        self._lock = threading.RLock()
        self.users: Dict[str, NemoUser] = {}
        
        # Load existing users
        self._load_users()

    def _load_users(self) -> None:
        """Load users from disk."""
        if self.users_file.exists():
            try:
                with open(self.users_file, "r") as f:
                    data = json.load(f)
                    self.users = {
                        uid: NemoUser.from_dict(user_data)
                        for uid, user_data in data.items()
                    }
            except (json.JSONDecodeError, KeyError):
                self.users = {}

    def _save_users(self) -> None:
        """Persist users to disk."""
        with open(self.users_file, "w") as f:
            json.dump(
                {uid: user.to_dict() for uid, user in self.users.items()},
                f,
                indent=2,
            )

    def add_user(
        self,
        user_id: str,
        username: str,
        role: Role,
        allowed_paths: List[str] = None,
    ) -> NemoUser:
        """
        Add a new user.
        
        Args:
            user_id: Unique user identifier
            username: Display name
            role: User role (affects permissions)
            allowed_paths: Whitelist of file paths user can access
            
        Returns:
            Created NemoUser object
        """
        with self._lock:
            if user_id in self.users:
                raise ValueError(f"User {user_id} already exists")
            
            user = NemoUser(
                user_id=user_id,
                username=username,
                role=role,
                created_at=datetime.utcnow().isoformat(),
                allowed_paths=allowed_paths or [],
            )
            self.users[user_id] = user
            self._save_users()
            return user

    def remove_user(self, user_id: str) -> bool:
        """
        Remove a user.
        
        Args:
            user_id: User to remove
            
        Returns:
            True if user was removed, False if not found
        """
        with self._lock:
            if user_id in self.users:
                del self.users[user_id]
                self._save_users()
                return True
            return False

    def update_role(self, user_id: str, new_role: Role) -> Optional[NemoUser]:
        """
        Update a user's role.
        
        Args:
            user_id: User to update
            new_role: New role to assign
            
        Returns:
            Updated user, or None if not found
        """
        with self._lock:
            if user_id not in self.users:
                return None
            
            self.users[user_id].role = new_role
            self._save_users()
            return self.users[user_id]

    def deactivate_user(self, user_id: str) -> Optional[NemoUser]:
        """
        Deactivate a user (prevent future access).
        
        Args:
            user_id: User to deactivate
            
        Returns:
            Updated user, or None if not found
        """
        with self._lock:
            if user_id not in self.users:
                return None
            
            self.users[user_id].active = False
            self._save_users()
            return self.users[user_id]

    def update_allowed_paths(
        self,
        user_id: str,
        allowed_paths: List[str],
    ) -> Optional[NemoUser]:
        """
        Update a user's allowed paths whitelist.
        
        Args:
            user_id: User to update
            allowed_paths: List of allowed path patterns
            
        Returns:
            Updated user, or None if not found
        """
        with self._lock:
            if user_id not in self.users:
                return None
            
            self.users[user_id].allowed_paths = allowed_paths
            self._save_users()
            return self.users[user_id]

    def check(
        self,
        user_id: str,
        action: ActionCategory,
        target: str = None,
    ) -> PermissionResult:
        """
        Check if a user is allowed to perform an action.
        
        Args:
            user_id: User performing the action
            action: Action category (from ActionCategory enum)
            target: Optional target (file path, etc.) for path-based checks
            
        Returns:
            PermissionResult with allowed flag and reason
        """
        with self._lock:
            timestamp = datetime.utcnow().isoformat()
            
            # Check user exists
            if user_id not in self.users:
                return PermissionResult(
                    allowed=False,
                    reason=f"User {user_id} not found",
                    role="unknown",
                    action=action.value,
                    timestamp=timestamp,
                )
            
            user = self.users[user_id]
            
            # Check if user is active
            if not user.active:
                return PermissionResult(
                    allowed=False,
                    reason=f"User {user_id} is deactivated",
                    role=user.role.value,
                    action=action.value,
                    timestamp=timestamp,
                )
            
            # Check if action is allowed for role
            allowed_actions = ROLE_PERMISSIONS.get(user.role, set())
            if action not in allowed_actions:
                return PermissionResult(
                    allowed=False,
                    reason=f"Role {user.role.value} cannot perform {action.value}",
                    role=user.role.value,
                    action=action.value,
                    timestamp=timestamp,
                )
            
            # Check path whitelist if target provided and user has path restrictions
            if target and user.allowed_paths:
                target_path = Path(target)
                allowed = any(
                    target_path.match(pattern)
                    for pattern in user.allowed_paths
                )
                if not allowed:
                    return PermissionResult(
                        allowed=False,
                        reason=f"Path {target} not in allowed paths for user",
                        role=user.role.value,
                        action=action.value,
                        timestamp=timestamp,
                    )
            
            return PermissionResult(
                allowed=True,
                reason="Permission granted",
                role=user.role.value,
                action=action.value,
                timestamp=timestamp,
            )

    def get_user(self, user_id: str) -> Optional[NemoUser]:
        """Get user by ID."""
        with self._lock:
            return self.users.get(user_id)

    def list_users(self) -> List[NemoUser]:
        """List all users."""
        with self._lock:
            return list(self.users.values())
