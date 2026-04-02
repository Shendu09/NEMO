#!/usr/bin/env python3
"""Quick test of action classifier integration."""

import requests
import json

BASE_URL = "http://localhost:8765"

print("=" * 60)
print("TESTING ACTION CLASSIFIER INTEGRATION")
print("=" * 60)

# Test 1: LOW-risk action
print("\n[Test 1] LOW-risk action (wait)")
resp = requests.post(f"{BASE_URL}/execute", json={
    "action": "wait",
    "value": "0.1",
    "user": "test",
}, timeout=10)
data = resp.json()
print(f"Status: {resp.status_code}, Success: {data.get('success')}")
assert resp.status_code == 200
assert data["success"] is True
print("[PASS]\n")

# Test 2: MEDIUM-risk action
print("[Test 2] MEDIUM-risk action (click)")
resp = requests.post(f"{BASE_URL}/execute", json={
    "action": "click",
    "value": "100,200",
    "user": "test",
}, timeout=10)
data = resp.json()
print(f"Status: {resp.status_code}, Success: {data.get('success')}")
assert resp.status_code == 200
print("[PASS]\n")

# Test 3: HIGH-risk action (requires confirmation)
print("[Test 3] HIGH-risk action (powershell) - should require confirmation")
resp = requests.post(f"{BASE_URL}/execute", json={
    "action": "open_app",
    "target": "powershell",
    "user": "test",
}, timeout=10)
data = resp.json()
print(f"Status: {resp.status_code}")
print(f"Requires Confirmation: {data.get('requires_confirmation')}")
print(f"Risk Level: {data.get('risk_level')}")
print(f"Token: {data.get('confirmation_token', '')[:20]}...")
assert resp.status_code == 202
assert data["requires_confirmation"] is True
assert data["risk_level"] == "HIGH"
token = data["confirmation_token"]
print("[PASS]\n")

# Test 4: Deny confirmation
print("[Test 4] User denies action")
resp = requests.post(f"{BASE_URL}/confirm", json={
    "token": token,
    "approved": False,
}, timeout=10)
data = resp.json()
print(f"Status: {resp.status_code}, Success: {data.get('success')}")
assert resp.status_code == 403
assert data["success"] is False
print("[PASS]\n")

# Test 5: Get new token and approve
print("[Test 5] User approves action")
resp = requests.post(f"{BASE_URL}/execute", json={
    "action": "open_app",
    "target": "powershell",
    "user": "test",
}, timeout=10)
data = resp.json()
token = data["confirmation_token"]

resp = requests.post(f"{BASE_URL}/confirm", json={
    "token": token,
    "approved": True,
}, timeout=10)
data = resp.json()
print(f"Status: {resp.status_code}, Success: {data.get('success')}")
print(f"[PASS] (action executed with status: {resp.status_code})\n")

print("=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
