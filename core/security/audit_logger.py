"""
Audit Logger - Tamper-evident, hash-chained audit log for NEMO Security Layer.
Provides immutable record of all security-relevant actions.
"""

import json
import hashlib
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class AuditEntry:
    """A single audit log entry."""
    seq: int
    timestamp: str
    user_id: str
    action: str
    target: str
    allowed: bool
    reason: str
    prev_hash: str
    entry_hash: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Remove entry_hash from dict before computing
        return {k: v for k, v in d.items() if k != "entry_hash"}

    def compute_hash(self) -> str:
        """
        Compute SHA256 hash of this entry (excluding entry_hash itself).
        Only includes: seq, timestamp, user_id, action, target, allowed, reason, prev_hash
        """
        d = self.to_dict()
        json_str = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(json_str.encode()).hexdigest()


class AuditLogger:
    """
    Append-only, hash-chained audit log with tamper detection.
    Thread-safe. Persists to JSONL format (one JSON object per line).
    """

    def __init__(
        self,
        data_dir: Path = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
    ):
        """
        Initialize audit logger.
        
        Args:
            data_dir: Directory for log files. Defaults to ./clevrr_data
            max_bytes: Max file size before rotation. Defaults to 10MB
        """
        self.data_dir = Path(data_dir) if data_dir else Path("./clevrr_data")
        self.data_dir.mkdir(exist_ok=True)
        
        self.max_bytes = max_bytes
        self.log_file = self.data_dir / "audit.jsonl"
        self.log_index = 0  # Current log file index for rotation
        
        self._lock = threading.RLock()
        self.entries: List[AuditEntry] = []
        self.seq_counter = 0
        
        # Load existing log
        self._load_log()

    def _load_log(self) -> None:
        """Load existing log entries from disk."""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            entry = AuditEntry(
                                seq=data["seq"],
                                timestamp=data["timestamp"],
                                user_id=data["user_id"],
                                action=data["action"],
                                target=data["target"],
                                allowed=data["allowed"],
                                reason=data["reason"],
                                prev_hash=data["prev_hash"],
                                entry_hash=data["entry_hash"],
                            )
                            self.entries.append(entry)
                            self.seq_counter = max(self.seq_counter, entry.seq)
            except (json.JSONDecodeError, KeyError, ValueError):
                # Corrupted log - start fresh
                self.entries = []
                self.seq_counter = 0

    def _should_rotate(self) -> bool:
        """Check if log file should be rotated."""
        if not self.log_file.exists():
            return False
        return self.log_file.stat().st_size >= self.max_bytes

    def _rotate_log(self) -> None:
        """Rotate log file when it exceeds max_bytes."""
        if self._should_rotate():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            rotated = self.data_dir / f"audit.{timestamp}.jsonl"
            self.log_file.rename(rotated)

    def _write_entry_to_disk(self, entry: AuditEntry) -> None:
        """Append entry to disk (append-only)."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def log(
        self,
        user_id: str,
        action: str,
        target: str,
        allowed: bool,
        reason: str,
    ) -> AuditEntry:
        """
        Log an action to the audit trail.
        
        Args:
            user_id: User performing the action
            action: Action being attempted
            target: Target of the action (file path, command, etc.)
            allowed: Whether the action was permitted
            reason: Reason for allow/deny decision
            
        Returns:
            The created AuditEntry
        """
        with self._lock:
            self.seq_counter += 1
            timestamp = datetime.utcnow().isoformat()
            
            # Get previous entry hash (or genesis hash)
            prev_hash = (
                self.entries[-1].entry_hash
                if self.entries
                else "0" * 64
            )
            
            # Create entry (without hash first)
            entry = AuditEntry(
                seq=self.seq_counter,
                timestamp=timestamp,
                user_id=user_id,
                action=action,
                target=target,
                allowed=allowed,
                reason=reason,
                prev_hash=prev_hash,
                entry_hash="",  # Will be computed
            )
            
            # Compute hash
            entry.entry_hash = entry.compute_hash()
            
            # Add to memory and disk
            self.entries.append(entry)
            self._write_entry_to_disk(entry)
            
            # Check if rotation needed
            self._rotate_log()
            
            return entry

    def verify(self) -> tuple[bool, Optional[str]]:
        """
        Verify the integrity of the audit chain.
        Recomputes all hashes and checks the chain.
        
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if chain is intact
            - error_message: Description of tampering if detected
        """
        with self._lock:
            if not self.entries:
                return True, None
            
            # Check first entry (should have prev_hash = genesis)
            first = self.entries[0]
            if first.prev_hash != "0" * 64:
                return False, "First entry prev_hash is not genesis"
            
            # Verify first entry hash
            expected_hash = first.compute_hash()
            if first.entry_hash != expected_hash:
                return (
                    False,
                    f"Entry {first.seq}: hash mismatch (tampering detected)",
                )
            
            # Check remaining entries
            for i in range(1, len(self.entries)):
                prev_entry = self.entries[i - 1]
                curr_entry = self.entries[i]
                
                # Check prev_hash points to previous entry
                if curr_entry.prev_hash != prev_entry.entry_hash:
                    return (
                        False,
                        f"Entry {curr_entry.seq}: prev_hash mismatch (tampering detected)",
                    )
                
                # Verify entry hash
                expected_hash = curr_entry.compute_hash()
                if curr_entry.entry_hash != expected_hash:
                    return (
                        False,
                        f"Entry {curr_entry.seq}: hash mismatch (tampering detected)",
                    )
            
            return True, None

    def query(
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
            allowed: Filter by permission result (True/False)
            since: Filter entries since ISO timestamp
            until: Filter entries until ISO timestamp
            limit: Maximum number of results
            
        Returns:
            Filtered list of AuditEntry objects
        """
        with self._lock:
            results = self.entries.copy()
            
            if user_id:
                results = [e for e in results if e.user_id == user_id]
            
            if action:
                results = [e for e in results if e.action == action]
            
            if allowed is not None:
                results = [e for e in results if e.allowed == allowed]
            
            if since:
                results = [e for e in results if e.timestamp >= since]
            
            if until:
                results = [e for e in results if e.timestamp <= until]
            
            if limit:
                results = results[-limit:]  # Last N entries
            
            return results

    def export_json(self, filepath: Path) -> None:
        """
        Export entire audit log to JSON file.
        
        Args:
            filepath: Path to write JSON file
        """
        with self._lock:
            data = [asdict(e) for e in self.entries]
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

    def get_entries(self) -> List[AuditEntry]:
        """Get all entries (thread-safe copy)."""
        with self._lock:
            return self.entries.copy()

    def get_entry_count(self) -> int:
        """Get total number of entries."""
        with self._lock:
            return len(self.entries)

    def get_chain_integrity(self) -> Dict:
        """
        Get detailed chain integrity report.
        
        Returns:
            Dictionary with integrity analysis
        """
        is_valid, error = self.verify()
        return {
            "valid": is_valid,
            "entry_count": self.get_entry_count(),
            "error": error,
            "genesis_hash": "0" * 64,
            "head_hash": self.entries[-1].entry_hash if self.entries else None,
        }
