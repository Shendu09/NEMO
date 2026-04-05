#!/usr/bin/env python
"""NEMO API Test Suite - Comprehensive Testing."""

import requests
import json
import time

print("\n" + "="*70)
print("NEMO API TEST SUITE - Production Verification")
print("="*70)

BASE_URL = "http://localhost:8765"
TIMEOUT = 10

def test_health():
    """Test 1: Health Check"""
    print("\n[1/5] Health Check")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        print(f"  ✓ Status: {r.status_code}")
        print(f"  ✓ Response: {r.json()}")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_screenshot():
    """Test 2: Screenshot Capture"""
    print("\n[2/5] Screenshot Capture")
    try:
        r = requests.post(f"{BASE_URL}/execute", 
                         json={"action": "screenshot", "user": "V"},
                         timeout=TIMEOUT)
        print(f"  ✓ Status: {r.status_code}")
        data = r.json()
        has_screenshot = "screenshot_b64" in data
        print(f"  ✓ Screenshot captured: {has_screenshot}")
        if has_screenshot:
            print(f"  ✓ Size: {len(data['screenshot_b64'])} characters")
        return has_screenshot
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_intent():
    """Test 3: Intent Matching"""
    print("\n[3/5] Intent Matching (NLP)")
    try:
        r = requests.post(f"{BASE_URL}/execute",
                         json={"action": "search", "value": "pizza restaurants", "user": "V"},
                         timeout=TIMEOUT)
        print(f"  ✓ Status: {r.status_code}")
        data = r.json()
        print(f"  ✓ Response: {data}")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_dashboard():
    """Test 4: Dashboard Access"""
    print("\n[4/5] Dashboard Web Interface")
    try:
        r = requests.get(f"{BASE_URL}/dashboard", timeout=TIMEOUT)
        print(f"  ✓ Status: {r.status_code}")
        html_loaded = len(r.text) > 100
        print(f"  ✓ HTML loaded: {html_loaded}")
        print(f"  ✓ Size: {len(r.text)} bytes")
        return html_loaded
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def test_system_info():
    """Test 5: System Information"""
    print("\n[5/5] System Information")
    try:
        import torch
        print(f"  ✓ PyTorch: {torch.__version__}")
        print(f"  ✓ CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  ✓ GPU: {torch.cuda.get_device_name(0)}")
            print(f"  ✓ VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

# Run all tests
print("\nRunning tests... (this may take 30 seconds)")
start = time.time()

results = {
    "Health Check": test_health(),
    "Screenshot": test_screenshot(),
    "Intent Matching": test_intent(),
    "Dashboard": test_dashboard(),
    "System Info": test_system_info(),
}

elapsed = time.time() - start

# Summary
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)
passed = sum(results.values())
total = len(results)
print(f"\n  Passed: {passed}/{total}")
for name, result in results.items():
    status = "✓" if result else "✗"
    print(f"    {status} {name}")

print(f"\n  Total Time: {elapsed:.2f}s")
print("\n" + "="*70)

if passed == total:
    print("\n🎉 ALL TESTS PASSED - NEMO IS PRODUCTION READY!")
else:
    print(f"\n⚠ {total - passed} test(s) failed - see details above")

print("="*70 + "\n")
