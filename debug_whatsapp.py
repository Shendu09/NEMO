#!/usr/bin/env python3
"""Debug WhatsApp message sending - check if message appeared."""

import time
import pyautogui
import win32gui
from mss import mss
from PIL import Image

# Focus WhatsApp
print("1. Focusing WhatsApp...")
hwnd = win32gui.FindWindow(None, "WhatsApp")
if hwnd:
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    print(f"   WhatsApp focused: {hwnd}")
else:
    print("   ERROR: WhatsApp not found!")

# Get screenshot
print("\n2. Taking screenshot to check message content...")
with mss() as sct:
    sct_img = sct.grab(sct.monitors[1])
    img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
    img.save('debug_whatsapp.png')
    print(f"   Screenshot saved: debug_whatsapp.png ({sct_img.width}x{sct_img.height})")

print("\n3. Checking if 'gandu' appears in screenshot...")
# For now, just save it so user can inspect
print("   Open debug_whatsapp.png and look for:")
print("   - Is Unni's chat open?")
print("   - Is 'gandu' visible in the message list?")
print("   - What is showing in the message input field?")
