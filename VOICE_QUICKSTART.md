# NEMO Voice Quick Start

## 60-Second Setup

### Step 1: Start Ollama (1 minute)
```bash
# Docker (easiest)
docker run -d -p 11434:11434 ollama/ollama:latest
docker exec $(docker ps -q -f image=ollama/ollama) ollama pull llama3
```

### Step 2: Start NEMO Service (30 seconds)
```bash
python clevrr_service.py run
```

Expected output:
```
Voice active. Say 'V' followed by your command.
```

### Step 3: Test Voice Feature
Speak into your microphone:
```
"V take a screenshot"
```

Done! Your command should execute.

## Common Voice Commands

| Command | Result |
|---------|--------|
| `V open chrome` | Opens Chrome browser |
| `BE search python` | Searches for "python" online |
| `V take a screenshot` | Captures your screen |
| `WE play cat videos` | Plays cat videos on YouTube |
| `B type hello world` | Types "hello world" |

## Wake Words Used

Say one of these, then your command:
- **V** - Easiest (single letter)
- **BE** - Two letters
- **WE** - Two letters  
- **B** - Single letter
- **VI** - Two letters

## Verify Installation

```bash
# Test voice module
python -c "from core.voice import wake_listener; print('✓ Voice module ready')"

# Test API endpoint
curl -X POST http://localhost:8765/task \
  -H "Content-Type: application/json" \
  -d '{"command":"take a screenshot","user":"test"}'
```

## System Requirements

- Windows 10/11
- Python 3.9+
- Microphone
- Ollama running (docker or local)
- 4GB RAM minimum

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Voice module not available" | `pip install faster-whisper sounddevice` |
| "Ollama not running" | `docker run -p 11434:11434 ollama/ollama` |
| "Wake word not detected" | Speak clearly, wait for "Voice active" message |
| "Action failed" | Check NEMO logs for error details |

## Next Steps

- Read [VOICE_GUIDE.md](VOICE_GUIDE.md) for full documentation
- Check `/dashboard` on http://localhost:8765 to view logs
- View executed commands in Security dashboard
- Customize wake words in `core/voice/wake_listener.py`

## Full Feature List

✅ Real-time speech recognition (faster-whisper)
✅ Wake word detection (V, BE, WE, B, VI)  
✅ AI command interpretation (Ollama llama3)
✅ Automatic action execution
✅ Screenshot capture
✅ Security audit logging
✅ Vision-based UI clicking
✅ Error handling & recovery

**Ready to use!** 🎤
