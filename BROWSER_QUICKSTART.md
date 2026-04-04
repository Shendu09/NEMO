# NEMO Browser Module - Quick Start

## What's New

NEMO can now **browse the web, search, summarize content, and play videos**!

- 🌐 **Browse** any website and extract content
- 🔍 **Search** Google for information  
- 📝 **Summarize** pages with AI (Ollama)
- ▶️ **Play** YouTube videos
- 🎵 **Play** songs from YouTube

---

## Installation (2 minutes)

### Step 1: Install Playwright
```bash
pip install playwright nest-asyncio
playwright install chromium
```

### Step 2: Verify
```bash
python -c "from core.browser.web_agent import browse; print('✓')"
```

### Step 3 (Optional): Install Ollama for Summarization
```bash
# Download from https://ollama.ai
ollama pull llama3
ollama serve  # In separate terminal
```

---

## Quick Examples

### 🌐 Browse a Website
```python
from core.browser.web_agent import browse

result = browse("https://python.org")
print(f"Title: {result['title']}")
print(f"Links: {len(result['links'])}")
print(f"Text: {result['text'][:200]}...")
```

### 🔍 Search Google
```python
from core.browser.web_agent import search_web

result = search_web("python tutorial")
for i, res in enumerate(result["results"][:3], 1):
    print(f"{i}. {res['title']}")
    print(f"   {res['url']}")
```

### 📝 Summarize a Page
```python
from core.browser.web_agent import summarize_page

result = summarize_page("https://wikipedia.org/wiki/Python")
print(f"Summary: {result['summary']}")
```

### ▶️ Play a Video
```python
from core.browser.web_agent import play_youtube

result = play_youtube("learn python")
if result["success"]:
    print(f"Playing: {result['video_title']}")
```

### 🎵 Play a Song
```python
from core.browser.web_agent import play_song

result = play_song("Imagine John Lennon")
if result["success"]:
    print(f"Now playing: {result['video_title']}")
```

---

## Dashboard Usage

### Browse Action
```json
{
  "action": "browse",
  "target": "https://example.com"
}
```

### Search Action
```json
{
  "action": "search",
  "value": "python programming"
}
```

### Summarize Action
```json
{
  "action": "summarize",
  "target": "https://example.com"
}
```

### Play Video Action
```json
{
  "action": "play",
  "value": "python tutorial"
}
```

### Play Song Action
```json
{
  "action": "play_song",
  "value": "Imagine"
}
```

---

## What Gets Extracted

### From browse()
✅ **Title** - Page title  
✅ **Text** - Cleaned main content (no scripts/styles)  
✅ **Links** - All `<a>` tags with text  
✅ **Screenshot** - Full page as PNG base64  

### From search_web()
✅ **Top 5 results** from Google  
✅ **Title** - Result title  
✅ **URL** - Result link  
✅ **Snippet** - Short description  

### From summarize_page()
✅ **Summary** - 3-5 sentence AI summary  
✅ **Uses** Ollama llama3 model  
✅ **Processes** first 3000 chars for speed  

### From play_youtube()
✅ **Video Title**  
✅ **Browser Window** (with video playing)  
✅ **Screenshot** - Player state captured  

---

## Key Differences

| Method | Headless | Speed | Use Case |
|--------|----------|-------|----------|
| browse() | Yes | Fast | Scrape content |
| search() | Yes | Fast | Find links |
| summarize() | Yes | Slow* | Understand content |
| play_youtube() | No | Normal | Watch videos |
| play_song() | No | Normal | Listen to audio |

*Summarization is slow because it waits for Ollama AI inference

---

## Requirements

### Python
- `playwright>=1.40.0` - Web automation
- `nest-asyncio>=1.5.8` - Async handling
- `requests>=2.31.0` - Already in requirements

### System
- **Chromium** - Installed via `playwright install chromium`
- **Internet connection** - For browsing

### Optional
- **Ollama** - For summarization (https://ollama.ai)

---

## Common Tasks

### Task 1: Research a Topic
```python
from core.browser.web_agent import search_web, summarize_page

# Search
results = search_web("quantum computing")

# Summarize first result
summary = summarize_page(results["results"][0]["url"])

print(f"Summary: {summary['summary']}")
```

### Task 2: Check Website Status
```python
from core.browser.web_agent import browse

result = browse("https://status.github.com")
if result["success"]:
    print("✓ Website is up")
    print(f"Title: {result['title']}")
else:
    print(f"✗ Website down: {result['error']}")
```

### Task 3: Find and Watch a Tutorial
```python
from core.browser.web_agent import play_youtube

result = play_youtube("how to use python flask")
if result["success"]:
    print(f"Watching: {result['video_title']}")
    # Video is now playing in browser window
```

### Task 4: Multi-Step Research
```python
from core.browser.web_agent import search_web, browse, summarize_page

query = "machine learning"

# 1. Search
results = search_web(query)
print(f"Found {len(results['results'])} results")

# 2. Browse top 3
for res in results["results"][:3]:
    data = browse(res["url"])
    print(f"\n{data['title']}")
    
    # 3. Summarize
    summary = summarize_page(res["url"])
    print(f"Summary: {summary['summary']}")
```

---

## Performance Tips

1. **Reuse search results** - Don't search the same query repeatedly
2. **Limit text extraction** - Use first 1000-3000 chars for summaries
3. **Cache pages** - Don't browse same URL multiple times
4. **Use specific queries** - "python tutorial" better than "python"
5. **Close browser** - For play_youtube(), browser closes after

---

## Debugging

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("nemo.browser")
logger.setLevel(logging.DEBUG)

from core.browser.web_agent import browse
result = browse("https://example.com")
```

### Check Structure
```python
import json

result = browse("https://example.com")
print(json.dumps({
    "success": result["success"],
    "title": result["title"],
    "text_length": len(result["text"]),
    "link_count": len(result["links"]),
}, indent=2))
```

### Verify Ollama
```bash
curl http://localhost:11434/api/generate -X POST \
  -d '{"model": "llama3", "prompt": "test"}'
```

---

## Testing

### Run Test Suite
```bash
pytest tests/test_browser.py -v
```

### Run Specific Test
```bash
pytest tests/test_browser.py::test_browse_simple_page -v
```

---

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| ModuleNotFoundError: playwright | Not installed | `pip install playwright` |
| Chromium not found | Browser not installed | `playwright install chromium` |
| Connection timeout | Site blocked/slow | Increase timeout in code |
| Ollama not available | Service not running | `ollama serve` |
| Google blocking | Too many searches | Wait between searches |

---

## Features at a Glance

| Feature | Status | What It Does |
|---------|--------|-------------|
| browse() | ✅ | Open URL, extract content |
| search_web() | ✅ | Google search, top 5 results |
| summarize_page() | ✅ | AI summary with Ollama |
| play_youtube() | ✅ | Search & play first video |
| play_song() | ✅ | Search & play song |
| Screenshots | ✅ | All in base64 PNG |
| Link extraction | ✅ | All `<a>` tags with text |
| Text cleaning | ✅ | No scripts/styles |

---

## Integration Points

✅ **Dashboard**: New actions (browse, search, summarize, play, play_song)  
✅ **Security**: Goes through SecurityGateway  
✅ **Audit**: All operations logged  
✅ **API**: Full REST integration  

---

## Next Steps

1. **Install**: `pip install playwright nest-asyncio`
2. **Test**: `pytest tests/test_browser.py -v`
3. **Use**: Try one of the quick examples
4. **Deploy**: Use in dashboard with actions

---

## Documentation

- **[BROWSER_GUIDE.md](BROWSER_GUIDE.md)** - Complete reference
- **[tests/test_browser.py](tests/test_browser.py)** - Test examples
- **[core/browser/web_agent.py](core/browser/web_agent.py)** - Source code

---

**Ready to browse the web with NEMO!** 🚀

```json
{
  "action": "browse",
  "target": "https://your-url.com"
}
```
