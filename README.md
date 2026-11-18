# VOICEGUARD AI — Cyber Acoustic Defense & AI Voice Anti-Spoofing

**Problem Statement:** SIH26104 — AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks  
**System Architecture:** Production-Grade FastAPI Backend + Autonomous Neural Audio Processing Pipeline + Cyberpunk 3D SecOps Dashboard  
**Version:** 3.1.0-PROD

---

## 1. Quick Start Guide

### Automated Startup (One-Click)

Run the automated startup script in PowerShell:

```powershell
.\start_voiceguard.ps1
```

The script automatically:
1. Detects and validates the Python 3.13 virtual environment (`.venv`).
2. Verifies installed core dependencies (FastAPI, PyAV, ONNX Runtime, NumPy, etc.).
3. Discovers FFmpeg and FFprobe binaries.
4. Starts the FastAPI server on `http://127.0.0.1:8000`.
5. Verifies server health.
6. Launches the application.

To terminate the running server cleanly:
```powershell
.\stop_voiceguard.ps1
```

---

## 2. Web Access & Endpoints

| Resource | URL | Description |
| :--- | :--- | :--- |
| **Landing Page** | `http://127.0.0.1:8000/` | Public homepage featuring 3D Three.js hero visualizer, feature matrix, audio visualizer canvas, and auth modal |
| **Security Dashboard** | `http://127.0.0.1:8000/app` | 8-view SecOps workspace (Overview, Voice Forensics, Live Stream, History, Analytics, Threat Intel, Settings, Profile) |
| **Interactive API Docs** | `http://127.0.0.1:8000/docs` | Swagger UI documentation with schema models and interactive API execution |
| **System Health API** | `http://127.0.0.1:8000/api/health` | Service and database connectivity health check |
| **Pipeline Health API**| `http://127.0.0.1:8000/api/v1/audio/health` | Detailed telemetry on ONNX models, execution devices (CUDA/CPU), and FFmpeg diagnostics |

---

## 3. Supported Audio Formats & Preprocessing

The audio engine accepts **10 formats and containers**:

- **Uncompressed:** `.wav`
- **Compressed Audio:** `.mp3`, `.flac`, `.ogg`, `.m4a`, `.aac`, `.opus`, `.webm`
- **MPEG Streams:** `.mpeg`, `.mpg` (MPEG-1/2 Audio, MP2, MP3, AAC in Program Streams)

### Stream Processing Architecture

1. **Magic Byte Inspection:** Evaluates raw binary file signatures (`RIFF...WAVE`, `\xff\xfb`, `fLaC`, `OggS`, `ftyp`, `\x00\x00\x01\xba`).
2. **Container Demuxing:** In mixed video/audio containers (e.g. MPEG), audio streams are isolated while video tracks are cleanly bypassed.
3. **Rejection Safeguards:** Video-only files (`NO_AUDIO_STREAM`), corrupted streams (`CORRUPTED_AUDIO`), and unsupported codecs (`UNSUPPORTED_CODEC`) are rejected with structured 400 Bad Request responses. Files > 25 MB are rejected with HTTP 413.
4. **Signal Normalization:** Standardizes to **16,000 Hz Mono Float32 PCM** in `[-1.0, 1.0]`.
5. **Segmentation:** Continuous recordings are windowed into overlapping **64,600-sample tensors** matching the AASIST model input specification. Short files are cyclically wrapped/padded.

---

## 4. AI Voice Anti-Spoofing & Zero-Hallucination Policy

VOICEGUARD AI supports three neural deepfake architectures:
1. **AASIST** (`aasist.onnx`): Graph attention networks modeling spectro-temporal voice cloning artifacts.
2. **RawNet2** (`rawnet2.onnx`): End-to-end raw waveform anti-spoofing.
3. **ECAPA-TDNN** (`ecapa_tdnn.onnx`): 192-dimensional biometric speaker voiceprint verification.

### Zero-Hallucination Guarantee
In strict adherence to cyber forensic integrity:
- If neural model checkpoints are not installed on disk in `backend/models_weights/`, the platform **never fabricates synthetic probabilities or random scores**.
- It outputs `status: "AI_MODEL_NOT_CONFIGURED"`, `model_status: "MODEL_NOT_AVAILABLE"`, and `prediction.label: "INCONCLUSIVE"`.
- It calculates and delivers **objective empirical acoustic metrics**: RMS power, spectral centroid (Hz), zero-crossing rate, silence ratio, and pitch stability.
- To configure trained neural models, place exported ONNX checkpoints in `backend/models_weights/` as documented in `backend/models_weights/README.md`.

---

## 5. Automated Verification & Testing

Execute the comprehensive test suites:

```powershell
# 1. Run all 76 backend automated tests (100% pass rate)
.venv\Scripts\pytest.exe backend/tests/ -v

# 2. Run dedicated E2E integration test suite (17 tests)
.venv\Scripts\pytest.exe backend/tests/test_e2e_integration.py -v

# 3. Run dedicated MPEG/MPG audio format test suite (10 tests)
.venv\Scripts\pytest.exe backend/tests/test_mpeg_support.py -v

# 4. Run real-user QA verification audit (42 functional features)
.venv\Scripts\python.exe backend/tests/real_user_qa_suite.py
```

---

## 6. Directory Structure

```
VoiceGard_AI/
├── backend/
│   ├── main.py                  # FastAPI application entrypoint & static serving
│   ├── database.py              # SQLite engine & session factory
│   ├── models.py                # SQLAlchemy ORM models (User, Audio, Threat, Speaker)
│   ├── schemas.py               # Pydantic validation & response schemas
│   ├── auth.py                  # JWT, bcrypt-sha256 hashing, current_user dependency
│   ├── models_weights/          # Checkpoint loading directory (AASIST, RawNet2, ECAPA)
│   ├── routes/                  # API routers (auth, audio, speaker, threat, dashboard, report)
│   ├── services/                # FFmpegService, AudioValidator, Preprocessor, InferencePipeline
│   └── tests/                   # 76 automated pytest tests & real user QA suite
├── index.html                   # Cyberpunk landing page & 3D hero visualization
├── app.html                     # 8-workspace SecOps security dashboard
├── api-client.js                # Unified frontend API client (Bearer auth, all routes)
├── app-controller.js            # Dashboard controller, live mic recording, 7-stage pipeline
├── start_voiceguard.ps1         # One-click automated production startup
├── stop_voiceguard.ps1          # One-click automated shutdown
├── requirements.txt             # Pinned Python 3.13 dependencies
└── README.md                    # System documentation
```
