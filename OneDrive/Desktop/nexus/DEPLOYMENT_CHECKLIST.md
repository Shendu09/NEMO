# Nexus Nova: Migration Checklist

## ✅ Implementation Complete

### Core Modules Rewritten
- [x] **voice_handler.py** - Voicebox (TTS) + Whisper (STT) with fallbacks
- [x] **analyzer.py** - PyTorch LSTM + Autoencoder + Z-score ensemble
- [x] **triage.py** - Ollama LLM (Mistral) + rule-based fallback
- [x] **handler.py** - FastAPI REST API + WebSocket + lifespan management

### Infrastructure
- [x] **docker-compose.yml** - 5 services (Ollama, Voicebox, Redis, PostgreSQL, Nexus API)
- [x] **setup.py** - One-command installer (Python 3.11+, venv, deps, .env, tests)
- [x] **pyproject.toml** - All dependencies updated (removed AWS, added torch, transformers, etc.)

### Testing
- [x] **test_voice_handler_new.py** - VoiceConfig, VoiceHandler, VoiceSession tests (~20 tests)
- [x] **test_analyzer_new.py** - LogEmbedder, Autoencoder, LSTM, AnomalyDetector tests (~20 tests)
- [x] **test_triage_new.py** - OllamaConfig, LogTriager, rule-based fallback tests (~25 tests)
- [x] **test_handler_new.py** - FastAPI endpoints, auth, error handling tests (~25 tests)

---

## 📊 AWS Services → Open-Source Mapping

| AWS Service | Replaced By | URL/Config | Status |
|------------|-----------|-----------|--------|
| **Amazon Nova 2 Lite** (LLM) | Mistral 7B + Ollama | http://localhost:11434 | ✅ Done |
| **Amazon Nova Embeddings** | sentence-transformers | ~/.nexus/models/ | ✅ Done |
| **Amazon Nova 2 Sonic** (TTS) | Voicebox REST API | http://localhost:17493 | ✅ Done |
| **Amazon Lex V2** (STT) | OpenAI Whisper | ~/.nexus/models/ | ✅ Done |
| **Cordon kNN** (Anomaly) | PyTorch LSTM+Autoencoder | ~/.nexus/models/ | ✅ Done |
| **Amazon Connect** (Calls) | FastAPI WebSocket | ws://localhost:8000/voice | ✅ Done |
| **AWS Lambda** (Compute) | FastAPI + Uvicorn | http://localhost:8000 | ✅ Done |

---

## 🧪 Test Coverage

### Voice Handler Tests (test_voice_handler_new.py)
```
✅ VoiceConfig initialization
✅ Voicebox availability check
✅ Speak with fallback to text file
✅ Listen with Whisper transcription
✅ Profile management
✅ QA context building
✅ Async context manager
✅ Error handling
```

### Analyzer Tests (test_analyzer_new.py)
```
✅ LogEmbedder vector creation
✅ Autoencoder forward pass
✅ Autoencoder reconstruction error
✅ LSTM sequence processing
✅ AnomalyDetector multi-model ensemble
✅ Z-score fallback
✅ Empty log handling
✅ Model training
✅ Percentile threshold selection
```

### Triage Tests (test_triage_new.py)
```
✅ OllamaConfig initialization
✅ LogTriager with Ollama
✅ Ollama model auto-pull
✅ JSON response parsing
✅ Rule-based fallback analysis
✅ Error pattern detection (DB, network, memory, CPU, auth, deployment)
✅ Empty/missing logs handling
✅ Retry logic with backoff
✅ Severity classification
```

### Handler Tests (test_handler_new.py)
```
✅ GET /health
✅ POST /triage
✅ POST /detect
✅ GET /models
✅ WS /voice
✅ X-API-Key authentication
✅ Invalid requests (422 Unprocessable Entity)
✅ Unauthorized access (401)
✅ Error handling (500)
✅ Response model validation
✅ Request model validation
```

---

## 📦 Installation Options

### Option 1: Automatic (Recommended)
```bash
python setup.py
```

### Option 2: Manual
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
mkdir -p ~/.nexus/models ~/.nexus/voice_fallback
docker-compose up -d
```

---

## 🚀 Starting Services

### Quick Start
```bash
# Terminal 1: Start Docker services
docker-compose up -d

# Terminal 2: Start FastAPI server
python -m uvicorn nexus.handler:app --reload

# Terminal 3: Pull Ollama model (first time only)
docker exec nexus-ollama ollama pull mistral
```

### Or Use Docker Everywhere
```bash
docker-compose up -d
# API automatically starts as a service
```

---

## 🧬 API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Full Triage Pipeline
```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -H "X-API-Key: nexus-dev-key" \
  -d '{
    "log_lines": ["ERROR: Database failed", "INFO: Retry attempt"],
    "anomaly_percentile": 75
  }'
```

### Anomaly Detection Only
```bash
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{
    "log_lines": ["log1", "log2", "log3"],
    "anomaly_percentile": 80
  }'
```

### List Available Models
```bash
curl http://localhost:8000/models
```

### Voice Briefing (WebSocket)
```bash
# Connect to ws://localhost:8000/voice
# Send: {"action": "briefing", "triage_report": {...}}
# Receive: {"audio": "<base64>", "transcript": "..."}
```

---

## 🔗 Service Dependencies

```
FastAPI Handler (8000)
  ├── Ollama (11434) - LLM triage
  ├── Voicebox (17493) - Voice synthesis
  ├── Redis (6379) - Caching
  └── PostgreSQL (5432) - Optional storage

Local Models (~/.nexus/models/)
  ├── sentence-transformers (embedder)
  ├── PyTorch LSTM + Autoencoder (detector)
  └── Whisper (STT)
```

---

## 📊 Cost Breakdown

| Item | AWS | Open-Source |
|------|-----|-------------|
| LLM (Nova 2 Lite) | $20-50/mo | $0 |
| Embeddings (Nova Embeddings) | $10-20/mo | $0 |
| TTS (Nova 2 Sonic/Polly) | $5-15/mo | $0 |
| STT (Lex V2) | $0.75/100 req | $0 |
| Compute (Lambda) | $0.20-2/mo | $0 |
| Anomaly Detection (Cordon) | License | $0 |
| Voice (Connect) | $0.50-1.50/min | $0 |
| **Total** | **$40-150+/mo** | **$0** |

---

## ⚙️ Configuration Files

### .env (Create at project root)
```env
API_KEY=nexus-dev-key
OLLAMA_MODEL=mistral
VOICEBOX_LANGUAGE=en
WHISPER_MODEL=base
DEVICE=cpu  # or 'cuda' for GPU
DEBUG=true
LOG_LEVEL=INFO
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  nexus-api:
    image: nexus:latest
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_URL=http://ollama:11434
      - VOICEBOX_URL=http://voicebox:17493
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
  voicebox:
    image: jamiepine/voicebox:latest
    ports:
      - "17493:17493"
  redis:
    image: redis:latest
    ports:
      - "6379:6379"
  postgres:
    image: postgres:latest
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=nexus
```

---

## 🧪 Running Tests

### All Tests
```bash
pytest tests/ -v
```

### With Coverage
```bash
pytest tests/ --cov=src/nexus --cov-report=html
```

### Specific Test File
```bash
pytest tests/test_voice_handler_new.py -v
```

### Specific Test
```bash
pytest tests/test_analyzer_new.py::TestLogEmbedder::test_embed -v
```

### With Markers
```bash
pytest tests/ -m "not slow" -v
```

---

## 🐛 Debugging

### View Logs
```bash
# Docker services
docker-compose logs -f ollama
docker-compose logs -f voicebox
docker-compose logs -f nexus-api

# FastAPI
export DEBUG=true
python -m uvicorn nexus.handler:app --log-level debug
```

### Check Service Status
```bash
# Test Ollama
curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "mistral", "prompt": "test"}'

# Test Voicebox
curl http://localhost:17493/profiles

# Test Whisper
python -c "import whisper; m = whisper.load_model('base')"
```

### Run Services Locally (No Docker)
```bash
# Terminal 1: Ollama
ollama serve

# Terminal 2: Voicebox
java -jar voicebox.jar

# Terminal 3: FastAPI
python -m uvicorn nexus.handler:app --reload
```

---

## 📚 File Structure

```
nexus/
├── src/nexus/
│   ├── __init__.py
│   ├── voice_handler.py    ✅ Voicebox + Whisper
│   ├── analyzer.py         ✅ PyTorch LSTM + Autoencoder
│   ├── triage.py           ✅ Ollama LLM + rules
│   ├── handler.py          ✅ FastAPI REST API
│   ├── config.py           (Legacy - config in .env now)
│   ├── classifier.py       (Unchanged)
│   ├── embedder.py         (Unchanged)
│   └── ...
├── tests/
│   ├── test_voice_handler_new.py  ✅ New
│   ├── test_analyzer_new.py       ✅ New
│   ├── test_triage_new.py         ✅ New
│   ├── test_handler_new.py        ✅ New
│   └── conftest.py        (Shared fixtures)
├── docker-compose.yml     ✅ New
├── setup.py               ✅ New
├── pyproject.toml         ✅ Updated
├── MIGRATION_GUIDE.md     ✅ New (you are here!)
└── README.md              (Exists)
```

---

## ✔️ Pre-Deployment Checklist

- [ ] All tests pass: `pytest tests/ -v`
- [ ] .env file configured with API_KEY
- [ ] Docker services running: `docker-compose ps`
- [ ] Health endpoint responding: `curl http://localhost:8000/health`
- [ ] Ollama model pulled: `docker exec nexus-ollama ollama ls`
- [ ] Models downloaded: `ls ~/.nexus/models/`
- [ ] API authentication working: `curl -H "X-API-Key: nexus-dev-key" http://localhost:8000/models`
- [ ] Triage endpoint working: Test with sample logs
- [ ] Anomaly detection working: Test with known anomalies
- [ ] Voice briefing accessible: Check WebSocket endpoint

---

## 🎓 Architecture Diagram

```
User Request (HTTP/JSON)
    ↓
FastAPI Handler (port 8000)
    ├─→ LogTriageRequest validation (Pydantic)
    ├─→ LogEmbedder (sentence-transformers)
    ├─→ AnomalyDetector (LSTM + Autoencoder + Z-score)
    │   └─→ Ensemble voting: LSTM → Autoencoder → Z-score
    ├─→ LogTriager (Ollama HTTP → LLM Mistral)
    │   ├─→ Ollama API call
    │   ├─→ JSON parsing
    │   └─→ Rule-based fallback if LLM fails
    ├─→ TriageResponse model
    └─→ JSON Response (HTTP 200)

Voice Option (WebSocket)
    ↓
VoiceHandler
    ├─→ Voicebox REST API (TTS)
    ├─→ Whisper (STT from microphone)
    └─→ LLM-generated answer via Ollama
```

---

## 📖 Learn More

### Documentation Files
- See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for detailed service comparison
- See [pyproject.toml](pyproject.toml) for all dependencies
- See individual module docstrings for API reference
- See test files for usage examples

### External Resources
- Ollama: https://ollama.ai
- Mistral 7B: https://mistral.ai
- Sentence-Transformers: https://www.sbert.net
- OpenAI Whisper: https://github.com/openai/whisper
- FastAPI: https://fastapi.tiangolo.com
- PyTorch: https://pytorch.org

---

## 🆘 Troubleshooting Guide

### Problem: "Ollama connection refused"
```bash
# Solution: Start Ollama service
docker-compose up -d ollama
# Wait 10 seconds, then retry
sleep 10
```

### Problem: "Model not found" (Whisper/embedder)
```bash
# Solution: Pre-download models
python -c "
import whisper
whisper.load_model('base')

from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
"
```

### Problem: "CUDA out of memory"
```bash
# Solution: Use CPU instead
export DEVICE=cpu
```

### Problem: "API Key rejected"
```bash
# Check your API_KEY
cat .env | grep API_KEY

# If not set:
echo "API_KEY=nexus-dev-key" >> .env

# Use correct header:
curl -H "X-API-Key: YOUR_KEY_HERE" http://localhost:8000/health
```

### Problem: "WebSocket connection failed"
```bash
# Check FastAPI is running
curl http://localhost:8000/health

# Verify WebSocket endpoint exists
curl http://localhost:8000/docs  # OpenAPI docs
```

---

## ✅ Success Indicators

After setup, you should see:

```
✅ docker-compose ps shows 5 services UP
✅ curl http://localhost:8000/health returns {"status": "healthy"}
✅ pytest tests/ shows all tests PASSED
✅ curl -X POST /triage returns TriageResponse with severity/root_cause
✅ ~/.nexus/models/ contains downloaded models
✅ ~/.nexus/voice_fallback/ directory exists (fallback scripts)
```

---

## 🎯 Next Steps

1. **Run setup**: `python setup.py`
2. **Start services**: `docker-compose up -d`
3. **Run tests**: `pytest tests/ -v`
4. **Try API**: `curl http://localhost:8000/health`
5. **Call triage**: See "API Endpoints" section above
6. **Deploy**: Use docker-compose.prod.yml for production

---

**Total Migration Complete: 4 modules rewritten + 4 test suites + Docker orchestration + one-command installer = 100% AWS-free!** 🎉
