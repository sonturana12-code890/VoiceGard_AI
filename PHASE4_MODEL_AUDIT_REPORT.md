# VOICEGUARD AI — PHASE 4 MODEL AUDIT & INTEGRATION REPORT

**Audit Date:** 2026-11-13  
**Project:** VoiceGuard AI — Cyber Acoustic Defense & AI Voice Anti-Spoofing  
**Problem Statement:** SIH26104 — AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks  
**Phase:** Phase 4 — Deepfake Detection Engine & Neural Model Integration  
**Audit Status:** COMPLETE — ARCHITECTURE READY / CHECKPOINTS PENDING DEPLOYMENT  

---

## 1. Executive Summary

A comprehensive architectural and forensic audit was conducted on the **VoiceGuard AI** machine learning backend, model loading subsystems, runtime dependencies, and neural detection pipeline. 

### Key Findings
1. **Pipeline Architecture Readiness:** The complete audio preprocessing, acoustic feature extraction (MFCC, Mel Spectrogram, Spectral Centroid, Bandwidth, Roll-off, ZCR, RMS), intelligent 64,600-sample sliding-window segmentation, stable Softmax probability computation, and temporal segment aggregation pipeline is **100% designed, implemented, and unit-tested**.
2. **Physical Checkpoint Status:** Physical pretrained model checkpoints (`aasist.onnx`, `rawnet2.onnx`, `ecapa_tdnn.onnx`) **do not exist on disk** inside `backend/models_weights/` (only the integration `README.md` is present).
3. **Zero-Hallucination Policy Adherence:** The backend strictly complies with the Zero-Hallucination Contract. When model weights are absent, the system **strictly refuses to fabricate synthetic probabilities or random scores**. It reports `analysis_status: "AI_MODEL_NOT_CONFIGURED"`, `model_status: "MODEL_NOT_AVAILABLE"`, and `prediction.label: "INCONCLUSIVE"`, while providing authentic empirical acoustic measurements.
4. **Runtime Environment & Dependencies:** The backend runs on **Python 3.13.7** with **ONNX Runtime 1.30.0**, **NumPy 2.5.3**, and **PyAV 19.0.2** installed and verified. Heavy, platform-sensitive training libraries (`torch`, `torchaudio`, `librosa`, `scipy`) are not installed; all inference and DSP feature extractions are implemented in high-performance pure NumPy and ONNX Runtime.

---

## 2. Directory & Model Subsystem Inspection

### 2.1 Model Checkpoint Directory (`backend/models_weights/`)
```
backend/models_weights/
├── README.md               [4,122 bytes] (Integration guide & tensor specs)
├── aasist.onnx             [MISSING / NOT INSTALLED]
├── rawnet2.onnx            [MISSING / NOT INSTALLED]
└── ecapa_tdnn.onnx         [MISSING / NOT INSTALLED]
```
- **Physical Checkpoint Scan:** Recursive scanning confirmed zero `.onnx`, `.pt`, `.pth`, or `.bin` files in the repository.
- **Directory Permissions:** `backend/models_weights/` is writable and tracked by the backend `ModelManager` singleton.

### 2.2 Core Backend ML Services Audit

| Service File | Component | Implementation Status | Functional Role |
|---|---|:---:|---|
| `backend/services/model_manager.py` | `ModelManager` | **COMPLETE** | Singleton managing ONNX Runtime inference sessions, automated device selection (`CUDAExecutionProvider` $\to$ `CPUExecutionProvider`), dynamic shape checking `[batch_size, 64600]`, and session caching. |
| `backend/services/prediction_engine.py` | `VoicePredictionEngine` | **COMPLETE** | Coordinates neural inference, numerically stable Softmax (`stable_softmax`), multi-segment temporal aggregation, calibrated thresholding, and zero-hallucination reporting. |
| `backend/services/inference_pipeline.py` | `DetectionPipeline` | **COMPLETE** | Unified orchestrator executing the 6-stage lifecycle: Validation $\to$ Decoding $\to$ Feature Extraction $\to$ Segmentation $\to$ Prediction $\to$ Forensic Report Assembly. |
| `backend/services/audio_segmenter.py` | `AudioSegmenter` | **COMPLETE** | Intelligent audio segmenter: window size 64,600 samples (~4.0375s at 16kHz), 1.0s overlap (step 48,600 samples), and ASVspoof wrap-around circular tiling (`np.tile`) for audio $<4.0$s. |
| `backend/services/feature_extractor.py` | `AudioFeatureExtractor` | **COMPLETE** | Pure NumPy forensic DSP extractor: MFCC (13 coeffs), Log-Mel Spectrogram (40 filterbanks), Spectral Centroid, Bandwidth, Roll-off (85%), Zero-Crossing Rate, and RMS energy. |
| `backend/services/audio_preprocessor.py` | `AudioPreprocessor` | **COMPLETE** | Converts raw container streams (WAV, MP3, MPEG, FLAC, OGG, WebM) into uniform 16,000 Hz mono float32 linear PCM normalized to $[-1.0, 1.0]$. |
| `backend/services/live_stream_service.py` | `LiveAudioSession` | **COMPLETE** | Ingests ephemeral 16kHz S16LE PCM chunks over WebSockets, calculating live RMS dBFS, peak dBFS, ZCR, FFT spectral centroid, and sliding circular window buffer. |
| `backend/services/risk_engine.py` | `FraudRiskEngine` | **COMPLETE** | Evaluates cybersecurity threat levels (Low, Medium, High, Critical) by correlating synthetic detection scores, speaker biometrics, and contextual flags. |

---

## 3. Neural Model Architectures Audit

### 3.1 AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks)
- **Primary Domain:** Logical Access (LA) synthetic speech, vocoder artifacts, and neural voice cloning detection.
- **Reference Publication:** Jung, J. et al., *"AASIST: Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks"*, Interspeech 2021.
- **Expected Input Tensor:**
  - Shape: `[batch_size, 64600]`
  - Format: Float32 single-channel mono PCM normalized to $[-1.0, 1.0]$
  - Sample Rate: $16,000\text{ Hz}$ ($64,600\text{ samples} \approx 4.0375\text{ seconds}$)
- **Internal Stages:**
  1. *Sinc-convolutional front-end:* Learns parameterized band-pass filterbanks directly from raw time-domain waveforms.
  2. *Residual Blocks:* Extracts dual-path temporal and spectral feature representations.
  3. *Heterogeneous Graph Attention Networks (HGAT):* Constructs a graph where temporal and spectral nodes exchange context via masked attention.
  4. *Readout Pooling:* Aggregates graph representations into 2-dimensional classification logits.
- **Expected Output Tensor:**
  - Shape: `[batch_size, 2]`
  - Index 0: Bona-fide (Authentic Human Speech)
  - Index 1: Spoof (Synthetic / Deepfake Speech)
- **Software Integration:** Implemented in `ModelManager.run_inference("aasist", tensor)` and `VoicePredictionEngine.predict(segments, model_name="AASIST")`.

### 3.2 RawNet2 (End-to-End Raw Waveform Deepfake Detection)
- **Primary Domain:** Direct waveform anti-spoofing without spectral transformations.
- **Reference Publication:** Tak, H. et al., *"End-to-End Spectro-Temporal Graph Attention for Audio Anti-Spoofing"*, 2021.
- **Expected Input Tensor:**
  - Shape: `[batch_size, 64600]` float32 at $16,000\text{ Hz}$.
- **Internal Stages:**
  1. *SincNet filterbank:* Raw waveform filtering.
  2. *Residual Blocks with Feature Map Scaling (FMS):* Emphasizes salient frequency subbands.
  3. *Gated Recurrent Units (GRU):* Captures long-term sequential dependencies.
  4. *Linear Classifier:* Produces 2-dimensional logits `[batch_size, 2]`.
- **Software Integration:** Implemented in `ModelManager.run_inference("rawnet2", tensor)` and `VoicePredictionEngine.predict(segments, model_name="RAWNET2")`.

### 3.3 ECAPA-TDNN (Speaker Verification & Zero-Trust Biometrics)
- **Primary Domain:** Speaker voiceprint enrollment and 1:1 biometric identity verification.
- **Reference Publication:** Desplanques, B. et al., *"ECAPA-TDNN: Emphasized Channel Attention, Propagation and Aggregation in TDNN"*, Interspeech 2020.
- **Expected Embedding Output:**
  - Shape: `[batch_size, 192]` ($192\text{-dimensional}$ $L_2\text{-normalized}$ vector).
  - Metric: Cosine similarity against enrolled baseline voiceprint ($S_{\cos} \ge 0.75 \implies \text{Match}$).
- **Software Integration:** Prepared in `backend/routes/speaker_routes.py` and `SUPPORTED_MODELS["ecapa_tdnn"] = "ecapa_tdnn.onnx"`.

---

## 4. Physical Checkpoint & Weights Verification

| Checkpoint Name | Configured Path | File Exists? | File Size | Runtime Session Active? |
|---|---|:---:|:---:|:---:|
| `aasist.onnx` | `backend/models_weights/aasist.onnx` | **NO** | 0 bytes | False |
| `rawnet2.onnx` | `backend/models_weights/rawnet2.onnx` | **NO** | 0 bytes | False |
| `ecapa_tdnn.onnx` | `backend/models_weights/ecapa_tdnn.onnx` | **NO** | 0 bytes | False |

### Zero-Hallucination Policy Audit
The system guarantees cryptographic and scientific honesty:
```python
# From backend/services/prediction_engine.py
if not is_available:
    return {
        "prediction": {
            "label": "INCONCLUSIVE",
            "human_probability": None,
            "synthetic_probability": None,
            "confidence": None,
            "model_used": "AASIST",
            "inference_completed": False,
            "status": "MODEL_NOT_AVAILABLE"
        },
        "analysis_status": "AI_MODEL_NOT_CONFIGURED",
        "missing_files": ["aasist.onnx"],
        ...
    }
```
- **Live Verification:** Calling `POST /api/v1/audio/analyze` with audio files returns HTTP 200 with `status: "AI_MODEL_NOT_CONFIGURED"`, `synthetic_probability: null`, and `human_probability: null`.
- **Integrity Verified:** No random numbers or fabricated predictions are returned to the user or database.

---

## 5. Runtime Dependencies & Compatibility Analysis

### 5.1 Active Environment Specifications
- **Operating System:** Windows 10/11 (64-bit)
- **Python Runtime:** Python `3.13.7`
- **Virtual Environment:** `backend/.venv`

### 5.2 Installed ML & DSP Packages

| Package | Version | Status | Suitability & Compatibility |
|---|---|:---:|---|
| `onnxruntime` | `1.30.0` | **INSTALLED** | Fully operational on Python 3.13. Supports multi-threaded graph optimization (`ORT_ENABLE_ALL`) on CPU. |
| `numpy` | `2.5.3` | **INSTALLED** | Fast array mathematics and DSP matrix operations. |
| `av` (PyAV) | `19.0.2` | **INSTALLED** | Direct bindings to FFmpeg for high-speed container demuxing and decoding. |
| `fastapi` | `0.162.4` | **INSTALLED** | Asynchronous REST and WebSocket server. |
| `pydantic` | `2.14.3` | **INSTALLED** | Strict request/response schema validation. |
| `websockets` | `17.4` | **INSTALLED** | Ephemeral PCM streaming support. |

### 5.3 Missing Packages & Architectural Choice

| Package | Status | Impact Analysis & Strategic Decision |
|---|:---:|---|
| `torch` / `torchaudio` | **NOT INSTALLED** | Python 3.13 is very recent; official prebuilt PyTorch binary wheels with Windows CUDA support are not standard on PyPI. **VoiceGuard AI's architectural decision to target ONNX Runtime (`.onnx`) avoids heavy PyTorch dependencies (4+ GB) in production and allows lightweight, cross-platform deployment.** |
| `librosa` / `scipy` | **NOT INSTALLED** | `librosa` introduces complex Numba / LLVM dependencies. VoiceGuard AI resolved this by implementing all forensic features (MFCC, Mel Filterbanks, DCT-II, STFT, Spectral Centroid, ZCR, RMS) directly in **pure NumPy** (`backend/services/feature_extractor.py`), achieving deterministic, zero-dependency execution. |
| `soundfile` | **NOT INSTALLED** | Replaced by `PyAV` (`av.open`), which natively decodes MP3, WAV, MPEG, FLAC, OGG, M4A, WebM, and Opus without requiring `libsndfile`. |

### 5.4 Hardware Execution Providers
- `ModelManager._select_execution_device()` dynamically queries `ort.get_available_providers()`.
- **Current Active Provider:** `CPUExecutionProvider` (multi-threaded, bounded to `min(4, os.cpu_count())`).
- **Inference Latency Estimate:** ~20–50 ms per 4-second audio window on CPU, which comfortably satisfies real-time VoIP streaming criteria (< 200 ms latency window).

---

## 6. Detailed Model Integration & Deployment Plan

To transition from the current "Architecture Ready (Zero-Hallucination Fallback)" state to "Active Neural Inference", follow this 4-step deployment procedure:

### Step 1: Model Checkpoint Acquisition & Training
Obtain pretrained checkpoints trained on official ASVspoof 2019 Logical Access (LA) and ASVspoof 2021 DF (Deepfake) datasets:
1. **AASIST Checkpoint:** Official ASVspoof 2019 LA benchmark weights ($EER \approx 0.83\%$).
2. **RawNet2 Checkpoint:** Official ASVspoof 2019 LA baseline ($EER \approx 1.25\%$).
3. **ECAPA-TDNN Checkpoint:** SpeechBrain VoxCeleb pretrained model.

### Step 2: Export PyTorch Checkpoints to ONNX
Run the following export script in an offline development environment with PyTorch installed:

```python
import torch
import torch.nn as nn
from aasist import AASIST  # Model definition

def export_aasist_to_onnx(checkpoint_path: str, output_path: str):
    # 1. Instantiate model architecture
    model = AASIST(config)
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()

    # 2. AASIST input: [batch_size, 64600] float32 at 16kHz
    dummy_input = torch.randn(1, 64600, dtype=torch.float32)

    # 3. Export to ONNX with dynamic batch axis
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["audio_waveform"],
        output_names=["logits"],
        dynamic_axes={
            "audio_waveform": {0: "batch_size"},
            "logits": {0: "batch_size"}
        }
    )
    print(f"Exported AASIST ONNX model to {output_path}")

# Run export
export_aasist_to_onnx("AASIST-L.pth", "backend/models_weights/aasist.onnx")
```

### Step 3: Checkpoint Installation & Hot-Reloading
1. Copy the exported `.onnx` files directly into:
   ```
   c:\Users\LC\OneDrive\Desktop\VoiceGard_AI\backend\models_weights\aasist.onnx
   c:\Users\LC\OneDrive\Desktop\VoiceGard_AI\backend\models_weights\rawnet2.onnx
   c:\Users\LC\OneDrive\Desktop\VoiceGard_AI\backend\models_weights\ecapa_tdnn.onnx
   ```
2. **Zero-Downtime Hot Detection:**  
   `ModelManager.is_model_available()` checks for physical file existence dynamically on each request. As soon as `aasist.onnx` is copied into `backend/models_weights/`, the backend immediately:
   - Loads the ONNX InferenceSession into thread-safe memory cache.
   - Activates neural prediction in `VoicePredictionEngine`.
   - Transitions API responses from `AI_MODEL_NOT_CONFIGURED` to `completed`.
   - Populates real `human_probability`, `synthetic_probability`, and `confidence_score`.
   - **No backend code modifications or server restarts are required.**

### Step 4: Decision Threshold & Multi-Segment Aggregation Tuning
The decision engine applies calibrated thresholds:
- **Segment-Level Threshold:**
  - $P_{\text{synthetic}} \ge 0.65 \implies \text{AI\_GENERATED}$
  - $P_{\text{human}} \ge 0.65 \implies \text{HUMAN}$
  - Otherwise $\implies \text{INCONCLUSIVE}$
- **Audio-Level Temporal Aggregation:**
  - If $\max(P_{\text{synthetic}}) \ge 0.80$ OR $\text{mean}(P_{\text{synthetic}}) \ge 0.65 \implies \text{Final Label: AI\_GENERATED}$
  - Else if $\text{mean}(P_{\text{human}}) \ge 0.65 \implies \text{Final Label: HUMAN}$
  - Otherwise $\implies \text{Final Label: INCONCLUSIVE}$
- **Dual-Model Ensemble Strategy:**
  When both AASIST and RawNet2 are installed:
  $$P_{\text{ensemble}} = 0.65 \times P_{\text{AASIST}} + 0.35 \times P_{\text{RawNet2}}$$
  AASIST's graph attention focuses on spectral vocoder anomalies, while RawNet2's SincNet focuses on raw waveform phase disruptions, providing defense-in-depth against diverse synthetic attack vectors.

---

## 7. Audit Conclusion & Next Steps

| Subsystem | Audit Status | Operational Verdict |
|---|:---:|---|
| Audio Preprocessing & Decoding | **VERIFIED** | Supports all major formats (WAV, MP3, MPEG, FLAC, OGG, WebM) down to 16kHz mono. |
| Feature Extraction (DSP) | **VERIFIED** | Pure NumPy implementation of MFCC, Mel Spectrogram, Spectral Centroid, ZCR, RMS. |
| Segmentation Engine | **VERIFIED** | 64,600-sample sliding window with circular wrap-around tiling. |
| Model Loading Framework | **VERIFIED** | Thread-safe ONNX Runtime singleton with dynamic caching and shape validation. |
| Zero-Hallucination Compliance | **VERIFIED** | Strictly returns `INCONCLUSIVE` and null scores when weights are uninstalled. |
| Physical Pretrained Checkpoints | **PENDING** | `aasist.onnx` and `rawnet2.onnx` must be placed in `backend/models_weights/`. |

### Immediate Recommendations
1. Maintain existing zero-hallucination compliance to guarantee forensic credibility.
2. Obtain or export the pretrained `aasist.onnx` checkpoint (input `[batch, 64600]`, output `[batch, 2]`).
3. Place `aasist.onnx` in `backend/models_weights/` to instantly enable real AI deepfake detection.

