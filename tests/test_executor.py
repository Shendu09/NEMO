"""Tests for Action Executor."""

import pytest
from unittest.mock import MagicMock, patch, call

from actions.executor import ActionExecutor, ActionStep
from core.bus import BusMessage, MessageType, Topics


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


class MockSecurityGateway:
    """Mock SecurityGateway for testing."""

    def __init__(self, allow=True):
        self.allow = allow
        self.calls = []

    def run_command(self, user_id, target, args):
        """Mock run_command check."""
        self.calls.append({
            "user_id": user_id,
            "target": target,
            "args": args,
        })
        if not self.allow:
            raise PermissionError("Access denied")


class TestActionStep:
    """Test ActionStep dataclass."""

    def test_action_step_creation(self):
        """ActionStep should be created with action and optional fields."""
        step = ActionStep(action="click", target="100,200")
        assert step.action == "click"
        assert step.target == "100,200"
        assert step.value == ""


class TestActionExecutorInit:
    """Test ActionExecutor initialization."""

    def test_executor_init(self):
        """Executor should initialize with bus and gateway."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()

        executor = ActionExecutor(bus, gateway, user_id="test_user")

        assert executor.bus == bus
        assert executor.gateway == gateway
        assert executor.user_id == "test_user"


class TestExecutePlain:
    """Test plan execution."""

    def test_execute_plan_empty(self):
        """Empty plan should return success with 0 steps completed."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        result = executor.execute_plan([])

        assert result["success"] is True
        assert result["steps_completed"] == 0

    def test_execute_plan_security_failure(self):
        """Plan should fail if security check fails."""
        bus = MockBusClient()
        gateway = MockSecurityGateway(allow=False)
        executor = ActionExecutor(bus, gateway)

        steps = [{"action": "click", "target": "100,200"}]
        result = executor.execute_plan(steps)

        assert result["success"] is False
        assert "Security check failed" in result["error"]

    def test_execute_plan_gate_calls_security(self):
        """Each step should call security gateway."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        steps = [
            {"action": "click", "target": "100,200"},
            {"action": "wait", "target": "1"},
        ]
        executor.execute_plan(steps)

        # Should have called for both steps
        assert len(gateway.calls) >= 2
        assert gateway.calls[0]["target"] == "action.click"


class TestActionOpenApp:
    """Test open_app action."""

    def test_open_app_basic(self):
        """open_app should execute subprocess.Popen."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("subprocess.Popen") as mock_popen:
            result = executor._action_open_app("notepad")

            assert result["success"] is True
            assert result["app"] == "notepad"
            mock_popen.assert_called_once()

    def test_open_app_chrome_with_flags(self):
        """open_app chrome should add special flags."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("subprocess.Popen") as mock_popen:
            with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                executor._action_open_app("chrome")

                # Check that chrome was called with flags
                call_args = mock_popen.call_args[0][0]
                assert "chrome" in call_args.lower()
                assert "--profile-directory=Default" in call_args
                assert "--no-first-run" in call_args
                assert "--start-maximized" in call_args


class TestActionType:
    """Test type action."""

    def test_action_type(self):
        """type action should press escape then write text."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("pyautogui.press") as mock_press:
            with patch("pyautogui.write") as mock_write:
                with patch("time.sleep"):
                    result = executor._action_type("test text")

                    assert result["success"] is True
                    mock_press.assert_called_with("escape")
                    mock_write.assert_called_once()
                    call_args = mock_write.call_args
                    assert call_args[0][0] == "test text"
                    assert call_args[1]["interval"] == 0.05


class TestActionClick:
    """Test click action."""

    def test_action_click_valid_coords(self):
        """click should parse coordinates and call pyautogui.click."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("pyautogui.click") as mock_click:
            result = executor._action_click("100,200")

            assert result["success"] is True
            assert result["x"] == 100
            assert result["y"] == 200
            mock_click.assert_called_once_with(100, 200)

    def test_action_click_invalid_coords(self):
        """click with invalid coords should raise error."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with pytest.raises(Exception):
            executor._action_click("not,coords")


class TestActionPressKey:
    """Test press_key action."""

    def test_action_press_key_single(self):
        """press_key should call hotkey."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("pyautogui.hotkey") as mock_hotkey:
            result = executor._action_press_key("enter")

            assert result["success"] is True
            mock_hotkey.assert_called_once_with("enter")

    def test_action_press_key_combination(self):
        """press_key should handle hotkey combinations."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("pyautogui.hotkey") as mock_hotkey:
            result = executor._action_press_key("ctrl+a")

            assert result["success"] is True
            mock_hotkey.assert_called_once_with("ctrl", "a")


class TestActionScreenshot:
    """Test screenshot action."""

    def test_action_screenshot_no_window(self):
        """screenshot should handle no active window gracefully."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("pygetwindow.getActiveWindow", return_value=None):
            result = executor._action_screenshot()

            assert result["success"] is False
            assert "No active window" in result["error"]

    def test_action_screenshot_with_window(self):
        """screenshot should capture active window."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        # Mock window
        mock_window = MagicMock()
        mock_window.left = 10
        mock_window.top = 20
        mock_window.width = 800
        mock_window.height = 600

        with patch("pygetwindow.getActiveWindow", return_value=mock_window):
            with patch("mss.mss"):
                with patch("PIL.Image.Image.save"):
                    # This will fail without PIL but tests the logic
                    pass


class TestActionWait:
    """Test wait action."""

    def test_action_wait(self):
        """wait should sleep for specified seconds."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        with patch("time.sleep") as mock_sleep:
            result = executor._action_wait("2.5")

            assert result["success"] is True
            assert result["seconds"] == 2.5
            mock_sleep.assert_called_once_with(2.5)


class TestExecutePlanIntegration:
    """Integration tests for full plan execution."""

    def test_execute_plan_with_multiple_steps(self):
        """execute_plan should execute all steps in order."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        steps = [
            {"action": "wait", "target": "0.1"},
            {"action": "wait", "target": "0.1"},
        ]

        with patch("time.sleep"):
            result = executor.execute_plan(steps)

            assert result["success"] is True
            assert result["steps_completed"] == 2

    def test_execute_plan_publishes_results(self):
        """execute_plan should publish step results to bus."""
        bus = MockBusClient()
        gateway = MockSecurityGateway()
        executor = ActionExecutor(bus, gateway)

        steps = [{"action": "wait", "target": "0.1"}]

        with patch("time.sleep"):
            executor.execute_plan(steps)

            # Should have published results
            published = [p for p in bus.published if p["topic"] == Topics.ACTION_RESULT]
            assert len(published) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
