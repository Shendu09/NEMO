"""Central IPC bus server - wires components together."""

from __future__ import annotations

import fnmatch
import logging
import socket
import threading
import time
from typing import Callable, Optional

from .message import BusMessage, MessageType
from .metrics import BusMetrics
from .object_pool import ObjectPool
from .topic_queue import TopicQueueManager
from .transport import TransportServer


class BusServer:
    """Central message bus server with single dispatch thread."""

    def __init__(self) -> None:
        """Initialize bus server."""
        self._queues = TopicQueueManager(
            per_topic_maxsize={"vision.screenshot": 5}
        )
        self._metrics = BusMetrics(enabled=True)
        self._transport = TransportServer(on_message=self._on_incoming)
        self._subscriptions: dict[str, set[socket.socket]] = {}
        self._sub_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._dispatch_thread: Optional[threading.Thread] = None
        self.logger = logging.getLogger("clevrr.bus")

    def start(self) -> None:
        """Start bus server."""
        self._stop_event.clear()
        self._transport.start()
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            name="clevrr-bus-dispatch",
            daemon=True,
        )
        self._dispatch_thread.start()
        self.logger.info("Bus server started")

    def stop(self) -> None:
        """Stop bus server."""
        self._stop_event.set()
        self._transport.stop()
        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=3)
        self.logger.info("Bus server stopped")

    def get_metrics(self) -> dict:
        """Get performance metrics."""
        return {
            **self._metrics.summary(),
            "queues": self._queues.sizes(),
            "dropped": self._queues.dropped(),
        }

    def _on_incoming(
        self,
        msg: BusMessage,
        conn: socket.socket,
    ) -> None:
        """Handle incoming message from client."""
        if msg.type == MessageType.SUBSCRIBE:
            self._handle_subscribe(msg.topic, conn)
            return

        if msg.type == MessageType.UNSUBSCRIBE:
            self._handle_unsubscribe(msg.topic, conn)
            return

        # Queue PUBLISH/REQUEST for dispatch
        self._queues.put(msg)

    def _handle_subscribe(
        self,
        pattern: str,
        conn: socket.socket,
    ) -> None:
        """Register subscription from client."""
        with self._sub_lock:
            if pattern not in self._subscriptions:
                self._subscriptions[pattern] = set()
            self._subscriptions[pattern].add(conn)

    def _handle_unsubscribe(
        self,
        pattern: str,
        conn: socket.socket,
    ) -> None:
        """Unregister subscription from client."""
        with self._sub_lock:
            if pattern in self._subscriptions:
                self._subscriptions[pattern].discard(conn)

    def _dispatch_loop(self) -> None:
        """Single dispatch thread processing queue."""
        self.logger.debug("Dispatcher loop started")
        while not self._stop_event.is_set():
            msg = self._queues.get_any(timeout=0.05)
            if msg is None:
                continue
            
            start = time.monotonic()
            self._dispatch(msg)
            latency_ms = (time.monotonic() - start) * 1000
            self._metrics.record(msg.topic, latency_ms)

    def _dispatch(self, msg: BusMessage) -> None:
        """Dispatch message to matching subscribers."""
        # Find matching subscribers
        with self._sub_lock:
            targets = []
            for pattern, sockets in self._subscriptions.items():
                if fnmatch.fnmatch(msg.topic, pattern):
                    targets.extend(sockets)

        # Send to each subscriber
        dead = []
        for sock in targets:
            try:
                self._transport.send(sock, msg)
            except Exception:
                dead.append(sock)

        # Remove dead connections
        if dead:
            with self._sub_lock:
                for pattern in self._subscriptions:
                    self._subscriptions[pattern] -= set(dead)
