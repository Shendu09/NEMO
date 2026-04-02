"""Tests for NEMO HTTP Server."""

import json
import pytest
from unittest.mock import MagicMock, patch

from bridge.nemo_server import app, set_dependencies, _capture_screenshot
from core.security.gateway_v2 import SecurityGateway
from core.security.audit_logger_v2 import AuditLogger


@pytest.fixture
def client():
    """Create test client."""
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def mock_gateway():
    """Create mock gateway."""
    gateway = MagicMock(spec=SecurityGateway)
    gateway.run_command = MagicMock(return_value={"allowed": True})
    return gateway


@pytest.fixture
def mock_audit():
    """Create mock audit logger."""
    audit = MagicMock(spec=AuditLogger)
    audit.log = MagicMock()
    return audit


@pytest.fixture(autouse=True)
def setup_dependencies(mock_gateway, mock_audit):
    """Inject dependencies before each test."""
    set_dependencies(mock_gateway, mock_audit)
    yield
    # Cleanup
    set_dependencies(None, None)


class TestHealthEndpoint:
    """Test GET /health endpoint."""

    def test_health_check(self, client):
        """GET /health should return ok status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"
        assert data["security"] == "active"


class TestScreenshotEndpoint:
    """Test GET /screenshot endpoint."""

    def test_screenshot_no_window(self, client):
        """GET /screenshot should handle no active window."""
        with patch("pygetwindow.getActiveWindow", return_value=None):
            response = client.get("/screenshot")

            assert response.status_code == 400
            data = json.loads(response.data)
            assert data["success"] is False

    def test_screenshot_success(self, client, mock_audit):
        """GET /screenshot should capture and return base64."""
        mock_window = MagicMock()
        mock_window.left = 0
        mock_window.top = 0
        mock_window.width = 800
        mock_window.height = 600

        with patch("pygetwindow.getActiveWindow", return_value=mock_window):
            with patch("bridge.nemo_server._capture_screenshot", return_value="base64data"):
                response = client.get("/screenshot")

                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["screenshot"] == "base64data"
                mock_audit.log.assert_called_once()


class TestExecuteEndpoint:
    """Test POST /execute endpoint."""

    def test_execute_no_action(self, client):
        """POST /execute without action should fail."""
        response = client.post(
            "/execute",
            data=json.dumps({}),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "action is required" in data["error"]

    def test_execute_unknown_action(self, client):
        """POST /execute with unknown action should fail."""
        response = client.post(
            "/execute",
            data=json.dumps({"action": "unknown"}),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False

    def test_execute_screenshot(self, client):
        """POST /execute screenshot should return base64."""
        with patch("bridge.nemo_server._capture_screenshot", return_value="base64data"):
            response = client.post(
                "/execute",
                data=json.dumps({
                    "action": "screenshot",
                    "user": "test",
                }),
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert "screenshot" in data

    def test_execute_wait(self, client):
        """POST /execute wait should sleep and return success."""
        with patch("time.sleep") as mock_sleep:
            response = client.post(
                "/execute",
                data=json.dumps({
                    "action": "wait",
                    "value": "0.5",
                    "user": "test",
                }),
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["seconds"] == 0.5
            mock_sleep.assert_called_once_with(0.5)

    def test_execute_security_failure(self, client, mock_gateway, mock_audit):
        """POST /execute should handle security failure."""
        mock_gateway.run_command.side_effect = PermissionError("Access denied")

        response = client.post(
            "/execute",
            data=json.dumps({
                "action": "click",
                "value": "100,200",
                "user": "restricted",
            }),
            content_type="application/json",
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Blocked by security" in data["error"]


class TestOpenAppAction:
    """Test open_app action."""

    def test_open_app_chrome(self, client):
        """open_app chrome should use special flags."""
        with patch("subprocess.Popen") as mock_popen:
            with patch("time.sleep"):
                response = client.post(
                    "/execute",
                    data=json.dumps({
                        "action": "open_app",
                        "target": "chrome",
                        "user": "test",
                    }),
                    content_type="application/json",
                )

                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True

                # Verify chrome was called with flags
                call_args = mock_popen.call_args[0][0]
                assert "chrome.exe" in call_args
                assert "--profile-directory=Default" in call_args
                assert "--no-first-run" in call_args

    def test_open_app_notepad(self, client):
        """open_app notepad should work."""
        with patch("subprocess.Popen") as mock_popen:
            with patch("time.sleep"):
                response = client.post(
                    "/execute",
                    data=json.dumps({
                        "action": "open_app",
                        "target": "notepad",
                        "user": "test",
                    }),
                    content_type="application/json",
                )

                assert response.status_code == 200
                data = json.loads(response.data)
                assert data["success"] is True
                assert data["app"] == "notepad"


class TestTypeAction:
    """Test type action."""

    def test_type_text(self, client):
        """type action should press escape then write."""
        with patch("pyautogui.press") as mock_press:
            with patch("pyautogui.write") as mock_write:
                with patch("time.sleep"):
                    response = client.post(
                        "/execute",
                        data=json.dumps({
                            "action": "type",
                            "value": "hello world",
                            "user": "test",
                        }),
                        content_type="application/json",
                    )

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data["success"] is True
                    assert data["text_length"] == 11

                    mock_press.assert_called_with("escape")
                    mock_write.assert_called_once()


class TestPressKeyAction:
    """Test press_key action."""

    def test_press_single_key(self, client):
        """press_key single key."""
        with patch("pyautogui.hotkey") as mock_hotkey:
            response = client.post(
                "/execute",
                data=json.dumps({
                    "action": "press_key",
                    "value": "enter",
                    "user": "test",
                }),
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            mock_hotkey.assert_called_once_with("enter")

    def test_press_hotkey_combination(self, client):
        """press_key hotkey combination."""
        with patch("pyautogui.hotkey") as mock_hotkey:
            response = client.post(
                "/execute",
                data=json.dumps({
                    "action": "press_key",
                    "value": "ctrl+a",
                    "user": "test",
                }),
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            mock_hotkey.assert_called_once_with("ctrl", "a")


class TestClickAction:
    """Test click action."""

    def test_click_coordinates(self, client):
        """click action should parse coords and click."""
        with patch("pyautogui.click") as mock_click:
            response = client.post(
                "/execute",
                data=json.dumps({
                    "action": "click",
                    "value": "100,200",
                    "user": "test",
                }),
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["x"] == 100
            assert data["y"] == 200
            mock_click.assert_called_once_with(100, 200)

    def test_click_invalid_coords(self, client):
        """click with invalid coords should fail."""
        response = client.post(
            "/execute",
            data=json.dumps({
                "action": "click",
                "value": "invalid",
                "user": "test",
            }),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False


class TestAuditLogging:
    """Test that actions are logged to audit."""

    def test_audit_logs_successful_action(self, client, mock_audit):
        """Successful action should be logged."""
        with patch("time.sleep"):
            client.post(
                "/execute",
                data=json.dumps({
                    "action": "wait",
                    "value": "0.1",
                    "user": "testuser",
                    "channel": "api",
                }),
                content_type="application/json",
            )

            mock_audit.log.assert_called()
            log_call = mock_audit.log.call_args
            assert log_call[1]["user_id"] == "testuser"
            assert log_call[1]["action"] == "wait"

    def test_audit_logs_failed_action(self, client, mock_gateway, mock_audit):
        """Failed action should be logged."""
        mock_gateway.run_command.side_effect = PermissionError("Denied")

        client.post(
            "/execute",
            data=json.dumps({
                "action": "click",
                "value": "100,200",
                "user": "restricted",
            }),
            content_type="application/json",
        )

        # Should have logged the denied action
        log_calls = [c for c in mock_audit.log.call_args_list if not c[1]["allowed"]]
        assert len(log_calls) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
