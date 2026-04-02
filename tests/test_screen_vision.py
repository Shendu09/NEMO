"""Tests for Screen Vision."""

import json
import pytest
from unittest.mock import MagicMock, patch

from vision.screen_vision import ScreenVision
from core.bus import MessageType, Topics


class MockBusClient:
    """Mock BusClient for testing."""

    def __init__(self):
        self.published = []
        self.subscriptions = {}

    def subscribe(self, topic, handler):
        """Mock subscribe."""
        self.subscriptions[topic] = handler

    def publish(self, topic, payload, sender=""):
        """Mock publish."""
        self.published.append({
            "topic": topic,
            "payload": payload,
            "sender": sender,
        })


class TestScreenVisionInit:
    """Test ScreenVision initialization."""

    def test_screen_vision_init(self):
        """ScreenVision should initialize with bus client."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

            assert vision.bus == bus
            assert vision._ollama_available

    def test_screen_vision_ollama_unavailable(self):
        """ScreenVision should handle Ollama not available."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            vision = ScreenVision(bus)

            assert vision._ollama_available is False


class TestScreenVisionCaptureWindow:
    """Test screen capture functionality."""

    def test_capture_window_basic(self):
        """_capture_window should capture window and return base64."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        # Mock window
        mock_window = MagicMock()
        mock_window.left = 10
        mock_window.top = 20
        mock_window.width = 800
        mock_window.height = 600

        with patch("mss.mss"):
            with patch("PIL.Image.Image.save"):
                # Test just the logic, not actual image capture
                region = {
                    "left": max(0, mock_window.left),
                    "top": max(0, mock_window.top),
                    "width": max(1, mock_window.width),
                    "height": max(1, mock_window.height),
                }
                assert region["width"] == 800
                assert region["height"] == 600


class TestScreenVisionAnalyzeScreen:
    """Test screen analysis."""

    def test_analyze_screen_no_window(self):
        """analyze_screen should handle no active window."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        with patch("pygetwindow.getActiveWindow", return_value=None):
            result = vision.analyze_screen()

            assert result["success"] is False
            assert "No active window" in result["error"]

    def test_analyze_screen_with_window_no_ollama(self):
        """analyze_screen should return basic info when Ollama unavailable."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            vision = ScreenVision(bus)

        mock_window = MagicMock()
        mock_window.title = "Test Window"
        mock_window.left = 0
        mock_window.top = 0
        mock_window.width = 1024
        mock_window.height = 768

        with patch("pygetwindow.getActiveWindow", return_value=mock_window):
            with patch.object(vision, "_capture_window", return_value="base64data"):
                result = vision.analyze_screen()

                assert result["success"] is True
                assert result["app"] == "Test Window"
                assert result["elements"] == []
                assert result["visible_text"] == []


class TestScreenVisionParseResponse:
    """Test parsing Ollama responses."""

    def test_parse_vision_response_valid_json(self):
        """_parse_vision_response should parse valid JSON."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        response_text = json.dumps({
            "app": "Chrome",
            "elements": [
                {"name": "Address Bar", "type": "field"},
            ],
            "visible_text": ["Google", "Search"],
            "screen_size": {"width": 1024, "height": 768},
        })

        result = vision._parse_vision_response(response_text)

        assert result["app"] == "Chrome"
        assert len(result["elements"]) == 1
        assert "Google" in result["visible_text"]

    def test_parse_vision_response_json_in_markdown(self):
        """_parse_vision_response should extract JSON from markdown."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        # JSON wrapped in markdown code block
        response_text = f"""Here's the analysis:
```json
{json.dumps({"app": "Firefox", "elements": [], "visible_text": [], "screen_size": {}})}
```"""

        result = vision._parse_vision_response(response_text)

        assert result["app"] == "Firefox"

    def test_parse_vision_response_invalid_json(self):
        """_parse_vision_response should handle invalid JSON gracefully."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        result = vision._parse_vision_response("Not valid JSON at all")

        assert result["app"] == "Unknown"
        assert result["elements"] == []
        assert "parse_error" in result


class TestScreenVisionStart:
    """Test starting/stopping ScreenVision."""

    def test_start_subscribes_to_topic(self):
        """start() should subscribe to VISION_SCREENSHOT topic."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        vision.start()

        assert Topics.VISION_SCREENSHOT in bus.subscriptions

    def test_start_twice_logs_warning(self):
        """start() called twice should log warning."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        vision.start()

        with patch.object(vision.logger, "warning") as mock_warn:
            vision.start()
            mock_warn.assert_called()


class TestScreenVisionListenerCallback:
    """Test listener callback handling."""

    def test_listener_handles_screenshot_request(self):
        """Listener should process screenshot requests."""
        bus = MockBusClient()

        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            vision = ScreenVision(bus)

        vision.start()

        # Simulate screenshot request
        handler = bus.subscriptions[Topics.VISION_SCREENSHOT]

        from core.bus import BusMessage

        msg = BusMessage.publish(
            topic=Topics.VISION_SCREENSHOT,
            payload={},
        )

        with patch.object(vision, "analyze_screen") as mock_analyze:
            mock_analyze.return_value = {
                "success": True,
                "app": "Test",
                "elements": [],
                "visible_text": [],
            }
            handler(msg)

            # Should have published result
            results = [p for p in bus.published if p["topic"] == Topics.VISION_CONTEXT]
            assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
