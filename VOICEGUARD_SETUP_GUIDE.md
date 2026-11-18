# VOICEGUARD AI — Setup & Deployment Guide

**Target Audience:** Developers, DevOps Engineers, and Security Administrators  
**System:** VOICEGUARD AI — Cyber Acoustic Defense & AI Voice Anti-Spoofing  
**Version:** 3.1.0-PROD  

---

## 1. Prerequisites & System Requirements

- **Operating System:** Windows 10/11, Linux (Ubuntu 22.04+), or macOS 13+
- **Python:** Python 3.11, 3.12, or 3.13 (Python 3.13.7 verified)
- **Node.js (Optional):** Node.js 18+ (only if running frontend dev server; FastAPI serves frontend directly)
- **FFmpeg & FFprobe:**
  - *Primary Engine:* `PyAV 19.0.2` is pre-installed in the virtual environment and provides embedded C-libraries (`libavformat`, `libavcodec`, `libswresample`).
  - *CLI Engine:* Downloaded at `C:\Users\LC\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin\` and auto-detected.

---

## 2. Environment Setup

### Step 1: Clone or Navigate to Workspace
```powershell
cd c:\Users\LC\OneDrive\Desktop\VoiceGard_AI
```

### Step 2: Virtual Environment & Dependencies
```powershell
# Create virtual environment (if not already existing)
python -m venv .venv

# Activate environment
.venv\Scripts\activate

# Install production dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Key environment settings in `.env`:
```ini
# Security & JWT Token
SECRET_KEY=generate-a-strong-random-key-here-for-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720

# Database
DATABASE_URL=sqlite:///./voiceguard.db

# FFmpeg Executables (Auto-discovered if left blank)
FFMPEG_PATH=C:\Users\LC\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe
FFPROBE_PATH=C:\Users\LC\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin\ffprobe.exe
```

---

## 3. Starting the Application

### Option A: Automated One-Click Startup (Recommended)
Run the PowerShell automation script:
```powershell
.\start_voiceguard.ps1
```

This script:
1. Detects `.venv` and confirms Python 3.13.
2. Checks all third-party dependencies.
3. Auto-discovers FFmpeg and FFprobe.
4. Starts FastAPI backend on `http://127.0.0.1:8000`.
5. Polls `/api/health` until the service is active.
6. Prints application URLs.

### Option B: Manual Startup via Uvicorn
```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### Stopping the Server
```powershell
.\stop_voiceguard.ps1
```

---

## 4. Application Access URLs

- **Public Landing Page:** `http://127.0.0.1:8000/`
- **Security Dashboard:** `http://127.0.0.1:8000/app`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
- **ReDoc API Spec:** `http://127.0.0.1:8000/redoc`
- **System Health:** `http://127.0.0.1:8000/api/health`
- **Pipeline Diagnostics:** `http://127.0.0.1:8000/api/v1/audio/health`

---

## 5. Adding AI Model Weights

VOICEGUARD AI supports three neural anti-spoofing models:
- **AASIST:** `backend/models_weights/aasist.onnx`
- **RawNet2:** `backend/models_weights/rawnet2.onnx`
- **ECAPA-TDNN:** `backend/models_weights/ecapa_tdnn.onnx`

### Exporting Checkpoints to ONNX

If you have trained PyTorch weights (`weights.pth`), export them to ONNX using this Python snippet:

```python
import torch

# 1. Load trained model architecture
model = AASIST(config)
model.load_state_dict(torch.load("weights.pth", map_location="cpu"))
model.eval()

# 2. Dummy 16kHz 4-second raw audio waveform (64,600 samples)
dummy_input = torch.randn(1, 64600, dtype=torch.float32)

# 3. Export to backend/models_weights/aasist.onnx
torch.onnx.export(
    model,
    dummy_input,
    "backend/models_weights/aasist.onnx",
    input_names=["audio_waveform"],
    output_names=["logits"],
    dynamic_axes={
        "audio_waveform": {0: "batch_size"},
        "logits": {0: "batch_size"},
    },
    opset_version=14,
)
```

Once the `.onnx` file is placed in `backend/models_weights/`, the backend automatically detects it without requiring a restart!

---

## 6. Running Automated Verification Tests

Execute all verification tests:

```powershell
# Complete test suite (76 automated tests)
.venv\Scripts\pytest.exe backend/tests/ -v

# Real-user QA verification audit (42 functional checks)
.venv\Scripts\python.exe backend/tests/real_user_qa_suite.py
```

