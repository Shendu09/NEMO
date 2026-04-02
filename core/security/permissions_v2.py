"""
RBAC Engine - Role-Based Access Control for NEMO Security Layer.
Manages user roles, permissions, and access control enforcement.
"""

import json
import time
import threading
from enum import Enum
from pathlib import Path
from typing import Optional, Set, List
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Role definitions for RBAC."""
    ADMIN = "admin"
    USER = "user"
    RESTRICTED = "restricted"
    GUEST = "guest"


class ActionCategory(str, Enum):
    """16 action categories for granular permission control."""
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


# Role → Permission mappings
ROLE_PERMISSIONS = {
    Role.ADMIN: set(ActionCategory),  # All 16
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
        ActionCategory.REGISTRY_READ,
    },
    Role.RESTRICTED: {
        ActionCategory.FILE_READ,
        ActionCategory.CLIPBOARD,
        ActionCategory.SCREENSHOT,
        ActionCategory.KEYBOARD_INPUT,
        ActionCategory.MOUSE_INPUT,
    },
    Role.GUEST: {
        ActionCategory.FILE_READ,
        ActionCategory.SCREENSHOT,
    },
}


class User(BaseModel):
    """User model with role and path restrictions."""
    user_id: str
    username: str
    role: Role
    created_at: float
    active: bool = True
    allowed_paths: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True

    def to_dict(self):
        """Convert to dict for JSON serialization."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,  # Already a string due to use_enum_values=True
            "created_at": self.created_at,
            "active": self.active,
            "allowed_paths": self.allowed_paths,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create from dict."""
        return cls(**data)


class PermissionResult(BaseModel):
    """Result of a permission check."""
    allowed: bool
    action: ActionCategory
    user_id: str
    role: Role
    reason: str
    timestamp: float


class PermissionEngine:
    """
    Role-Based Access Control engine.
    Thread-safe user and permission management.
    """

    def __init__(self, data_dir: Path = None):
        """
        Initialize permission engine.
        
        Args:
            data_dir: Directory for user persistence. Defaults to ./clevrr_data
        """
        self.data_dir = Path(data_dir) if data_dir else Path("./clevrr_data")
        self.data_dir.mkdir(exist_ok=True)
        self.users_file = self.data_dir / "users.json"
        
        self._lock = threading.RLock()
        self.users: dict[str, User] = {}
        self._load()

    def _load(self) -> None:
        """Load users from disk."""
        if self.users_file.exists():
            try:
                with open(self.users_file) as f:
                    data = json.load(f)
                    self.users = {
                        uid: User.from_dict(user_dict)
                        for uid, user_dict in data.items()
                    }
            except (json.JSONDecodeError, ValueError):
                self.users = {}

    def _persist(self) -> None:
        """Save users to disk."""
        data = {uid: user.to_dict() for uid, user in self.users.items()}
        with open(self.users_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_user(
        self,
        user_id: str,
        username: str,
        role: Role,
        allowed_paths: List[str] = None,
    ) -> User:
        """Add a new user."""
        with self._lock:
            if user_id in self.users:
                raise ValueError(f"User {user_id} already exists")
            
            user = User(
                user_id=user_id,
                username=username,
                role=role,
                created_at=time.time(),
                allowed_paths=allowed_paths or [],
            )
            self.users[user_id] = user
            self._persist()
            return user

    def remove_user(self, user_id: str) -> None:
        """Remove a user."""
        with self._lock:
            if user_id in self.users:
                del self.users[user_id]
                self._persist()

    def update_role(self, user_id: str, new_role: Role) -> Optional[User]:
        """Update user's role."""
        with self._lock:
            if user_id not in self.users:
                return None
            self.users[user_id].role = new_role
            self._persist()
            return self.users[user_id]

    def deactivate_user(self, user_id: str) -> Optional[User]:
        """Deactivate a user."""
        with self._lock:
            if user_id not in self.users:
                return None
            self.users[user_id].active = False
            self._persist()
            return self.users[user_id]

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        with self._lock:
            return self.users.get(user_id)

    def check(
        self,
        user_id: str,
        action: ActionCategory,
        target: str = None,
    ) -> PermissionResult:
        """
        Check if user can perform action on target.
        
        Logic:
        1. User exists?
        2. User active?
        3. Action in role permissions?
        4. Target path allowed (if path restriction)?
        """
        with self._lock:
            timestamp = time.time()
            
            # 1. User exists?
            if user_id not in self.users:
                return PermissionResult(
                    allowed=False,
                    action=action,
                    user_id=user_id,
                    role=Role.GUEST,
                    reason="Unknown user",
                    timestamp=timestamp,
                )
            
            user = self.users[user_id]
            
            # 2. User active?
            if not user.active:
                return PermissionResult(
                    allowed=False,
                    action=action,
                    user_id=user_id,
                    role=user.role,
                    reason="User deactivated",
                    timestamp=timestamp,
                )
            
            # 3. Action in role permissions?
            allowed_actions = ROLE_PERMISSIONS.get(user.role, set())
            if action not in allowed_actions:
                return PermissionResult(
                    allowed=False,
                    action=action,
                    user_id=user_id,
                    role=user.role,
                    reason=f"Role {user.role} does not permit {action.value}",
                    timestamp=timestamp,
                )
            
            # 4. Target path allowed?
            if target and user.allowed_paths:
                allowed = any(
                    Path(target).match(pattern)
                    for pattern in user.allowed_paths
                )
                if not allowed:
                    return PermissionResult(
                        allowed=False,
                        action=action,
                        user_id=user_id,
                        role=user.role,
                        reason="Target path outside allowed paths",
                        timestamp=timestamp,
                    )
            
            # All checks passed
            return PermissionResult(
                allowed=True,
                action=action,
                user_id=user_id,
                role=user.role,
                reason="Permitted",
                timestamp=timestamp,
            )

    def list_permissions(self, user_id: str) -> Set[ActionCategory]:
        """Get all permissions for a user."""
        with self._lock:
            user = self.users.get(user_id)
            if not user:
                return set()
            return ROLE_PERMISSIONS.get(user.role, set())
