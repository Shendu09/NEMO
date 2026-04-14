# 🤖 NEMO-OS v3.0.0

**NEMO** (Networked Extensible Machine Operating system) is a security-hardened automation layer for Windows that enables safe, controlled PC operation through voice commands, HTTP APIs, and intelligent automation.

## ✨ Features

- ** Voice Control**: Speak commands like "V open chrome" or "V search for face prep"
- ** HTTP API**: RESTful interface on `localhost:8765` for script integration
- ** Security-First**: RBAC with Auth0 integration, audit logging, risk classification
- **Vision AI**: EasyOCR-based Chrome profile picker auto-detection
- ** Web Automation**: Browser control, search, screenshot, summarize
- **⚡ Windows Apps**: Launch Edge, Chrome, WhatsApp, Discord, Spotify, PyCharm, Jupyter
- **🔐 Action Confirmation**: LOW/MEDIUM/HIGH risk assessment with approval flow

## 🚀 Quick Start

### Prerequisites
- Windows 10/11
- Python 3.10+
- Dependencies: `pip install -r requirements.txt`

### Installation

```bash
# Clone and navigate
cd NEMO

# Install dependencies
pip install -r requirements.txt

# Run NEMO
python clevrr_service.py run
```

NEMO will start with:
- HTTP API: `http://localhost:8765`
- Dashboard: `http://localhost:8766`
- Voice Listener: Say "V <command>"

## 📡 HTTP API

### Endpoint: `/execute`

**Request:**
```json
{
  "action": "open_app",
  "target": "chrome",
  "value": "Bushra",
  "user": "test"
}
```

### Supported Actions

| Action | Target | Value | Example |
|--------|--------|-------|---------|
| `open_app` | chrome, edge, whatsapp, discord, etc. | Profile (Chrome) | `open_app` → `chrome` → `Bushra` |
| `search` | - | Search query | `search` → `face prep` |
| `screenshot` | - | - | `screenshot` |
| `type` | - | Text | `type` → `hello world` |
| `type_code` | - | Code | `type_code` → `print("hello")` |
| `press_key` | - | Key name | `press_key` → `enter` |
| `click` | - | Coordinates | `click` → `100,200` |
| `browse` | URL | - | `browse` → `https://example.com` |
| `wait` | - | Seconds | `wait` → `2` |
| `summarize` | - | - | `summarize` |
| `play` | - | Song/URL | `play` → `Shape of You` |

### Response
```json
{
  "success": true,
  "action": "open_app",
  "app": "chrome",
  "exe_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "window_focused": true
}
```

## 🎙️ Voice Commands

Say **"V"** followed by your command:

```
"V open chrome"
"V open edge bushra"
"V search for face prep"
"V take screenshot"
"V press enter"
"V click 500 300"
"V type hello world"
```

## 🏗️ Architecture

```
NEMO/
├── bridge/                    # HTTP API Server (Flask)
│   ├── nemo_server.py        # REST endpoints & action executor
│   ├── dashboard.py          # Web dashboard
│   ├── templates/            # HTML templates
│   └── static/               # JS, CSS
├── core/
│   ├── browser/              # Web automation (browsing, search, screenshots)
│   ├── vision/               # OCR for Chrome profile picker (EasyOCR)
│   ├── voice/                # Voice recognition (Whisper)
│   ├── bus/                  # IPC for inter-process communication
│   └── security/             # RBAC, audit, risk classification
├── actions/                  # Action executor interface
├── clevrr_service.py         # Main service entry point
└── requirements.txt          # Python dependencies
```

## 🔒 Security Model

NEMO uses **layered security**:

1. **Risk Classification** (`LOW` / `MEDIUM` / `HIGH`)
   - HIGH risk actions require token-based approval
   - Returns `requires_confirmation: true` with token

2. **RBAC with Auth0**
   - `pc:admin` → Full access
   - `pc:write` → Standard operations
   - `pc:read` → View-only

3. **Audit Logging**
   - All actions logged to `clevrr_data/audit.jsonl`
   - User, action, timestamp, allowed/denied

4. **Action Confirmation Flow**
```
/execute (HIGH risk) 
  ↓
requires_confirmation: true + token
  ↓
/confirm?token=xxx&proceed=true
  ↓
Action executed
```

## 📊 Chrome Profile Picker

When opening Chrome with a profile:
1. Chrome launches with `--profile-directory` flag
2. If profile picker appears, EasyOCR auto-detects profile names
3. Automatically clicks the requested profile

**Example:**
```
POST /execute
{
  "action": "open_app",
  "target": "chrome",
  "value": "Bushra"
}
↓
Browser launches → Profile picker appears → 
OCR reads: "Default", "Bushra", "V"
→ Clicks "Bushra" automatically
```

## 🛠️ Common Tasks

### Open Chrome with Profile and Search
```bash
curl -X POST http://localhost:8765/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action": "open_app",
    "target": "chrome",
    "value": "Bushra",
    "user": "test"
  }'
```

### Take Screenshot
```bash
curl -X POST http://localhost:8765/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action": "screenshot",
    "user": "test"
  }'
```

### Search Web
```bash
curl -X POST http://localhost:8765/execute \
  -H "Content-Type: application/json" \
  -d '{
    "action": "search",
    "value": "face prep",
    "user": "test"
  }'
```

## 🎯 Workflow Example

**Task:** Open Chrome with Bushra profile and search for Face Prep

```bash
# 1. Open Chrome
curl http://localhost:8765/execute \
  -d '{"action":"open_app","target":"chrome","value":"Bushra","user":"test"}' \
  -H "Content-Type: application/json"

# 2. Search (in browser)
curl http://localhost:8765/execute \
  -d '{"action":"search","value":"face prep","user":"test"}' \
  -H "Content-Type: application/json"

# 3. Screenshot
curl http://localhost:8765/execute \
  -d '{"action":"screenshot","user":"test"}' \
  -H "Content-Type: application/json"
```

## 📋 Supported Applications

| App | Launch | Version |
|-----|--------|---------|
| Chrome | ✅ | Latest |
| Edge | ✅ | Latest |
| WhatsApp | ✅ | Desktop |
| Telegram | ✅ | Desktop |
| Discord | ✅ | Latest |
| Spotify | ✅ | Latest |
| PyCharm | ✅ | Community/Pro |
| Jupyter | ✅ | Notebook |

## 🐛 Troubleshooting

### NEMO won't start
```bash
python -c "import bridge.nemo_server; print('OK')"
```

### Port 8765 in use
```bash
netstat -ano | findstr 8765
taskkill /PID <PID> /F
```

### Chrome profile picker not detecting profiles
- EasyOCR model downloads on first run (~5-10 minutes)
- Ensure `easyocr` is installed: `pip install easyocr`

### Voice not working
- Check microphone permissions
- Ensure `faster-whisper` is installed: `pip install faster-whisper`

## 📚 Dependencies

See [requirements.txt](requirements.txt) for full list:
- Flask (HTTP API)
- pyautogui (keyboard/mouse)
- win32gui/ctypes (Windows API)
- EasyOCR (Chrome profile detection)
- faster-whisper (voice recognition)
- requests (HTTP client)

## 📝 License

Proprietary - NEMO-OS Security Automation Layer

## 🔗 Related

- **OpenClaw**: Underlying integration framework
- **Audit Logs**: `clevrr_data/audit.jsonl`
- **User DB**: `clevrr_data/users.json`

---

**Status**: Production Ready | **Platform**: Windows 10/11 | **Version**: 3.0.0
