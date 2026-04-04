#!/usr/bin/env python3
"""
NEMO Vision Module Demo.

Demonstrates smart element detection and clicking using OmniParser.
"""

from __future__ import annotations

import base64
import io
import logging
import sys
from pathlib import Path

import pyautogui
from PIL import Image

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.vision.omniparser_vision import find_element, list_elements, VisionProvider
from bridge.nemo_server import _capture_screenshot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def demo_1_capture_and_explore():
    """Demo 1: Capture screenshot and explore detected elements."""
    print("\n" + "=" * 70)
    print("DEMO 1: Capture Screenshot & Explore Elements")
    print("=" * 70)
    
    logger.info("Capturing active window screenshot...")
    screenshot_b64 = _capture_screenshot()
    
    if not screenshot_b64:
        logger.error("Failed to capture screenshot")
        return
    
    logger.info("Listing all detected UI elements...")
    elements = list_elements(screenshot_b64)
    
    print(f"\nFound {len(elements)} UI elements:")
    print("-" * 70)
    
    if elements:
        print(f"{'Label':<40} {'X':>6} {'Y':>6} {'Conf':>6}")
        print("-" * 70)
        
        for elem in sorted(elements, key=lambda e: e.get('confidence', 0), reverse=True)[:20]:
            label = elem['label'][:38]
            x = elem['x']
            y = elem['y']
            conf = elem['confidence']
            print(f"{label:<40} {x:>6} {y:>6} {conf:>5.1%}")
    else:
        print("(No elements detected - OmniParser may need setup)")
    
    print("=" * 70)
    return screenshot_b64


def demo_2_find_specific_element(screenshot_b64: str | None = None):
    """Demo 2: Find a specific element by name."""
    print("\n" + "=" * 70)
    print("DEMO 2: Find Specific Element")
    print("=" * 70)
    
    if not screenshot_b64:
        logger.info("Capturing active window screenshot...")
        screenshot_b64 = _capture_screenshot()
        
        if not screenshot_b64:
            logger.error("Failed to capture screenshot")
            return
    
    # Try to find various common UI elements
    targets = [
        "Send Button",
        "Send",
        "Button",
        "Close",
        "Save",
        "Exit",
        "OK",
        "Cancel",
    ]
    
    print(f"\nSearching for common UI elements...")
    print("-" * 70)
    print(f"{'Target':<20} {'Found':<7} {'Label':<25} {'Conf':>6}")
    print("-" * 70)
    
    for target in targets:
        result = find_element(screenshot_b64, target)
        
        found = "✓" if result['found'] else "✗"
        label = result['label'][:23] if result['label'] else "(not found)"
        conf = f"{result['confidence']:.1%}" if result['found'] else "-"
        
        print(f"{target:<20} {found:<7} {label:<25} {conf:>6}")
    
    print("=" * 70)


def demo_3_smart_click(screenshot_b64: str | None = None):
    """Demo 3: Smart click on an element."""
    print("\n" + "=" * 70)
    print("DEMO 3: Smart Click on Element")
    print("=" * 70)
    
    if not screenshot_b64:
        logger.info("Capturing active window screenshot...")
        screenshot_b64 = _capture_screenshot()
        
        if not screenshot_b64:
            logger.error("Failed to capture screenshot")
            return
    
    # Try to find a button
    target = "Button"
    logger.info(f"Searching for '{target}'...")
    
    result = find_element(screenshot_b64, target)
    
    print(f"\nSearch Result:")
    print("-" * 70)
    print(f"  Target: {target}")
    print(f"  Found: {result['found']}")
    
    if result['found']:
        print(f"  Label: {result['label']}")
        print(f"  Position: ({result['x']}, {result['y']})")
        print(f"  Confidence: {result['confidence']:.1%}")
        
        print(f"\n  ➜ Would click at ({result['x']}, {result['y']})")
        print(f"  ➜ Run demo_4_click_demo() to actually click")
    else:
        print(f"  Element not found on screen")
    
    print("=" * 70)


def demo_4_click_demo():
    """Demo 4: Actually perform a click (demonstration)."""
    print("\n" + "=" * 70)
    print("DEMO 4: Execute Smart Click")
    print("=" * 70)
    
    print("\nCaptioning enabled for demo...")
    print("WARNING: This will ACTUALLY click on detected elements!")
    print("\nCurrently showing simulation mode (not clicking).")
    print("Uncomment the pyautogui.click() line to enable real clicks.")
    
    logger.info("Capturing screenshot...")
    screenshot_b64 = _capture_screenshot()
    
    if not screenshot_b64:
        logger.error("Failed to capture screenshot")
        return
    
    target = "Button"
    logger.info(f"Finding '{target}'...")
    result = find_element(screenshot_b64, target)
    
    if result['found']:
        x, y = result['x'], result['y']
        print(f"\nTarget Found: {result['label']}")
        print(f"Coordinates: ({x}, {y})")
        print(f"Confidence: {result['confidence']:.1%}")
        
        # SIMULATION MODE (commented out actual click)
        print(f"\n  [SIMULATION] Would click at ({x}, {y})")
        # UNCOMMENT to enable real clicking:
        # pyautogui.click(x, y)
        # logger.info(f"Clicked at ({x}, {y})")
    else:
        print(f"\nElement not found")
    
    print("=" * 70)


def demo_5_vision_api():
    """Demo 5: Using VisionProvider class API."""
    print("\n" + "=" * 70)
    print("DEMO 5: VisionProvider API")
    print("=" * 70)
    
    logger.info("Using VisionProvider class interface...")
    
    screenshot_b64 = _capture_screenshot()
    if not screenshot_b64:
        logger.error("Failed to capture screenshot")
        return
    
    print("\nUsing VisionProvider class:")
    print("-" * 70)
    
    # Static method - find
    print("\n1. VisionProvider.find(screenshot, 'OK')")
    result = VisionProvider.find(screenshot_b64, "OK")
    if result['found']:
        print(f"   ✓ Found '{result['label']}' at ({result['x']}, {result['y']})")
    else:
        print(f"   ✗ Not found")
    
    # Static method - list_all
    print("\n2. VisionProvider.list_all(screenshot)")
    all_elements = VisionProvider.list_all(screenshot_b64)
    print(f"   ✓ Detected {len(all_elements)} elements")
    if all_elements:
        print(f"   First element: {all_elements[0]['label']}")
    
    print("\n" + "=" * 70)


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "NEMO Vision Module - Interactive Demo".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    print("\nThis demo showcases the OmniParser vision capabilities:")
    print("- Capturing screenshots")
    print("- Detecting UI elements")
    print("- Finding elements by name")
    print("- Smart clicking")
    
    # Run demos sequentially
    screenshot_b64 = demo_1_capture_and_explore()
    
    if screenshot_b64:
        demo_2_find_specific_element(screenshot_b64)
        demo_3_smart_click(screenshot_b64)
        demo_5_vision_api()
    
    # Demo 4 is separate (actual clicking)
    print("\n" + "=" * 70)
    print("ADDITIONAL: Run demo_4_click_demo() for actual clicking demo")
    print("=" * 70)
    
    print("\n✓ Demo completed!")
    print("\nNext steps:")
    print("  1. Read VISION_GUIDE.md for detailed documentation")
    print("  2. Install dependencies: pip install -r requirements.txt")
    print("  3. Try 'target:' format in dashboard")


if __name__ == "__main__":
    main()
