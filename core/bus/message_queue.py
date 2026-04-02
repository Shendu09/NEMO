"""Thread-safe async message queue for the NEMO-OS IPC bus."""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional

from .message import BusMessage


class MessageQueue:
    """Thread-safe queue for bus messages with TTL expiry."""

    def __init__(self, maxsize: int = 1000) -> None:
        """Initialize message queue."""
        self._queue: queue.Queue[BusMessage] = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._dropped: int = 0
        self.logger = logging.getLogger("clevrr.bus.queue")

    def put(self, msg: BusMessage, block: bool = False) -> bool:
        """Add message to queue. Returns False if dropped."""
        # Skip expired messages
        if msg.is_expired():
            with self._lock:
                self._dropped += 1
            return False

        try:
            self._queue.put(msg, block=block, timeout=0.1)
            return True
        except queue.Full:
            with self._lock:
                self._dropped += 1
            self.logger.warning(
                f"Queue full — dropped message on topic {msg.topic}"
            )
            return False

    def get(self, timeout: float = 1.0) -> Optional[BusMessage]:
        """Get next message from queue. Returns None on timeout/expiry."""
        try:
            msg = self._queue.get(timeout=timeout)
            # Skip expired messages
            if msg.is_expired():
                with self._lock:
                    self._dropped += 1
                return None
            return msg
        except queue.Empty:
            return None

    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()

    def dropped(self) -> int:
        """Get count of dropped messages."""
        with self._lock:
            return self._dropped

    def clear(self) -> None:
        """Clear all messages from queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
