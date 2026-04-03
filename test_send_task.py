#!/usr/bin/env python3
"""Test assigning a WhatsApp task to NEMO."""

import time
import requests
import json

# Task: Send WhatsApp message
task = {
    'actions': [
        {
            'action': 'open_app',
            'target': 'whatsapp',
            'value': '',
            'verify_instruction': None
        },
        {
            'action': 'wait',
            'target': '',
            'value': '2',
            'verify_instruction': None
        },
        {
            'action': 'press_key',
            'target': '',
            'value': 'home',
            'verify_instruction': None
        },
        {
            'action': 'wait',
            'target': '',
            'value': '0.3',
            'verify_instruction': None
        },
        {
            'action': 'press_key',
            'target': '',
            'value': 'down',
            'verify_instruction': None
        },
        {
            'action': 'wait',
            'target': '',
            'value': '0.5',
            'verify_instruction': None
        },
        {
            'action': 'press_key',
            'target': '',
            'value': 'enter',
            'verify_instruction': None
        },
        {
            'action': 'wait',
            'target': '',
            'value': '1',
            'verify_instruction': None
        },
        {
            'action': 'press_key',
            'target': '',
            'value': 'tab',
            'verify_instruction': None  # Tab to focus message input field
        },
        {
            'action': 'wait',
            'target': '',
            'value': '0.5',
            'verify_instruction': None
        },
        {
            'action': 'type',
            'target': '',
            'value': 'gandu',
            'verify_instruction': None
        },
        {
            'action': 'wait',
            'target': '',
            'value': '0.5',
            'verify_instruction': None
        },
        {
            'action': 'press_key',
            'target': '',
            'value': 'enter',
            'verify_instruction': None
        }
    ],
    'user': 'demo',
    'channel': 'test_task',
    'max_retries': 0,  # No retries - vision API not available
    'vision_api_url': 'http://localhost:5000'
}

print('=' * 80)
print('ASSIGNING TASK TO NEMO')
print('=' * 80)
print('\nTask: Send WhatsApp message to Unni with message "gandu"')
print('Actions:', len(task['actions']))
for i, action in enumerate(task['actions'], 1):
    print(f'  {i}. {action["action"]}: {action.get("value", action.get("target", ""))}')

print('\n' + '-' * 80)
print('Waiting for NEMO server...')
print('-' * 80)

# Wait for server
for attempt in range(10):
    try:
        resp = requests.get('http://127.0.0.1:8765/health', timeout=1)
        if resp.status_code == 200:
            print('OK Server is ready!\n')
            break
    except:
        pass
    if attempt < 9:
        time.sleep(0.5)

print('\nSending task to NEMO...')

try:
    # Send task
    response = requests.post(
        'http://127.0.0.1:8765/execute_with_vision',
        json=task,
        timeout=60
    )
    
    result = response.json()
    
    print(f'\n✅ Response received (HTTP {response.status_code})')
    print(f'   Success: {result.get("success")}')
    print(f'   Actions executed: {result.get("executed")}/{result.get("total_actions")}')
    print(f'   Verifications: {result.get("verifications_passed")}')
    print(f'   Duration: {result.get("duration_seconds", 0):.2f}s')
    
    print('\n' + '=' * 80)
    print('📊 STEP RESULTS')
    print('=' * 80)
    
    for i, step in enumerate(result.get('steps', []), 1):
        status = '✅' if step.get('status') == 'verified' else '⚠️' if step.get('status') == 'executed' else '❌'
        print(f'\n{status} Step {i}: {step.get("action").upper()}')
        print(f'   Status: {step.get("status")}')
        print(f'   Verified: {step.get("verified")}')
        if step.get('error'):
            print(f'   Error: {step.get("error")}')
    
    if result.get('warnings'):
        print('\n' + '=' * 80)
        print('⚠️  WARNINGS')
        print('=' * 80)
        for warning in result.get('warnings'):
            print(f'  • {warning}')
    
    print('\n' + '=' * 80)
    print('📈 SUMMARY')
    print('=' * 80)
    print(f'Outcome: {"✅ SUCCESS" if result.get("success") else "⚠️ PARTIAL/FAILURE"}')
    print(f'Actions: {result.get("executed")}/{result.get("total_actions")}')
    print(f'Duration: {result.get("duration_seconds", 0):.2f} seconds')
    
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
