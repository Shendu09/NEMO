"""
Tests for Web Browser Automation Module.

Tests browsing, searching, summarization, and video playback.
"""

import base64
import logging
from pathlib import Path

from core.browser.web_agent import (
    browse,
    search_web,
    summarize_page,
    play_youtube,
    play_song,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_browse_simple_page():
    """Test browsing a simple page."""
    logger.info("Testing browse()...")
    
    try:
        # Browse a simple test page
        result = browse("https://example.com")
        
        logger.info(f"Browse result keys: {result.keys()}")
        
        # Check result structure
        assert "success" in result
        assert "title" in result
        assert "text" in result
        assert "links" in result
        assert "screenshot_b64" in result
        assert "url" in result
        
        if result["success"]:
            print(f"✓ Successfully browsed: {result['title']}")
            print(f"  Text length: {len(result['text'])}")
            print(f"  Links found: {len(result['links'])}")
            print(f"  Screenshot size: {len(result['screenshot_b64'])} bytes")
        else:
            print(f"✗ Browse failed: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        logger.error(f"browse() test failed: {e}")
        raise


def test_search_web():
    """Test web search."""
    logger.info("Testing search_web()...")
    
    try:
        # Search for something
        result = search_web("python programming")
        
        logger.info(f"Search result keys: {result.keys()}")
        
        # Check result structure
        assert "query" in result
        assert "engine" in result
        assert "results" in result
        
        print(f"✓ Search results for: {result['query']}")
        print(f"  Engine: {result['engine']}")
        print(f"  Results found: {len(result['results'])}")
        
        if result["results"]:
            for i, res in enumerate(result["results"][:3], 1):
                print(f"  {i}. {res.get('title', 'No title')}")
    
    except Exception as e:
        logger.error(f"search_web() test failed: {e}")
        raise


def test_summarize_page():
    """Test page summarization."""
    logger.info("Testing summarize_page()...")
    
    try:
        # Summarize a page
        # Using example.com as it's simple and reliable
        result = summarize_page("https://example.com")
        
        logger.info(f"Summarize result keys: {result.keys()}")
        
        # Check result structure
        assert "url" in result
        assert "title" in result
        assert "summary" in result
        assert "full_text_length" in result
        
        print(f"✓ Summarized: {result['url']}")
        print(f"  Title: {result['title']}")
        print(f"  Summary: {result['summary'][:100]}...")
        print(f"  Text length: {result['full_text_length']}")
    
    except Exception as e:
        logger.error(f"summarize_page() test failed: {e}")
        raise


def test_play_youtube():
    """Test YouTube playback."""
    logger.info("Testing play_youtube()...")
    
    try:
        # Note: This will open a Chromium window with video
        logger.warning("This test will open a browser window with video")
        
        result = play_youtube("official python tutorial")
        
        logger.info(f"Play result keys: {result.keys()}")
        
        # Check result structure
        assert "success" in result
        assert "video_title" in result
        assert "screenshot_b64" in result
        
        if result["success"]:
            print(f"✓ Playing video: {result['video_title']}")
            print(f"  Screenshot: {len(result['screenshot_b64'])} bytes")
        else:
            print(f"✗ Play failed: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        logger.error(f"play_youtube() test failed: {e}")
        raise


def test_play_song():
    """Test song playback."""
    logger.info("Testing play_song()...")
    
    try:
        # Note: This will open a Chromium window with music
        logger.warning("This test will open a browser window with music")
        
        result = play_song("Imagine John Lennon")
        
        logger.info(f"Play song result keys: {result.keys()}")
        
        # Check result structure
        assert "success" in result
        assert "video_title" in result
        assert "screenshot_b64" in result
        
        if result["success"]:
            print(f"✓ Playing song: {result['video_title']}")
            print(f"  Screenshot: {len(result['screenshot_b64'])} bytes")
        else:
            print(f"✗ Play failed: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        logger.error(f"play_song() test failed: {e}")
        raise


if __name__ == "__main__":
    print("=" * 70)
    print("NEMO Browser Module Tests")
    print("=" * 70)
    
    tests = [
        ("Browse", test_browse_simple_page),
        ("Search", test_search_web),
        ("Summarize", test_summarize_page),
        # Note: YouTube tests open windows, so skip by default
        # ("Play YouTube", test_play_youtube),
        # ("Play Song", test_play_song),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n[TEST] {name}")
        print("-" * 70)
        
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        exit(1)
