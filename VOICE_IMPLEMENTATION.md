# Voice Implementation Architecture

## System Design

The NEMO voice system is built on a 3-layer architecture:

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: Audio Input & Wake Word Detection              │
│  File: core/voice/wake_listener.py                        │
├──────────────────────────────────────────────────────────┤
│  - listen_for_wake_word(callback)                        │
│  - start(callback)                                       │
│  - Audio recording via sounddevice                       │
│  - Transcription via faster-whisper                      │
│  - Wake word pattern matching                            │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Layer 2: Command Integration & Routing                  │
│  File: clevrr_service.py                                  │
├──────────────────────────────────────────────────────────┤
│  - launch_voice_listener()                               │
│  - handle_voice_command() callback                       │
│  - POST to /task endpoint                                │
│  - Error handling & recovery                             │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Layer 3: Command Processing & Execution                 │
│  File: bridge/nemo_server.py                              │
├──────────────────────────────────────────────────────────┤
│  - POST /task endpoint                                   │
│  - Ollama llama3 integration                              │
│  - Action execution pipeline                             │
│  - Security & audit logging                              │
│  - Result aggregation                                    │
└──────────────────────────────────────────────────────────┘
```

## Layer 1: Audio Input & Wake Word Detection

### File: `core/voice/wake_listener.py`

**Key Components:**

1. **Model Loading** (`_get_model()`)
   - Lazy initialization (first use only)
   - Thread-safe with lock mechanism
   - faster-whisper small model
   - int8 quantization for CPU efficiency
   - Cached in global `_model` variable

2. **Audio Recording Loop** (`listen_for_wake_word()`)
   ```python
   def listen_for_wake_word(callback: Callable[[str], None]) -> None:
       """Record and transcribe audio, detect wake words."""
       
       # 1. Audio input setup
       stream = sounddevice.InputStream(
           channels=1,           # Mono
           samplerate=16000,     # 16kHz
           blocksize=16000*2,    # 2-second chunks
       )
       
       # 2. Recognition loop
       while True:
           audio_chunk = stream.read()  # 2-second chunk
           
           # 3. Transcribe
           text = model.transcribe(audio_chunk)
           
           # 4. Detect wake word
           if wake_word_detected(text):
               command = extract_command(text)
               callback(command)  # Execute via handler
   ```

3. **Wake Word Detection** (`wake_word_detected()`)
   - Pattern: `WAKE_WORDS = ["V", "BE", "WE", "B", "VI"]`
   - Case-insensitive matching
   - Index-based word boundary detection
   - Command extraction after wake word index

4. **Daemon Thread Execution** (`start()`)
   ```python
   def start(callback: Callable[[str], None]) -> None:
       """Start listener in background daemon thread."""
       
       thread = threading.Thread(
           target=listen_for_wake_word,
           args=(callback,),
           daemon=True  # Dies with main process
       )
       thread.start()
   ```

### Key Parameters

| Parameter | Value | Reason |
|-----------|-------|--------|
| Sample Rate | 16kHz | Whisper optimal rate |
| Channels | Mono | Reduce data size |
| Chunk Size | 2 seconds | Balance speed vs accuracy |
| Model | small | CPU efficiency |
| Quantization | int8 | 4x faster, lower memory |

### Performance Profile

| Metric | Value |
|--------|-------|
| Memory | ~400MB (model) + ~50MB (runtime) |
| CPU | ~50% single core during transcription |
| Latency | ~1-2 seconds per 2-sec chunk |
| Accuracy | ~95% on clear audio (English) |
| First load | ~10-15 seconds |
| Subsequent | <1 second (cached) |

## Layer 2: Command Integration

### File: `clevrr_service.py`

**Integration Point: `cmd_run()` function**

```python
def cmd_run(args):
    """Start NEMO service with optional voice listening."""
    
    # Existing service startup...
    gateway = SecurityGateway()
    audit_logger = AuditLogger()
    
    # NEW: Voice listener startup
    try:
        from core.voice import wake_listener
        
        def handle_voice_command(command: str) -> None:
            """Convert voice command to API request."""
            
            try:
                response = requests.post(
                    "http://localhost:8765/task",
                    json={
                        "command": command,
                        "user": "voice",
                        "channel": "voice",
                    },
                    timeout=60,
                )
                
                result = response.json()
                print(f"✓ Executed: {command}")
                print(f"  Result: {result.get('message')}")
                
            except Exception as e:
                logger.error(f"Voice command failed: {e}")
        
        # Start listener in daemon thread
        wake_listener.start(handle_voice_command)
        print("Voice active. Say 'V' followed by your command.\n")
        
    except ImportError:
        logger.warning("Voice module not available (optional)")
    except Exception as e:
        logger.warning(f"Voice listener failed to start (optional): {e}")
    
    # Continue with service loop...
```

**Error Handling Strategy:**
- Voice module is optional (ImportError caught)
- Failed initialization doesn't crash service
- Graceful fallback if Ollama unavailable
- All exceptions logged but non-fatal

## Layer 3: Command Processing & Execution

### File: `bridge/nemo_server.py`

**Endpoint: `POST /task`**

```python
@app.route("/task", methods=["POST"])
def task() -> dict[str, Any]:
    """
    1. Parse voice command from request
    2. Send to Ollama llama3 with system prompt
    3. Parse action steps from JSON response
    4. Execute each action sequentially
    5. Return aggregated results
    """
```

#### Step 1: Input Parsing
```python
data = request.get_json() or {}
command = data.get("command", "").strip()
user = data.get("user", "voice")
channel = data.get("channel", "voice")
```

#### Step 2: Ollama Request
```python
system_prompt = """You are a Windows PC automation system...
Supported actions: open_app, type, press_key, click, etc.
Return ONLY valid JSON array."""

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3",
        "prompt": f"System prompt: {system_prompt}\n\n"
                  f"User command: {command}\n\n"
                  "Return ONLY the JSON array of actions, no extra text.",
        "stream": False,
    },
    timeout=30,
)
```

#### Step 3: Action Parsing
```python
ollama_response = response.json().get("response", "[]")

# Extract JSON from response (Ollama may add text)
start = ollama_response.find("[")
end = ollama_response.rfind("]") + 1
json_str = ollama_response[start:end]
actions = json.loads(json_str)

# Validate structure
for action in actions:
    action_name = action.get("action")
    target = action.get("target", "")
    value = action.get("value", "")
```

#### Step 4: Sequential Execution
```python
executed_actions = []
steps_completed = 0

for idx, action_spec in enumerate(actions):
    action = action_spec.get("action")
    target = action_spec.get("target", "")
    value = action_spec.get("value", "")
    
    # Execute action using existing _execute_action()
    result = _execute_action(action, target, value)
    
    # Log to audit trail
    if _audit_logger:
        _audit_logger.log(
            user_id=user,
            action=action,
            target=target or "",
            allowed=result.get("success", False),
            reason=f"Voice command step {idx+1}"
        )
    
    # Track results
    executed_actions.append({
        "step": idx + 1,
        "action": action,
        "status": "success" if result.get("success") else "failed",
        "error": result.get("error")
    })
    
    if result.get("success"):
        steps_completed += 1
    
    time.sleep(0.5)  # Delay between actions
```

#### Step 5: Result Aggregation
```python
screenshot_b64 = _capture_screenshot()

return {
    "success": steps_completed == len(actions),
    "steps_completed": steps_completed,
    "total_steps": len(actions),
    "actions": executed_actions,
    "screenshot": screenshot_b64 or "",
    "message": f"Completed {steps_completed} of {len(actions)} steps",
    "command": command,
}
```

## System Prompt Engineering

The system prompt is critical for correct action generation:

```
Supported actions:
- open_app: {action: "open_app", target: "app_name"}
- type: {action: "type", value: "text"}
- press_key: {action: "press_key", value: "key_name" or "key1+key2"}
- click: {action: "click", value: "x,y"} or {action: "click", value: "target:element_name"}
- screenshot: {action: "screenshot"}
- wait: {action: "wait", value: "seconds"}
- browse: {action: "browse", target: "url"}
- search: {action: "search", value: "query"}
- summarize: {action: "summarize", target: "url"}
- play: {action: "play", value: "video_query"}
- play_song: {action: "play_song", value: "song_name"}

Examples:
"open chrome and search for python"
→ [
    {"action": "open_app", "target": "chrome"},
    {"action": "wait", "value": "2"},
    {"action": "search", "value": "python"}
  ]

"play the song thriller"
→ [{"action": "play_song", "value": "thriller"}]
```

## Data Flow Diagram

```
User Audio
    ↓
[listen_for_wake_word]
    ↓
[Wake word detected?] ─No→ Loop
    ↓
   Yes
    ↓
[Extract command text]
    ↓
[callback(command)]
    ↓
[handle_voice_command]
    ↓
[POST /task with command]
    ↓
[Ollama llama3 prompt]
    ↓
[Parse JSON actions]
    ↓
[For each action: _execute_action()]
    ↓
[Log to audit trail]
    ↓
[Capture screenshot]
    ↓
[Return results JSON]
    ↓
[Response logged]
```

## Error Recovery

### Ollama Connection Failure
```python
except requests.exceptions.RequestException as e:
    return {
        "success": False,
        "error": "Ollama not running on localhost:11434"
    }, 503
```

### JSON Parsing Failure
```python
except json.JSONDecodeError as e:
    return {
        "success": False,
        "error": f"Failed to parse action steps: {str(e)}"
    }, 500
```

### Action Execution Failure
```python
if not result.get("success"):
    executed_actions.append({
        "step": idx + 1,
        "action": action,
        "status": "failed",
        "error": result.get("error")
    })
    # Continue with next action
```

## Security Integration

All voice commands are subject to NEMO's security framework:

1. **Risk Classification**: Each action classified (LOW/MEDIUM/HIGH)
2. **Audit Logging**: All commands logged with timestamp, user, result
3. **RBAC**: User "voice" subject to role-based access control
4. **Threat Detection**: Anomalous patterns flagged
5. **Sandboxing**: Actions execute in restricted context

## Testing Strategy

### Unit Tests
- `test_voice_module()` - Module import and function availability
- `test_wake_word_detection()` - Wake word pattern matching
- `test_command_extraction()` - Command text extraction

### Integration Tests
- `test_nemo_health()` - Server health check
- `test_task_endpoint()` - API endpoint functionality
- `test_action_execution()` - Action execution verification
- `test_screenshot_capture()` - Screenshot functionality

### End-to-End Tests
- Real audio input with wake word
- Command-to-action conversion accuracy
- Action execution and result verification
- Audit trail validation

Run tests:
```bash
python test_voice_integration.py
```

## Deployment Checklist

- [ ] Ollama running (docker/local) with llama3 model
- [ ] NEMO server started (`python clevrr_service.py run`)
- [ ] Microphone configured and working
- [ ] Voice dependencies installed (`pip install -r requirements.txt`)
- [ ] Test script passing (`python test_voice_integration.py`)
- [ ] Dashboard accessible (http://localhost:8765/dashboard)
- [ ] Audit logs visible in dashboard

## Performance Optimization

### Critical Path
```
Audio Input (2s) → Transcription (1-2s) → Wake Word Detection (0.1s)
→ API Call (0.1s) → Ollama Processing (5-10s) → Action Execution (varies)
→ Screenshot (0.2s) → Response (0.1s)

Total: ~8-16 seconds per command
```

### Optimization Opportunities
1. **Model Caching**: Keep Ollama warm in memory
2. **Parallel Recording**: Pre-record next chunk while processing
3. **Action Batching**: Execute non-dependent actions in parallel
4. **Response Compression**: Reduce screenshot size

## Customization Guide

### Adding Wake Words
Edit `core/voice/wake_listener.py`:
```python
WAKE_WORDS = ["V", "BE", "WE", "B", "VI", "YOUR_WORD"]
```

### Adding New Actions
1. Implement in `_execute_action()` in `nemo_server.py`
2. Add to system prompt in `/task` endpoint
3. Add example to prompt

### Tuning Ollama Prompt
Edit `/task` endpoint system_prompt variable to:
- Add more examples
- Clarify ambiguous commands
- Restrict certain actions
- Add domain-specific vocabulary

## Monitoring & Maintenance

### Key Metrics
```bash
# Check voice command success rate
curl http://localhost:8765/api/audit-log?action=open_app | jq '.entries | length'

# Monitor Ollama performance
watch -n 1 'curl -s http://localhost:11434/api/tags | jq'

# Check wake word detection accuracy
tail -f /var/log/nemo/voice.log | grep "wake_word_detected"
```

### Common Issues & Solutions

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| Slow responses | Ollama warm-up | Keep running in background |
| Wake word ignored | Low audio quality | Speak clearly, check mic |
| Wrong actions | Poor prompt | Improve system prompt examples |
| Crashes | Memory exhaustion | Reduce model size, increase RAM |

## Version History

- **v1.0.0** (Current)
  - Wake word detection (V, BE, WE, B, VI)
  - faster-whisper integration
  - Ollama llama3 command conversion
  - Full action execution pipeline
  - Security audit logging

## Future Enhancements

- [ ] Voice feedback (TTS) for confirmations
- [ ] Multi-language support
- [ ] Custom wake word training
- [ ] Voice emotion/intent detection
- [ ] Personalized command learning
- [ ] Voice command history & macros
