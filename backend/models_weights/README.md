# VOICEGUARD AI — AI Voice Anti-Spoofing Model Architecture & Integration Guide

**Problem Statement:** SIH26104 — AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks

This directory (`backend/models_weights/`) is the designated loading location for trained deepfake detection neural network checkpoints.

---

## 1. Supported Neural Architectures

### Model A: AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks)
- **Reference Paper:** Jung, J. et al., *"AASIST: Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks"*, Interspeech 2021.
- **Filename:** `aasist.onnx` (recommended for low-latency production inference) or `aasist.pt` (PyTorch checkpoint)
- **Input Specification:**
  - **Sample Rate:** `16,000 Hz` (Uniform 16kHz mono PCM)
  - **Input Tensor Shape:** `[batch_size, 64600]` (approx. 4.0375 seconds of audio)
  - **Data Type:** `float32` (normalized between `-1.0` and `+1.0`)
  - **Padding/Truncation:** Files shorter than 64,600 samples are wrapped/repeated or zero-padded; longer files are analyzed via 4-second sliding windows.
- **Internal Architecture:**
  1. *Sinc-convolutional front-end* (learns band-pass filter banks directly from raw waveform).
  2. *Residual Blocks* (extracts spectro-temporal feature representations).
  3. *Heterogeneous Graph Attention Layer* (models spectro-temporal nodes and temporal cross-attention).
  4. *Readout Pooling & Linear Classifier* (maps to 2-dimensional output logits: `[spoof_score, bona_fide_score]`).
- **Output Specification:**
  - **Output Tensor Shape:** `[batch_size, 2]`
  - **Classes:** Index 0 = `Spoof (Synthetic / Cloned Voice)`, Index 1 = `Bona-fide (Authentic Human Voice)`

### Model B: RawNet2
- **Reference Paper:** Tak, H. et al., *"End-to-End Spectro-Temporal Graph Attention for Audio Anti-Spoofing"*, 2021.
- **Filename:** `rawnet2.onnx`
- **Input Specification:** `[batch_size, 64600]` float32 at 16kHz.

### Model C: ECAPA-TDNN (Speaker Verification)
- **Reference Paper:** Desplanques, B. et al., *"ECAPA-TDNN: Emphasized Channel Attention, Propagation and Aggregation in TDNN"*, Interspeech 2020.
- **Filename:** `ecapa_tdnn.onnx`
- **Embedding Dimension:** `192-dimensional L2-normalized vector`

---

## 2. Exporting PyTorch Checkpoints to ONNX

If you have a trained PyTorch checkpoint (`weights.pth`), export it to ONNX for fast inference using the following snippet:

```python
import torch

# 1. Load model architecture and weights
model = AASIST(config)
model.load_state_dict(torch.load("weights.pth", map_location="cpu"))
model.eval()

# 2. Dummy 16kHz 4-second raw audio waveform
dummy_input = torch.randn(1, 64600, dtype=torch.float32)

# 3. Export to ONNX
torch.onnx.export(
    model,
    dummy_input,
    "backend/models_weights/aasist.onnx",
    input_names=["audio_waveform"],
    output_names=["logits"],
    dynamic_axes={
        "audio_waveform": {0: "batch_size"},
        "logits": {0: "batch_size"}
    },
    opset_version=14,
)
```

---

## 3. Runtime Detection Workflow

1. When an audio file or microphone recording is submitted:
   - It is ingested and checked for container integrity (WAV, MP3, FLAC, OGG, WebM).
   - Downmixed to single-channel (mono) and resampled to 16,000 Hz.
   - Padded or windowed to 64,600 samples (`[1, 64600]`).
2. **Inference Execution:**
   - If `backend/models_weights/aasist.onnx` exists, it is loaded via `onnxruntime` and inference is performed immediately.
   - Classification is assigned based on calibrated threshold:
     - `spoof_prob > 0.65` &rarr; `SYNTHETIC`
     - `spoof_prob < 0.35` &rarr; `AUTHENTIC`
     - `0.35 <= spoof_prob <= 0.65` &rarr; `INCONCLUSIVE`
3. **Unconfigured Fallback (Zero-Hallucination Contract):**
   - If no model weights are found in this directory, VOICEGUARD AI will **strictly refuse to fabricate fake results or random numbers**.
   - It outputs `classification = "INCONCLUSIVE"`, `analysis_status = "AI_MODEL_NOT_CONFIGURED"`, and provides empirical acoustic signal measurements (RMS power, zero-crossing rate, spectral centroid).

