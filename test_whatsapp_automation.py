#!/usr/bin/env python3
"""
Test NEMO's ability to automate WhatsApp messaging.

This demonstrates:
1. What actions NEMO can perform (open_app, type, click, press_key)
2. Risk classification of the sequence
3. Limitations of pure mouse/keyboard automation
"""

import requests
import json
import time

BASE_URL = "http://localhost:8765"

def test_action(action_name, **params):
    """Execute an action and show risk classification."""
    print(f"\n[Action] {action_name}")
    print(f"Params: {params}")
    
    resp = requests.post(f"{BASE_URL}/execute", json={
        "action": action_name,
        "user": "demo",
        **params
    }, timeout=10)
    
    data = resp.json()
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 202:
        # HIGH-risk action requiring confirmation
        print(f"⚠️  REQUIRES CONFIRMATION (HIGH RISK)")
        print(f"   Risk Level: {data.get('risk_level')}")
        print(f"   Reason: {data.get('reason')}")
        print(f"   Token: {data.get('confirmation_token')[:20]}...")
        return None  # Don't actually execute
    elif resp.status_code == 200:
        # LOW/MEDIUM risk, executed successfully
        print(f"✓ Action executed")
        if data.get("success"):
            print(f"  Result: {json.dumps(data, indent=2)[:200]}")
        else:
            print(f"  Error: {data.get('error')}")
    
    return resp

print("=" * 80)
print("TESTING NEMO FOR WHATSAPP AUTOMATION")
print("=" * 80)

print("\n" + "="*80)
print("STEP 1: Open WhatsApp")
print("="*80)
resp = test_action("open_app", target="whatsapp")

print("\n" + "="*80)
print("STEP 2: Wait for WhatsApp to load")
print("="*80)
test_action("wait", value="3")

print("\n" + "="*80)
print("STEP 3: Use keyboard shortcut to search contacts")
print("="*80)
print("\nℹ️  Using Ctrl+F to open search in WhatsApp")
test_action("press_key", value="ctrl+f")

print("\n" + "="*80)
print("STEP 4: Type contact name 'Rohitha DG'")
print("="*80)
test_action("type", value="Rohitha DG")

print("\n" + "="*80)
print("STEP 5: Press Enter to select contact")
print("="*80)
test_action("press_key", value="enter")

print("\n" + "="*80)
print("STEP 6: Wait for chat to open")
print("="*80)
test_action("wait", value="1")

print("\n" + "="*80)
print("STEP 7: Type message 'hi'")
print("="*80)
test_action("type", value="hi")

print("\n" + "="*80)
print("STEP 8: Send message (Ctrl+Enter or Enter)")
print("="*80)
test_action("press_key", value="ctrl+enter")

print("\n" + "="*80)
print("ANALYSIS: WhatsApp Automation Capability")
print("="*80)

print("""
CAN DO (with action_classifier risk check):
✓ Open WhatsApp (MEDIUM risk - unknown app)
✓ Type text "hi" (LOW risk - normal text)
✓ Press keyboard keys (varies: safe keys=LOW, system keys=MEDIUM)
✓ Click on UI elements (MEDIUM risk - unknown coordinates)
✓ Wait for app to load (LOW risk)

LIMITATIONS (Cannot do automatically):
✗ Can't reliably find and click "Rohitha DG" without knowing exact coordinates
✗ Can't read screen to verify contact was found
✗ Can't handle UI variations across different WhatsApp versions
✗ Can't verify message was actually sent
✗ Can't handle pop-ups/notifications that appear
✗ Requires manual coordinate discovery for clicks

BEST APPROACH FOR RELIABILITY:
1. WhatsApp Web (in browser) - has consistent DOM, easier to automate
2. Use OpenClaw agent that can:
   - Take screenshot to see current state
   - Use OCR/vision to find contact
   - Adapt to UI changes
   - Provide human feedback on coordinate selection
3. Pre-record good coordinates for click actions
4. Use step-up auth for non-critical, low-risk portions

RISK CLASSIFICATION:
- open_app("whatsapp") → MEDIUM (unknown app)
- type("hi") → LOW (normal text, <200 chars)
- press_key("ctrl+f") → MEDIUM (system hotkey)
- click() → MEDIUM (unknown coordinates)
- wait(1) → LOW (non-destructive)

Total Risk: MEDIUM - Would execute with user approval via dashboard
""")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)
print("""
For reliable WhatsApp automation:

OPTION A: Use WhatsApp Web + OpenClaw Agent
  - More reliable (consistent CSS structure)
  - Agent can see screen and adapt
  - Better error handling

OPTION B: Use NEMO with Pre-recorded Coordinates
  - Record exact (x,y) coordinates of UI elements
  - Use click action with those coordinates
  - Works but fragile if UI changes

OPTION C: Use API Integration
  - WhatsApp Business API (official, requires setup)
  - Twilio/SendGrid integration
  - Most reliable but requires ext. service

Current NEMO System: ✓ Can do it with limitations
- Would need manual coordinate discovery
- UI-aware approach recommended
- Great for structured UI (web apps, forms)
- Less ideal for complex discovery tasks
""")
