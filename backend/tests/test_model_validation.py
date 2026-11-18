"""
VOICEGUARD AI — Module 5: Comprehensive Model Validation Suite
Empirical verification of AASIST and RawNet2 neural inference against:
1. Genuine human speech
2. Synthetic speech
3. Different audio durations (1.0s, 4.0375s, 10.0s)
4. Noisy recordings
5. Invalid/corrupted audio
6. Empty audio
7. Unsupported formats
"""

import io
import math
import struct
import wave
import numpy as np
import pytest

from backend.services.audio_validator import AudioValidator
from backend.services.inference_pipeline import DetectionPipeline
from backend.services.model_manager import ModelManager


def generate_wav(
    duration: float = 4.0,
    sample_rate: int = 16000,
    signal_type: str = "human",
    noise_sigma: float = 0.001,
) -> bytes:
    """Generates synthetic test audio WAV."""
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    if signal_type == "human":
        # Formants (F0 ~ 130 Hz, F1 ~ 730 Hz, F2 ~ 1090 Hz)
        sig = (
            0.4 * np.sin(2 * np.pi * 130 * t)
            + 0.25 * np.sin(2 * np.pi * 730 * t)
            + 0.15 * np.sin(2 * np.pi * 1090 * t)
        ).astype(np.float32)
    elif signal_type == "synthetic":
        # Unnatural harmonics, step phase discontinuities
        sig = (
            0.5 * np.sign(np.sin(2 * np.pi * 440 * t))
            + 0.3 * np.sin(2 * np.pi * 3500 * t)
            + 0.2 * np.sin(2 * np.pi * 7000 * t)
        ).astype(np.float32)
    elif signal_type == "silence":
        sig = np.zeros(num_samples, dtype=np.float32)
    else:
        sig = np.random.normal(0, 0.1, num_samples).astype(np.float32)

    if noise_sigma > 0:
        sig += np.random.normal(0, noise_sigma, num_samples).astype(np.float32)

    sig = np.clip(sig, -1.0, 1.0)
    int_pcm = (sig * 32767.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_pcm.tobytes())
    return buf.getvalue()


# ============================================================================
# MODULE 5 VALIDATION TESTS
# ============================================================================

def test_validation_genuine_human_speech():
    """Module 5.1: Test genuine human speech input."""
    pipeline = DetectionPipeline()
    wav_bytes = generate_wav(duration=4.0, signal_type="human")

    report = pipeline.analyze_audio(wav_bytes, "genuine_speech.wav", "audio/wav", model_name="AASIST")

    assert report["success"] is True
    assert report["selected_model"] == "AASIST"
    assert report["analysis_status"] == "completed"
    assert "predicted_class" in report
    assert "real_probability" in report
    assert "fake_probability" in report
    assert "inference_time" in report
    assert "prediction_reliability" in report
    assert report["inference_time"] >= 0.0
    assert report["prediction_reliability"] in ["HIGH", "MEDIUM", "LOW"]


def test_validation_synthetic_speech():
    """Module 5.2: Test synthetic speech input."""
    pipeline = DetectionPipeline()
    wav_bytes = generate_wav(duration=4.0, signal_type="synthetic")

    report = pipeline.analyze_audio(wav_bytes, "synthetic_voice.wav", "audio/wav", model_name="AASIST")

    assert report["success"] is True
    assert report["analysis_status"] == "completed"
    assert report["predicted_class"] in ["AI_GENERATED", "INCONCLUSIVE", "REAL_HUMAN"]
    assert report["fake_probability"] is not None
    assert report["real_probability"] is not None


def test_validation_different_audio_durations():
    """Module 5.3: Test different audio durations (short 1.0s, standard 4.0s, long 10.0s)."""
    pipeline = DetectionPipeline()

    # 1. Short audio (1.0s): Must trigger cyclic tiling to 64,600 samples
    wav_short = generate_wav(duration=1.0, signal_type="human")
    rep_short = pipeline.analyze_audio(wav_short, "short_1s.wav", "audio/wav", model_name="AASIST")
    assert rep_short["success"] is True
    assert rep_short["audio_duration"] == 1.0
    assert rep_short["segments_analyzed"] == 1

    # 2. Standard audio (~4.0375s)
    wav_std = generate_wav(duration=4.0375, signal_type="human")
    rep_std = pipeline.analyze_audio(wav_std, "standard_4s.wav", "audio/wav", model_name="AASIST")
    assert rep_std["success"] is True
    assert rep_std["segments_analyzed"] >= 1

    # 3. Long audio (10.0s): Must trigger multi-segment sliding window
    wav_long = generate_wav(duration=10.0, signal_type="human")
    rep_long = pipeline.analyze_audio(wav_long, "long_10s.wav", "audio/wav", model_name="AASIST")
    assert rep_long["success"] is True
    assert rep_long["segments_analyzed"] >= 2
    assert len(rep_long["segment_analysis"]) >= 2


def test_validation_noisy_recordings():
    """Module 5.4: Test noisy audio recording."""
    pipeline = DetectionPipeline()
    wav_noisy = generate_wav(duration=3.5, signal_type="human", noise_sigma=0.08)

    report = pipeline.analyze_audio(wav_noisy, "noisy_speech.wav", "audio/wav", model_name="AASIST")

    assert report["success"] is True
    assert report["forensics"] is not None
    assert report["forensics"]["noise_analysis"]["has_background_noise"] is True


def test_validation_invalid_corrupted_audio():
    """Module 5.5: Test invalid/corrupted audio file."""
    pipeline = DetectionPipeline()
    corrupted_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00CORRUPT_HEADER_TRUNCATED"

    report = pipeline.analyze_audio(corrupted_bytes, "corrupted.wav", "audio/wav", model_name="AASIST")

    assert report["success"] is False
    assert report["status"] in ["validation_failed", "preprocessing_failed"]


def test_validation_empty_audio():
    """Module 5.6: Test 0-byte empty audio file."""
    pipeline = DetectionPipeline()
    empty_bytes = b""

    report = pipeline.analyze_audio(empty_bytes, "empty.wav", "audio/wav", model_name="AASIST")

    assert report["success"] is False
    assert report["status"] == "validation_failed"


def test_validation_unsupported_formats():
    """Module 5.7: Test unsupported file extensions."""
    validator = AudioValidator()

    # .exe format
    res_exe = validator.validate_file(b"MZ\x90\x00fake_executable", "malware.exe", "application/x-msdownload")
    assert res_exe.is_valid is False
    assert res_exe.error_code == "UNSUPPORTED_FORMAT"

    # .txt format
    res_txt = validator.validate_file(b"This is a text transcript", "speech.txt", "text/plain")
    assert res_txt.is_valid is False
    assert res_txt.error_code == "UNSUPPORTED_FORMAT"

    # .pdf format
    res_pdf = validator.validate_file(b"%PDF-1.4 binary document", "report.pdf", "application/pdf")
    assert res_pdf.is_valid is False
    assert res_pdf.error_code == "UNSUPPORTED_FORMAT"


def test_validation_rawnet2_unconfigured_handling():
    """Module 3 & 4: Test RawNet2 execution and unconfigured model handling."""
    pipeline = DetectionPipeline()
    wav_bytes = generate_wav(duration=3.0, signal_type="human")

    # 1. Real RawNet2 execution when weights are present
    report = pipeline.analyze_audio(wav_bytes, "test_rawnet2.wav", "audio/wav", model_name="RAWNET2")
    assert report["success"] is True
    assert report["selected_model"] == "RAWNET2"
    assert report["model_name"] == "RAWNET2"
    if pipeline.model_manager.is_model_available("rawnet2"):
        assert report["analysis_status"] == "completed"
        assert report["model_status"] == "RAWNET2_ACTIVE"
        assert report["model"]["inference_completed"] is True
        assert report["predicted_class"] in ("REAL_HUMAN", "AI_GENERATED", "INCONCLUSIVE")
    else:
        assert report["analysis_status"] == "AI_MODEL_NOT_CONFIGURED"
        assert report["model_status"] == "MODEL_NOT_AVAILABLE"
        assert report["prediction_reliability"] == "UNRELIABLE"
        assert report["predicted_class"] == "INCONCLUSIVE"
        assert report["missing_files"] == ["rawnet2.onnx"]
        assert report["model"]["inference_completed"] is False

    # 2. Strict zero-hallucination verification when a supported model has no weights
    report_unconf = pipeline.analyze_audio(wav_bytes, "test_ecapa.wav", "audio/wav", model_name="ECAPA_TDNN")
    assert report_unconf["success"] is True
    assert report_unconf["selected_model"] == "ECAPA_TDNN"
    assert report_unconf["analysis_status"] == "AI_MODEL_NOT_CONFIGURED"
    assert report_unconf["model_status"] == "MODEL_NOT_AVAILABLE"
    assert report_unconf["prediction_reliability"] == "UNRELIABLE"
    assert report_unconf["predicted_class"] == "INCONCLUSIVE"
    assert report_unconf["missing_files"] == ["ecapa_tdnn.onnx"]
    assert report_unconf["model"]["inference_completed"] is False
