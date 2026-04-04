# NEMO Vision Module - Quick Start

## What's New

NEMO now has **AI-powered vision** to find and click UI elements by name, not just coordinates!

### Before (Old Way)
```python
pyautogui.click(100, 200)  # Must know exact pixels
```

### After (New Way)
```python
# Dashboard smart click
{"action": "click", "value": "target:Send Button"}

# Python API
find_element(screenshot, "Send Button")  # Returns coordinates
```

## Installation (5 minutes)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
# OR manually:
pip install torch torchvision transformers timm einops
```

### Step 2: Verify
```bash
python -c "from core.vision.omniparser_vision import find_element; print('✓ OK')"
```

## Usage

### In Dashboard
Replace hardcoded coordinates with smart targeting:

```json
{
  "action": "click",
  "value": "target:Send Button"
}
```

The system will:
1. Take a screenshot
2. Find "Send Button" using AI
3. Click at the detected location
4. Return success with confidence score

### In Python
```python
from core.vision.omniparser_vision import find_element, list_elements

# Find element
result = find_element(screenshot_b64, "Send Button")
if result['found']:
    print(f"Click at ({result['x']}, {result['y']})")

# List all elements
elements = list_elements(screenshot_b64)
for e in elements:
    print(f"  {e['label']} at ({e['x']}, {e['y']})")
```

## How It Works

```
"target:Send Button"
    ↓
Capture screenshot
    ↓
Run OmniParser (AI model)
    ↓
Detect all UI elements
    ↓
Fuzzy match "Send Button"
    ↓
Get center coordinates
    ↓
Click!
```

## First Run Notes

- **First inference**: 2-5 minutes (downloads model from HuggingFace)
- **Subsequent**: 0.5-2 seconds per inference
- **Model size**: ~1-2 GB (cached after download)

## Fallback

If OmniParser fails, system automatically falls back to **Ollama LLaVA**:

```bash
# Optional: Setup Ollama for fallback
ollama pull llava
ollama serve
```

No code changes needed — fallback is automatic.

## Command Examples

### Simple Target Matching
```
target:Send Button       → Exact or fuzzy match
target:Cancel            → Match "Cancel Button"
target:OK                → Match "OK" in any context
target:button            → Match any visible button
```

### When to Use "target:" vs Coordinates

| Scenario | Use |
|----------|-----|
| Target doesn't move | Coordinates (faster) |
| Target position varies | target: (adaptive) |
| Testing/automation | target: (robust) |
| Performance critical | Coordinates |

## Testing

```bash
# Run tests
pytest tests/test_vision.py -v

# Run interactive demo
python demo_vision.py

# Try manually
python
>>> from core.vision.omniparser_vision import list_elements
>>> from bridge.nemo_server import _capture_screenshot
>>> ss = _capture_screenshot()
>>> elements = list_elements(ss)
>>> print(f"Found {len(elements)} elements")
```

## Troubleshooting

### Error: "No module named 'torch'"
```bash
pip install torch torchvision transformers timm einops
```

### Error: "OmniParser model failed to load"
- Check internet connection (needs to download from HuggingFace)
- Or setup Ollama fallback: `ollama serve`

### Element not found
```python
# Debug what's detected:
elements = list_elements(screenshot)
for e in elements:
    print(e['label'])  # See actual element names
```

### Wrong element clicked
- Be more specific: "Send Message" vs "Send"
- Check confidence score
- Use list_elements() to verify

## Features Enabled

✅ Smart element detection
✅ Fuzzy matching
✅ Adaptive UI handling
✅ Confidence scoring
✅ Ollama fallback
✅ Element listing
✅ Thread-safe model loading
✅ Security-checked operations

## Documentation

- **[VISION_GUIDE.md](VISION_GUIDE.md)** - Detailed guide with examples
- **[tests/test_vision.py](tests/test_vision.py)** - Test suite
- **[demo_vision.py](demo_vision.py)** - Interactive demo
- **[core/vision/omniparser_vision.py](core/vision/omniparser_vision.py)** - Source

## Architecture

```
NEMO Dashboard
  ↓
_action_click("target:element_name")
  ↓
find_element(screenshot, "element_name")
  ↓
OmniParser (or Ollama fallback)
  ↓
Fuzzy match
  ↓
Return coordinates
  ↓
pyautogui.click(x, y)
```

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Screenshot capture | 0.2s | Fast |
| First OmniParser load | 2-5s | Model warmup |
| OmniParser inference | 0.5-2s | Subsequent runs |
| Ollama inference | 5-10s | Slower fallback |
| Fuzzy matching | <0.1s | Fast |

## Security

Vision operations are subject to NEMO security:
- ✅ Threat detection scan
- ✅ Permission checks
- ✅ Audit logging
- ✅ User tracking

No blindside access — all through SecurityGateway.

## Next Steps

1. ✅ Install dependencies
2. ✅ Run `pytest tests/test_vision.py -v`
3. ✅ Try `python demo_vision.py`
4. ✅ Use "target:" in dashboard
5. 📖 Read [VISION_GUIDE.md](VISION_GUIDE.md) for details

---

**Ready?** Start using `"target:Element Name"` in your dashboard clicks!
