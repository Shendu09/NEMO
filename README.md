# NEMO: Secure OS Automation Layer

> **N**ow **E**nabling **M**any **O**perations securely for AI agents

NEMO is an **enterprise-grade security layer** for AI agents that need to interact with operating systems. It provides controlled, audited access to OS operations while preventing malicious actions through threat detection, permission management, and cryptographic audit logging.

## 🎯 Key Features

### Security-First Design
- **Defense in Depth**: Multiple security layers (threat detection → permissions → execution → audit)
- **Zero Trust Architecture**: Every action validated, even by admins
- **Tamper-Proof Audit Log**: Cryptographically hash-chained, append-only logging
- **Thread-Safe**: Production-ready concurrent operation handling

### Access Control
- **Role-Based Access Control (RBAC)**: 4 roles (ADMIN, USER, RESTRICTED, GUEST)
- **16 Action Categories**: Fine-grained permission control
  - File operations (read, write, delete)
  - Process management (spawn, kill)
  - Network requests
  - System configuration
  - Keyboard/mouse/clipboard input
  - Screenshot capture
  - Windows registry access
  - Service control
  - Package installation

### Threat Detection
Identifies and blocks:
- **Prompt Injection**: Jailbreak attempts, instruction overrides
- **Dangerous Commands**: `rm -rf /`, fork bombs, reverse shells, disk writes
- **Data Exfiltration**: Credential theft, sensitive file access
- **Privilege Escalation**: Unauthorized elevation attempts

### AI Vision (New!)
- **OmniParser Integration**: AI-powered UI element detection
- **Smart Clicking**: Find elements by name, not just coordinates (`"target:Send Button"`)
- **Element Listing**: Enumerate all UI elements with confidence scores
- **Ollama Fallback**: Graceful degradation to LLaVA for vision tasks
- **Adaptive Workflows**: Handles UI variations and layout changes

### Comprehensive Audit Trail
- Per-action logging with timestamps
- User identity tracking
- Success/failure status
- Chain integrity verification
- Persistent JSON storage

## 🏗️ Architecture

```
AI Agent / Application
        ↓
    SecurityGateway (Single Entry Point)
        ↓
    ┌───┴───┬───────────┬──────────┐
    ↓       ↓           ↓          ↓
 Threat  Permission   Action    Audit
Detector  Engine     Sandbox    Logger
    ↓       ↓           ↓          ↓
    └───┬───┴───────────┴──────────┘
        ↓
    OS Operations
```

### Components

| Component | Purpose | File |
|-----------|---------|------|
| **SecurityGateway** | Single entry point, orchestrates all checks | `core/security/gateway.py` |
| **Permission Engine** | RBAC implementation, user management | `core/security/permissions.py` |
| **Threat Detector** | Pattern-based threat analysis | `core/security/threat_detector.py` |
| **Audit Logger** | Hash-chained tamper-evident logging | `core/security/audit_logger.py` |
| **Action Executor** | OS automation (keyboard, mouse, screen) | `actions/executor.py` |
| **Message Bus** | Async action queueing and execution | `core/bus/` |
| **Dashboard** | Real-time monitoring and verification | `bridge/dashboard.py` |

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd NEMO

# Install dependencies
pip install -r requirements.txt
```

### Start Complete NEMO System

Start all components (BusServer, SecurityGateway, AuditLogger, HTTP API, Voice Listener, Health Monitor):

```bash
python clevrr_service.py run
```

You'll see:
```
╔══════════════════════════════════════╗
║         NEMO-OS  is  running         ║
║  HTTP  →  http://localhost:8765      ║
║  Dashboard → http://localhost:8766   ║
║  Voice → Say  "V <your command>"    ║
╚══════════════════════════════════════╝
```

### Execute Commands via CLI

Test NEMO without voice interaction using the `--task` argument:

```bash
# Play a YouTube video
python clevrr_service.py run --task "play BTS V on youtube"

# Summarize a webpage
python clevrr_service.py run --task "summarize https://bbc.com"

# Send a message via WhatsApp
python clevrr_service.py run --task "open whatsapp and send hi to Rohitha"

# Open an app and search
python clevrr_service.py run --task "open chrome and search for python"
```

The task executes immediately while NEMO stays running. You can then use voice commands or stop with `Ctrl+C`.

### System Architecture

```
┌─────────────────────────────────────────────┐
│  clevrr_service.py (Main Orchestrator)      │
├─────────────────────────────────────────────┤
│  1. BusServer (IPC message queue)           │
│  2. SecurityGateway (RBAC + threat detect)  │
│  3. AuditLogger (tamper-proof logging)      │
│  4. HTTP API Server (Flask on :8765)         │
│  5. Voice Listener (speech recognition)     │
│  6. Health Monitor (system health checks)   │
└─────────────────────────────────────────────┘
         ↓
    [All components running in daemon threads]
         ↓
    [Keep-alive loop: while True: time.sleep(1)]
```

### Basic Usage

```python
from core.security import SecurityGateway, Role

# Initialize gateway
gateway = SecurityGateway(dry_run=False)

# Create users with different roles
gateway.add_user("alice", "Alice Admin", Role.ADMIN)
gateway.add_user("bob", "Bob Limited", Role.USER, 
                 allowed_paths=["/home/bob/*", "/tmp/*"])
gateway.add_user("charlie", "Charlie Guest", Role.GUEST)

# Execute secure commands
result = gateway.run_command("alice", "ls -la /home")
if result.success:
    print(f"Output: {result.output}")

# Read files securely
result = gateway.read_file("bob", "/tmp/data.txt")

# Take screenshots
result = gateway.take_screenshot("alice")

# Verify audit integrity
is_valid, error = gateway.verify_audit_chain()
print(f"Audit log valid: {is_valid}")
```

### Vision-Based UI Detection (New!)

```python
from core.vision.omniparser_vision import find_element, list_elements

# Find an element by name using AI
result = find_element(screenshot_b64, "Send Button")
if result['found']:
    print(f"Click at ({result['x']}, {result['y']})")

# Or in dashboard: {"action": "click", "value": "target:Send Button"}

# List all detected elements
elements = list_elements(screenshot_b64)
for elem in elements:
    print(f"  {elem['label']} at ({elem['x']}, {elem['y']})")
```

### Voice Commands (New!)

After starting NEMO, speak voice commands:

```bash
# Start NEMO with voice listening
python clevrr_service.py run

# Then speak into your microphone:
"V open chrome"              # Opens Chrome
"BE search for python"       # Searches for Python
"WE play the song thriller"  # Plays song on YouTube
"B take a screenshot"        # Captures screen
"VI type hello world"        # Types text
```

For detailed voice documentation, see [VOICE_GUIDE.md](VOICE_GUIDE.md).

## 📱 Voice Commands

The NEMO voice system provides real-time speech recognition:

**Wake Words**: V, BE, WE, B, VI

**Common Commands**:
- `"open <app>"` - Open applications (Chrome, WhatsApp, Slack, etc.)
- `"search for <term>"` - Web search
- `"type <text>"` - Input text
- `"play <video>"` - Play YouTube videos
- `"play the song <song>"` - Play songs
- `"summarize <url>"` - AI webpage summarization
- `"take a screenshot"` - Capture screen

See [VOICE_GUIDE.md](VOICE_GUIDE.md) and [VOICE_QUICKSTART.md](VOICE_QUICKSTART.md) for complete voice documentation.

## 📋 Usage Guide

See [USAGE_GUIDE.md](USAGE_GUIDE.md) for comprehensive examples including:
- User creation and management
- Running commands
- File operations (read, write, delete)
- Input simulation (keyboard, mouse, clipboard)
- Screenshot capture
- Audit log queries

## 👁️ Vision Module

See [VISION_QUICKSTART.md](VISION_QUICKSTART.md) for vision capabilities:
- Smart element detection using OmniParser
- Click on named UI elements (not just coordinates)
- Fuzzy matching for element names
- Element listing and exploration
- Ollama fallback for vision

For detailed vision documentation, see [VISION_GUIDE.md](VISION_GUIDE.md).

## 🔐 Security Architecture

For detailed security model, threat patterns, and implementation details, see [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md).

### Authorization Decision Flow

```
User Request
    ↓
[1] Threat Scan
    ├─ Detected? → DENY (Log threat)
    └─ Safe? → Continue
    ↓
[2] Permission Check
    ├─ User disabled? → DENY
    ├─ Role has permission? → Continue
    ├─ Path whitelisted? → Continue
    └─ Else? → DENY
    ↓
[3] Sandbox Execution
    ├─ Dry-run mode enabled? → Log only
    └─ Else? → Execute
    ↓
[4] Audit Log
    └─ Record result + reason
```

## 🎬 Integration with OpenClaw

NEMO is integrated with **OpenClaw**, an AI agent framework that provides:
- **Vision/Screenshot Analysis**: AI sees what's on screen
- **Smart Locating**: Finds UI elements without hardcoded coordinates
- **Action Verification**: Confirms actions succeeded
- **Adaptive Workflows**: Handles UI variations

**Why OpenClaw + NEMO?**

| Aspect | NEMO Only | NEMO + OpenClaw |
|--------|-----------|-----------------|
| Command execution | ✅ | ✅ |
| Verify success | ❌ | ✅ Vision-based |
| Find UI elements | ❌ Fixed coords only | ✅ AI vision |
| Handle UI changes | ❌ Breaks | ✅ Adapts |
| Complex workflows | ❌ Blind execution | ✅ Intelligent |

See [openclaw/README.md](openclaw/README.md) for OpenClaw integration details.

## 📊 Dashboard

Real-time monitoring interface at `http://localhost:5000`

Features:
- Live action log with status
- Audit trail with timestamps
- Security event dashboard
- User activity tracking
- Manual verification workflow

Run dashboard:
```bash
python bridge/nemo_server.py
```

## 📁 Project Structure

```
NEMO/
├── core/                          # Core security & infrastructure
│   ├── security/                  # Security components
│   │   ├── gateway.py             # SecurityGateway
│   │   ├── permissions.py         # RBAC engine
│   │   ├── threat_detector.py     # Threat analysis
│   │   └── audit_logger.py        # Audit logging
│   └── bus/                       # Message bus for async operations
├── actions/                       # Action execution
│   └── executor.py                # OS automation (keyboard, mouse, screen)
├── bridge/                        # Dashboard & web interface
│   ├── nemo_server.py            # Flask server
│   ├── dashboard.py              # Dashboard logic
│   └── static/                   # Frontend assets
├── vision/                        # Vision & screenshot analysis
│   └── screen_vision.py          # Screen vision capabilities
├── openclaw/                      # OpenClaw integration
│   └── ...                        # AI agent framework
├── tests/                         # Unit & integration tests
├── clevrr_data/                  # Runtime data (users, audit logs)
├── USAGE_GUIDE.md                # User documentation
├── SECURITY_ARCHITECTURE.md      # Security details
├── HONEST_ASSESSMENT.md          # Current limitations
└── requirements.txt              # Python dependencies
```

## 🧪 Testing

Run tests:

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_security.py

# With coverage
pytest --cov=core tests/
```

Key test files:
- `tests/test_security.py` - Core security functionality
- `tests/test_security_v2.py` - Advanced scenarios
- `tests/test_executor.py` - Action execution
- `tests/test_bus.py` - Message bus operations
- `tests/test_nemo_server.py` - Dashboard server

## ⚠️ Known Limitations

**Current State:**
- NEMO executes actions **blindly** - cannot verify success
- Requires fixed widget coordinates
- Breaks if UI layout changes
- Cannot handle unexpected situations

**Solution in Progress:**
- OpenClaw vision integration for verification
- AI-powered element detection
- Adaptive action sequences

See [HONEST_ASSESSMENT.md](HONEST_ASSESSMENT.md) for detailed analysis.

## 🔧 Configuration

### Environment Variables

```bash
# Data directory for users & audit logs
export NEMO_DATA_DIR=/var/nemo/security

# Dry-run mode (logs actions without executing)
export NEMO_DRY_RUN=true

# Dashboard port
export NEMO_DASHBOARD_PORT=5000
```

### Gateway Initialization

```python
from pathlib import Path
from core.security import SecurityGateway

# Custom data directory
gateway = SecurityGateway(
    data_dir=Path("/var/nemo/security"),
    dry_run=False
)
```

## 📚 Documentation

- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - How to use NEMO
- **[SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md)** - Security model & components
- **[HONEST_ASSESSMENT.md](HONEST_ASSESSMENT.md)** - Limitations & solutions
- **[openclaw/README.md](openclaw/README.md)** - OpenClaw integration

## 🤝 Contributing

1. Create a feature branch
2. Make changes with security in mind
3. Add/update tests
4. Submit pull request

## 📄 License

See [LICENSE](LICENSE) file.

## 🆘 Support

For issues, questions, or integration requests:
- Check [USAGE_GUIDE.md](USAGE_GUIDE.md) and [HONEST_ASSESSMENT.md](HONEST_ASSESSMENT.md)
- Review [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) for technical details
- Check test files for usage examples

---

**Built for AI agents that need secure, audited OS access.**
