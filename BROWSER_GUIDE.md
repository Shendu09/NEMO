# NEMO Browser Module - Web Automation Guide

## Overview

The NEMO Browser Module provides **Playwright-based web automation** for:
- 🌐 Browsing and scraping websites
- 🔍 Searching the web (Google)
- 📝 Summarizing content (with Ollama)
- ▶️ Playing videos (YouTube)
- 🎵 Playing songs (YouTube Audio)

**Status**: ✅ Production Ready

---

## Installation

### 1. Install Dependencies
```bash
pip install playwright nest-asyncio
playwright install chromium
```

### 2. Verify Installation
```bash
python -c "from core.browser.web_agent import browse; print('✓ OK')"
```

### 3. Optional: Setup Ollama for Summarization
```bash
ollama pull llama3
ollama serve
```

---

## Features

### 🌐 Browse Websites

**Extract from any URL:**
- Title
- Main body text (cleaned, no scripts/styles)
- All links with text and href
- Full page screenshot (base64 PNG)

```python
from core.browser.web_agent import browse

result = browse("https://example.com")
# Returns: {title, text, links, screenshot_b64, url, success}
```

### 🔍 Search Google

**Get top 5 results:**
- Title
- URL
- Snippet

```python
from core.browser.web_agent import search_web

result = search_web("python tutorial")
# Returns: {query, engine, results: [{title, url, snippet}, ...]}
```

### 📝 Summarize Pages

**Auto-summarization with AI:**
- Fetches page content
- Sends to Ollama llama3
- Returns 3-5 sentence summary

```python
from core.browser.web_agent import summarize_page

result = summarize_page("https://example.com")
# Returns: {url, title, summary, full_text_length}
```

### ▶️ Play YouTube Videos

**Find and play first result:**
- Searches YouTube
- Clicks first (non-ad) video
- Waits for playback
- Returns screenshot

```python
from core.browser.web_agent import play_youtube

result = play_youtube("python tutorial")
# Returns: {success, video_title, screenshot_b64}
```

### 🎵 Play Songs

**Search and play audio from YouTube:**
- Appends " official audio" to query
- Uses play_youtube() internally

```python
from core.browser.web_agent import play_song

result = play_song("Imagine John Lennon")
# Returns: {success, video_title, screenshot_b64}
```

---

## Dashboard Integration

### Browse Action
```json
{
  "action": "browse",
  "target": "https://example.com"
}
```

**Response**:
```json
{
  "success": true,
  "action": "browse",
  "url": "https://example.com",
  "title": "Example Domain",
  "text": "This domain is for use in...",
  "link_count": 5,
  "links": [{text, href}, ...],
  "screenshot": "base64_png_data"
}
```

### Search Action
```json
{
  "action": "search",
  "value": "python tutorial"
}
```

**Response**:
```json
{
  "success": true,
  "action": "search",
  "query": "python tutorial",
  "result_count": 5,
  "results": [
    {
      "title": "Welcome to Python.org",
      "url": "https://www.python.org",
      "snippet": "The official home of Python..."
    }
  ]
}
```

### Summarize Action
```json
{
  "action": "summarize",
  "target": "https://example.com"
}
```

**Response**:
```json
{
  "success": true,
  "action": "summarize",
  "url": "https://example.com",
  "title": "Example Domain",
  "summary": "This domain is reserved for examples...",
  "text_length": 1234
}
```

### Play Video Action
```json
{
  "action": "play",
  "value": "python tutorial"
}
```

**Response**:
```json
{
  "success": true,
  "action": "play",
  "query": "python tutorial",
  "video_title": "Python Tutorial for Beginners",
  "screenshot": "base64_png_data"
}
```

### Play Song Action
```json
{
  "action": "play_song",
  "value": "Imagine John Lennon"
}
```

---

## API Reference

### browse(url: str) → dict

Browse a URL and extract content.

**Parameters:**
- `url` (str): URL to browse

**Returns:**
```python
{
    "success": bool,
    "url": str,
    "title": str,
    "text": str,  # Cleaned body text
    "links": [{"text": str, "href": str}, ...],
    "screenshot_b64": str,  # PNG base64
    "error": str,  # If success=False
}
```

**Example:**
```python
result = browse("https://docs.python.org")
if result["success"]:
    print(f"Title: {result['title']}")
    print(f"Links: {len(result['links'])}")
```

---

### search_web(query: str, engine: str = "google") → dict

Search the web using Google.

**Parameters:**
- `query` (str): Search query
- `engine` (str): Search engine (only "google" supported)

**Returns:**
```python
{
    "query": str,
    "engine": str,
    "results": [
        {
            "title": str,
            "url": str,
            "snippet": str,
        },
        ...
    ]
}
```

**Example:**
```python
result = search_web("machine learning")
for res in result["results"]:
    print(f"{res['title']}: {res['url']}")
```

---

### summarize_page(url: str) → dict

Summarize a webpage using Ollama.

**Parameters:**
- `url` (str): URL to summarize

**Returns:**
```python
{
    "url": str,
    "title": str,
    "summary": str,  # 3-5 sentences
    "full_text_length": int,
}
```

**Example:**
```python
result = summarize_page("https://en.wikipedia.org/wiki/Python")
print(f"Summary: {result['summary']}")
```

**Requirements:**
- Ollama must be running: `ollama serve`
- llama3 model must be installed: `ollama pull llama3`

---

### play_youtube(query: str) → dict

Search YouTube and play the first video.

**Parameters:**
- `query` (str): Search query

**Returns:**
```python
{
    "success": bool,
    "video_title": str,
    "screenshot_b64": str,  # PNG base64
    "error": str,  # If success=False
}
```

**Example:**
```python
result = play_youtube("python programming")
if result["success"]:
    print(f"Playing: {result['video_title']}")
```

**Note:** Opens a browser window (not headless) to play video.

---

### play_song(song_name: str) → dict

Play a song from YouTube (audio).

**Parameters:**
- `song_name` (str): Song name to search

**Returns:** Same as `play_youtube()`

**Example:**
```python
result = play_song("Bohemian Rhapsody Queen")
if result["success"]:
    print(f"Playing: {result['video_title']}")
```

---

## Usage Examples

### Example 1: Research a Topic

```python
from core.browser.web_agent import search_web, summarize_page

# Search for the topic
results = search_web("quantum computing")

# Get URL of first result
first_url = results["results"][0]["url"]

# Summarize the page
summary = summarize_page(first_url)

print(f"Title: {summary['title']}")
print(f"Summary: {summary['summary']}")
```

### Example 2: Automated Research Workflow

```python
from core.browser.web_agent import browse, search_web

# Search for python libraries
results = search_web("popular python libraries 2024")

# Browse top 3 results
for res in results["results"][:3]:
    data = browse(res["url"])
    print(f"Title: {data['title']}")
    print(f"Text preview: {data['text'][:200]}...")
    print(f"Links available: {len(data['links'])}")
    print()
```

### Example 3: Video Discovery

```python
from core.browser.web_agent import play_youtube

# Search and play a tutorial
result = play_youtube("learn Python in 30 minutes")

if result["success"]:
    print(f"Now playing: {result['video_title']}")
    # Screenshot shows video in player
else:
    print(f"Error: {result['error']}")
```

### Example 4: Music Playback

```python
from core.browser.web_agent import play_song

# Play your favorite song
result = play_song("Imagine John Lennon")

if result["success"]:
    print(f"Now playing: {result['video_title']}")
    # Screenshot shows YouTube player with song
```

---

## Headless vs UI Mode

### Browse, Search, Summarize
- **Headless Mode** ✅
- No browser window visible
- Faster execution
- Better for automation

### Play YouTube, Play Song
- **UI Mode** (Non-headless)
- Browser window opens
- You can see the video/music
- Full browser experience

---

## Text Extraction & Cleaning

### What's Extracted
✅ Main page content from `<body>`  
✅ Cleaned of scripts and styles  
✅ Whitespace normalized  
✅ All visible text text  

### What's NOT Extracted
❌ Scripts, stylesheets, metadata  
❌ Hidden elements  
❌ ARIA-hidden content  

---

## Link Extraction

### What's Extracted
✅ All `<a href="...">text</a>` elements  
✅ Both text and href attributes  
✅ Full URLs (absolute and relative)  

### Filtering
Only links with visible text are included.

**Example Result**:
```python
[
    {"text": "Home", "href": "https://example.com"},
    {"text": "About", "href": "/about"},
    {"text": "Contact", "href": "/contact"},
]
```

---

## Screenshots

All browse and play functions return **PNG screenshots as base64**:

```python
# In response
"screenshot_b64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADU..."

# To save:
import base64
with open("page.png", "wb") as f:
    f.write(base64.b64decode(screenshot_b64))
```

---

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Browse (simple page) | 2-5s | Page load dependent |
| Browse (complex site) | 5-10s | More content = slower |
| Search Google | 5-10s | Depends on search results |
| Summarize | 10-30s | Includes Ollama inference |
| Play YouTube | 5-10s | Video startup time |
| Play Song | 5-10s | Audio startup time |

---

## Security

### What's Secure
✅ No sensitive credentials sent  
✅ Read-only operations (browse, search)  
✅ All through SecurityGateway  
✅ Logged in audit trail  

### What to Avoid
❌ Don't browse untrusted sites (malware risk)  
❌ Don't summarize sensitive documents  
❌ Don't assume extraction is perfect  

---

## Troubleshooting

### Issue: Playwright not installed
```bash
pip install playwright
playwright install chromium
```

### Issue: SSL/Certificate errors
Some sites have SSL issues. Try:
```python
# Playwright handles this on startup
# Usually just retry
```

### Issue: JavaScript not running
Some sites need JavaScript. Playwright waits for:
- Page load: `domcontentloaded`
- Network idle: `networkidle` (10s timeout)

### Issue: Google blocking searches
Google may block automated requests. Only search occasionally.

### Issue: YouTube not loading videos
Try more specific queries:
```python
# Bad: "python"
# Good: "python tutorial for beginners"
play_youtube("python tutorial for beginners")
```

### Issue: Ollama not found for summarization
```bash
# Start Ollama service
ollama serve

# In another terminal
ollama pull llama3
```

---

## Best Practices

1. **Check success flag first**
   ```python
   result = browse(url)
   if not result["success"]:
       print(f"Error: {result['error']}")
       return
   ```

2. **Handle long text**
   ```python
   text = result["text"][:3000]  # Limit to first 3000 chars
   ```

3. **Validate URLs**
   ```python
   if not url.startswith("http"):
       url = "https://" + url
   browse(url)
   ```

4. **Cache results**
   ```python
   # Don't re-browse same URL immediately
   # Results don't change that quickly
   ```

5. **Use search before browse**
   ```python
   # Good: Search first, browse top result
   results = search_web("topic")
   browse(results["results"][0]["url"])
   
   # Avoid: Browsing random URLs
   ```

---

## Testing

### Run Tests
```bash
pytest tests/test_browser.py -v
```

### Manual Testing
```bash
python
>>> from core.browser.web_agent import browse
>>> result = browse("https://example.com")
>>> print(result["title"])
```

---

## Integration with Dashboard

The browser module is fully integrated with NEMO's dashboard:

### New Actions Available
- `browse` - Browse a URL
- `search` - Search Google
- `summarize` - Summarize a page
- `play` - Play a YouTube video
- `play_song` - Play a song

### Usage in Dashboard
```json
{
  "action": "browse",
  "target": "https://docs.python.org"
}
```

### Response Format
Same as direct API calls, includes:
- Success status
- Content (title, text, links, summary)
- Screenshots
- Metadata

---

## Future Enhancements

Possible improvements:
- Multiple search engines (Bing, DuckDuckGo)
- PDF document handling
- Pagination support
- JavaScript form filling
- Cookie/session handling
- Proxy support
- Custom user agents

---

## Support

### Documentation
- **README.md** - Project overview
- **This file** - Browser module guide
- **tests/test_browser.py** - Test examples
- **core/browser/web_agent.py** - Source code

### Resources
- **Playwright Docs**: https://playwright.dev
- **Ollama**: https://ollama.ai
- **Python**: https://python.org

---

**Ready to browse?** Start using the browser module in NEMO! 🚀
