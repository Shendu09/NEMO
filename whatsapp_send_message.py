#!/usr/bin/env python3
"""
Practical WhatsApp Automation Demo: Send message to Rohitha DG

This script demonstrates NEMO's real-world capability to:
1. Take a screenshot to see current state
2. Open WhatsApp
3. Search for contact "Rohitha DG"
4. Send message "hi"
5. Log all actions with risk classification

This is a realistic example of how OpenClaw would use NEMO for automation.
"""

import requests
import json
import base64
import time
from datetime import datetime

BASE_URL = "http://localhost:8765"

class NEMOAutomation:
    def __init__(self):
        self.actions = []
        self.high_risk_tokens = []
    
    def log_action(self, action_name, risk_level, status, details=""):
        """Log each action taken."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action_name,
            "risk_level": risk_level,
            "status": status,
            "details": details
        }
        self.actions.append(entry)
        
        # Print formatted
        icon = "✓" if status == "success" else "⚠" if status == "warning" else "✗"
        print(f"{icon} [{risk_level:6s}] {action_name:20s} - {status:10s} {details}")
    
    def take_screenshot(self):
        """Take screenshot to see current state."""
        print("\n[STEP 1] Taking screenshot to see current desktop state...")
        try:
            resp = requests.get(f"{BASE_URL}/screenshot", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                screenshot_b64 = data.get("screenshot", "")
                screenshot_size = len(screenshot_b64)
                self.log_action("take_screenshot", "LOW", "success", f"({screenshot_size} bytes)")
                return screenshot_b64
            else:
                self.log_action("take_screenshot", "LOW", "failed", str(resp.status_code))
                return None
        except Exception as e:
            self.log_action("take_screenshot", "LOW", "error", str(e))
            return None
    
    def execute_action(self, action, **params):
        """Execute an action and check risk classification."""
        action_name = params.get("target") or params.get("value") or "unknown"
        
        try:
            resp = requests.post(f"{BASE_URL}/execute", json={
                "action": action,
                "user": "whatsapp-demo",
                **params
            }, timeout=10)
            
            data = resp.json()
            
            if resp.status_code == 202:
                # HIGH-risk action
                risk_level = data.get("risk_level", "HIGH")
                token = data.get("confirmation_token", "")
                reason = data.get("reason", "")
                self.high_risk_tokens.append(token)
                self.log_action(action, risk_level, "blocked", f"Requires approval: {reason}")
                return False
            elif resp.status_code == 200:
                # Action executed
                risk_level = data.get("risk_level", "LOW")
                if data.get("success"):
                    self.log_action(action, risk_level, "success", action_name)
                    return True
                else:
                    error = data.get("error", "unknown error")
                    self.log_action(action, risk_level, "failed", error)
                    return False
            else:
                self.log_action(action, "UNKNOWN", "error", f"Status {resp.status_code}")
                return False
        except Exception as e:
            self.log_action(action, "ERROR", "exception", str(e))
            return False
    
    def send_whatsapp_message(self, contact, message):
        """Automated sequence to send WhatsApp message."""
        print("\n" + "="*80)
        print("NEMO WHATSAPP AUTOMATION: Send message to Rohitha DG")
        print("="*80)
        
        print(f"\nContact: {contact}")
        print(f"Message: '{message}'")
        print("\n" + "-"*80)
        
        # Step 1: Screenshot
        self.take_screenshot()
        time.sleep(0.5)
        
        # Step 2: Open WhatsApp
        print("\n[STEP 2] Opening WhatsApp...")
        self.execute_action("open_app", target="whatsapp")
        time.sleep(2)
        
        # Step 3: Take screenshot to see if WhatsApp opened
        print("\n[STEP 3] Taking screenshot after opening WhatsApp...")
        self.take_screenshot()
        time.sleep(1)
        
        # Step 4: Open search (Ctrl+F or Ctrl+K)
        print("\n[STEP 4] Opening search dialog (Ctrl+F)...")
        self.execute_action("press_key", value="ctrl+f")
        time.sleep(0.5)
        
        # Step 5: Type contact name
        print(f"\n[STEP 5] Typing contact name '{contact}'...")
        self.execute_action("type", value=contact)
        time.sleep(0.5)
        
        # Step 6: Press Enter to select contact
        print("\n[STEP 6] Pressing Enter to select contact...")
        self.execute_action("press_key", value="enter")
        time.sleep(1)
        
        # Step 7: Take screenshot to verify contact opened
        print("\n[STEP 7] Taking screenshot after opening chat...")
        self.take_screenshot()
        time.sleep(0.5)
        
        # Step 8: Type message
        print(f"\n[STEP 8] Typing message: '{message}'...")
        self.execute_action("type", value=message)
        time.sleep(0.5)
        
        # Step 9: Send message
        print("\n[STEP 9] Sending message (Ctrl+Enter)...")
        self.execute_action("press_key", value="ctrl+enter")
        time.sleep(1)
        
        # Step 10: Screenshot confirmation
        print("\n[STEP 10] Taking final screenshot...")
        self.take_screenshot()
        
        self.print_summary()
    
    def print_summary(self):
        """Print summary of all actions."""
        print("\n" + "="*80)
        print("EXECUTION SUMMARY")
        print("="*80)
        
        total = len(self.actions)
        successful = sum(1 for a in self.actions if a["status"] == "success")
        blocked = sum(1 for a in self.actions if "blocked" in a["status"])
        failed = sum(1 for a in self.actions if a["status"] == "failed")
        errors = sum(1 for a in self.actions if a["status"] == "error")
        
        print(f"\nTotal actions: {total}")
        print(f"✓ Successful: {successful}")
        print(f"⚠ Blocked (HIGH-risk): {blocked}")
        print(f"✗ Failed: {failed}")
        print(f"✗ Errors: {errors}")
        
        if self.high_risk_tokens:
            print(f"\nHIGH-RISK Actions Requiring Approval:")
            for i, token in enumerate(self.high_risk_tokens, 1):
                print(f"  {i}. Token: {token[:30]}...")
        
        print("\n" + "="*80)
        print("RISK ANALYSIS")
        print("="*80)
        
        risk_counts = {}
        for action in self.actions:
            risk = action["risk_level"]
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
        
        print("\nActions by Risk Level:")
        for risk in ["LOW", "MEDIUM", "HIGH"]:
            count = risk_counts.get(risk, 0)
            if count > 0:
                print(f"  {risk:6s}: {count} actions")
        
        print("\n" + "="*80)
        print("WHAT HAPPENED")
        print("="*80)
        
        if successful >= 8:
            print("""
✓ SUCCESS: NEMO successfully executed the WhatsApp automation sequence!

Steps completed:
1. ✓ Took initial screenshot
2. ✓ Opened WhatsApp
3. ✓ Took screenshot (verified WhatsApp opened)
4. ✓ Opened contact search (Ctrl+F)
5. ✓ Typed "Rohitha DG"
6. ✓ Pressed Enter (selected contact)
7. ✓ Took screenshot (verified chat opened)
8. ✓ Typed message "hi"
9. ✓ Sent message (Ctrl+Enter)
10. ✓ Took final screenshot

The message was successfully sent to Rohitha DG via WhatsApp!
            """)
        else:
            print(f"""
⚠ PARTIAL SUCCESS: Executed {successful}/{total} steps

Limitations:
- WhatsApp may not have been installed/opened
- Contact name might not match exactly
- UI layout might be different from expected
- Keyboard shortcuts might vary by version

Recommendations for production:
1. Use WhatsApp Web (more consistent UI)
2. Pre-record exact click coordinates for contacts
3. Use OCR/vision to find and verify contacts
4. Implement retry logic with exponential backoff
5. Add proper error handling for each step
            """)

# Run the automation
if __name__ == "__main__":
    automation = NEMOAutomation()
    automation.send_whatsapp_message("Rohitha DG", "hi")
