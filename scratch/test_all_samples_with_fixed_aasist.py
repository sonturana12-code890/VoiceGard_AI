"""
Comprehensive Benchmark & Regression Test for Fixed AASIST ONNX Model
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.

Tests:
1. sontu1.mpeg (Real Human Voice)
2. Ayush CR.mpeg (Real Human Voice)
3. vocoder_clone.wav (Synthetic / Neural Vocoder Cloned Voice)
4. AI GENERATED.mp3 (Synthetic / TTS AI Cloned Voice)
5. noisy_vocal.wav (Real Human Voice with Acoustic Noise)
6. pure_silence.wav (Inaudible / Zero-Energy Control)
"""

import io
import math
import os
import sys
import wave
from pathlib import Path
import numpy as np
import soundfile as sf
import onnxruntime as ort

# Add repo root to path
sys.path.insert(0, os.path.abspath("."))

from backend.services.inference_pipeline import DetectionPipeline
from backend.services.audio_preprocessor import AudioPreprocessor
from backend.services.audio_segmenter import AudioSegmenter
from backend.services.prediction_engine import VoicePredictionEngine, stable_softmax
from backend.services.model_manager import ModelManager


def generate_fixtures():
    fixtures = {}

    # 1. vocoder_clone.wav
    sr = 16000
    duration = 2.5
    t = np.linspace(0.0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    f0 = 140.0
    synth_wave = (
        0.5 * np.sin(2.0 * np.pi * f0 * t)
        + 0.3 * np.sin(2.0 * np.pi * (f0 * 2) * t)
        + 0.2 * np.sin(2.0 * np.pi * (f0 * 3) * t)
        + 0.15 * np.sign(np.sin(2.0 * np.pi * (f0 * 4) * t))
    )
    fft_b = np.fft.rfft(synth_wave)
    freqs = np.fft.rfftfreq(len(synth_wave), 1.0 / sr)
    fft_b[freqs > 3200] = 0.0
    vocoder_pcm = np.fft.irfft(fft_b, n=len(synth_wave)).astype(np.float32)
    vocoder_pcm = vocoder_pcm / (np.max(np.abs(vocoder_pcm)) + 1e-8) * 0.95
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((vocoder_pcm * 32767.0).astype(np.int16).tobytes())
    fixtures["vocoder_clone.wav"] = buf.getvalue()

    # 2. noisy_vocal.wav
    f_formants = [500.0, 1500.0, 2500.0]
    vocal = np.zeros_like(t)
    for f in f_formants:
        vocal += (1.0 / (f / 500.0)) * np.sin(2.0 * np.pi * f * t)
    noise = np.random.normal(0, 0.05, len(t)).astype(np.float32)
    noisy_pcm = (vocal * 0.7 + noise).astype(np.float32)
    noisy_pcm = noisy_pcm / (np.max(np.abs(noisy_pcm)) + 1e-8) * 0.90
    buf_n = io.BytesIO()
    with wave.open(buf_n, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((noisy_pcm * 32767.0).astype(np.int16).tobytes())
    fixtures["noisy_vocal.wav"] = buf_n.getvalue()

    # 3. pure_silence.wav
    silence_pcm = np.zeros(int(sr * 2.0), dtype=np.float32)
    buf_s = io.BytesIO()
    with wave.open(buf_s, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((silence_pcm * 32767.0).astype(np.int16).tobytes())
    fixtures["pure_silence.wav"] = buf_s.getvalue()

    return fixtures


def main():
    print("=" * 80)
    print("VOICEGUARD AI — STEP 5: FORENSIC TESTING ACROSS ALL TEST SAMPLES")
    print("=" * 80)

    fixtures = generate_fixtures()

    test_files = [
        ("sontu1.mpeg", open("sontu1.mpeg", "rb").read()),
        ("Ayush CR.mpeg", open("Ayush CR.mpeg", "rb").read()),
        ("vocoder_clone.wav", fixtures["vocoder_clone.wav"]),
        ("AI GENERATED.mp3", open("AI GENERATED.mp3", "rb").read()),
        ("noisy_vocal.wav", fixtures["noisy_vocal.wav"]),
        ("pure_silence.wav", fixtures["pure_silence.wav"]),
    ]

    pipeline = DetectionPipeline()

    print(f"\n{'Test Sample':<20s} | {'Model':<8s} | {'Logits [0, 1]':<22s} | {'Synthetic%':<11s} | {'Human%':<10s} | {'Prediction':<14s} | {'Confidence':<10s}")
    print("-" * 110)

    for filename, raw_bytes in test_files:
        for model in ["AASIST", "RAWNET2"]:
            res = pipeline.analyze_audio(raw_bytes, filename=filename, model_name=model)
            h_prob = res.get("human_probability")
            s_prob = res.get("synthetic_probability")
            pred = res.get("predicted_class") or res.get("prediction", {}).get("label")
            conf = res.get("confidence_score")

            h_str = f"{h_prob*100:.2f}%" if h_prob is not None else "N/A"
            s_str = f"{s_prob*100:.2f}%" if s_prob is not None else "N/A"
            c_str = f"{conf*100:.2f}%" if conf is not None else "N/A"

            # Check raw segment logits from first segment if available
            seg_results = res.get("segment_analysis", [])
            log_str = "N/A"
            if seg_results and "raw_logits" in seg_results[0]:
                log_str = f"[{seg_results[0]['raw_logits'][0]:.2f}, {seg_results[0]['raw_logits'][1]:.2f}]"
            elif seg_results:
                log_str = f"Segs: {len(seg_results)}"

            print(f"{filename:<20s} | {model:<8s} | {log_str:<22s} | {s_str:<11s} | {h_str:<10s} | {pred:<14s} | {c_str:<10s}")

    print("\n" + "=" * 80)
    print("STEP 5 COMPLETE.")
    print("=" * 80)


if __name__ == "__main__":
    main()
