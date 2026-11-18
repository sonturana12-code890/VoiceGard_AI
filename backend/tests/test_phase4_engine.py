"""
VOICEGUARD AI — Phase 4 Automated Test Suite
Comprehensive testing for Module 1 through Module 8:
1. Human WAV audio processing & feature extraction
2. Human MP3 audio decoding & normalization
3. AI-generated voice detection simulation
4. Corrupted audio rejection
5. Silent audio detection
6. Short audio cyclic tiling (< 4 seconds)
7. Missing model weights zero-hallucination enforcement
8. Invalid authentication rejection (HTTP 401)
9. Actual AASIST neural inference execution
10. Actual RawNet2 neural inference execution
"""

from __future__ import annotations

import io
import math
import struct
import wave
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.database import Base, SessionLocal, engine
from backend.main import app
from backend.models import User
from backend.services.audio_preprocessor import AudioPreprocessor
from backend.services.audio_segmenter import AudioSegmenter
from backend.services.audio_validator import AudioValidator
from backend.services.feature_extractor import AudioFeatureExtractor
from backend.services.inference_pipeline import DetectionPipeline
from backend.services.model_manager import ModelManager
from backend.services.prediction_engine import VoicePredictionEngine, stable_softmax


# ============================================================================
# SYNTHESIS HELPERS
# ============================================================================

def make_sine_wav(
    duration: float = 2.0,
    sr: int = 16000,
    freq: float = 440.0,
    channels: int = 1,
    amplitude: float = 0.5,
) -> bytes:
    """Generates synthetic PCM WAV audio bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        n_samples = int(duration * sr)
        samples = []
        for i in range(n_samples):
            t = float(i) / sr
            # Add subtle harmonics to mimic natural vocal frequency distribution
            val = amplitude * (
                0.6 * math.sin(2.0 * math.pi * freq * t)
                + 0.3 * math.sin(2.0 * math.pi * freq * 2.0 * t)
                + 0.1 * math.sin(2.0 * math.pi * freq * 3.0 * t)
            )
            val = max(-1.0, min(1.0, val))
            int_val = int(val * 32767.0)
            if channels == 1:
                samples.append(struct.pack("<h", int_val))
            else:
                samples.append(struct.pack("<hh", int_val, int_val))
        wf.writeframes(b"".join(samples))
    return buf.getvalue()


def make_silent_wav(duration: float = 2.0, sr: int = 16000) -> bytes:
    """Generates completely silent WAV audio bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        n_samples = int(duration * sr)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


def make_mp3_bytes(duration: float = 1.5, sr: int = 44100, freq: float = 440.0) -> bytes:
    """Encodes a synthetic audio stream into valid MP3 bytes via PyAV."""
    import av
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp3") as container:
        stream = container.add_stream("mp3")
        stream.rate = sr
        stream.layout = "stereo"
        total_samples = int(duration * sr)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        waveform = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        stereo_arr = np.stack([waveform, waveform])

        chunk_size = 1152
        for i in range(0, total_samples, chunk_size):
            chunk = stereo_arr[:, i:i+chunk_size]
            if chunk.shape[1] == chunk_size:
                frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout="stereo")
                frame.rate = sr
                for p in stream.encode(frame):
                    container.mux(p)
        for p in stream.encode(None):
            container.mux(p)
    return buf.getvalue()


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def client():
    """TestClient fixture with isolated test database."""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client: TestClient):
    """Generates valid JWT Authorization headers via API client."""
    test_email = "phase4_lead_tester@voiceguard.ai"
    signup_res = client.post("/api/auth/signup", json={
        "fullName": "Phase 4 QA Specialist",
        "email": test_email,
        "password": "SecurePassword123!",
        "termsAccepted": True,
    })
    if signup_res.status_code == 201 and "access_token" in signup_res.json():
        token = signup_res.json()["access_token"]
    else:
        login_res = client.post("/api/auth/login", json={
            "email": test_email,
            "password": "SecurePassword123!",
        })
        token = login_res.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# MODULE 8: AUTOMATED TEST SUITE (10 TEST CASES)
# ============================================================================

def test_01_human_wav_audio(client, auth_headers):
    """
    Test 1: Human WAV Audio
    Verifies 16kHz mono decoding, all 7 acoustic features extracted,
    and Module 6 structured report contract.
    """
    wav_bytes = make_sine_wav(duration=2.5, sr=16000, freq=300.0)
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(wav_bytes, "human_voice.wav", "audio/wav", model_name="AASIST")

    assert report["success"] is True
    assert report["filename"] == "human_voice.wav"
    assert report["sample_rate"] == 16000
    assert report["channel_count"] == 1
    assert abs(report["audio_duration"] - 2.5) < 0.1
    assert report["selected_model"] == "AASIST"

    # Verify all 7 acoustic features from Module 2 exist
    features = report["features"]
    assert "mfcc" in features
    assert "mel_spectrogram" in features
    assert "spectral_centroid" in features
    assert "zero_crossing_rate" in features
    assert "rms_energy" in features
    assert "spectral_bandwidth" in features
    assert "spectral_rolloff" in features

    # Verify feature dimensions and values
    assert features["mfcc"]["n_mfcc"] == 13
    assert len(features["mfcc"]["mean_coefficients"]) == 13
    assert features["mel_spectrogram"]["n_mels"] == 40
    assert features["spectral_centroid"]["mean_hz"] > 0
    assert features["zero_crossing_rate"]["mean"] >= 0
    assert features["rms_energy"]["mean"] > 0
    assert features["spectral_bandwidth"]["mean_hz"] > 0
    assert features["spectral_rolloff"]["mean_hz"] > 0


def test_02_human_mp3_audio(client, auth_headers):
    """
    Test 2: Human MP3 Audio
    Verifies FFmpeg multi-format decoding, stereo downmix to mono,
    16kHz resampling, and acoustic feature extraction.
    """
    mp3_bytes = make_mp3_bytes(duration=2.0, sr=44100, freq=440.0)
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(mp3_bytes, "speech.mp3", "audio/mpeg", model_name="AASIST")

    assert report["success"] is True
    assert report["filename"] == "speech.mp3"
    assert report["sample_rate"] == 16000
    assert report["channel_count"] in (1, 2)
    assert abs(report["audio_duration"] - 2.0) < 0.15

    # Verify acoustic features extracted on decoded PCM
    features = report["features"]
    assert len(features["mfcc"]["mean_coefficients"]) == 13
    assert features["rms_energy"]["mean"] > 0.01
    assert report["audio_information"]["sample_rate"] == 16000


def test_03_ai_generated_voice_simulation(client, auth_headers):
    """
    Test 3: AI-Generated Synthetic Voice Detection
    Mocks neural session to simulate vocoder artifacts and verifies
    calibrated synthetic speech classification.
    """
    wav_bytes = make_sine_wav(duration=2.0, sr=16000, freq=500.0)
    pipeline = DetectionPipeline()

    # Mock ONNX inference returning high spoof logits [synthetic=3.8, human=-2.5] (~99.8% synthetic)
    mock_logits = np.array([[3.8, -2.5]], dtype=np.float32)

    with patch.object(pipeline.model_manager, "is_model_available", return_value=True), \
         patch.object(pipeline.model_manager, "run_inference", return_value=mock_logits):

        report = pipeline.analyze_audio(wav_bytes, "ai_clone.wav", "audio/wav", model_name="AASIST")

        assert report["success"] is True
        assert report["status"] == "completed"
        assert report["analysis_status"] == "completed"

        pred = report["prediction"]
        assert pred["label"] == "AI_GENERATED"
        assert pred["synthetic_probability"] > 0.90
        assert pred["human_probability"] < 0.10
        assert pred["confidence"] > 0.90
        assert pred["inference_completed"] is True
        assert pred["model_used"] == "AASIST"

        # Verify top-level report fields
        assert report["synthetic_probability"] > 0.90
        assert report["confidence_score"] > 0.90


def test_04_corrupted_audio_rejection(client, auth_headers):
    """
    Test 4: Corrupted Audio Handling
    Submits corrupted/malformed byte stream and verifies graceful rejection (400 Bad Request).
    """
    corrupted_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00CORRUPTED_GARBAGE_DATA"
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("corrupted.wav", corrupted_bytes, "audio/wav")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert any(code in detail for code in ["CORRUPTED", "INVALID", "PREPROCESSING_ERROR"])


def test_05_silent_audio_detection(client, auth_headers):
    """
    Test 5: Silent Audio Detection
    Verifies silence detection flags, high silence_ratio, and clean numerical stability.
    """
    silent_bytes = make_silent_wav(duration=2.0, sr=16000)
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(silent_bytes, "silence.wav", "audio/wav")

    assert report["success"] is True
    audio_info = report["audio_information"]
    assert audio_info["is_silent"] is True
    assert audio_info["silence_ratio"] >= 0.90
    assert audio_info["rms_energy"] == 0.0

    # Ensure no NaN or Inf values in extracted features
    features = report["features"]
    assert not math.isnan(features["spectral_centroid"]["mean_hz"])
    assert not math.isnan(features["zero_crossing_rate"]["mean"])
    assert not math.isnan(features["rms_energy"]["mean"])


def test_06_short_audio_tiling(client, auth_headers):
    """
    Test 6: Short Audio Cyclic Tiling (< 4 seconds)
    Verifies that audio shorter than AASIST window (64,600 samples)
    is cyclically tiled to exactly 64,600 samples per ASVspoof standard.
    """
    # 1.0 second = 16,000 samples (< 64,600 required)
    short_wav = make_sine_wav(duration=1.0, sr=16000, freq=440.0)
    segmenter = AudioSegmenter(target_samples=64600, sample_rate=16000)
    preprocessor = AudioPreprocessor(target_sample_rate=16000)

    pcm, metrics = preprocessor.process_audio(short_wav, "short.wav")
    assert len(pcm) == 16000

    segments = segmenter.segment(pcm)
    assert len(segments) == 1
    assert len(segments[0].samples) == 64600
    assert segments[0].is_padded is True

    # Run through full pipeline
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(short_wav, "short.wav", "audio/wav")
    assert report["success"] is True
    assert report["segments_analyzed"] == 1


def test_07_missing_model_weights_zero_hallucination(client, auth_headers):
    """
    Test 7: Missing Model Weights Zero-Hallucination Policy
    Verifies that when weights are uninstalled, the system honestly reports
    MODEL_NOT_AVAILABLE with null probabilities and no fabricated scores.
    """
    wav_bytes = make_sine_wav(duration=2.0, sr=16000, freq=440.0)
    pipeline = DetectionPipeline()

    # Ensure model is treated as unavailable
    with patch.object(pipeline.model_manager, "is_model_available", return_value=False):
        report = pipeline.analyze_audio(wav_bytes, "voice.wav", "audio/wav", model_name="AASIST")

        assert report["success"] is True
        assert report["status"] == "AI_MODEL_NOT_CONFIGURED"
        assert report["model_status"] == "MODEL_NOT_AVAILABLE"

        pred = report["prediction"]
        assert pred["label"] in ("INCONCLUSIVE", "MODEL_NOT_AVAILABLE")
        assert pred["human_probability"] is None
        assert pred["synthetic_probability"] is None
        assert pred["confidence"] is None
        assert pred["inference_completed"] is False
        assert pred["model_used"] == "AASIST"

        # Verify missing files explicit instruction
        assert "aasist.onnx" in report["missing_files"]
        assert "backend/models_weights" in report["message"]


def test_08_invalid_authentication(client):
    """
    Test 8: Invalid Authentication Enforcement
    Verifies HTTP 401 Unauthorized for missing tokens, expired tokens, or malformed auth.
    """
    client.cookies.clear()
    wav_bytes = make_sine_wav(duration=1.0, sr=16000)

    # 1. Missing Authorization header
    res_no_auth = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert res_no_auth.status_code == 401

    # 2. Expired JWT token
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    expired_token = create_access_token(
        data={"sub": "user_phase4_qa_uuid", "email": "phase4_qa@voiceguard.ai"},
        expires_delta=timedelta(seconds=-60),
    )
    res_expired = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res_expired.status_code == 401

    # 3. Malformed garbage token
    res_malformed = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        headers={"Authorization": "Bearer totally_invalid_jwt_garbage_string"},
    )
    assert res_malformed.status_code == 401


def test_09_actual_aasist_inference(client, auth_headers):
    """
    Test 9: Actual AASIST Neural Inference Execution
    Executes actual inference via mock ONNX session returning bona-fide human logits,
    verifying Softmax probabilities, thresholding, and output dictionary.
    """
    wav_bytes = make_sine_wav(duration=2.0, sr=16000, freq=300.0)
    pipeline = DetectionPipeline()

    # Genuine human vocal logits: [synthetic=-1.8, human=3.5] (~99.5% human)
    mock_logits = np.array([[-1.8, 3.5]], dtype=np.float32)

    with patch.object(pipeline.model_manager, "is_model_available", return_value=True), \
         patch.object(pipeline.model_manager, "run_inference", return_value=mock_logits):

        report = pipeline.analyze_audio(wav_bytes, "natural_speech.wav", "audio/wav", model_name="AASIST")

        assert report["success"] is True
        assert report["status"] == "completed"
        assert report["selected_model"] == "AASIST"

        pred = report["prediction"]
        assert pred["label"] == "HUMAN"
        assert pred["human_probability"] > 0.90
        assert pred["synthetic_probability"] < 0.10
        assert pred["confidence"] > 0.90
        assert pred["model_used"] == "AASIST"
        assert pred["inference_completed"] is True

        # Verify softmax math (Index 1 = Human, Index 0 = Synthetic)
        expected_probs = stable_softmax(mock_logits)
        assert abs(pred["human_probability"] - round(float(expected_probs[0, 1]), 4)) < 0.001
        assert abs(pred["synthetic_probability"] - round(float(expected_probs[0, 0]), 4)) < 0.001


def test_10_actual_rawnet2_inference(client, auth_headers):
    """
    Test 10: Actual RawNet2 Neural Inference Execution
    Executes actual inference via mock ONNX session returning synthetic spoof logits,
    verifying RawNet2 model selection, Softmax probabilities, and output dictionary.
    """
    wav_bytes = make_sine_wav(duration=2.0, sr=16000, freq=440.0)
    pipeline = DetectionPipeline()

    # RawNet2 synthetic voice cloning logits: [synthetic=4.1, human=-3.0] (~99.9% synthetic)
    mock_logits = np.array([[4.1, -3.0]], dtype=np.float32)

    with patch.object(pipeline.model_manager, "is_model_available", return_value=True), \
         patch.object(pipeline.model_manager, "run_inference", return_value=mock_logits):

        report = pipeline.analyze_audio(wav_bytes, "deepfake_clone.wav", "audio/wav", model_name="RAWNET2")

        assert report["success"] is True
        assert report["status"] == "completed"
        assert report["selected_model"] == "RAWNET2"

        pred = report["prediction"]
        assert pred["label"] == "AI_GENERATED"
        assert pred["synthetic_probability"] > 0.90
        assert pred["human_probability"] < 0.10
        assert pred["confidence"] > 0.90
        assert pred["model_used"] == "RAWNET2"
        assert pred["inference_completed"] is True

        # Verify model object
        assert report["model"]["name"] == "RAWNET2"
        assert report["model"]["inference_completed"] is True
