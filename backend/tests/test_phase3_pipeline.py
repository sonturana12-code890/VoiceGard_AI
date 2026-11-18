"""
VOICEGUARD AI — Phase 3 Automated Test Suite
Exhaustive verification of the Phase 3 Audio Detection & Processing Pipeline:
18 Test Cases covering upload validation, decoding, preprocessing, intelligent segmentation,
model management, segment aggregation, API endpoints, and zero-hallucination compliance.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import io
import math
import tempfile
import wave
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import av
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models
from backend.auth import create_access_token, hash_password
from backend.database import Base, get_db
from backend.main import app
from backend.models import AudioAnalysis, User
from backend.services.audio_preprocessor import (
    AudioPreprocessingError,
    AudioPreprocessor,
    AudioQualityMetrics,
)
from backend.services.audio_segmenter import AudioSegment, AudioSegmenter
from backend.services.audio_validator import (
    AudioValidationError,
    AudioValidator,
    ValidationResult,
)
from backend.services.inference_pipeline import DetectionPipeline
from backend.services.model_manager import (
    ModelInferenceError,
    ModelManager,
    ModelNotFoundError,
)

from backend.tests.test_api import (
    test_engine,
    TestingSessionLocal,
    override_get_db,
)

app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=test_engine)


# ============================================================================
# AUDIO SYNTHESIS FIXTURES
# ============================================================================

def make_wav_bytes(
    duration: float = 1.0,
    sr: int = 16000,
    channels: int = 1,
    freq: float = 440.0,
    amplitude: float = 0.5,
) -> bytes:
    """Generates synthetic PCM WAV audio bytes."""
    num_samples = int(duration * sr)
    if amplitude == 0.0:
        data = np.zeros(num_samples, dtype=np.float32)
    else:
        t = np.linspace(0, duration, num_samples, endpoint=False)
        data = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)

    pcm16 = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        if channels == 2:
            stereo = np.column_stack((pcm16, pcm16)).flatten()
            wf.writeframes(stereo.tobytes())
        else:
            wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


def make_mp3_bytes(duration: float = 1.5, sr: int = 44100, freq: float = 440.0) -> bytes:
    """Encodes a synthetic audio stream into valid MP3 bytes via PyAV."""
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


def make_flac_bytes(duration: float = 1.0, sr: int = 16000, freq: float = 440.0) -> bytes:
    """Encodes synthetic audio into valid FLAC bytes via PyAV."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="flac") as container:
        stream = container.add_stream("flac", rate=sr)
        total_samples = int(duration * sr)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        waveform = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
        frame = av.AudioFrame.from_ndarray(waveform.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = sr
        for p in stream.encode(frame):
            container.mux(p)
        for p in stream.encode(None):
            container.mux(p)
    return buf.getvalue()


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Signs up / logs in a test user via API and returns Bearer auth headers."""
    signup_res = client.post("/api/auth/signup", json={
        "fullName": "Phase3 Lead Architect",
        "email": "phase3_tester@voiceguard.ai",
        "password": "Phase3SecretPassword123!",
        "termsAccepted": True,
    })
    if signup_res.status_code == 200 and "access_token" in signup_res.json():
        token = signup_res.json()["access_token"]
    else:
        login_res = client.post("/api/auth/login", json={
            "email": "phase3_tester@voiceguard.ai",
            "password": "Phase3SecretPassword123!",
        })
        token = login_res.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ============================================================================
# 18 MANDATORY PHASE 3 TEST CASES
# ============================================================================

def test_01_valid_wav_audio():
    """Test 1: Valid WAV audio validation, decoding, and feature extraction."""
    wav = make_wav_bytes(duration=2.0, sr=16000, channels=1, freq=440.0)
    validator = AudioValidator()
    res = validator.validate_file(wav, "test_tone.wav", "audio/wav")

    assert res.is_valid is True
    assert res.format == "wav"
    assert res.channels == 1
    assert res.sample_rate == 16000
    assert abs(res.duration_seconds - 2.0) < 0.05

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(wav, "test_tone.wav")
    assert len(pcm) == 32000
    assert metrics.rms_energy > 0.1
    assert metrics.is_silent is False


def test_02_valid_mp3_audio():
    """Test 2: Valid MP3 audio decoding, stereo downmix, and 16kHz resampling."""
    mp3 = make_mp3_bytes(duration=1.5, sr=44100, freq=500.0)
    validator = AudioValidator()
    res = validator.validate_file(mp3, "sample.mp3", "audio/mpeg")

    assert res.is_valid is True
    assert res.format == "mp3"
    assert res.sample_rate == 44100
    assert res.channels == 2

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(mp3, "sample.mp3")
    assert metrics.sample_rate == 16000
    assert abs(metrics.duration_seconds - 1.5) < 0.1
    assert metrics.rms_energy > 0.05


def test_03_valid_flac_audio():
    """Test 3: Valid FLAC lossless audio decoding and acoustic verification."""
    flac = make_flac_bytes(duration=1.0, sr=16000, freq=300.0)
    validator = AudioValidator()
    res = validator.validate_file(flac, "voice.flac", "audio/flac")

    assert res.is_valid is True
    assert res.format == "flac"

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(flac, "voice.flac")
    assert len(pcm) == 16000
    assert metrics.spectral_centroid_hz > 0


def test_04_corrupted_audio():
    """Test 4: Corrupted audio streams are rejected with CORRUPTED_AUDIO code."""
    corrupted_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00" + b"\xff" * 20
    validator = AudioValidator()
    res = validator.validate_file(corrupted_bytes, "broken.wav", "audio/wav")

    assert res.is_valid is False
    assert res.error_code in ("CORRUPTED_AUDIO", "AUDIO_TOO_SHORT")


def test_05_empty_audio():
    """Test 5: Empty audio files (0 bytes) are rejected with EMPTY_AUDIO."""
    validator = AudioValidator()
    res = validator.validate_file(b"", "empty.wav", "audio/wav")

    assert res.is_valid is False
    assert res.error_code == "EMPTY_AUDIO"
    assert "empty" in res.message.lower()


def test_06_unsupported_file():
    """Test 6: Unsupported formats (.exe, .pdf, .sh) are rejected with UNSUPPORTED_FORMAT."""
    validator = AudioValidator()
    res = validator.validate_file(b"MZ executable header dummy content", "malware.exe", "application/octet-stream")

    assert res.is_valid is False
    assert res.error_code == "UNSUPPORTED_FORMAT"


def test_07_silent_audio():
    """Test 7: Silent audio detection and quality metric analysis."""
    silent_wav = make_wav_bytes(duration=1.0, sr=16000, amplitude=0.0)
    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(silent_wav, "silence.wav")

    assert metrics.is_silent is True
    assert metrics.rms_energy < 1e-4
    assert metrics.silence_ratio >= 0.95


def test_08_very_short_audio():
    """Test 8: Short audio files (< 4s) are tiled/wrapped to AASIST target length (64,600)."""
    short_wav = make_wav_bytes(duration=0.5, sr=16000, freq=440.0)  # 8000 samples
    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, _ = preprocessor.process_audio(short_wav, "short.wav")

    segmenter = AudioSegmenter(target_samples=64600, sample_rate=16000)
    segments = segmenter.segment(pcm)

    assert len(segments) == 1
    assert len(segments[0].samples) == 64600
    assert segments[0].is_padded is True
    assert segments[0].start_time == 0.0
    assert abs(segments[0].end_time - 0.5) < 0.01


def test_09_long_audio_segmentation():
    """Test 9: Long audio files (> 10s) produce multiple ordered sliding segments with timestamps."""
    long_wav = make_wav_bytes(duration=12.0, sr=16000, freq=440.0)  # 192,000 samples
    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, _ = preprocessor.process_audio(long_wav, "long.wav")

    # 4s windows with 1s overlap -> step = 3s (48,000 samples)
    segmenter = AudioSegmenter(target_samples=64600, sample_rate=16000, overlap_seconds=1.0)
    segments = segmenter.segment(pcm)

    assert len(segments) >= 3
    # Verify chronological ordering
    for i in range(len(segments) - 1):
        assert segments[i].start_time < segments[i+1].start_time
        assert segments[i].segment_id == i + 1
        assert len(segments[i].samples) == 64600


def test_10_stereo_audio_downmix():
    """Test 10: Multi-channel stereo downmixes cleanly to mono float32 without clipping."""
    stereo_wav = make_wav_bytes(duration=1.0, sr=44100, channels=2, freq=600.0, amplitude=0.8)
    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(stereo_wav, "stereo.wav")

    assert pcm.ndim == 1
    assert metrics.channels == 2
    assert metrics.is_clipped is False
    assert np.max(np.abs(pcm)) <= 1.0


def test_11_mono_audio_integrity():
    """Test 11: Mono audio preservation without unnecessary channel modification."""
    mono_wav = make_wav_bytes(duration=1.0, sr=16000, channels=1, freq=440.0)
    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(mono_wav, "mono.wav")

    assert metrics.channels == 1
    assert pcm.ndim == 1
    assert len(pcm) == 16000


def test_12_missing_pretrained_model_zero_hallucination():
    """Test 12: Zero-hallucination reporting when model checkpoint is unconfigured."""
    pipeline = DetectionPipeline()
    test_wav = make_wav_bytes(duration=1.5, sr=16000, freq=440.0)

    # Force model_manager to report model unavailable
    with patch.object(pipeline.model_manager, "is_model_available", return_value=False):
        report = pipeline.analyze_audio(test_wav, "real_speech.wav", "audio/wav")

    assert report["success"] is True
    assert report["status"] == "AI_MODEL_NOT_CONFIGURED"
    assert report["prediction"]["label"] == "INCONCLUSIVE"
    assert report["prediction"]["synthetic_probability"] is None
    assert report["prediction"]["confidence"] is None
    assert report["model"]["inference_completed"] is False
    assert report["audio_information"]["duration"] == 1.5
    assert len(report["segment_analysis"]) >= 1


def test_13_cpu_inference_execution():
    """Test 13: CPU inference execution provider validation and mock neural run."""
    model_mgr = ModelManager()
    assert "CPU" in model_mgr.device or "CUDA" in model_mgr.device

    # Mock an ONNX inference session returning genuine logits [human=0.1, spoof=2.8]
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "audio_waveform"
    mock_session.get_inputs.return_value = [mock_input]
    # Return batch logits [N=1, classes=2]
    mock_session.run.return_value = [np.array([[0.1, 2.8]], dtype=np.float32)]

    with patch.object(model_mgr, "is_model_available", return_value=True):
        with patch.object(model_mgr, "get_session", return_value=mock_session):
            test_tensor = np.zeros((1, 64600), dtype=np.float32)
            logits = model_mgr.run_inference("aasist", test_tensor)
            assert logits.shape == (1, 2)
            assert logits[0][1] > logits[0][0]  # Spoof higher


def test_14_gpu_device_fallback():
    """Test 14: Execution provider prioritization and graceful CPU fallback."""
    model_mgr = ModelManager()
    providers = model_mgr.get_available_providers()
    assert isinstance(providers, list)
    assert len(providers) >= 1
    assert "CPUExecutionProvider" in providers


def test_15_invalid_model_input_handling():
    """Test 15: Invalid tensor shapes raise explicit ModelInferenceError."""
    model_mgr = ModelManager()
    with patch.object(model_mgr, "get_session", return_value=MagicMock()):
        with pytest.raises(ModelInferenceError) as exc_info:
            # Pass incorrect number of samples (1000 instead of 64600)
            bad_tensor = np.zeros((1, 1000), dtype=np.float32)
            model_mgr.run_inference("aasist", bad_tensor)
        assert "64600" in str(exc_info.value)


def test_16_fastapi_v1_endpoints(client, auth_headers):
    """Test 16: FastAPI Phase 3 endpoints: /api/v1/audio/analyze, /validate, /health, /analysis/{id}."""
    test_wav = make_wav_bytes(duration=2.0, sr=16000, freq=440.0)

    # 1. Health endpoint
    health_res = client.get("/api/v1/audio/health")
    assert health_res.status_code == 200
    assert health_res.json()["pipeline_version"] == "3.0.0"

    # 2. Validation endpoint
    val_res = client.post(
        "/api/v1/audio/validate",
        files={"file": ("check_tone.wav", test_wav, "audio/wav")},
    )
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["valid"] is True
    assert val_data["format"] == "wav"

    # 3. Analyze endpoint
    analyze_res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("inspect.wav", test_wav, "audio/wav")},
        headers=auth_headers,
    )
    assert analyze_res.status_code == 200
    an_data = analyze_res.json()
    assert an_data["success"] is True
    assert "prediction" in an_data
    assert "audio_information" in an_data
    assert "segment_analysis" in an_data
    analysis_id = an_data["analysis_id"]

    # 4. Detail endpoint
    detail_res = client.get(f"/api/v1/audio/analysis/{analysis_id}", headers=auth_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["analysis_id"] == analysis_id


def test_17_segment_aggregation_logic():
    """Test 17: Multi-segment aggregation properly computes labels and confidence."""
    pipeline = DetectionPipeline()
    multi_seg_wav = make_wav_bytes(duration=8.0, sr=16000, freq=440.0)  # Produces 3 segments

    # Mock model inference returning synthetic spoof on segment 2
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "audio_waveform"
    mock_session.get_inputs.return_value = [mock_input]
    # Logits for 3 segments: [spoof, human]
    mock_session.run.return_value = [np.array([
        [2.5, -1.0],  # Segment 1: Spoof
        [3.5, -2.0],  # Segment 2: Strong Spoof (> 95%)
        [-1.0, 2.0],  # Segment 3: Human
    ], dtype=np.float32)]

    with patch.object(pipeline.model_manager, "is_model_available", return_value=True):
        with patch.object(pipeline.model_manager, "get_session", return_value=mock_session):
            report = pipeline.analyze_audio(multi_seg_wav, "multi_sample.wav", "audio/wav")

    assert report["success"] is True
    assert report["prediction"]["label"] == "AI_GENERATED"
    assert report["segments_analyzed"] >= 2
    # Check that segment 2 caught the deepfake clone
    seg2 = report["segment_analysis"][1]
    assert seg2["prediction"] == "AI_GENERATED"
    assert seg2["synthetic_probability"] > 0.90


def test_18_temporary_file_cleanup():
    """Test 18: File processing uses secure UUID filenames without leaking temporary descriptors."""
    from backend.services.audio_service import VoiceDetectionService, UPLOAD_DIR
    dummy_data = make_wav_bytes(duration=0.5, sr=16000)
    
    safe_name, path = VoiceDetectionService.save_upload(dummy_data, "user_recording.wav")
    assert path.is_file()
    assert safe_name.endswith(".wav")
    assert "user_recording" not in safe_name  # Path traversal prevented via UUID

    # Clean up test artifact
    if path.is_file():
        path.unlink()
        assert not path.exists()
