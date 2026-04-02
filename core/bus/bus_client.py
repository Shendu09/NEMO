"""Client library for connecting to NEMO-OS IPC bus (optimized)."""

from __future__ import annotations

import fnmatch
import logging
import platform
import socket
import threading
import time
import uuid
from typing import Callable, Optional

from .message import BusMessage, MessageType
from .transport import frame, recv_framed


class BusClient:
    """Client for connecting to the central bus and sending/receiving messages."""

    def __init__(self, client_id: str = "") -> None:
        """Initialize bus client."""
        self._id = client_id or str(uuid.uuid4())[:8]
        self._is_windows = platform.system() == "Windows"
        self._subs: dict[str, Callable[[BusMessage], None]] = {}
        self._stop = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._pending: dict[str, threading.Event] = {}
        self._replies: dict[str, BusMessage] = {}
        self._send_lock = threading.Lock()
        self.logger = logging.getLogger(f"clevrr.client.{self._id}")

    def connect(self) -> None:
        """Connect to bus server."""
        from .transport import UNIX_SOCKET_PATH
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.connect(UNIX_SOCKET_PATH)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        self._stop.clear()
        threading.Thread(
            target=self._listen_loop,
            daemon=True,
        ).start()
        
        self.logger.info(f"Bus client {self._id} connected")

    def disconnect(self) -> None:
        """Disconnect from bus server."""
        self._stop.set()
        if self._sock:
            self._sock.close()

    def publish(self, topic: str, payload: dict = None) -> None:
        """Publish a message to a topic."""
        msg = BusMessage.publish(topic, payload or {}, self._id)
        self._send(msg)

    def request(
        self,
        topic: str,
        payload: dict = None,
        timeout: float = 5.0,
    ) -> Optional[BusMessage]:
        """Send REQUEST and wait for REPLY."""
        msg = BusMessage.request(topic, payload or {}, self._id)
        evt = threading.Event()
        self._pending[msg.id] = evt
        self._send(msg)
        
        if evt.wait(timeout=timeout):
            return self._replies.pop(msg.id, None)
        
        self._pending.pop(msg.id, None)
        self.logger.warning(f"Request timed out: {topic}")
        return None

    def subscribe(
        self,
        topic_pattern: str,
        handler: Callable[[BusMessage], None],
    ) -> None:
        """Subscribe to a topic pattern."""
        self._subs[topic_pattern] = handler
        sub_msg = BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.SUBSCRIBE,
            topic=topic_pattern,
            payload={},
            sender_id=self._id,
            reply_to="",
            ts=time.time(),
            ttl=30,
        )
        self._send(sub_msg)

    def unsubscribe(self, topic_pattern: str) -> None:
        """Unsubscribe from a topic pattern."""
        self._subs.pop(topic_pattern, None)
        unsub_msg = BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.UNSUBSCRIBE,
            topic=topic_pattern,
            payload={},
            sender_id=self._id,
            reply_to="",
            ts=time.time(),
            ttl=30,
        )
        self._send(unsub_msg)

    def _send(self, msg: BusMessage) -> None:
        """Send message to bus."""
        if not self._sock:
            self.logger.error("Not connected to bus")
            return
        try:
            with self._send_lock:
                data = msg.to_bytes()
                self._sock.sendall(frame(data))
        except Exception as exc:
            self.logger.error(f"Send error: {exc}")

    def _listen_loop(self) -> None:
        """Background thread receiving messages."""
        while not self._stop.is_set():
            try:
                data = recv_framed(self._sock)
                if data is None:
                    break
                msg = BusMessage.from_bytes(data)
                self._handle(msg)
            except Exception as exc:
                if not self._stop.is_set():
                    self.logger.error(f"Listener error: {exc}")
                break

    def _handle(self, msg: BusMessage) -> None:
        """Handle incoming message from bus."""
        # Handle reply to waiting request
        if msg.type == MessageType.REPLY and msg.reply_to:
            if msg.reply_to in self._pending:
                self._replies[msg.reply_to] = msg
                self._pending.pop(msg.reply_to).set()
            return

        # Match against local subscriptions
        for pattern, handler in self._subs.items():
            if fnmatch.fnmatch(msg.topic, pattern):
                threading.Thread(
                    target=handler,
                    args=(msg,),
                    daemon=True,
                ).start()
