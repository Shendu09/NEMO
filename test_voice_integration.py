"""
Test Voice Integration Pipeline

Tests the complete voice command processing pipeline:
1. Voice command → Ollama llama3 action generation
2. Action step execution
3. Result verification and screenshot capture

Run with: python test_voice_integration.py
"""

import json
import requests
import time
from typing import Optional

# Configuration
NEMO_API_URL = "http://localhost:8765"
TASK_ENDPOINT = f"{NEMO_API_URL}/task"
SCREENSHOT_ENDPOINT = f"{NEMO_API_URL}/screenshot"

# Test commands
TEST_COMMANDS = [
    {
        "name": "Basic screenshot",
        "command": "take a screenshot",
        "expected_actions": ["screenshot"],
    },
    {
        "name": "Open app",
        "command": "open notepad",
        "expected_actions": ["open_app"],
    },
    {
        "name": "Type and sleep",
        "command": "type hello and wait 2 seconds",
        "expected_actions": ["type", "wait"],
    },
    {
        "name": "Browser search",
        "command": "search for python on the web",
        "expected_actions": ["search"],
    },
    {
        "name": "Play video",
        "command": "play cat videos on youtube",
        "expected_actions": ["play"],
    },
]


def test_nemo_health() -> bool:
    """Check if NEMO server is running."""
    print("\n[1/5] Checking NEMO server health...")
    try:
        response = requests.get(f"{NEMO_API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ NEMO server is running")
            return True
        else:
            print(f"✗ NEMO server returned {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ NEMO server not accessible: {e}")
        return False


def test_task_endpoint(command: str) -> Optional[dict]:
    """Test the /task endpoint with a command."""
    print(f"\n[2/5] Testing /task endpoint with: '{command}'")
    try:
        payload = {
            "command": command,
            "user": "test",
            "channel": "voice",
        }
        print(f"  Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(TASK_ENDPOINT, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Task endpoint responded successfully")
            print(f"  Status: {result.get('success')}")
            print(f"  Steps completed: {result.get('steps_completed')}/{result.get('total_steps')}")
            print(f"  Message: {result.get('message')}")
            
            # Print action details
            actions = result.get('actions', [])
            for action in actions:
                status_icon = "✓" if action.get('status') == 'success' else "✗"
                print(f"  {status_icon} Step {action.get('step')}: {action.get('action')}")
                if action.get('error'):
                    print(f"      Error: {action.get('error')}")
            
            return result
        else:
            print(f"✗ Task endpoint returned {response.status_code}")
            print(f"  Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("✗ Task endpoint timed out (Ollama may be slow)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"✗ Task endpoint error: {e}")
        return None


def test_action_execution(result: dict) -> bool:
    """Verify that actions were executed."""
    print("\n[3/5] Verifying action execution...")
    
    if not result:
        print("✗ No result to verify")
        return False
    
    steps = result.get('steps_completed', 0)
    total = result.get('total_steps', 0)
    
    if steps == total and total > 0:
        print(f"✓ All {steps} steps executed successfully")
        return True
    elif steps > 0:
        print(f"⚠ Partial completion: {steps}/{total} steps executed")
        return True
    else:
        print(f"✗ No steps executed")
        return False


def test_screenshot_capture(result: dict) -> bool:
    """Verify that screenshot was captured."""
    print("\n[4/5] Verifying screenshot capture...")
    
    if not result:
        print("✗ No result to verify")
        return False
    
    screenshot = result.get('screenshot', '')
    if screenshot and len(screenshot) > 100:  # base64 strings are fairly long
        print(f"✓ Screenshot captured ({len(screenshot)} bytes)")
        return True
    else:
        print("✗ No screenshot captured")
        return False


def test_voice_module() -> bool:
    """Test if voice module can be imported and initialized."""
    print("\n[5/5] Testing voice module availability...")
    try:
        from core.voice import wake_listener
        print("✓ Voice module imported successfully")
        
        # Check if functions exist
        assert hasattr(wake_listener, 'listen_for_wake_word'), "Missing listen_for_wake_word"
        assert hasattr(wake_listener, 'start'), "Missing start function"
        print("✓ Voice module has required functions")
        return True
        
    except ImportError as e:
        print(f"⚠ Voice module not available (optional): {e}")
        return False
    except AssertionError as e:
        print(f"✗ Voice module incomplete: {e}")
        return False


def run_full_integration_test():
    """Run comprehensive voice integration test."""
    print("="*60)
    print("NEMO Voice Integration Test Suite")
    print("="*60)
    
    # Test 1: Server health
    if not test_nemo_health():
        print("\n✗ NEMO server is not running. Start it with:")
        print("  python clevrr_service.py run")
        return False
    
    # Test 2: Voice module
    test_voice_module()
    
    # Test 3-6: Task endpoint with different commands
    print("\n" + "="*60)
    print("Testing Task Endpoint with Various Commands")
    print("="*60)
    
    test_results = []
    
    # Run a simple test command (screenshot) first
    print("\n[TEST 1] Simple command (screenshot)")
    result = test_task_endpoint("take a screenshot")
    if result:
        test_action_execution(result)
        test_screenshot_capture(result)
        test_results.append(("screenshot", result.get('success', False)))
    
    # Optional: Test additional commands if desired
    # Uncomment to test more complex scenarios
    # print("\n[TEST 2] Open notepad")
    # result = test_task_endpoint("open notepad")
    # if result:
    #     test_action_execution(result)
    #     test_results.append(("open_app", result.get('success', False)))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    if test_results:
        passed = sum(1 for _, success in test_results if success)
        total = len(test_results)
        print(f"Passed: {passed}/{total}")
        
        for command, success in test_results:
            status = "✓" if success else "✗"
            print(f"  {status} {command}")
    
    print("\n✓ Voice integration test complete")
    print("\nTo test voice input:")
    print("  1. Run: python clevrr_service.py run")
    print("  2. Say wake word 'V' or 'BE' followed by command")
    print("  3. Check logs for voice processing")


if __name__ == "__main__":
    run_full_integration_test()
