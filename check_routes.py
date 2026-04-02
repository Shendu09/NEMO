#!/usr/bin/env python3
"""Check which routes are registered in the Flask app."""

from bridge.nemo_server import app

print("Registered routes in Flask app:")
print("=" * 70)

for rule in app.url_map.iter_rules():
    if rule.endpoint != "static":
        print(f"  {rule.rule:30} → {rule.endpoint:20} {list(rule.methods)}")

print("\n" + "=" * 70)

# Check if /execute is registered
execute_found = False
for rule in app.url_map.iter_rules():
    if rule.rule == "/execute":
        execute_found = True
        print(f"\nFound /execute route: {rule}")
        break

if not execute_found:
    print("\n✗ /execute route NOT FOUND!")
else:
    print("\n✓ /execute route is registered")
