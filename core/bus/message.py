"""Message data models and types for the NEMO-OS IPC bus (optimized)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

try:
    import msgpack
    _USE_MSGPACK = True
except ImportError:
    _USE_MSGPACK = False


class MessageType(str, Enum):
    """Message type enumeration (short codes save bytes)."""

    PUBLISH = "pub"
    REQUEST = "req"
    REPLY = "rep"
    SUBSCRIBE = "sub"
    UNSUBSCRIBE = "uns"
    HEARTBEAT = "hbt"
    ERROR = "err"


@dataclass(slots=True)
class BusMessage:
    """Message that flows through the IPC bus (optimized with short fields)."""

    type: MessageType
    topic: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    payload: dict = field(default_factory=dict)
    sender_id: str = ""
    reply_to: str = ""
    ts: float = field(default_factory=time.time)
    ttl: int = 30

    def reset(self) -> None:
        """Reset message for object pool reuse."""
        self.id = str(uuid.uuid4())[:8]
        self.payload = {}
        self.reply_to = ""
        self.ts = time.time()
        self.ttl = 30

    def to_bytes(self) -> bytes:
        """Serialize message to bytes (msgpack or JSON)."""
        data = {
            "i": self.id,
            "t": self.type.value,
            "p": self.topic,
            "d": self.payload,
            "s": self.sender_id,
            "r": self.reply_to,
            "ts": self.ts,
            "ttl": self.ttl,
        }
        if _USE_MSGPACK:
            return msgpack.packb(data, use_bin_type=True)
        return json.dumps(data).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> BusMessage:
        """Deserialize message from bytes."""
        if _USE_MSGPACK:
            d = msgpack.unpackb(data, raw=False)
        else:
            d = json.loads(data)
        return cls(
            id=d["i"],
            type=MessageType(d["t"]),
            topic=d["p"],
            payload=d["d"],
            sender_id=d["s"],
            reply_to=d["r"],
            ts=d["ts"],
            ttl=d["ttl"],
        )

    def is_expired(self) -> bool:
        """Check if message has exceeded TTL."""
        return time.time() > self.ts + self.ttl

    def age_ms(self) -> float:
        """Get message age in milliseconds."""
        return (time.time() - self.ts) * 1000

    @staticmethod
    def publish(
        topic: str,
        payload: dict = None,
        sender: str = "",
    ) -> BusMessage:
        """Create a PUBLISH message."""
        return BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.PUBLISH,
            topic=topic,
            payload=payload or {},
            sender_id=sender,
            reply_to="",
            ts=time.time(),
            ttl=30,
        )

    @staticmethod
    def request(
        topic: str,
        payload: dict = None,
        sender: str = "",
    ) -> BusMessage:
        """Create a REQUEST message."""
        return BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.REQUEST,
            topic=topic,
            payload=payload or {},
            sender_id=sender,
            reply_to="",
            ts=time.time(),
            ttl=30,
        )

    @staticmethod
    def reply(
        original: BusMessage,
        payload: dict = None,
        sender: str = "",
    ) -> BusMessage:
        """Create a REPLY message in response to a REQUEST."""
        return BusMessage(
            id=str(uuid.uuid4())[:8],
            type=MessageType.REPLY,
            topic=original.topic + ".reply",
            payload=payload or {},
            sender_id=sender,
            reply_to=original.id,
            ts=time.time(),
            ttl=30,
        )
