# NEMO Voice Integration Guide

## Overview

The NEMO voice system provides real-time speech recognition and command processing:

1. **Wake Word Detection**: Listen for voice activation ("V", "BE", "WE", "B", "VI")
2. **Command Extraction**: Capture spoken command after wake word
3. **AI Processing**: Convert natural language to structured action steps
4. **Execution**: Automatically execute actions on your PC

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ User speaks: "V, open chrome and search for python"         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Audio Input (sounddevice)                                   │
│ - Records 2-second chunks at 16kHz                          │
│ - Continuous real-time monitoring                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Speech Recognition (faster-whisper)                         │
│ - GPU/CPU transcription (int8 quantization)                 │
│ - Small model (CPU-efficient)                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Wake Word Detection                                         │
│ - Detects: V, BE, WE, B, VI                                │
│ - Extracts command text after wake word                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ POST to /task Endpoint                                      │
│ {                                                           │
│   "command": "open chrome and search for python",          │
│   "user": "voice",                                          │
│   "channel": "voice"                                        │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Ollama llama3 Command→Action Conversion                     │
│ - System prompt specifies all available actions             │
│ - Generates JSON action steps                               │
│ - Example output:                                           │
│   [{"action": "open_app", "target": "chrome"},              │
│    {"action": "wait", "value": "2"},                        │
│    {"action": "search", "value": "python"}]                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Action Execution                                            │
│ - Executes each action sequentially                         │
│ - Captures before/after screenshots                         │
│ - Logs to security audit trail                              │
│ - 0.5s delay between actions                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Results & Response                                          │
│ {                                                           │
│   "success": true,                                          │
│   "steps_completed": 3,                                     │
│   "total_steps": 3,                                         │
│   "actions": [...],                                         │
│   "screenshot": "base64...",                                │
│   "message": "Completed 3 of 3 steps"                       │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
```

## Getting Started

### 1. Prerequisites

Install required dependencies:

```bash
pip install -r requirements.txt
```

Key voice dependencies:
- `faster-whisper>=0.10.0` - CPU-efficient speech recognition
- `sounddevice>=0.4.6` - Audio recording
- `numpy>=1.24.0` - Numerical operations
- `ollama` - Local LLM for command conversion (via Docker/Podman)

### 2. Start Ollama Server

The voice system requires Ollama running with llama3 model:

```bash
# Option 1: Docker (recommended)
docker run -d -p 11434:11434 ollama/ollama:latest
docker exec ${container_id} ollama pull llama3

# Option 2: Podman
podman run -d -p 11434:11434 ollama/ollama:latest
podman exec ${container_id} ollama pull llama3

# Option 3: Direct installation
# See https://ollama.ai
ollama pull llama3
```

Verify Ollama is running:
```bash
curl http://localhost:11434/api/tags
```

### 3. Start NEMO Service

```bash
python clevrr_service.py run
```

You should see:
```
Voice active. Say 'V' followed by your command.
```

### 4. Use Voice Commands

Speak your commands after hearing "Voice active":

```
Say: "V open chrome"
→ Opens Google Chrome

Say: "BE search for python tutorials"
→ Searches the web for "python tutorials"

Say: "V take a screenshot"
→ Captures screenshot

Say: "WE play the song Bohemian Rhapsody"
→ Plays the song on YouTube
```

## Supported Voice Commands

### Application Control
```
"open chrome"              → Opens Chrome browser
"open notepad"             → Opens Notepad
"open slack"               → Opens Slack
"open whatsapp"            → Opens WhatsApp
```

### Text Input
```
"type hello world"         → Types "hello world"
"type my name is john"     → Types "my name is john"
```

### Web Browsing
```
"browse google.com"        → Navigate to Google
"search for python"        → Google search for Python
"summarize this page"      → AI summarize webpage
```

### Media Playback
```
"play cat videos"          → Search and play on YouTube
"play the song thriller"   → Play "thriller official audio" on YouTube
```

### System Actions
```
"take a screenshot"        → Capture screen
"press enter"              → Press Enter key
"press control+c"          → Hotkey combination
"wait 2 seconds"           → Wait 2 seconds
```

### Smart UI Clicking
```
"click send button"        → Find and click Send button
"click target:login"       → AI vision-based element clicking
```

## Wake Words

The system listens for these wake words:
- **"V"** - Single letter (easiest to say)
- **"BE"** - Two letters
- **"WE"** - Two letters
- **"B"** - Single letter
- **"VI"** - Two letters

After the wake word, speak your command naturally:
```
Wake word: "V"
Command: "open chrome and search for python"
```

## Advanced Features

### Vision-Based Element Clicking

The voice system supports AI vision for smart clicking:

```
"V click the send button"
→ Uses OmniParser to find "send button" and click it
```

### Chained Commands

The system converts complex commands to multiple steps:

```
"V open chrome, wait 2 seconds, and search for machine learning"
→ Step 1: open_app (chrome)
→ Step 2: wait (2 seconds)
→ Step 3: search (machine learning)
```

### Security & Audit

All voice commands are:
- **Logged**: Full audit trail in Security dashboard
- **Classified**: Risk assessment (LOW/MEDIUM/HIGH)
- **Authorized**: RBAC verification
- **Monitored**: Real-time security monitoring

View voice command history:
```bash
curl http://localhost:8765/api/audit-log?action=voice
```

## Troubleshooting

### Voice module not available
```
Error: Voice module not available (optional)
```
**Solution**: Install voice dependencies
```bash
pip install faster-whisper>=0.10.0 sounddevice>=0.4.6
```

### Ollama connection failed
```
Error: Ollama not running on localhost:11434
```
**Solution**: Start Ollama server (see Prerequisites)

### Wake word not detected
- Speak clearly and firmly
- Wait for "Voice active" message before speaking
- Try different wake words (V, BE, WE, B, VI)
- Check microphone volume levels

### Slow response times
- First use downloads whisper model (~400MB)
- Ollama first request may be slow (warm-up)
- Subsequent commands will be faster

### Action execution fails
- Check NEMO server logs: `python clevrr_service.py run`
- Verify target application is installed
- Test action via HTTP: `/execute` endpoint

## Testing

Run the test suite:

```bash
python test_voice_integration.py
```

This tests:
1. ✓ NEMO server health
2. ✓ Voice module availability
3. ✓ /task endpoint functionality
4. ✓ Action execution
5. ✓ Screenshot capture

## API Reference

### POST /task

Convert voice command to actions and execute.

**Request:**
```json
{
  "command": "open chrome and search for python",
  "user": "voice",
  "channel": "voice"
}
```

**Response:**
```json
{
  "success": true,
  "steps_completed": 3,
  "total_steps": 3,
  "actions": [
    {
      "step": 1,
      "action": "open_app",
      "target": "chrome",
      "value": null,
      "status": "success",
      "error": null
    },
    {
      "step": 2,
      "action": "wait",
      "target": "",
      "value": "2",
      "status": "success",
      "error": null
    },
    {
      "step": 3,
      "action": "search",
      "target": "",
      "value": "python",
      "status": "success",
      "error": null
    }
  ],
  "screenshot": "iVBORw0KGgo... (base64)",
  "message": "Completed 3 of 3 steps",
  "command": "open chrome and search for python"
}
```

**Status Codes:**
- `200` - Success
- `400` - Missing command parameter
- `500` - Ollama request error
- `503` - Ollama server unavailable

## Performance Notes

### Model Loading
- **First run**: ~10-15 seconds (downloads ~400MB model)
- **Subsequent runs**: <1 second (cached)

### Audio Processing
- **Recording**: 2-second chunks (real-time)
- **Transcription**: ~1-2 seconds per 2-sec chunk
- **Action conversion**: ~5-10 seconds (Ollama)
- **Execution**: Depends on action complexity

### Optimization Tips
- Keep Ollama running in background
- Use wake words consistently
- Cache frequently used commands
- Monitor system resources

## Security Considerations

### Privacy
- Audio processed locally (not cloud)
- Voice commands stored in audit log
- No audio recording files kept

### Authorization
- Voice commands subject to RBAC
- HIGH-risk actions require confirmation
- All commands logged to immutable audit trail

### Threats Mitigated
- **Command injection**: Ollama controls command format
- **Unauthorized access**: RBAC verification
- **Data exfiltration**: Audit logging
- **Malware execution**: Sandbox execution

## Architecture Files

- **Module**: `/core/voice/wake_listener.py` (200+ lines)
  - `listen_for_wake_word(callback)` - Audio listening loop
  - `start(callback)` - Daemon thread launcher

- **Service Integration**: `/clevrr_service.py`
  - Voice listener startup
  - Callback handler for `/task` endpoint

- **API Endpoint**: `/bridge/nemo_server.py`
  - `POST /task` - Command processing
  - Ollama integration
  - Action execution

- **Documentation**:
  - This file: `VOICE_GUIDE.md`
  - Implementation: `VOICE_IMPLEMENTATION.md`
  - Quick Start: `VOICE_QUICKSTART.md`

## Next Steps

1. **Deploy**: `python clevrr_service.py run`
2. **Test**: `python test_voice_integration.py`
3. **Monitor**: Check `/dashboard` for audit logs
4. **Customize**: Adjust wake words, system prompt, action list

## Support

For issues:
1. Check logs: See console output from `clevrr_service.py run`
2. Test endpoint: `curl -X POST http://localhost:8765/task -d '{"command":"take a screenshot"}'`
3. Verify Ollama: `curl http://localhost:11434/api/tags`
4. Review security: `curl http://localhost:8765/api/audit-log`

---

**Status**: ✅ Voice integration complete and ready for use

**Version**: 1.0.0

**Components**: faster-whisper + sounddevice + Ollama + Flask API
