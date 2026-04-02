#!/usr/bin/env python3
"""Direct test of execute() function without Flask."""

import sys
import json
from unittest.mock import Mock, patch

# Set up logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test the execute function directly
from bridge.nemo_server import execute
from flask import Flask, request

app = Flask(__name__)

# Mock the dependencies
from core.security.gateway_v2 import SecurityGateway
from core.security.audit_logger_v2 import AuditLogger

gateway = SecurityGateway(data_dir="clevrr_data")
audit_logger = AuditLogger(log_path="clevrr_data/audit.jsonl")

# Set up dependencies
from bridge.nemo_server import set_dependencies
set_dependencies(gateway, audit_logger)

# Create a mock request context
with app.test_request_context(
    '/execute',
    method='POST',
    json={
        "action": "open_app",
        "target": "powershell",
        "user": "test",
    }
):
    print("[*] Testing execute() with powershell...")
    result = execute()
    print(f"[*] Result: {result}")
    
    # Parse the response (it's a tuple of (dict, status_code))
    if isinstance(result, tuple):
        response_dict, status_code = result
        print(f"[*] Status: {status_code}")
        print(f"[*] Response: {json.loads(response_dict.data)}")
    else:
        print(f"[*] Response: {result}")
