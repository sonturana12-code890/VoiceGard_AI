import os
import sys
import torch
import numpy as np
import soundfile as sf
import onnxruntime as ort
from scipy.signal import resample_poly
from math import gcd

# Ensure repo root on path
sys.path.insert(0, os.path.abspath("."))

from scripts.clova_aasist import Model
from backend.tests.test_full_pipeline_verification import make_synthetic_vocoder_voice

print("=" * 80)
print("BENCHMARKING OFFICIAL PYTORCH AASIST vs backend/models_weights/aasist.onnx")
print("=" * 80)

# 1. Load PyTorch model
d_args = {
    "first_conv": 128,
    "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
    "gat_dims": [64, 32],
    "pool_ratios": [0.5, 0.7, 0.5, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0]
}
py_model = Model(d_args)
py_model.load_state_dict(torch.load("weights/AASIST.pth", map_location="cpu"))
py_model.eval()

# 2. Load ONNX model
so = ort.SessionOptions()
so.enable_cpu_mem_arena = False
so.intra_op_num_threads = 1
onnx_session = ort.InferenceSession("backend/models_weights/aasist.onnx", so, providers=["CPUExecutionProvider"])
onnx_in = onnx_session.get_inputs()[0].name

def prepare_tensor(audio_data, sr):
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)
    if sr != 16000:
        g = gcd(sr, 16000)
        audio_data = resample_poly(audio_data, 16000 // g, sr // g)
    audio_data = audio_data.astype(np.float32)
    # Match standard AASIST padding/truncation
    if len(audio_data) < 64600:
        # Repeating wrap-pad or zero pad?
        num_repeats = int(64600 / len(audio_data)) + 1
        padded = np.tile(audio_data, num_repeats)[:64600]
    else:
        padded = audio_data[:64600]
    return padded

# Prepare test samples
samples = {}

# 1. Human voice: sontu1
a_sontu, sr_sontu = sf.read("sontu1.mp3", frames=64600)
samples["Human: sontu1.mp3"] = prepare_tensor(a_sontu, sr_sontu)

# 2. Human voice: human_test_95
a_h95, sr_h95 = sf.read("backend/uploads/human_test_95.wav", frames=64600)
samples["Human: human_test_95.wav"] = prepare_tensor(a_h95, sr_h95)

# 3. Synthetic: vocoder_clone
a_voc = make_synthetic_vocoder_voice(duration=2.5)
import io, wave
with wave.open(io.BytesIO(a_voc), "rb") as wf:
    raw = wf.readframes(wf.getnframes())
    samples["Synthetic: vocoder_clone.wav"] = (np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0)[:64600]
    if len(samples["Synthetic: vocoder_clone.wav"]) < 64600:
        samples["Synthetic: vocoder_clone.wav"] = np.pad(samples["Synthetic: vocoder_clone.wav"], (0, 64600 - len(samples["Synthetic: vocoder_clone.wav"])))

# 4. Synthetic: AI GENERATED.mp3
a_ai, sr_ai = sf.read("backend/uploads/3065c3498daf4856912fc23cf6e14420.mp3", frames=64600)
samples["Synthetic: AI GENERATED.mp3"] = prepare_tensor(a_ai, sr_ai)

# 5. Pure silence
samples["Control: pure_silence"] = np.zeros(64600, dtype=np.float32)

print("\nRunning Inference on all samples...\n")
for name, wav in samples.items():
    print(f"--- Sample: {name} ---")
    t_in = torch.from_numpy(wav).unsqueeze(0)
    
    # PyTorch official forward
    with torch.no_grad():
        _, py_out = py_model(t_in)
    py_logits = py_out.numpy()[0]
    py_exp = np.exp(py_logits - np.max(py_logits))
    py_probs = py_exp / np.sum(py_exp)
    
    # ONNX forward
    onnx_out = onnx_session.run(None, {onnx_in: np.expand_dims(wav, axis=0)})[0][0]
    onnx_exp = np.exp(onnx_out - np.max(onnx_out))
    onnx_probs = onnx_exp / np.sum(onnx_exp)
    
    print(f"  PyTorch Official Logits: [0]={py_logits[0]:.4f}, [1]={py_logits[1]:.4f}")
    print(f"  PyTorch Softmax Probs:   [0]={py_probs[0]*100:.2f}%, [1]={py_probs[1]*100:.2f}%")
    print(f"  ONNX Exported Logits:   [0]={onnx_out[0]:.4f}, [1]={onnx_out[1]:.4f}")
    print(f"  ONNX Softmax Probs:     [0]={onnx_probs[0]*100:.2f}%, [1]={onnx_probs[1]*100:.2f}%")
    
    # Check if ONNX matches PyTorch
    diff = np.max(np.abs(py_logits - onnx_out))
    print(f"  Max Logit Discrepancy (|PyTorch - ONNX|): {diff:.4f}")
    print()
