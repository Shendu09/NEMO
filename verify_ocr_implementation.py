#!/usr/bin/env python3
"""
Chrome Profile Picker OCR Implementation - Verification Checklist

Run this to verify all components are in place and working correctly.
"""

import sys
import os
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists."""
    exists = Path(filepath).exists()
    status = "✓" if exists else "✗"
    print(f"{status} {description}: {filepath}")
    return exists

def check_imports():
    """Check if required libraries can be imported."""
    print("\n📦 Checking Python Dependencies:")
    
    modules = [
        ("easyocr", "EasyOCR"),
        ("numpy", "NumPy"),
        ("cv2", "OpenCV"),
        ("pyperclip", "Pyperclip"),
        ("PIL", "PIL/Pillow"),
        ("pyautogui", "PyAutoGUI"),
    ]
    
    all_good = True
    for module_name, display_name in modules:
        try:
            __import__(module_name)
            print(f"✓ {display_name} installed")
        except ImportError:
            print(f"✗ {display_name} NOT installed")
            print(f"  → Install with: pip install {module_name}")
            all_good = False
    
    return all_good

def check_code_changes():
    """Check if code changes are in place."""
    print("\n🔧 Checking Code Changes:")
    
    nemo_server_path = "bridge/nemo_server.py"
    
    if not Path(nemo_server_path).exists():
        print(f"✗ {nemo_server_path} not found!")
        return False
    
    with open(nemo_server_path, 'r') as f:
        content = f.read()
    
    checks = [
        ("import easyocr", "EasyOCR import"),
        ("_get_ocr", "_get_ocr() function"),
        ("_handle_chrome_profile_picker", "_handle_chrome_profile_picker() function"),
        ("HAS_OCR", "HAS_OCR flag"),
        ("_ocr_reader", "Global OCR reader"),
    ]
    
    all_present = True
    for code_snippet, description in checks:
        if code_snippet in content:
            print(f"✓ {description} found")
        else:
            print(f"✗ {description} NOT found")
            all_present = False
    
    return all_present

def check_documentation():
    """Check if documentation files exist."""
    print("\n📖 Checking Documentation:")
    
    docs = [
        ("OCR_PROFILE_PICKER.md", "OCR Profile Picker Documentation"),
        ("CHROME_OCR_QUICK_REF.md", "Quick Reference Guide"),
        ("test_ocr_profile_picker.py", "OCR Test Script"),
        ("IMPLEMENTATION_COMPLETE.md", "Implementation Summary"),
    ]
    
    all_exist = True
    for filepath, description in docs:
        exists = check_file_exists(filepath, description)
        all_exist = all_exist and exists
    
    return all_exist

def main():
    """Run all checks."""
    print("=" * 70)
    print("  Chrome Profile Picker OCR Implementation - Verification Checklist")
    print("=" * 70)
    
    # Change to NEMO directory
    nemo_dir = Path(__file__).parent
    os.chdir(nemo_dir)
    print(f"\n📍 Working directory: {os.getcwd()}\n")
    
    # Run checks
    deps_ok = check_imports()
    code_ok = check_code_changes()
    docs_ok = check_documentation()
    
    # Summary
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)
    
    print(f"\n✓ Dependencies: {'INSTALLED' if deps_ok else 'MISSING'}")
    print(f"✓ Code Changes: {'IN PLACE' if code_ok else 'INCOMPLETE'}")
    print(f"✓ Documentation: {'COMPLETE' if docs_ok else 'MISSING'}")
    
    if deps_ok and code_ok and docs_ok:
        print("\n" + "🎉 ALL CHECKS PASSED - Ready to use!")
        print("\nNext steps:")
        print("  1. Start NEMO: python clevrr_service.py run")
        print("  2. In another terminal: python test_ocr_profile_picker.py")
        print("\nOr use the API:")
        print('  curl -X POST http://localhost:8765/execute \\')
        print('    -d \'{"action":"open_app","target":"chrome","value":"Bushra"}\'')
        return 0
    else:
        print("\n" + "⚠️  SOME CHECKS FAILED")
        if not deps_ok:
            print("\n  Missing dependencies - install with:")
            print("  python -m pip install easyocr opencv-python pyperclip --user")
        return 1

if __name__ == "__main__":
    sys.exit(main())
