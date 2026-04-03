#!/usr/bin/env python3
"""
Test NEMO Task Assignment: Send WhatsApp message with vision verification.

This demonstrates:
1. Starting the NEMO HTTP server
2. Assigning a task (WhatsApp automation)
3. Getting results with before/after screenshots and verification
"""

import json
import time
import requests
import subprocess
import threading
import sys
from pathlib import Path

BASE_URL = "http://localhost:8765"
VISION_API_URL = "http://localhost:5000"

# Task: Send WhatsApp message to Rohitha DG
WHATSAPP_TASK = {
    "actions": [
        {
            "action": "open_app",
            "target": "whatsapp",
            "value": "",
            "verify_instruction": "WhatsApp window should be visible on screen"
        },
        {
            "action": "press_key",
            "target": "",
            "value": "ctrl+f",
            "verify_instruction": "Search dialog should appear with input field"
        },
        {
            "action": "type",
            "target": "",
            "value": "Rohitha DG",
            "verify_instruction": "Contact name 'Rohitha DG' should be typed in search field"
        },
        {
            "action": "press_key",
            "target": "",
            "value": "enter",
            "verify_instruction": "Contact 'Rohitha DG' should be selected or opened"
        },
        {
            "action": "type",
            "target": "",
            "value": "hi",
            "verify_instruction": "Text 'hi' should appear in message input field"
        },
        {
            "action": "press_key",
            "target": "",
            "value": "ctrl+enter",
            "verify_instruction": "Message should be sent (chat view should refresh or confirmation visible)"
        }
    ],
    "user": "demo",
    "channel": "test_automation",
    "max_retries": 1,
    "vision_api_url": VISION_API_URL
}


def start_server():
    """Start the NEMO HTTP server in background."""
    print("\n" + "=" * 80)
    print("🚀 STARTING NEMO SERVER")
    print("=" * 80)
    
    try:
        # Import server code
        from bridge.nemo_server import start_server as run_server
        from core.security.gateway_v2 import SecurityGateway
        from core.security.audit_logger_v2 import AuditLogger
        from pathlib import Path
        
        # Initialize gateway and logger
        gateway = SecurityGateway(dry_run=False)
        log_path = Path("clevrr_data/audit.jsonl")
        audit_logger = AuditLogger(log_path=log_path)
        
        # Start server in background thread
        def run_in_thread():
            try:
                run_server(gateway, audit_logger, host="127.0.0.1", port=8765)
            except Exception as e:
                print(f"❌ Server error: {e}")
        
        server_thread = threading.Thread(target=run_in_thread, daemon=True)
        server_thread.start()
        
        # Wait for server to be ready
        print("⏳ Waiting for server to start...")
        for attempt in range(10):
            try:
                resp = requests.get(f"{BASE_URL}/health", timeout=2)
                if resp.status_code == 200:
                    print("✅ Server is ready!")
                    return True
            except:
                time.sleep(0.5)
        
        print("⚠️ Server might be ready, continuing anyway...")
        time.sleep(2)
        return True
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        print("\nTip: Make sure you're in the NEMO project directory")
        print("Tip: Make sure core/security/gateway_v2.py and audit_logger_v2.py exist")
        import traceback
        traceback.print_exc()
        return False


def assign_task(task_config):
    """Assign a task to NEMO and get results."""
    print("\n" + "=" * 80)
    print("📋 ASSIGNING TASK: WhatsApp Message to Rohitha DG")
    print("=" * 80)
    
    print("\nTask details:")
    print(f"  Actions: {len(task_config['actions'])}")
    for i, action in enumerate(task_config['actions'], 1):
        print(f"    {i}. {action['action']}: {action.get('value', action.get('target', ''))}")
    
    print("\nVerification instructions:")
    for i, action in enumerate(task_config['actions'], 1):
        if action.get('verify_instruction'):
            print(f"    Step {i}: {action['verify_instruction']}")
    
    print("\n" + "-" * 80)
    print("📤 Sending to NEMO server...")
    print("-" * 80)
    
    try:
        # Send task to server
        response = requests.post(
            f"{BASE_URL}/execute_with_vision",
            json=task_config,
            timeout=60
        )
        
        result = response.json()
        
        print(f"\n✅ Response received (status: {response.status_code})")
        print(f"   Success: {result.get('success')}")
        print(f"   Actions executed: {result.get('executed')}/{result.get('total_actions')}")
        print(f"   Verifications passed: {result.get('verifications_passed')}")
        print(f"   Duration: {result.get('duration_seconds')}s")
        
        # Show step-by-step results
        print("\n" + "=" * 80)
        print("📊 STEP-BY-STEP RESULTS")
        print("=" * 80)
        
        for i, step in enumerate(result.get('steps', []), 1):
            status_emoji = "✅" if step.get('status') == 'verified' else "⚠️" if step.get('status') == 'executed' else "❌"
            print(f"\n{status_emoji} Step {i}: {step.get('action').upper()}")
            print(f"   Status: {step.get('status')}")
            print(f"   Verified: {step.get('verified')}")
            
            if step.get('value'):
                print(f"   Value: {step.get('value')}")
            
            if step.get('vision_analysis'):
                print(f"   Vision Analysis: {step.get('vision_analysis')}")
            
            if step.get('error'):
                print(f"   Error: {step.get('error')}")
            
            print(f"   Confidence: {step.get('confidence', 0.0):.0%}")
            print(f"   Timestamp: {step.get('timestamp')}")
        
        # Show warnings if any
        if result.get('warnings'):
            print("\n" + "=" * 80)
            print("⚠️  WARNINGS")
            print("=" * 80)
            for warning in result.get('warnings'):
                print(f"  • {warning}")
        
        # Show final summary
        print("\n" + "=" * 80)
        print("📈 FINAL SUMMARY")
        print("=" * 80)
        print(f"Overall Status: {'✅ SUCCESS' if result.get('success') else '❌ FAILED'}")
        print(f"Actions Completed: {result.get('executed')}/{result.get('total_actions')}")
        print(f"Verifications: {result.get('verifications_passed')} passed, {result.get('all_verified')} verified")
        print(f"Duration: {result.get('duration_seconds', 0.0):.2f} seconds")
        
        # Print full JSON if verbose
        if "--verbose" in sys.argv:
            print("\n" + "=" * 80)
            print("📄 RAW RESPONSE (JSON)")
            print("=" * 80)
            print(json.dumps(result, indent=2))
        
        return result
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to NEMO server at {BASE_URL}")
        print("   Make sure the server is running: python -m bridge.nemo_server")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ Request timeout - task may still be executing")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run the test."""
    print("\n" + "=" * 80)
    print("🎯 NEMO TASK ASSIGNMENT TEST")
    print("=" * 80)
    print(f"Target: Send WhatsApp message to Rohitha DG with 'hi'")
    print(f"Vision API: {VISION_API_URL}")
    print(f"Server: {BASE_URL}")
    
    # Start server
    if not start_server():
        print("\n❌ Could not start server. Exiting.")
        return
    
    # Assign task
    result = assign_task(WHATSAPP_TASK)
    
    if result and result.get('success'):
        print("\n" + "=" * 80)
        print("🎉 TASK COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("✅ WhatsApp message was sent to Rohitha DG")
    else:
        print("\n" + "=" * 80)
        print("⚠️  TASK COMPLETED WITH ISSUES")
        print("=" * 80)
        print("Check the step-by-step results above for details")
    
    print("\nUsage tips:")
    print("  • Run with --verbose to see full JSON response")
    print("  • Check /dashboard to see audit log: http://localhost:8765/dashboard")
    print("  • Start vision API for full verification: python -m openclaw ...")


if __name__ == "__main__":
    main()
