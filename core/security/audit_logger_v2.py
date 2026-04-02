"""
Audit Logger - Tamper-evident, hash-chained audit log for NEMO Security Layer.
Provides immutable record of all security-relevant actions with integrity verification.
"""

import json
import hashlib
import time
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel


@dataclass(slots=True)
class AuditEntry:
    """Single audit log entry with hash chaining."""
    seq: int
    timestamp: float
    user_id: str
    action: str
    target: Optional[str]
    allowed: bool
    reason: str
    prev_hash: str
    entry_hash: str = ""

    def compute_hash(self) -> str:
        """
        Compute SHA256 hash of entry (excluding entry_hash itself).
        Deterministic: sort_keys=True for consistent hashing.
        """
        data = {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "action": self.action,
            "target": self.target,
            "allowed": self.allowed,
            "reason": self.reason,
            "prev_hash": self.prev_hash,
        }
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AuditEntry":
        """Create AuditEntry from dict."""
        return cls(**data)


class AuditLogger:
    """
    Tamper-evident, hash-chained append-only audit log.
    All write operations are protected by threading.Lock().
    """

    GENESIS_HASH = "0" * 64

    def __init__(
        self,
        log_path: Path,
        max_bytes: int = 10 * 1024 * 1024,
    ):
        """
        Initialize audit logger.
        
        Args:
            log_path: Path to JSONL log file
            max_bytes: Auto-rotate at this size (default 10MB)
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        
        self._lock = threading.Lock()
        self._entries: List[AuditEntry] = []
        self._seq = 0
        
        # Load existing log
        if self.log_path.exists():
            self._load()

    def _load(self) -> None:
        """Load existing audit entries from disk."""
        try:
            with open(self.log_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            entry = AuditEntry.from_dict(data)
                            self._entries.append(entry)
                            self._seq = max(self._seq, entry.seq)
                        except (json.JSONDecodeError, ValueError):
                            pass  # Skip malformed lines
        except IOError:
            pass

    def _append_to_disk(self, entry: AuditEntry) -> None:
        """Append entry to log file (JSONL format)."""
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        
        # Check if rotation needed
        if self.log_path.stat().st_size > self.max_bytes:
            self._rotate()

    def _rotate(self) -> None:
        """Rotate log file when exceeding max_bytes."""
        timestamp = int(time.time())
        rotated_path = self.log_path.with_suffix(f".{timestamp}.log")
        self.log_path.rename(rotated_path)

    def log(
        self,
        user_id: str,
        action: str,
        allowed: bool,
        reason: str,
        target: str = None,
    ) -> AuditEntry:
        """
        Log an action to the audit trail.
        Thread-safe with internal locking.
        """
        with self._lock:
            self._seq += 1
            prev_hash = (
                self._entries[-1].entry_hash
                if self._entries
                else self.GENESIS_HASH
            )
            
            entry = AuditEntry(
                seq=self._seq,
                timestamp=time.time(),
                user_id=user_id,
                action=action,
                target=target,
                allowed=allowed,
                reason=reason,
                prev_hash=prev_hash,
                entry_hash="",
            )
            
            entry.entry_hash = entry.compute_hash()
            self._entries.append(entry)
            self._append_to_disk(entry)
            
            return entry

    def verify(self) -> tuple[bool, str]:
        """
        Verify integrity of the hash chain.
        Returns (valid, message).
        """
        if not self._entries:
            return True, "Empty log"
        
        prev_hash = self.GENESIS_HASH
        
        for entry in self._entries:
            # Recompute hash
            recomputed = entry.compute_hash()
            if recomputed != entry.entry_hash:
                return (
                    False,
                    f"Tampered at entry {entry.seq}: hash mismatch",
                )
            
            # Check chain link
            if entry.prev_hash != prev_hash:
                return (
                    False,
                    f"Chain broken at entry {entry.seq}: prev_hash mismatch",
                )
            
            prev_hash = entry.entry_hash
        
        return True, f"Chain intact — {len(self._entries)} entries verified"

    def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        allowed: Optional[bool] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Query audit log with optional filtering.
        Returns last `limit` matching entries.
        """
        with self._lock:
            results = self._entries
            
            if user_id is not None:
                results = [e for e in results if e.user_id == user_id]
            if action is not None:
                results = [e for e in results if e.action == action]
            if allowed is not None:
                results = [e for e in results if e.allowed == allowed]
            if since is not None:
                results = [e for e in results if e.timestamp >= since]
            if until is not None:
                results = [e for e in results if e.timestamp <= until]
            
            return results[-limit:]

    def tail(self, n: int = 20) -> List[AuditEntry]:
        """Return last n entries."""
        with self._lock:
            return self._entries[-n:]

    def export_json(self, out_path: Path) -> None:
        """Export all entries as JSON array."""
        with self._lock:
            data = [entry.to_dict() for entry in self._entries]
            with open(out_path, "w") as f:
                json.dump(data, f, indent=2)
