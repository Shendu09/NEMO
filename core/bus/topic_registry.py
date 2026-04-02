"""Topic subscription registry for the NEMO-OS IPC bus."""

from __future__ import annotations

import fnmatch
import logging
import threading
from typing import Callable

from .message import BusMessage


class TopicRegistry:
    """Tracks topic subscriptions and route handlers."""

    def __init__(self) -> None:
        """Initialize topic registry."""
        self._subscriptions: dict[str, set[str]] = {}
        self._handlers: dict[str, Callable[[BusMessage], None]] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger("clevrr.bus.registry")

    def subscribe(
        self,
        subscriber_id: str,
        topic_pattern: str,
        handler: Callable[[BusMessage], None],
    ) -> None:
        """Subscribe a handler to a topic pattern."""
        with self._lock:
            if topic_pattern not in self._subscriptions:
                self._subscriptions[topic_pattern] = set()
            self._subscriptions[topic_pattern].add(subscriber_id)
            self._handlers[subscriber_id] = handler
            self.logger.debug(
                f"{subscriber_id} subscribed to {topic_pattern}"
            )

    def unsubscribe(self, subscriber_id: str, topic_pattern: str) -> None:
        """Unsubscribe from a specific topic pattern."""
        with self._lock:
            if topic_pattern in self._subscriptions:
                self._subscriptions[topic_pattern].discard(subscriber_id)

    def unsubscribe_all(self, subscriber_id: str) -> None:
        """Unsubscribe from all topics."""
        with self._lock:
            for subs in self._subscriptions.values():
                subs.discard(subscriber_id)
            self._handlers.pop(subscriber_id, None)

    def get_handlers(self, topic: str) -> list[Callable[[BusMessage], None]]:
        """Get all handlers for a topic using wildcard matching."""
        with self._lock:
            handlers = []
            for pattern, subscriber_ids in self._subscriptions.items():
                if fnmatch.fnmatch(topic, pattern):
                    for sub_id in subscriber_ids:
                        handler = self._handlers.get(sub_id)
                        if handler:
                            handlers.append(handler)
            return handlers

    def list_subscriptions(self) -> dict[str, list[str]]:
        """Return copy of current subscriptions for debugging."""
        with self._lock:
            return {
                pattern: list(subs)
                for pattern, subs in self._subscriptions.items()
            }
