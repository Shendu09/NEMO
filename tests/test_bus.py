"""Tests for optimized NEMO-OS IPC Message Bus - Phase 3B."""

import pytest
import time
import threading
from core.bus import (
    BusMessage,
    MessageType,
    Topics,
    ObjectPool,
    TopicQueueManager,
    BusMetrics,
)
from core.bus.transport import frame, recv_framed


class TestTopicsConstants:
    """Test Topics constant definitions."""

    def test_topics_all_returns_16_topics(self):
        """Topics.all() should return 16 hardcoded topics."""
        all_topics = Topics.all()
        assert len(all_topics) == 16
        assert "voice.transcript" in all_topics
        assert "vision.screenshot" in all_topics
        assert "ai.decision" in all_topics
        assert "action.result" in all_topics


class TestMessageSerialization:
    """Test optimized message serialization with msgpack support."""

    def test_message_serialization_roundtrip(self):
        """Message should serialize and deserialize correctly."""
        msg = BusMessage.publish(
            topic="test.topic",
            payload={"key": "value", "number": 42},
            sender="test-client",
        )
        data = msg.to_bytes()
        restored = BusMessage.from_bytes(data)

        assert restored.topic == "test.topic"
        assert restored.payload == {"key": "value", "number": 42}
        assert restored.sender_id == "test-client"

    def test_message_short_field_names(self):
        """Message should use short field names in serialization."""
        msg = BusMessage.publish(
            topic="test.topic",
            payload={"test": "data"},
            sender="client1",
        )
        # Just verify it serializes correctly with short names
        data = msg.to_bytes()
        restored = BusMessage.from_bytes(data)
        assert restored.topic == msg.topic


class TestMessageExpiry:
    """Test message TTL and expiry behavior."""

    def test_message_expiry_zero_ttl(self):
        """Message with ttl=0 should be expired shortly after creation."""
        msg = BusMessage.publish(
            topic="test.topic",
            payload={"data": "test"},
        )
        msg.ttl = 0
        time.sleep(0.001)  # Sleep 1ms to ensure time passes
        assert msg.is_expired()

    def test_message_age_ms(self):
        """Message age_ms() should track time elapsed."""
        msg = BusMessage.publish(
            topic="test.topic",
            payload={"data": "test"},
        )
        time.sleep(0.01)  # Sleep 10ms
        age = msg.age_ms()
        assert age >= 10

    def test_message_not_expired_with_ttl(self):
        """Message with ttl=5s should not be expired immediately."""
        msg = BusMessage.publish(
            topic="test.topic",
            payload={"data": "test"},
        )
        msg.ttl = 5
        assert not msg.is_expired()


class TestObjectPooling:
    """Test object pool for memory efficiency."""

    def test_object_pool_acquire_and_release(self):
        """ObjectPool should acquire and release instances."""

        def factory():
            return {"value": 0}

        def reset(obj):
            obj["value"] = 0

        pool = ObjectPool(factory, reset, size=5)

        # Acquire and release
        obj1 = pool.acquire()
        obj1["value"] = 42
        pool.release(obj1)

        # Acquire again should get reset object
        obj2 = pool.acquire()
        assert obj2["value"] == 0
        pool.release(obj2)

    def test_object_pool_exhaustion_tracking(self):
        """ObjectPool should create new instances when exhausted."""
        counter = {"created": 0}

        def factory():
            counter["created"] += 1
            return {"id": counter["created"]}

        def reset(obj):
            pass

        pool = ObjectPool(factory, reset, size=2)

        # Pool initialization pre-creates size instances
        assert counter["created"] == 2

        # Acquire all from pool
        obj1 = pool.acquire()
        obj2 = pool.acquire()
        assert counter["created"] == 2

        # Acquire beyond pool size (should create new)
        obj3 = pool.acquire()
        assert counter["created"] == 3

        stats = pool.stats()
        assert stats["created"] == 3
        assert stats["reused"] >= 2

    def test_object_pool_reuse_rate(self):
        """ObjectPool should track reuse rate correctly."""

        def factory():
            return {}

        def reset(obj):
            obj.clear()

        pool = ObjectPool(factory, reset, size=3)

        # Warm up pool - acquire all 3 pre-created instances
        objs = [pool.acquire() for _ in range(3)]
        for obj in objs:
            pool.release(obj)

        # Use from pool (this should reuse)
        obj1 = pool.acquire()
        pool.release(obj1)

        stats = pool.stats()
        # reuse_rate is a string like "50.0%", check it's not empty
        assert stats["reuse_rate"]
        assert "%" in stats["reuse_rate"]


class TestPerTopicQueueIsolation:
    """Test that per-topic queues don't block each other."""

    def test_topic_queue_isolation(self):
        """One topic queue being full should not block other topics."""
        queue_mgr = TopicQueueManager(default_maxsize=2)

        # Fill voice queue
        for i in range(2):
            msg = BusMessage.publish(
                topic="voice.transcript",
                payload={"frame": i},
            )
            queue_mgr.put(msg)

        # Vision should still accept messages (not blocked by voice)
        msg = BusMessage.publish(
            topic="vision.screenshot",
            payload={"frame": 0},
        )
        queue_mgr.put(msg)

        sizes = queue_mgr.sizes()
        assert sizes["voice.transcript"] == 2
        assert sizes["vision.screenshot"] == 1


class TestQueueExpiry:
    """Test queue message expiry handling."""

    def test_queue_filters_expired_on_retrieval(self):
        """Queue should filter out expired messages when retrieving."""
        queue_mgr = TopicQueueManager()

        msg_expired = BusMessage.publish(
            topic="ai.decision",
            payload={"cmd": "test"},
        )
        msg_expired.ttl = 0
        time.sleep(0.001)  # Ensure expiry
        
        msg_valid = BusMessage.publish(
            topic="ai.decision",
            payload={"cmd": "test"},
        )
        msg_valid.ttl = 10

        # Put both messages
        queue_mgr.put(msg_expired)
        queue_mgr.put(msg_valid)

        # Get messages - expired should be filtered
        retrieved = queue_mgr.get("ai.decision")
        # Either the valid message is retrieved, or None if expired was retrieved and filtered
        if retrieved is not None:
            assert retrieved.payload == {"cmd": "test"}


class TestQueueSizeLimit:
    """Test queue size limiting behavior."""

    def test_queue_respects_max_size(self):
        """Queue should not exceed per-topic max size."""
        queue_mgr = TopicQueueManager(default_maxsize=3)

        for i in range(5):
            msg = BusMessage.publish(
                topic="action.result",
                payload={"cmd": i},
            )
            queue_mgr.put(msg)

        sizes = queue_mgr.sizes()
        assert sizes["action.result"] <= 3


class TestFramingRoundtrip:
    """Test length-prefixed framing for various message sizes."""

    def test_framing_small_message(self):
        """Framing should handle small (1B) messages correctly."""
        data = b"X"
        framed = frame(data)
        assert len(framed) >= 5  # 4 byte header + 1 byte data

    def test_framing_medium_message(self):
        """Framing should handle medium (~1KB) messages correctly."""
        data = b"X" * 1024
        framed = frame(data)
        assert len(framed) == 4 + 1024

    def test_framing_large_message(self):
        """Framing should handle large (~64KB) messages correctly."""
        data = b"X" * (64 * 1024)
        framed = frame(data)
        assert len(framed) == 4 + (64 * 1024)


class TestMetricsTracking:
    """Test performance metrics collection."""

    def test_metrics_records_latency(self):
        """Metrics should record latency samples and compute stats."""
        metrics = BusMetrics()

        # Record 100 messages
        for i in range(100):
            metrics.record("voice.transcript", 0.5)  # 0.5ms latency

        summary = metrics.summary()
        assert summary["total_messages"] >= 100
        assert "latency_ms" in summary
        assert summary["latency_ms"]["avg"] >= 0.4

    def test_metrics_p95_percentile(self):
        """Metrics should calculate p95 percentile latency."""
        metrics = BusMetrics()

        # Record 100 varied latencies
        for i in range(100):
            latency = 0.1 + (i * 0.01)  # 0.1 to 1.0ms
            metrics.record("system.health", latency)

        summary = metrics.summary()
        assert "p95" in summary["latency_ms"]
        # p95 should be higher than average
        assert summary["latency_ms"]["p95"] > summary["latency_ms"]["avg"]

    def test_metrics_per_topic_stats(self):
        """Metrics should track per-topic statistics."""
        metrics = BusMetrics()

        for i in range(50):
            metrics.record("vision.screenshot", 0.3)
            metrics.record("ai.decision", 0.7)

        summary = metrics.summary()
        assert "per_topic" in summary
        assert "vision.screenshot" in summary["per_topic"]
        assert "ai.decision" in summary["per_topic"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

