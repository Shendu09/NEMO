#!/usr/bin/env python3
"""Test the /execute endpoint with detailed debugging."""

import requests
import json

BASE_URL = "http://localhost:8765"

print("=" * 70)
print("Testing /execute endpoint with HIGH-risk action (powershell)")
print("=" * 70)

payload = {
    "action": "open_app",
    "target": "powershell",
    "user": "test_user",
}

print(f"\nRequest payload:")
print(json.dumps(payload, indent=2))

try:
    resp = requests.post(f"{BASE_URL}/execute", json=payload, timeout=10)
    
    print(f"\nResponse status: {resp.status_code}")
    print(f"Response headers: {dict(resp.headers)}")
    print(f"Response body:")
    print(json.dumps(resp.json(), indent=2))
    
    # Verify the response
    if resp.status_code == 202:
        print("\n✓ SUCCESS: Got expected 202 status with confirmation token")
    else:
        print(f"\n✗ FAILED: Expected 202 but got {resp.status_code}")
        
except requests.exceptions.RequestException as e:
    print(f"\n✗ ERROR: {e}")
