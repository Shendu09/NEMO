"""Tests for action_classifier.py and /confirm endpoint."""

import json
import time
from pathlib import Path
import pytest
from unittest import mock

from core.security.action_classifier import (
    ActionClassifier,
    RiskLevel,
    classify,
)


class TestActionClassifier:
    """Test ActionClassifier risk levels."""

    def test_screenshot_is_low_risk(self):
        """Screenshot should be LOW risk."""
        result = classify("screenshot")
        assert result.risk_level == RiskLevel.LOW
        assert not result.requires_confirmation

    def test_wait_is_low_risk(self):
        """Wait should be LOW risk."""
        result = classify("wait", value="5")
        assert result.risk_level == RiskLevel.LOW
        assert not result.requires_confirmation

    def test_open_chrome_is_low_risk(self):
        """Opening Chrome should be LOW risk."""
        result = classify("open_app", target="chrome")
        assert result.risk_level == RiskLevel.LOW
        assert not result.requires_confirmation

    def test_open_firefox_is_low_risk(self):
        """Opening Firefox should be LOW risk."""
        result = classify("open_app", target="firefox")
        assert result.risk_level == RiskLevel.LOW
        assert not result.requires_confirmation

    def test_open_powershell_is_high_risk(self):
        """Opening PowerShell should be HIGH risk."""
        result = classify("open_app", target="powershell")
        assert result.risk_level == RiskLevel.HIGH
        assert result.requires_confirmation

    def test_open_cmd_is_high_risk(self):
        """Opening CMD should be HIGH risk."""
        result = classify("open_app", target="cmd.exe")
        assert result.risk_level == RiskLevel.HIGH
        assert result.requires_confirmation

    def test_type_normal_text_is_low_risk(self):
        """Typing normal text should be LOW risk."""
        result = classify("type", value="hello world")
        assert result.risk_level == RiskLevel.LOW
        assert not result.requires_confirmation

    def test_type_long_text_is_medium_risk(self):
        """Typing very long text should be MEDIUM risk."""
        long_text = "x" * 300
        result = classify("type", value=long_text)
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.requires_confirmation

    def test_type_with_password_keyword_is_medium_risk(self):
        """Typing text with 'password' should be MEDIUM risk."""
        result = classify("type", value="password admin123")
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.requires_confirmation

    def test_press_enter_is_low_risk(self):
        """Pressing Enter should be LOW risk."""
        result = classify("press_key", value="enter")
        assert result.risk_level == RiskLevel.LOW
        assert not result.requires_confirmation

    def test_press_escape_is_low_risk(self):
        """Pressing Escape should be LOW risk."""
        result = classify("press_key", value="escape")
        assert result.risk_level == RiskLevel.LOW
        assert not result.requires_confirmation

    def test_press_alt_f4_is_medium_risk(self):
        """Pressing Alt+F4 should be MEDIUM risk."""
        result = classify("press_key", value="alt+f4")
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.requires_confirmation

    def test_press_ctrl_alt_delete_is_medium_risk(self):
        """Pressing Ctrl+Alt+Delete should be MEDIUM risk."""
        result = classify("press_key", value="ctrl+alt+delete")
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.requires_confirmation

    def test_click_is_medium_risk(self):
        """Clicking on coordinates should be MEDIUM risk."""
        result = classify("click", target="100,200")
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.requires_confirmation

    def test_open_app_with_delete_keyword_is_high_risk(self):
        """Opening app with 'delete' in name should be HIGH risk."""
        result = classify("open_app", target="file_delete_tool.exe")
        assert result.risk_level == RiskLevel.HIGH
        assert result.requires_confirmation

    def test_open_app_with_system32_path_is_high_risk(self):
        """Opening app from system32 should be HIGH risk."""
        result = classify("open_app", target="C:\\Windows\\System32\\cmd.exe")
        assert result.risk_level == RiskLevel.HIGH
        assert result.requires_confirmation

    def test_unknown_action_is_medium_risk(self):
        """Unknown action should be MEDIUM risk."""
        result = classify("unknown_action", target="unknown")
        assert result.risk_level == RiskLevel.MEDIUM
        assert result.requires_confirmation


class TestConfirmEndpoint:
    """Test /confirm endpoint."""

    @pytest.fixture
    def client(self):
        """Flask test client."""
        from bridge.nemo_server import app
        from core.security.gateway_v2 import SecurityGateway
        from core.security.audit_logger_v2 import AuditLogger
        from bridge import nemo_server

        # Set up dependencies
        nemo_server._gateway = SecurityGateway()
        nemo_server._audit_logger = AuditLogger(Path("./test_audit.jsonl"))

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_confirm_requires_token(self, client):
        """POST /confirm without token should fail."""
        resp = client.post("/confirm", json={"approved": True})
        data = resp.get_json()
        assert data["success"] is False
        assert "token" in data["error"].lower()

    def test_confirm_invalid_token(self, client):
        """POST /confirm with invalid token should fail."""
        resp = client.post("/confirm", json={
            "token": "invalid-token",
            "approved": True,
        })
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False

    def test_confirm_denied_logs_audit(self, client):
        """User denying action should be logged."""
        # First, request a HIGH-risk action to get a token
        resp = client.post("/execute", json={
            "action": "open_app",
            "target": "powershell",
            "user": "test_user",
        })
        assert resp.status_code == 202
        token = resp.get_json()["confirmation_token"]

        # Deny it
        resp = client.post("/confirm", json={
            "token": token,
            "approved": False,
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False
        assert "denied" in data["error"].lower()

    def test_confirm_approved_executes_action(self, client):
        """User approving action should execute it."""
        with mock.patch("bridge.nemo_server._execute_action") as mock_exec:
            mock_exec.return_value = {"success": True, "action": "open_app", "app": "powershell"}

            # Request HIGH-risk action
            resp = client.post("/execute", json={
                "action": "open_app",
                "target": "powershell",
                "user": "test_user",
            })
            token = resp.get_json()["confirmation_token"]

            # Approve it
            resp = client.post("/confirm", json={
                "token": token,
                "approved": True,
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            mock_exec.assert_called_once()

    def test_confirm_expires_after_60_seconds(self, client):
        """Token should expire after 60 seconds."""
        from bridge import nemo_server

        # Request HIGH-risk action
        resp = client.post("/execute", json={
            "action": "open_app",
            "target": "powershell",
            "user": "test_user",
        })
        token = resp.get_json()["confirmation_token"]

        # Manually set timestamp to 70 seconds ago
        with nemo_server._pending_lock:
            nemo_server._pending_actions[token]["timestamp"] = time.time() - 70

        # Try to confirm
        resp = client.post("/confirm", json={
            "token": token,
            "approved": True,
        })
        assert resp.status_code == 410
        data = resp.get_json()
        assert "expired" in data["error"].lower()


class TestExecuteWithClassifier:
    """Test /execute endpoint with action classifier."""

    @pytest.fixture
    def client(self):
        """Flask test client."""
        from bridge.nemo_server import app
        from core.security.gateway_v2 import SecurityGateway
        from core.security.audit_logger_v2 import AuditLogger
        from bridge import nemo_server
        from pathlib import Path

        # Set up dependencies
        nemo_server._gateway = SecurityGateway()
        nemo_server._audit_logger = AuditLogger(Path("./test_audit.jsonl"))

        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_low_risk_action_executes_immediately(self, client):
        """LOW-risk actions should execute immediately."""
        with mock.patch("bridge.nemo_server._execute_action") as mock_exec:
            mock_exec.return_value = {"success": True, "action": "wait", "seconds": 1.0}

            resp = client.post("/execute", json={
                "action": "wait",
                "value": "1",
                "user": "test_user",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            mock_exec.assert_called_once()

    def test_medium_risk_action_executes_immediately(self, client):
        """MEDIUM-risk actions should execute immediately."""
        with mock.patch("bridge.nemo_server._execute_action") as mock_exec:
            mock_exec.return_value = {"success": True, "action": "click", "x": 100, "y": 200}

            resp = client.post("/execute", json={
                "action": "click",
                "target": "100,200",
                "user": "test_user",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["success"] is True
            mock_exec.assert_called_once()

    def test_high_risk_action_requires_confirmation(self, client):
        """HIGH-risk actions should require confirmation."""
        resp = client.post("/execute", json={
            "action": "open_app",
            "target": "powershell",
            "user": "test_user",
        })
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["success"] is False
        assert data["requires_confirmation"] is True
        assert data["confirmation_token"]
        assert data["risk_level"] == "HIGH"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
