"""
Tests for OmniParser Vision Module.

Test vision capabilities for UI element detection and finding.
"""

import base64
import io
import logging
from pathlib import Path
from PIL import Image

from core.vision.omniparser_vision import find_element, list_elements, VisionProvider

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def create_test_screenshot(width: int = 1920, height: int = 1080) -> str:
    """Create a simple test screenshot as base64."""
    # Create a simple image with some colors
    img = Image.new('RGB', (width, height), color='white')
    
    # Add some colored rectangles to simulate UI elements
    pixels = img.load()
    
    # Red button area (100,100 to 300,150)
    for x in range(100, 300):
        for y in range(100, 150):
            pixels[x, y] = (255, 0, 0)
    
    # Green input field (100,200 to 400,250)
    for x in range(100, 400):
        for y in range(200, 250):
            pixels[x, y] = (0, 255, 0)
    
    # Convert to base64
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_b64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
    
    return img_b64


def test_vision_provider_import():
    """Test that vision provider can be imported."""
    logger.info("Testing vision provider import...")
    assert VisionProvider is not None
    print("✓ Vision provider imported successfully")


def test_find_element_with_fallback():
    """
    Test find_element function with fallback to Ollama.
    
    This test will use Ollama fallback since OmniParser model
    may not be available in test environment.
    """
    logger.info("Testing find_element function...")
    
    try:
        screenshot_b64 = create_test_screenshot()
        
        # Try to find a "send" button (should trigger Ollama fallback)
        result = find_element(screenshot_b64, "Send Button")
        
        logger.info(f"Find result: {result}")
        
        # Check result structure
        assert "found" in result
        assert "x" in result
        assert "y" in result
        assert "label" in result
        assert "confidence" in result
        
        # Coordinates should be reasonable
        if result["found"]:
            assert 0 <= result["x"] <= 1920, f"X coordinate {result['x']} out of range"
            assert 0 <= result["y"] <= 1080, f"Y coordinate {result['y']} out of range"
            assert 0 <= result["confidence"] <= 1.0, f"Confidence {result['confidence']} invalid"
        
        print(f"✓ find_element returned valid result: {result}")
        
    except Exception as e:
        logger.error(f"find_element test failed: {e}")
        raise


def test_list_elements_with_fallback():
    """
    Test list_elements function with fallback to Ollama.
    """
    logger.info("Testing list_elements function...")
    
    try:
        screenshot_b64 = create_test_screenshot()
        
        # List all elements (should return list, even if empty due to fallback)
        elements = list_elements(screenshot_b64)
        
        logger.info(f"Found {len(elements)} elements")
        
        # Check result is a list
        assert isinstance(elements, list), "Result must be a list"
        
        # Check each element structure
        for elem in elements:
            assert "label" in elem
            assert "x" in elem
            assert "y" in elem
            assert "width" in elem
            assert "height" in elem
            assert "confidence" in elem
        
        print(f"✓ list_elements returned {len(elements)} elements")
        
    except Exception as e:
        logger.error(f"list_elements test failed: {e}")
        raise


def test_vision_provider_methods():
    """Test VisionProvider static methods."""
    logger.info("Testing VisionProvider methods...")
    
    try:
        screenshot_b64 = create_test_screenshot()
        
        # Test find method
        result = VisionProvider.find(screenshot_b64, "Test Element")
        assert "found" in result
        assert "x" in result
        print("✓ VisionProvider.find() works")
        
        # Test list_all method
        elements = VisionProvider.list_all(screenshot_b64)
        assert isinstance(elements, list)
        print("✓ VisionProvider.list_all() works")
        
    except Exception as e:
        logger.error(f"VisionProvider test failed: {e}")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("NEMO Vision Module Tests")
    print("=" * 60)
    
    tests = [
        ("Import", test_vision_provider_import),
        ("Find Element", test_find_element_with_fallback),
        ("List Elements", test_list_elements_with_fallback),
        ("Vision Provider", test_vision_provider_methods),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n[TEST] {name}")
            print("-" * 60)
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        exit(1)
