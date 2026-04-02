"""Object pool for pre-allocated message reuse (zero GC on hot path)."""

from __future__ import annotations

import threading
from typing import Callable, Generic, Optional, TypeVar


T = TypeVar("T")


class ObjectPool(Generic[T]):
    """Generic object pool for reusing instances without GC."""

    def __init__(
        self,
        factory: Callable[[], T],
        reset: Callable[[T], None],
        size: int = 50,
    ) -> None:
        """Initialize object pool."""
        self._factory = factory
        self._reset = reset
        self._max_size = size
        self._pool: list[T] = [factory() for _ in range(size)]
        self._lock = threading.Lock()
        self._created = size
        self._reused = 0
        self._exhausted = 0

    def acquire(self) -> T:
        """Get object from pool or create new one."""
        with self._lock:
            if self._pool:
                obj = self._pool.pop()
                self._reused += 1
                return obj
        
        self._exhausted += 1
        self._created += 1
        return self._factory()

    def release(self, obj: T) -> None:
        """Return object to pool for reuse."""
        self._reset(obj)
        with self._lock:
            if len(self._pool) < self._max_size:
                self._pool.append(obj)

    def stats(self) -> dict:
        """Get pool statistics."""
        with self._lock:
            reuse_rate = (
                self._reused / (self._created or 1) * 100
            )
            return {
                "pool_size": len(self._pool),
                "created": self._created,
                "reused": self._reused,
                "exhausted": self._exhausted,
                "reuse_rate": f"{reuse_rate:.1f}%",
            }
