# VOICEGUARD AI — Phase 3 Technical Documentation
## Advanced Audio Detection & Processing Pipeline Architecture

**Problem Statement:** SIH26104 — AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks  
**System Version:** 3.0.0-PROD  
**Author:** Principal AI/ML Engineer, Audio Signal Processing Architect, and Software Systems Lead  

---

## 1. Executive Summary

Phase 3 implements an end-to-end, production-grade **Audio Detection & Preprocessing Pipeline** for **VOICEGUARD AI**. The architecture accepts arbitrary multi-format audio streams, validates container integrity, resamples signals to 16,000 Hz mono PCM, slices continuous recordings into overlapping 64,600-sample windows, executes neural anti-spoofing inference via ONNX Runtime (AASIST / RawNet2), aggregates segment-level predictions, and generates structured forensic telemetry.

The implementation strictly honors the **Zero-Hallucination Contract**: in the absence of trained neural weights, the platform calculates empirical acoustic signal metrics (RMS energy, spectral centroid, silence ratio, clipping, autocorrelation pitch stability) and returns explicit `INCONCLUSIVE` / `AI_MODEL_NOT_CONFIGURED` statuses without fabricating artificial probabilities.

---

## 2. Pipeline Architecture & Workflow

```
                        [ User Audio Stream ]
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ AudioValidator Engine │
                     └───────────────────────┘
                                 │
           ┌─────────────────────┴─────────────────────┐
     [Invalid/Malware]                           [Valid Audio]
           │                                           │
           ▼                                           ▼
┌──────────────────────┐                  ┌─────────────────────────┐
│ Structured Rejection │                  │   AudioPreprocessor     │
│ (400/413 Error Code) │                  │ (Decode, Mono, 16kHz)   │
└──────────────────────┘                  └─────────────────────────┘
                                                       │
                                                       ▼
                                          ┌─────────────────────────┐
                                          │     AudioSegmenter      │
                                          │ (64,600-sample Windows) │
                                          └─────────────────────────┘
                                                       │
                                                       ▼
                                          ┌─────────────────────────┐
                                          │      ModelManager       │
                                          │ (CUDA/CPU ONNX Session) │
                                          └─────────────────────────┘
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                    [Weights Present]                                       [Weights Missing]
                           │                                                       │
                           ▼                                                       ▼
               ┌───────────────────────┐                               ┌───────────────────────┐
               │    Neural Inference   │                               │  Zero-Hallucination   │
               │   (AASIST / RawNet2)  │                               │    Acoustic Report    │
               │ Logits & Softmax Prob │                               │  (Empirical DSP Only) │
               └───────────────────────┘                               └───────────────────────┘
                           │                                                       │
                           ▼                                                       ▼
               ┌───────────────────────┐                               ┌───────────────────────┐
               │  Segment Aggregation  │                               │  Unconfigured Status  │
               │ (Mean, Max Anomaly)   │                               │ (INCONCLUSIVE Result) │
               └───────────────────────┘                               └───────────────────────┘
                           │                                                       │
                           └───────────────────────────┬───────────────────────────┘
                                                       │
                                                       ▼
                                          ┌─────────────────────────┐
                                          │ Structured API Response │
                                          │    (FastAPI Endpoint)   │
                                          └─────────────────────────┘
```

---

## 3. Core Engine Components

### 3.1 Audio Upload & Validation Engine (`backend/services/audio_validator.py` & `ffmpeg_service.py`)
- **Supported Formats:** `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`, `.aac`, `.webm`, `.opus`, `.mpeg`, `.mpg`.
- **Validation Layers:**
  1. *Extension & Path Traversal Guard:* Strips directory separators; enforces strict extension whitelisting.
  2. *MIME Verification:* Permissive audio and MPEG video/container MIME validation (`audio/mpeg`, `video/mpeg`, `audio/mpg`, `video/mpg`).
  3. *Size Bounds:* Rejects empty files (0 bytes) with `EMPTY_AUDIO` and oversized files (>25 MB) with `FILE_TOO_LARGE` (HTTP 413).
  4. *Header Signature (Magic Bytes):* Inspects binary signatures (e.g. `RIFF...WAVE`, `ID3`, `\xff\xfb`, `fLaC`, `OggS`, `ftyp`, MPEG Program Stream pack headers `\x00\x00\x01\xba`, MPEG system sequence headers `\x00\x00\x01\xb3`, and MPEG-TS sync bytes `\x47`).
  5. *Stream Inspection, Codec Normalization & Validation (`FFmpegService`):* For MPEG/MPG files, demuxes the container, verifies presence of an audio stream (rejecting video-only files with `NO_AUDIO_STREAM`), checks audio codec compatibility, and rejects corrupted streams with `CORRUPTED_AUDIO`.
     - **Safe Codec Normalization Matrix:** Libavcodec/FFprobe decoders often report floating-point internal decoder variants (`mp3float`, `mp2float`, `mp1float`, `mp3adufloat`, `aac_latm`). The normalization engine transparently maps decoder aliases to canonical codec standards without bypassing security or decoder availability checks:
       - `mp3float`, `mp3`, `mp3on4`, `mp3on4float` $\rightarrow$ `mp3`
       - `mp3adu`, `mp3adufloat` $\rightarrow$ `mp3adu`
       - `mp1float`, `mp1` $\rightarrow$ `mp1`
       - `mp2float`, `mp2` $\rightarrow$ `mp2`
       - `aac_latm`, `aac_fixed`, `aac` $\rightarrow$ `aac`
       - `ac3_fixed`, `ac3` $\rightarrow$ `ac3`
     - **Hardware & Library Decoder Availability:** Validates codec against `av.codec.Codec(name, 'r')` (`is_decoder=True`, `type='audio'`) and FFmpeg CLI decoder registry. Non-decodable or unknown codecs (e.g. `experimental_unsupported_codec_xyz`) are strictly rejected with structured error code `UNSUPPORTED_CODEC`.
  6. *Stream Decodability:* Uses embedded PyAV (`av`) and `wave` to verify that the container contains valid decodable audio frames.
  7. *Duration Guard:* Rejects audio shorter than 200ms (`AUDIO_TOO_SHORT`) or longer than 300 seconds (`AUDIO_TOO_LONG`).

### 3.2 Advanced Audio Preprocessing Engine (`backend/services/audio_preprocessor.py` & `ffmpeg_service.py`)
- **Audio Decoding & FFmpeg Integration:** High-precision float32 decoding in `[-1.0, 1.0]`. For MPEG/MPG containers, `FFmpegService.decode_to_pcm()` extracts the first audio stream using PyAV C-bindings (or safe CLI subprocessing), demuxes audio frames, ignores video frames, and standardizes to 16,000 Hz mono PCM.
- **Downmixing:** Channels > 1 are averaged along axis 1 (`pcm.reshape(-1, channels).mean(axis=1)`) to preserve multi-mic energy.
- **Sample Rate Normalization:** Standardizes to 16,000 Hz using linear interpolation or embedded resamplers (`av.AudioResampler`).
- **Amplitude Scaling:** Non-destructive peak normalization (`peak_target = 0.98`); gentle boost for weak recordings (>1e-4, <0.05).
- **Acoustic Quality Analysis:**
  - `duration_seconds`: Stream length in seconds.
  - `sample_rate` & `channels`: Sampling parameters.
  - `peak_amplitude`: Max absolute amplitude.
  - `rms_energy`: Root-mean-square energy $\sqrt{\frac{1}{N}\sum x[n]^2}$.
  - `silence_ratio`: Fraction of 20ms frames where RMS < 0.01 (-40 dB).
  - `clipping_ratio`: Fraction of samples where $|x[n]| \ge 0.995$.
  - `is_clipped` & `is_silent`: Binary acoustic sanity flags.
  - `spectral_centroid_hz`: Frequency center of mass $\frac{\sum f \cdot |X[f]|}{\sum |X[f]|}$.
  - `high_frequency_ratio`: Ratio of power above 4,000 Hz (identifies neural vocoder low-pass cutoffs).
  - `pitch_stability`: Autocorrelation peak between 50 Hz and 500 Hz.

### 3.3 Audio Segmentation Engine (`backend/services/audio_segmenter.py`)
- **AASIST Input Specification:** Window duration of 64,600 samples (~4.0375 seconds at 16,000 Hz).
- **Short Audio Strategy:** When $N < 64600$, the waveform is cyclically tiled/repeated (`np.tile(pcm, k)[:64600]`), matching ASVspoof / AASIST training conditions.
- **Long Audio Strategy:** Sliding window with configurable overlap (default 1.0 second). Slices continuous audio into ordered segments with timestamps (`start_time`, `end_time`) and segment indices.
- **Tail Preservation:** Ensures trailing samples are covered by extracting a final window `pcm[-64600:]`.

### 3.4 AI Model Manager (`backend/services/model_manager.py`)
- **Singleton Pattern:** Thread-safe instance managing ONNX Runtime inference sessions.
- **Device Prioritization:**
  1. `CUDAExecutionProvider` (if GPU and CUDA libraries are active).
  2. `CPUExecutionProvider` (optimized intra-op thread allocation).
- **Input Dimension Enforcement:** Validates 2D tensor shape `[batch_size, 64600]` and `float32` dtype.
- **Session Caching:** Sessions are loaded once on demand and reused across concurrent requests.

### 3.5 Centralized Detection Pipeline (`backend/services/inference_pipeline.py`)
- Coordinates validation, preprocessing, segmentation, model execution, and segment prediction aggregation.
- **Aggregation Formula:**
  - Mean Synthetic Probability: $\bar{P}_{\text{spoof}} = \frac{1}{K}\sum_{i=1}^K P_{\text{spoof}}^{(i)}$
  - Peak Anomaly Detection: $P_{\text{spoof}}^{\max} = \max_i P_{\text{spoof}}^{(i)}$
  - Final Classification:
    - If $P_{\text{spoof}}^{\max} \ge 0.80$ or $\bar{P}_{\text{spoof}} \ge 0.65$: `AI_GENERATED`
    - Else if $\bar{P}_{\text{human}} \ge 0.65$: `HUMAN`
    - Otherwise: `INCONCLUSIVE`

---

## 4. API Endpoints Reference

### `POST /api/v1/audio/analyze`
Executes full Phase 3 detection pipeline and persists metadata in SQLite.
- **Headers:** `Authorization: Bearer <token>`
- **Content-Type:** `multipart/form-data`
- **Parameters:**
  - `file`: Audio binary (WAV, MP3, FLAC, OGG, M4A, AAC, WEBM, OPUS, MPEG, MPG)
  - `model_name` (query, optional): Model selector (`AASIST`, `RawNet2`, `Ensemble`). Default: `AASIST`.
- **Response (200 OK):**
```json
{
  "success": true,
  "analysis_id": "8b51d8b2-5f60-496a-a2ff-e56c547f3ad9",
  "filename": "sample_call.wav",
  "status": "completed",
  "prediction": {
    "label": "AI_GENERATED",
    "human_probability": 0.08,
    "synthetic_probability": 0.92,
    "confidence": 0.92
  },
  "model": {
    "name": "AASIST",
    "inference_completed": true,
    "device": "CPUExecutionProvider",
    "version": "1.0.0"
  },
  "audio_information": {
    "duration": 8.4,
    "sample_rate": 16000,
    "channels": 1,
    "peak_amplitude": 0.85,
    "rms_energy": 0.22,
    "silence_ratio": 0.02,
    "clipping_ratio": 0.0,
    "is_clipped": false,
    "is_silent": false,
    "spectral_centroid_hz": 1940.2,
    "high_frequency_ratio": 0.11,
    "pitch_stability": 0.94
  },
  "segments_analyzed": 2,
  "processing_time_seconds": 0.18,
  "segment_analysis": [
    {
      "segment_id": 1,
      "start": 0.0,
      "end": 4.038,
      "prediction": "HUMAN",
      "score": 0.88,
      "human_probability": 0.88,
      "synthetic_probability": 0.12,
      "status": "completed"
    },
    {
      "segment_id": 2,
      "start": 3.038,
      "end": 7.076,
      "prediction": "AI_GENERATED",
      "score": 0.95,
      "human_probability": 0.05,
      "synthetic_probability": 0.95,
      "status": "completed"
    }
  ]
}
```

### `POST /api/v1/audio/validate`
Validates container, decodability, duration, and returns validation status without running inference.
- **Content-Type:** `multipart/form-data`
- **Response (200 OK):**
```json
{
  "success": true,
  "valid": true,
  "filename": "sample.wav",
  "format": "wav",
  "file_size": 192044,
  "duration_seconds": 6.0,
  "sample_rate": 16000,
  "channels": 1,
  "message": "Audio file passed validation."
}
```

### `GET /api/v1/audio/analysis/{analysis_id}`
Retrieves complete forensic report including segment-level analysis for an existing record.
- **Headers:** `Authorization: Bearer <token>`
- **Response (200 OK):** Complete forensic dictionary matching the schema above.

### `GET /api/v1/audio/health`
Checks detection pipeline readiness, model files on disk, and execution devices.
- **Response (200 OK):**
```json
{
  "status": "healthy",
  "pipeline_version": "3.0.0",
  "supported_models": ["AASIST", "RawNet2", "ECAPA-TDNN"],
  "supported_formats": ["wav", "mp3", "flac", "ogg", "m4a", "aac", "webm", "opus", "mpeg", "mpg"],
  "target_sample_rate": 16000,
  "expected_input_samples": 64600,
  "models_status": {
    "device": "CPUExecutionProvider",
    "onnxruntime_available": true,
    "models": {
      "aasist": { "installed": false, "filename": "aasist.onnx" },
      "rawnet2": { "installed": false, "filename": "rawnet2.onnx" }
    }
  }
}
```

---

## 5. Verification Commands

```powershell
# 1. Run all Phase 3 automated pipeline tests (18 tests)
.venv\Scripts\pytest.exe backend/tests/test_phase3_pipeline.py -v

# 2. Run MPEG/MPG audio format & codec regression test suite (15 tests)
.venv\Scripts\pytest.exe backend/tests/test_mpeg_support.py -v

# 3. Run comprehensive test suite across all modules (81 tests)
.venv\Scripts\pytest.exe backend/tests/ -v

# 4. Run full real-user QA verification suite (42 checks)
.venv\Scripts\python.exe backend/tests/real_user_qa_suite.py
```

---

## 6. Known Limitations & Zero-Hallucination Guardrails
1. **Pretrained Weights Dependency:** High-fidelity deepfake classification requires trained ONNX checkpoints in `backend/models_weights/aasist.onnx` or `rawnet2.onnx`.
2. **Zero-Hallucination Enforcement:** If weights are missing, the system strictly outputs `INCONCLUSIVE` and `synthetic_probability: null`, preventing deceptive false-confidence metrics in production.

