"""
Web Browser Automation Module — Playwright-based web browsing for NEMO.

Provides web browsing, search, summarization, and video playback capabilities.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Any, Optional

import requests
from urllib.parse import quote

logger = logging.getLogger("nemo.browser")

# For async execution in sync context
_loop: Optional[Any] = None


def _get_event_loop():
    """Get or create event loop for async Playwright code."""
    global _loop
    try:
        _loop = asyncio.get_event_loop()
    except RuntimeError:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def _run_async(coro):
    """Run async coroutine in sync context."""
    loop = _get_event_loop()
    try:
        return loop.run_until_complete(coro)
    except RuntimeError:
        # Loop already running (nested async)
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(coro)


async def _browse_async(url: str) -> dict[str, Any]:
    """
    Internal async function to browse a URL.
    
    Opens URL in headless Chromium, waits for load, extracts content.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright")
        return {
            "success": False,
            "error": "Playwright not installed",
            "title": "",
            "text": "",
            "links": [],
            "screenshot_b64": "",
            "url": url,
        }
    
    browser = None
    page = None
    
    try:
        logger.info(f"Opening URL: {url}")
        
        async with async_playwright() as p:
            # Launch headless Chromium
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            
            # Navigate and wait for load
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            logger.debug(f"Page loaded: {url}")
            
            # Extract title
            title = await page.title()
            logger.debug(f"Title: {title}")
            
            # Extract main body text (cleaned)
            body_text = await page.evaluate("""
                () => {
                    // Remove scripts, styles, and other non-content elements
                    const uselessElements = document.querySelectorAll(
                        'script, style, meta, noscript, [aria-hidden="true"]'
                    );
                    uselessElements.forEach(el => el.remove());
                    
                    // Get text from body
                    let text = document.body.innerText || document.body.textContent || '';
                    
                    // Clean up excessive whitespace
                    text = text.replace(/\\s+/g, ' ').trim();
                    
                    return text;
                }
            """)
            
            logger.debug(f"Body text length: {len(body_text)}")
            
            # Extract all links
            links_data = await page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        const href = a.getAttribute('href');
                        const text = a.textContent?.trim() || '';
                        if (href && text) {  // Only include links with text
                            links.push({text, href});
                        }
                    });
                    return links;
                }
            """)
            
            logger.debug(f"Found {len(links_data)} links")
            
            # Take screenshot
            screenshot_bytes = await page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            logger.info(f"Successfully browsed: {url}")
            
            await context.close()
            await browser.close()
            
            return {
                "success": True,
                "title": title,
                "text": body_text,
                "links": links_data,
                "screenshot_b64": screenshot_b64,
                "url": url,
            }
    
    except Exception as e:
        logger.error(f"Browse failed: {e}")
        if browser:
            await browser.close()
        
        return {
            "success": False,
            "error": str(e),
            "title": "",
            "text": "",
            "links": [],
            "screenshot_b64": "",
            "url": url,
        }


def browse(url: str) -> dict[str, Any]:
    """
    Browse a URL and extract content.
    
    Opens URL in headless Chromium, waits for full page load,
    extracts title, text, links, and screenshot.
    
    Args:
        url: URL to browse
    
    Returns:
        {
            "success": bool,
            "title": str,
            "text": str (cleaned body text),
            "links": [{text, href}, ...],
            "screenshot_b64": str (PNG base64),
            "url": str,
        }
    """
    logger.debug(f"browse({url})")
    return _run_async(_browse_async(url))


async def _search_web_async(query: str, engine: str = "google") -> dict[str, Any]:
    """Internal async function for web search."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return {
            "query": query,
            "engine": engine,
            "results": [],
        }
    
    browser = None
    
    try:
        logger.info(f"Searching {engine} for: {query}")
        
        if engine.lower() != "google":
            logger.warning(f"Only Google supported, using Google for: {query}")
        
        search_url = f"https://www.google.com/search?q={quote(query)}"
        logger.debug(f"Search URL: {search_url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            
            # Navigate to search results
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            logger.debug("Search results page loaded")
            
            # Extract top 5 results
            results = await page.evaluate("""
                () => {
                    const results = [];
                    const searchResults = document.querySelectorAll('div[data-sokoban-container]');
                    
                    for (let i = 0; i < Math.min(searchResults.length, 5); i++) {
                        const item = searchResults[i];
                        
                        // Extract title and URL
                        const titleEl = item.querySelector('a[href*="/url?q="]');
                        const snippetEl = item.querySelector('div[data-sncf]');
                        
                        if (titleEl) {
                            const title = titleEl.innerText;
                            let href = titleEl.getAttribute('href');
                            
                            // Decode URL from /url?q=... format
                            const urlMatch = href.match(/\\/url\\?q=([^&]+)/);
                            if (urlMatch) {
                                href = decodeURIComponent(urlMatch[1]);
                            }
                            
                            const snippet = snippetEl?.innerText || '';
                            
                            results.push({title, url: href, snippet});
                        }
                    }
                    
                    return results;
                }
            """)
            
            logger.info(f"Found {len(results)} search results")
            
            await context.close()
            await browser.close()
            
            return {
                "query": query,
                "engine": engine,
                "results": results,
            }
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        if browser:
            await browser.close()
        
        return {
            "query": query,
            "engine": engine,
            "results": [],
        }


def search_web(query: str, engine: str = "google") -> dict[str, Any]:
    """
    Search the web using Google.
    
    Args:
        query: Search query
        engine: Search engine (currently only "google" supported)
    
    Returns:
        {
            "query": str,
            "engine": str,
            "results": [{title, url, snippet}, ...]
        }
    """
    logger.debug(f"search_web({query}, {engine})")
    return _run_async(_search_web_async(query, engine))


def summarize_page(url: str) -> dict[str, Any]:
    """
    Summarize a webpage using Ollama.
    
    Fetches page content and sends to Ollama llama3 for summarization.
    
    Args:
        url: URL to summarize
    
    Returns:
        {
            "url": str,
            "title": str,
            "summary": str,
            "full_text_length": int,
        }
    """
    logger.info(f"Summarizing: {url}")
    
    try:
        # First, get page content
        page_data = browse(url)
        
        if not page_data.get("success", False):
            logger.error(f"Failed to browse {url}")
            return {
                "url": url,
                "title": "",
                "summary": f"Error: Could not access {url}",
                "full_text_length": 0,
            }
        
        title = page_data.get("title", "")
        text = page_data.get("text", "")
        
        # Take first 3000 chars for summarization
        text_to_summarize = text[:3000]
        
        logger.debug(f"Using {len(text_to_summarize)} chars for summarization")
        
        # Prepare prompt
        prompt = f"""Summarize this webpage clearly and concisely in 3-5 sentences.

Page title: {title}

Content:
{text_to_summarize}

Summary:"""
        
        logger.info("Calling Ollama llama3 for summarization")
        
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3",
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=60,
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama returned {response.status_code}")
                summary = "Failed to summarize"
            else:
                result = response.json()
                summary = result.get("response", "").strip()
                logger.debug(f"Summary: {summary}")
        
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama at localhost:11434")
            summary = "Ollama not available for summarization"
        
        return {
            "url": url,
            "title": title,
            "summary": summary,
            "full_text_length": len(text),
        }
    
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return {
            "url": url,
            "title": "",
            "summary": f"Error: {str(e)}",
            "full_text_length": 0,
        }


async def _play_youtube_async(query: str) -> dict[str, Any]:
    """Internal async function to search and play YouTube video."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return {
            "success": False,
            "error": "Playwright not installed",
            "video_title": "",
            "screenshot_b64": "",
        }
    
    browser = None
    page = None
    
    try:
        logger.info(f"Finding YouTube video: {query}")
        
        search_url = f"https://www.youtube.com/results?search_query={quote(query)}"
        
        async with async_playwright() as p:
            # Launch Chromium with UI (not headless for video playback)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            
            # Navigate to search results
            logger.debug(f"Navigating to: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for results to load
            await page.wait_for_load_state("networkidle", timeout=10000)
            logger.debug("Search results loaded")
            
            # Find first video result (not an ad)
            first_video = await page.evaluate("""
                () => {
                    const videos = document.querySelectorAll('ytd-video-renderer');
                    if (videos.length > 0) {
                        const link = videos[0].querySelector('a#video-title');
                        if (link) {
                            return {
                                href: link.getAttribute('href'),
                                title: link.getAttribute('title'),
                            };
                        }
                    }
                    return null;
                }
            """)
            
            if not first_video:
                logger.error(f"No video found for: {query}")
                await context.close()
                await browser.close()
                
                return {
                    "success": False,
                    "error": "No video found",
                    "video_title": "",
                    "screenshot_b64": "",
                }
            
            video_title = first_video.get("title", "Unknown")
            video_href = first_video.get("href", "")
            
            logger.info(f"Found video: {video_title}")
            
            # Click the video (navigate to it)
            full_url = f"https://www.youtube.com{video_href}"
            logger.debug(f"Navigating to video: {full_url}")
            await page.goto(full_url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for video to start playing
            await page.wait_for_timeout(2000)  # Wait 2 seconds
            logger.debug("Video started playing")
            
            # Take screenshot
            screenshot_bytes = await page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            
            logger.info(f"Successfully playing: {video_title}")
            
            await context.close()
            await browser.close()
            
            return {
                "success": True,
                "video_title": video_title,
                "screenshot_b64": screenshot_b64,
            }
    
    except Exception as e:
        logger.error(f"YouTube playback failed: {e}")
        if browser:
            await browser.close()
        
        return {
            "success": False,
            "error": str(e),
            "video_title": "",
            "screenshot_b64": "",
        }


def play_youtube(query: str) -> dict[str, Any]:
    """
    Search YouTube and play the first video result.
    
    Searches YouTube for the query, finds the first video (not ads),
    clicks it, and waits for playback to start.
    
    Args:
        query: Search query for YouTube
    
    Returns:
        {
            "success": bool,
            "video_title": str,
            "screenshot_b64": str (PNG base64),
        }
    """
    logger.debug(f"play_youtube({query})")
    return _run_async(_play_youtube_async(query))


def play_song(song_name: str) -> dict[str, Any]:
    """
    Search YouTube and play a song (audio).
    
    Appends " official audio" to query and calls play_youtube.
    
    Args:
        song_name: Song name to search for
    
    Returns:
        {
            "success": bool,
            "video_title": str,
            "screenshot_b64": str,
        }
    """
    logger.debug(f"play_song({song_name})")
    query = f"{song_name} official audio"
    logger.info(f"Playing song: {query}")
    return play_youtube(query)
