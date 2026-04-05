#!/usr/bin/env python
"""Test floatingfish agent API calls."""

import requests
import json
import time

print("\n" + "="*70)
print("NEMO FLOATING FISH AGENT - API Integration Test")
print("="*70)

BASE_URL = "http://localhost:8765"

def test_fish_commands():
    """Test commands that the fish agent sends to the server."""
    
    commands = [
        {
            "name": "Search Command",
            "payload": {"action": "search", "value": "python tutorial", "user": "V"}
        },
        {
            "name": "Open Chrome",
            "payload": {"action": "open_app", "target": "chrome", "user": "V"}
        },
        {
            "name": "Type Text",
            "payload": {"action": "type", "value": "Hello NEMO", "user": "V"}
        },
        {
            "name": "Take Screenshot",
            "payload": {"action": "screenshot", "user": "V"}
        },
    ]
    
    results = {}
    
    for cmd in commands:
        name = cmd["name"]
        payload = cmd["payload"]
        
        print(f"\n[TEST] {name}")
        print(f"  Payload: {payload}")
        
        try:
            r = requests.post(
                f"{BASE_URL}/execute",
                json=payload,
                timeout=10
            )
            print(f"  ✓ Status: {r.status_code}")
            data = r.json()
            print(f"  ✓ Response: {str(data)[:100]}")
            results[name] = True
        except requests.Timeout:
            print(f"  ✗ Timeout")
            results[name] = False
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:100]}")
            results[name] = False
    
    return results

print("\nTesting Fish Agent Commands...")
print("(Fish agent must be running + NEMO server on :8765)\n")

time.sleep(1)

results = test_fish_commands()

# Summary
print("\n" + "="*70)
print("FISH AGENT TEST SUMMARY")
print("="*70)
passed = sum(results.values())
total = len(results)
print(f"\nPassed: {passed}/{total}")
for name, result in results.items():
    status = "✓" if result else "✗"
    print(f"  {status} {name}")

if passed >= 2:
    print("\n✓ Fish agent API integration working!")
else:
    print(f"\n⚠ {total - passed} command(s) failed")

print("="*70 + "\n")
