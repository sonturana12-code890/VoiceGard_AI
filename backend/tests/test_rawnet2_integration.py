"""
VOICEGUARD AI — RawNet2 Integration & Anti-Spoofing Test Suite
Comprehensive verification of pretrained RawNet2 model loading, ONNX Runtime inference,
audio preprocessing compatibility, segmentation, noise robustness, API integration,
and concurrent co-existence with AASIST.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.audio_preprocessor import AudioPreprocessor
from backend.services.audio_segmenter import AudioSegmenter
from backend.services.inference_pipeline import DetectionPipeline
from backend.services.model_manager import ModelManager, ModelNotFoundError, ModelInferenceError
from backend.services.prediction_engine import VoicePredictionEngine, stable_softmax
from backend.services.rawnet2_service import (
    EXPECTED_SAMPLES,
    RAWNET2_ONNX_PATH,
    RawNet2InferenceError,
    RawNet2InferenceResult,
    RawNet2ModelError,
    RawNet2Service,
)


# ============================================================================
# Helpers: Generate In-Memory WAV Files
# ============================================================================

def make_test_wav_bytes(
    duration_s: float = 4.05,
    sample_rate: int = 16000,
    frequency: float = 440.0,
    noise_level: float = 0.0,
    clipping: bool = False,
) -> bytes:
    """Creates a standard PCM 16-bit mono WAV in bytes."""
    n_samples = int(duration_s * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        samples = []
        for i in range(n_samples):
            t = float(i) / sample_rate
            # Harmonic speech-like carrier
            val = 0.6 * math.sin(2.0 * math.pi * frequency * t) + 0.3 * math.sin(2.0 * math.pi * (frequency * 2.0) * t)
            if noise_level > 0.0:
                val += noise_level * (np.random.uniform(-1.0, 1.0))
            if clipping and i % 50 < 5:
                val = 1.2  # Clipped

            val = max(-1.0, min(1.0, val))
            sample_int = int(val * 32767.0)
            samples.append(struct.pack("<h", sample_int))

        wf.writeframes(b"".join(samples))
    buf.seek(0)
    return buf.read()


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def rawnet2_service() -> RawNet2Service:
    return RawNet2Service()


@pytest.fixture
def model_manager() -> ModelManager:
    return ModelManager()


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


import uuid

def get_auth_headers(test_client: TestClient) -> Dict[str, str]:
    """Helper to authenticate a test analyst user."""
    email = f"rawnet_analyst_{uuid.uuid4().hex[:8]}@voiceguard.ai"
    password = "StrongSecurityPassword123!"

    signup_res = test_client.post(
        "/api/auth/signup",
        json={
            "fullName": "RawNet Analyst",
            "email": email,
            "password": password,
            "confirmPassword": password,
            "termsAccepted": True,
            "remember": False,
        },
    )
    if signup_res.status_code == 201:
        token = signup_res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    raise RuntimeError(f"Failed to authenticate test client: {signup_res.text}")


# ============================================================================
# 1. Checkpoint & Service Initialization Tests
# ============================================================================

def test_rawnet2_onnx_file_exists():
    """Verify that backend/models_weights/rawnet2.onnx exists and is valid size."""
    assert RAWNET2_ONNX_PATH.is_file(), f"Model file missing at: {RAWNET2_ONNX_PATH}"
    size_mb = RAWNET2_ONNX_PATH.stat().st_size / (1024 * 1024)
    assert size_mb >= 50.0, f"Expected RawNet2 ONNX model > 50 MB, got {size_mb:.2f} MB"


def test_rawnet2_service_metadata(rawnet2_service: RawNet2Service):
    """Verify RawNet2 service metadata reporting."""
    assert rawnet2_service.is_available() is True
    info = rawnet2_service.get_model_info()
    assert info["model_name"] == "RAWNET2"
    assert info["installed"] is True
    assert info["expected_samples"] == 64600
    assert info["sample_rate"] == 16000
    assert "REAL_HUMAN" in info["output_classes"]
    assert "AI_GENERATED" in info["output_classes"]


def test_rawnet2_service_session_initialization(rawnet2_service: RawNet2Service):
    """Verify ONNX Runtime session loads successfully."""
    session = rawnet2_service.initialize_session()
    assert session is not None
    assert rawnet2_service._input_name == "audio_input"
    assert rawnet2_service._output_name == "logits"


# ============================================================================
# 2. RawNet2 Inference & Output Standard Tests
# ============================================================================

def test_rawnet2_inference_single_sample(rawnet2_service: RawNet2Service):
    """Verify forward pass on 1D tensor [64600] float32."""
    waveform = np.random.randn(64600).astype(np.float32)
    result = rawnet2_service.predict(waveform)

    assert isinstance(result, RawNet2InferenceResult)
    assert result.predicted_class in ("REAL_HUMAN", "AI_GENERATED", "INCONCLUSIVE")
    assert 0.0 <= result.real_probability <= 1.0
    assert 0.0 <= result.fake_probability <= 1.0
    assert abs((result.real_probability + result.fake_probability) - 1.0) < 1e-3
    assert result.confidence >= 0.5
    assert result.inference_time_ms > 0.0
    assert result.prediction_reliability in ("HIGH", "MEDIUM", "LOW")
    assert result.model_name == "RAWNET2"
    assert result.model_status == "RAWNET2_ACTIVE"


def test_rawnet2_inference_batch(rawnet2_service: RawNet2Service):
    """Verify forward pass on 2D batch tensor [2, 64600]."""
    batch = np.random.randn(2, 64600).astype(np.float32)
    result = rawnet2_service.predict(batch)

    assert isinstance(result, RawNet2InferenceResult)
    assert result.model_status == "RAWNET2_ACTIVE"
    d = result.to_dict()
    assert "real_probability" in d
    assert "fake_probability" in d
    assert "human_probability" in d
    assert "synthetic_probability" in d
    assert "inference_time_ms" in d


def test_rawnet2_inference_invalid_samples(rawnet2_service: RawNet2Service):
    """Verify error handling on incorrect sample dimensions."""
    wrong_length = np.random.randn(32000).astype(np.float32)
    with pytest.raises(RawNet2InferenceError) as exc_info:
        rawnet2_service.predict(wrong_length)
    assert "64600" in str(exc_info.value)


# ============================================================================
# 3. ModelManager Dual-Model Support (AASIST & RawNet2)
# ============================================================================

def test_model_manager_both_models_available(model_manager: ModelManager):
    """Verify ModelManager detects both AASIST and RawNet2 checkpoints."""
    assert model_manager.is_model_available("aasist") is True
    assert model_manager.is_model_available("rawnet2") is True
    assert model_manager.is_model_available("AASIST") is True
    assert model_manager.is_model_available("RAWNET2") is True


def test_model_manager_independent_execution(model_manager: ModelManager):
    """Verify AASIST and RawNet2 can execute independently on identical input."""
    dummy = np.random.randn(1, 64600).astype(np.float32)

    logits_aasist = model_manager.run_inference("aasist", dummy)
    logits_rawnet = model_manager.run_inference("rawnet2", dummy)

    assert logits_aasist.shape == (1, 2)
    assert logits_rawnet.shape == (1, 2)

    # Models should produce distinct logits given different architectures
    assert not np.allclose(logits_aasist, logits_rawnet, atol=1e-2)


def test_model_manager_unsupported_model(model_manager: ModelManager):
    """Verify ModelNotFoundError on nonexistent model."""
    with pytest.raises(ModelNotFoundError):
        model_manager.run_inference("nonexistent_model_xyz", np.zeros((1, 64600), dtype=np.float32))


# ============================================================================
# 4. Audio Preprocessing, Padding, Truncation & Noise Tests
# ============================================================================

def test_rawnet2_with_short_audio_padding():
    """Verify short audio (1.5s < 4.0375s) is padded and successfully scored."""
    short_wav = make_test_wav_bytes(duration_s=1.5, sample_rate=16000, frequency=300.0)
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(file_bytes=short_wav, filename="short_sample.wav", model_name="RAWNET2")

    assert report["success"] is True
    assert report["model_name"] == "RAWNET2"
    assert report["model_status"] == "RAWNET2_ACTIVE"
    assert report["analysis_status"] == "completed"
    assert report["predicted_class"] in ("REAL_HUMAN", "AI_GENERATED", "INCONCLUSIVE")
    assert report["real_probability"] is not None
    assert report["fake_probability"] is not None


def test_rawnet2_with_long_audio_multisegment():
    """Verify long audio (~9.0s) is segmented into multiple windows and temporally aggregated."""
    long_wav = make_test_wav_bytes(duration_s=9.0, sample_rate=16000, frequency=220.0)
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(file_bytes=long_wav, filename="long_sample.wav", model_name="RAWNET2")

    assert report["success"] is True
    assert report["model_name"] == "RAWNET2"
    assert report["segments_analyzed"] >= 2
    assert len(report["segment_analysis"]) >= 2
    for seg in report["segment_analysis"]:
        assert "prediction" in seg
        assert "score" in seg
        assert "human_probability" in seg
        assert "synthetic_probability" in seg


def test_rawnet2_with_noisy_audio():
    """Verify audio with high background noise executes stably without failure."""
    noisy_wav = make_test_wav_bytes(duration_s=4.5, sample_rate=16000, frequency=400.0, noise_level=0.35)
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(file_bytes=noisy_wav, filename="noisy_sample.wav", model_name="RAWNET2")

    assert report["success"] is True
    assert report["model_name"] == "RAWNET2"
    assert report["model_status"] == "RAWNET2_ACTIVE"
    assert report["real_probability"] is not None
    assert report["fake_probability"] is not None


def test_rawnet2_with_clipping_audio():
    """Verify clipped audio executes and forensics module flags clipping."""
    clipped_wav = make_test_wav_bytes(duration_s=4.1, sample_rate=16000, frequency=350.0, clipping=True)
    pipeline = DetectionPipeline()
    report = pipeline.analyze_audio(file_bytes=clipped_wav, filename="clipped_sample.wav", model_name="RAWNET2")

    assert report["success"] is True
    assert report["model_name"] == "RAWNET2"
    assert report["forensics"] is not None
    assert "clipping_analysis" in report["forensics"]


# ============================================================================
# 5. Full API Endpoint Verification (POST /api/v1/audio/analyze)
# ============================================================================

def test_api_analyze_with_rawnet2(test_client: TestClient):
    """Verify POST /api/v1/audio/analyze?model_name=RAWNET2 returns standardized Phase 4 fields."""
    wav_bytes = make_test_wav_bytes(duration_s=4.1, sample_rate=16000, frequency=440.0)
    headers = get_auth_headers(test_client)

    files = {"file": ("test_rawnet.wav", wav_bytes, "audio/wav")}
    res = test_client.post("/api/v1/audio/analyze?model_name=RAWNET2", files=files, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()

    assert data["success"] is True
    assert data["model_name"] == "RAWNET2"
    assert data["model_status"] == "RAWNET2_ACTIVE"
    assert data["status"] == "completed"
    assert data["predicted_class"] in ("REAL_HUMAN", "AI_GENERATED", "INCONCLUSIVE")
    assert 0.0 <= data["real_probability"] <= 1.0
    assert 0.0 <= data["fake_probability"] <= 1.0
    assert 0.0 <= data["confidence_score"] <= 1.0
    assert data["inference_time"] >= 0.0
    assert data["prediction_reliability"] in ("HIGH", "MEDIUM", "LOW")
    assert "features" in data
    assert "forensics" in data
    assert "spectrogram" in data


def test_api_analyze_with_aasist(test_client: TestClient):
    """Verify POST /api/v1/audio/analyze?model_name=AASIST continues to function with AASIST active."""
    wav_bytes = make_test_wav_bytes(duration_s=4.1, sample_rate=16000, frequency=440.0)
    headers = get_auth_headers(test_client)

    files = {"file": ("test_aasist.wav", wav_bytes, "audio/wav")}
    res = test_client.post("/api/v1/audio/analyze?model_name=AASIST", files=files, headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()

    assert data["success"] is True
    assert data["model_name"] == "AASIST"
    assert data["model_status"] == "AASIST_ACTIVE"
    assert data["status"] == "completed"
    assert data["predicted_class"] in ("REAL_HUMAN", "AI_GENERATED", "INCONCLUSIVE")


def test_api_analyze_invalid_audio_handled(test_client: TestClient):
    """Verify corrupted non-audio input returns HTTP 400."""
    headers = get_auth_headers(test_client)

    corrupt_bytes = b"NOT_A_VALID_AUDIO_FILE_DATA_CORRUPT"
    files = {"file": ("corrupt.wav", corrupt_bytes, "audio/wav")}
    res = test_client.post("/api/v1/audio/analyze?model_name=RAWNET2", files=files, headers=headers)

    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "corrupted" in detail or "invalid" in detail or "failed" in detail
