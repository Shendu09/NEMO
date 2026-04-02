#!/usr/bin/env python3
"""Test /execute with Flask test client vs HTTP requests."""

import json
from bridge.nemo_server import app
from core.security.gateway_v2 import SecurityGateway
from core.security.audit_logger_v2 import AuditLogger
from bridge.nemo_server import set_dependencies

# Set up dependencies
gateway = SecurityGateway(data_dir="clevrr_data")
audit_logger = AuditLogger(log_path="clevrr_data/audit.jsonl")
set_dependencies(gateway, audit_logger)

payload = {
    "action": "open_app",
    "target": "powershell",
    "user": "test",
}

print("=" * 70)
print("TEST 1: Using Flask test client")
print("=" * 70)

with app.test_client() as client:
    resp = client.post("/execute", json=payload)
    print(f"Status: {resp.status_code}")
    data = resp.get_json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    if resp.status_code == 202:
        print("\n✓ Test client returned 202 - classifier is working!")
    else:
        print(f"\n✗ Test client returned {resp.status_code}")

print("\n" + "=" * 70)
print("TEST 2: Head-to-head comparison with HTTP")
print("=" * 70)

import requests

resp_http = requests.post("http://localhost:8765/execute", json=payload, timeout=5)
print(f"Status: {resp_http.status_code}")
data = resp_http.json()
print(f"Response: {json.dumps(data, indent=2)}")

if resp_http.status_code == 202:
    print("\n✓ HTTP request returned 202")
else:
    print(f"\n✗ HTTP request returned {resp_http.status_code}")

print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)
print(f"Test client status: {resp.status_code}")
print(f"HTTP request status: {resp_http.status_code}")

if resp.status_code != resp_http.status_code:
    print(f"\n⚠ MISMATCH: Test client returns {resp.status_code} but HTTP returns {resp_http.status_code}")
    print("This suggests the running Flask server is not using the same code!")
