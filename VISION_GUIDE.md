# NEMO Vision Module Guide

## Overview

The NEMO Vision Module adds **AI-powered UI element detection** to the dashboard, allowing smart clicking on named elements instead of hardcoded coordinates.

**Problem Solved:**
- ❌ Old way: Must know exact pixel coordinates `click(100, 200)`
- ✅ New way: Ask for element by name `click("target:Send Button")`

## Features

### 1. Smart Element Finding
- Uses Microsoft's **OmniParser-v2.0** to detect UI elements
- Automatically finds element you describe
- Returns center coordinates for accurate clicking
- Falls back to Ollama LLaVA if OmniParser unavailable

### 2. Element Listing  
- List all detected UI elements in a screenshot
- Get bounding boxes, labels, and confidence scores
- Useful for exploring what's on screen

### 3. Adaptive Workflows
- Handles UI variations (different window sizes, layouts)
- Fuzzy matching for approximate element names
- Confidence scores indicate match quality

## Installation

### 1. Install Vision Dependencies

```bash
pip install torch torchvision transformers timm einops
```

This installs:
- **torch** - PyTorch for ML inference
- **torchvision** - Computer vision utilities
- **transformers** - HuggingFace model loading
- **timm** - Vision model backbones
- **einops** - Tensor operations

### 2. Verify Installation

```bash
python -c "from core.vision.omniparser_vision import find_element; print('✓ Vision module ready')"
```

## Usage

### Dashboard Click Action

**Old Way (Direct Coordinates):**
```json
{
  "action": "click",
  "value": "100,200"
}
```

**New Way (Smart Element Targeting):**
```json
{
  "action": "click",
  "value": "target:Send Button"
}
```

### Python API

```python
from core.vision.omniparser_vision import find_element, list_elements, VisionProvider
import base64

# Load screenshot as base64 string
with open("screenshot.png", "rb") as f:
    screenshot_b64 = base64.b64encode(f.read()).decode()

# Find a specific element
result = find_element(screenshot_b64, "Send Button")
print(f"Found: {result['found']}")
print(f"Location: ({result['x']}, {result['y']})")
print(f"Label: {result['label']}")
print(f"Confidence: {result['confidence']:.2%}")

# Or use the VisionProvider class
result = VisionProvider.find(screenshot_b64, "Send Button")

# List all elements
elements = VisionProvider.list_all(screenshot_b64)
for elem in elements:
    print(f"  {elem['label']:20} at ({elem['x']}, {elem['y']})")
```

## Response Format

### find_element() Result

```json
{
  "found": true,
  "x": 950,
  "y": 542,
  "label": "Send Button",
  "confidence": 0.95
}
```

### list_elements() Result

```json
[
  {
    "label": "Contact Name Input",
    "x": 240,
    "y": 156,
    "width": 320,
    "height": 40,
    "confidence": 0.92
  },
  {
    "label": "Message Text Area",
    "x": 240,
    "y": 220,
    "width": 320,
    "height": 200,
    "confidence": 0.88
  },
  {
    "label": "Send Button",
    "x": 950,
    "y": 542,
    "width": 80,
    "height": 40,
    "confidence": 0.95
  }
]
```

## How It Works

### Processing Pipeline

```
Dashboard Request
    ↓
Parse "target:element_name"
    ↓
Capture Active Window Screenshot (PNG)
    ↓
Decode Base64 to PIL Image
    ↓
Run OmniParser Inference
    ├─ Detect all UI elements
    ├─ Extract bounding boxes (0-1 normalized)
    └─ Get element labels
    ↓
Fuzzy Match "element_name" Against Labels
    ├─ Exact match? → 1.0 confidence
    ├─ Substring match? → 0.8 confidence
    └─ Similarity → SequenceMatcher ratio
    ↓
Scale Bbox to Screen Pixels
    ├─ x1_px = bbox_x1 * screen_width
    ├─ y1_px = bbox_y1 * screen_height
    ├─ (same for x2, y2)
    ↓
Calculate Center Coordinates
    ├─ center_x = (x1_px + x2_px) / 2
    └─ center_y = (y1_px + y2_px) / 2
    ↓
Click at (center_x, center_y)
    ↓
Return Success with Found Label & Confidence
```

## Fallback Mechanism

If OmniParser model fails to load or inference fails:

1. **Automatically** falls back to **Ollama LLaVA**
2. Requires Ollama running at `localhost:11434` with `llava` model
3. Sends screenshot + prompt to Ollama
4. Parses JSON response for coordinates
5. **Same result format** — code doesn't need changes

### Ollama Setup (Optional Fallback)

```bash
# Install Ollama: https://ollama.ai

# Pull llava model
ollama pull llava

# Start Ollama service
ollama serve

# In another terminal, test it:
curl http://localhost:11434/api/generate -X POST \
  -d '{"model": "llava", "prompt": "test"}'
```

## Element Matching

### Fuzzy Matching Strategy

The vision module uses **three-tier matching**:

1. **Exact Match** (confidence: 1.0)
   - `target: "Send Button"` → Element label: "Send Button"
   - Case-insensitive comparison

2. **Substring Match** (confidence: 0.8)
   - `target: "Send"` → Element label: "Send Button"
   - One string contains the other

3. **Similarity Match** (confidence: 0.0-0.7)
   - `target: "Submit Button"` → Element label: "Send Button"
   - Uses SequenceMatcher ratio

### Example Matches

| Target | Label | Method | Confidence |
|--------|-------|--------|-----------|
| "send button" | "Send Button" | Exact | 1.0 |
| "send" | "Send Button" | Substring | 0.8 |
| "submit" | "Send Button" | Similarity | ~0.5 |
| "button" | "Send Button" | Substring | 0.8 |

## Performance Considerations

### Model Loading (First Time)
- OmniParser downloads ~1-2 GB from HuggingFace
- Cached after first load
- Can take 5-10 minutes on first run
- Subsequent loads are instant (from cache)

### Inference Speed
- First inference: 2-5 seconds (model warmup)
- Subsequent inferences: 0.5-2 seconds
- Depends on screenshot size and GPU availability

### Memory Usage
- Model + tensors: ~2-3 GB RAM
- Loaded once (singleton pattern)
- Thread-safe for concurrent requests

## Troubleshooting

### Issue: OmniParser Model Fails to Load

```
[WARNING] Failed to load OmniParser model
[INFO] Will fall back to Ollama LLaVA for vision
```

**Solution 1: Install PyTorch**
```bash
pip install torch torchvision transformers timm einops
```

**Solution 2: Or use Ollama fallback**
```bash
ollama pull llava
ollama serve
```

### Issue: Element Not Found

**Cause 1: Poor match confidence**
- Try being more specific with element name
- Use element's actual visible text

**Cause 2: OmniParser didn't detect element**
- Fall back to Ollama LLaVA
- Or use direct coordinates

**Debug:**
```python
# List all detected elements to see what's available
elements = list_elements(screenshot_b64)
print("Detected elements:")
for e in elements:
    print(f"  - {e['label']}")
```

### Issue: Wrong Element Clicked

**Solution:**
- Increase fuzzy match specificity
- Use more unique element names
- Check `list_elements()` output to verify detection

## Advanced Usage

### Custom Screen Dimensions

If auto-detection doesn't work:

```python
result = find_element(
    screenshot_b64, 
    "Send Button",
    screen_width=1920,
    screen_height=1080
)
```

### Element Exploration

```python
# Explore what's on screen before clicking
elements = list_elements(screenshot_b64)

# Find clickable buttons
buttons = [e for e in elements if 'button' in e['label'].lower()]
print(f"Found {len(buttons)} buttons")

# Print with positions
for btn in buttons:
    print(f"  {btn['label']:30} at ({btn['x']:4}, {btn['y']:4})")
```

### Batch Operations

```python
from core.vision.omniparser_vision import VisionProvider
import pyautogui

# Use vision to navigate a workflow
steps = [
    ("target: Login Field", "username@example.com"),
    ("target: Password Field", "secret123"),
    ("target: Login Button", None),  # Just click
    ("target: Proceed Button", None),
]

screenshot = _capture_screenshot()

for target, text in steps:
    result = VisionProvider.find(screenshot, target)
    if result['found']:
        pyautogui.click(result['x'], result['y'])
        if text:
            pyautogui.typewrite(text)
```

## Testing

### Run Test Suite

```bash
pytest tests/test_vision.py -v
```

### Manual Test

```bash
# Capture a screenshot from your app
# Then test element detection

python
>>> from core.vision.omniparser_vision import list_elements
>>> import base64
>>> with open('screenshot.png', 'rb') as f:
...     b64 = base64.b64encode(f.read()).decode()
>>> elements = list_elements(b64)
>>> for e in elements[:5]:
...     print(f"{e['label']}: {e['confidence']:.2%}")
```

## Integration with OpenClaw

The vision module is designed to work seamlessly with **OpenClaw** agent workflows:

```python
# OpenClaw agent can now do:
agent.click("target: Continue Button")  # Smart clicking
agent.type("target: Email Field", "user@example.com")  # Adaptive typing
agent.verify("target: Success Message", "visible")  # Vision verification
```

## Security Note

Vision operations are **security-checked** like all NEMO actions:
- Pass through SecurityGateway threat detection
- Logged in audit trail
- Subject to user permissions
- Can be restricted by role/path

## Resources

- **OmniParser**: https://huggingface.co/microsoft/OmniParser-v2.0
- **Ollama**: https://ollama.ai
- **HuggingFace**: https://huggingface.co
- **NEMO Security**: See [SECURITY_ARCHITECTURE.md](../SECURITY_ARCHITECTURE.md)

---

**Next**: Try it out! Enable vision in your dashboard and start using `"target:"` syntax.
