"""Per-topic queue manager for isolated message backpressure."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

from .message import BusMessage
from .topics import Topics


class TopicQueueManager:
    """Manages per-topic queues for isolation between layers."""

    def __init__(
        self,
        default_maxsize: int = 200,
        per_topic_maxsize: dict[str, int] = None,
    ) -> None:
        """Initialize queue manager."""
        self.default_maxsize = default_maxsize
        self._queues: dict[str, queue.Queue] = {}
        self._dropped_per_topic: dict[str, int] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("clevrr.bus.queues")

        # Pre-create queues for all known topics
        for topic in Topics.all():
            size = (per_topic_maxsize or {}).get(topic, default_maxsize)
            self._queues[topic] = queue.Queue(maxsize=size)
            self._dropped_per_topic[topic] = 0

    def put(self, msg: BusMessage) -> bool:
        """Add message to topic queue. Returns False if dropped."""
        if msg.is_expired():
            return False

        q = self._get_or_create(msg.topic)
        try:
            q.put_nowait(msg)
            return True
        except queue.Full:
            with self._lock:
                self._dropped_per_topic[msg.topic] = (
                    self._dropped_per_topic.get(msg.topic, 0) + 1
                )
            self.logger.warning(
                f"Queue full for topic '{msg.topic}' — message dropped"
            )
            return False

    def get(
        self,
        topic: str,
        timeout: float = 0.5,
    ) -> Optional[BusMessage]:
        """Get message from specific topic queue."""
        q = self._get_or_create(topic)
        try:
            msg = q.get(timeout=timeout)
            if msg.is_expired():
                return None
            return msg
        except queue.Empty:
            return None

    def get_any(self, timeout: float = 0.1) -> Optional[BusMessage]:
        """Non-blocking scan across all queues."""
        for topic, q in self._queues.items():
            try:
                msg = q.get_nowait()
                if not msg.is_expired():
                    return msg
            except queue.Empty:
                continue
        return None

    def sizes(self) -> dict[str, int]:
        """Get size of all non-empty queues."""
        return {
            t: q.qsize()
            for t, q in self._queues.items()
            if q.qsize() > 0
        }

    def dropped(self) -> dict[str, int]:
        """Get count of dropped messages per topic."""
        return {
            t: n
            for t, n in self._dropped_per_topic.items()
            if n > 0
        }

    def _get_or_create(self, topic: str) -> queue.Queue:
        """Get or create queue for topic."""
        with self._lock:
            if topic not in self._queues:
                self._queues[topic] = queue.Queue(
                    maxsize=self.default_maxsize
                )
                self._dropped_per_topic[topic] = 0
            return self._queues[topic]
