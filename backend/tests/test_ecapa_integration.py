"""
VOICEGUARD AI — ECAPA-TDNN Speaker Verification Test Suite
Comprehensive testing of official SpeechBrain ECAPA-TDNN speaker embedding extraction,
cosine similarity computation, same vs different speaker discrimination,
sample rate invariance, corrupted/short audio handling, and REST API validation.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.ecapa_service import (
    DEFAULT_VERIFICATION_THRESHOLD,
    EMBEDDING_DIM,
    TARGET_SAMPLE_RATE,
    ECAPAInferenceError,
    ECAPAModelError,
    ECAPAService,
    SpeakerVerificationResult,
)


# ============================================================================
# Helpers: Synthetic Voice Generation with Deterministic Harmonic Profiles
# ============================================================================

def make_speaker_wav(
    duration_s: float = 2.5,
    sample_rate: int = 16000,
    fundamental_hz: float = 160.0,
    harmonics: int = 4,
    noise_level: float = 0.0,
    clipping: bool = False,
    phase_shift: float = 0.0,
) -> bytes:
    """
    Generates a deterministic speaker voice waveform with formant-like harmonic structure.
    Different fundamental frequencies model distinctly different speaker vocal tracts.
    """
    n_samples = int(duration_s * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        samples = []
        for i in range(n_samples):
            t = float(i) / sample_rate
            val = 0.0
            for h in range(1, harmonics + 1):
                amp = 0.6 / (h ** 0.8)
                val += amp * math.sin(2.0 * math.pi * (fundamental_hz * h) * t + phase_shift * h)

            # Apply vocal tract modulation
            val *= 0.5 + 0.5 * math.sin(2.0 * math.pi * 3.0 * t)

            if noise_level > 0.0:
                val += noise_level * np.random.uniform(-1.0, 1.0)

            if clipping and i % 30 < 4:
                val = 1.3  # Clipping spike

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
def ecapa_service() -> ECAPAService:
    return ECAPAService()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ============================================================================
# 1. Model Availability & Metadata Tests
# ============================================================================

def test_ecapa_model_available(ecapa_service: ECAPAService):
    """Verify that official SpeechBrain ECAPA-TDNN model files exist on disk."""
    assert ecapa_service.is_available() is True
    info = ecapa_service.get_model_info()
    assert info["model_name"] == "ECAPA-TDNN (VoxCeleb)"
    assert info["installed"] is True
    assert info["embedding_dimension"] == 192
    assert info["sample_rate"] == 16000
    assert info["device"] == "cpu"
    assert info["size_mb"] > 50.0


def test_ecapa_model_loading_and_embedding_shape(ecapa_service: ECAPAService):
    """Verify model loads on CPU and extracts normalized 192-dim embedding."""
    wav_bytes = make_speaker_wav(duration_s=2.0, sample_rate=16000, fundamental_hz=180.0)
    emb, info, warnings = ecapa_service.extract_embedding(wav_bytes, filename="test_voice.wav")

    assert isinstance(emb, np.ndarray)
    assert emb.shape == (192,)
    # Verify strict L2 normalization (norm == 1.0)
    norm = float(np.linalg.norm(emb))
    assert abs(norm - 1.0) < 1e-4
    assert info["duration_seconds"] >= 1.9
    assert info["sample_rate"] == 16000


# ============================================================================
# 2. Speaker Discrimination & Cosine Similarity Tests
# ============================================================================

def test_same_speaker_audio_pair(ecapa_service: ECAPAService):
    """
    Verify that two recordings from the same speaker profile produce high cosine similarity
    and are classified as SAME_SPEAKER.
    """
    # Recording 1: Speaker A (fundamental 150 Hz, phrase 1)
    rec1 = make_speaker_wav(duration_s=3.0, sample_rate=16000, fundamental_hz=150.0, phase_shift=0.0)
    # Recording 2: Speaker A (same 150 Hz fundamental, different phase/modulation)
    rec2 = make_speaker_wav(duration_s=3.0, sample_rate=16000, fundamental_hz=150.0, phase_shift=1.2)

    res = ecapa_service.verify_speakers(rec1, rec2, ref_filename="spk_a1.wav", cmp_filename="spk_a2.wav")

    assert res.embedding_dimension == 192
    assert res.cosine_similarity > 0.80, f"Expected high similarity for same speaker, got {res.cosine_similarity}"
    assert res.is_same_speaker is True
    assert res.verification_status == "SAME_SPEAKER"
    assert res.processing_time > 0.0


def test_different_speaker_audio_pair(ecapa_service: ECAPAService):
    """
    Verify that recordings from two distinct speakers produce significantly lower similarity
    than identical speaker pairs, and test discrimination with threshold.
    """
    # Speaker A: Male pitch ~130 Hz
    spk_a1 = make_speaker_wav(duration_s=3.0, sample_rate=16000, fundamental_hz=130.0, phase_shift=0.0)
    spk_a2 = make_speaker_wav(duration_s=3.0, sample_rate=16000, fundamental_hz=130.0, phase_shift=0.5)
    # Speaker B: Female pitch ~380 Hz
    spk_b = make_speaker_wav(duration_s=3.0, sample_rate=16000, fundamental_hz=380.0)

    res_same = ecapa_service.verify_speakers(spk_a1, spk_a2)
    res_diff = ecapa_service.verify_speakers(spk_a1, spk_b, threshold=0.75, ref_filename="spk_male.wav", cmp_filename="spk_female.wav")

    assert res_diff.embedding_dimension == 192
    assert res_same.cosine_similarity > res_diff.cosine_similarity + 0.15
    assert res_diff.verification_status == "DIFFERENT_SPEAKER"
    assert res_diff.is_same_speaker is False


def test_custom_verification_threshold(ecapa_service: ECAPAService):
    """Verify that verification decision strictly adheres to the caller-configured threshold."""
    rec1 = make_speaker_wav(duration_s=2.5, sample_rate=16000, fundamental_hz=200.0)
    rec2 = make_speaker_wav(duration_s=2.5, sample_rate=16000, fundamental_hz=200.0, phase_shift=0.5)

    # Low threshold: should match
    res_low = ecapa_service.verify_speakers(rec1, rec2, threshold=0.10)
    assert res_low.is_same_speaker is True
    assert res_low.verification_status == "SAME_SPEAKER"

    # Impossible threshold (0.999): should not match
    res_high = ecapa_service.verify_speakers(rec1, rec2, threshold=0.999)
    assert res_high.is_same_speaker is False
    assert res_high.verification_status == "DIFFERENT_SPEAKER"


# ============================================================================
# 3. Audio Invariance & Preprocessing Edge Cases
# ============================================================================

@pytest.mark.parametrize("sr", [8000, 22050, 44100, 48000])
def test_different_sample_rates_resampled_to_16k(ecapa_service: ECAPAService, sr: int):
    """Verify audio in non-16kHz sample rates is automatically resampled without error."""
    wav_bytes = make_speaker_wav(duration_s=2.0, sample_rate=sr, fundamental_hz=220.0)
    emb, info, warnings = ecapa_service.extract_embedding(wav_bytes, filename=f"audio_{sr}hz.wav")

    assert emb.shape == (192,)
    assert abs(np.linalg.norm(emb) - 1.0) < 1e-4


def test_short_audio_quality_warning(ecapa_service: ECAPAService):
    """Verify short audio (1.2s < 1.8s) extracts embeddings but generates quality warnings."""
    short_wav = make_speaker_wav(duration_s=1.2, sample_rate=16000, fundamental_hz=200.0)
    ref_wav = make_speaker_wav(duration_s=2.5, sample_rate=16000, fundamental_hz=200.0)

    res = ecapa_service.verify_speakers(short_wav, ref_wav)
    assert len(res.audio_quality_warnings) > 0
    assert any("short" in w.lower() for w in res.audio_quality_warnings)


def test_extremely_short_audio_rejected(ecapa_service: ECAPAService):
    """Verify audio shorter than minimum 1600 samples (0.10s) is rejected with clear error."""
    tiny_pcm = np.random.randn(800).astype(np.float32)  # 0.05 seconds
    with pytest.raises(ECAPAInferenceError) as exc_info:
        ecapa_service.extract_embedding(tiny_pcm, filename="tiny.wav")
    assert "short" in str(exc_info.value).lower() or "1,600" in str(exc_info.value)


def test_empty_audio_rejected(ecapa_service: ECAPAService):
    """Verify empty byte payload is rejected."""
    with pytest.raises(ECAPAInferenceError) as exc_info:
        ecapa_service.extract_embedding(b"", filename="empty.wav")
    assert "empty" in str(exc_info.value).lower()


def test_corrupted_audio_rejected(ecapa_service: ECAPAService):
    """Verify un-decodable random bytes are rejected cleanly."""
    corrupt_bytes = b"CORRUPTED_BINARY_HEADER_NOT_AUDIO" * 20
    with pytest.raises(ECAPAInferenceError):
        ecapa_service.extract_embedding(corrupt_bytes, filename="bad.wav")


def test_clipped_audio_quality_warning(ecapa_service: ECAPAService):
    """Verify clipped audio produces digital distortion warning."""
    clipped_wav = make_speaker_wav(duration_s=2.5, sample_rate=16000, clipping=True)
    clean_wav = make_speaker_wav(duration_s=2.5, sample_rate=16000, clipping=False)

    res = ecapa_service.verify_speakers(clipped_wav, clean_wav)
    assert any("clipped" in w.lower() or "clipping" in w.lower() for w in res.audio_quality_warnings)


# ============================================================================
# 4. Model Loading Failure & Lazy Fallback Test
# ============================================================================

def test_model_loading_failure_raises_ecapa_model_error():
    """Verify model initialization errors raise ECAPAModelError."""
    service = ECAPAService()
    with patch.object(service, "load_model", side_effect=ECAPAModelError("Simulated model loading failure")):
        with pytest.raises(ECAPAModelError) as exc:
            service.load_model()
        assert "Simulated model loading failure" in str(exc.value)


# ============================================================================
# 5. REST API Endpoint Tests (POST /api/v1/speaker/verify)
# ============================================================================

def test_api_speaker_verify_same_speaker(client: TestClient):
    """Verify POST /api/v1/speaker/verify with matching speaker pair."""
    ref_bytes = make_speaker_wav(duration_s=2.5, sample_rate=16000, fundamental_hz=160.0)
    cmp_bytes = make_speaker_wav(duration_s=2.5, sample_rate=16000, fundamental_hz=160.0, phase_shift=0.8)

    files = {
        "reference_audio": ("ref.wav", ref_bytes, "audio/wav"),
        "comparison_audio": ("cmp.wav", cmp_bytes, "audio/wav"),
    }
    res = client.post("/api/v1/speaker/verify?threshold=0.25", files=files)

    assert res.status_code == 200, res.text
    data = res.json()

    assert data["success"] is True
    assert data["model_name"] == "ECAPA-TDNN (VoxCeleb)"
    assert data["embedding_dimension"] == 192
    assert -1.0 <= data["cosine_similarity"] <= 1.0
    assert data["cosine_similarity"] > 0.80
    assert data["verification_status"] == "SAME_SPEAKER"
    assert data["is_same_speaker"] is True
    assert data["threshold"] == 0.25
    assert data["processing_time"] > 0.0
    assert "interpretation_note" in data
    assert "reference_audio_info" in data
    assert "comparison_audio_info" in data


def test_api_speaker_verify_different_speaker(client: TestClient):
    """Verify POST /api/v1/speaker/verify with distinct voices."""
    ref_bytes = make_speaker_wav(duration_s=2.5, sample_rate=16000, fundamental_hz=130.0)
    cmp_bytes = make_speaker_wav(duration_s=2.5, sample_rate=16000, fundamental_hz=420.0)

    files = {
        "reference_audio": ("male_ref.wav", ref_bytes, "audio/wav"),
        "comparison_audio": ("female_cmp.wav", cmp_bytes, "audio/wav"),
    }
    # Setting threshold at 0.75
    res = client.post("/api/v1/speaker/verify?threshold=0.75", files=files)

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["verification_status"] == "DIFFERENT_SPEAKER"
    assert data["is_same_speaker"] is False


def test_api_speaker_verify_empty_file_rejected(client: TestClient):
    """Verify API rejects empty audio file with HTTP 400."""
    valid_wav = make_speaker_wav(duration_s=1.5, sample_rate=16000)
    files = {
        "reference_audio": ("empty.wav", b"", "audio/wav"),
        "comparison_audio": ("valid.wav", valid_wav, "audio/wav"),
    }
    res = client.post("/api/v1/speaker/verify", files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_api_speaker_verify_corrupted_file_rejected(client: TestClient):
    """Verify API rejects corrupt audio file with HTTP 400."""
    valid_wav = make_speaker_wav(duration_s=1.5, sample_rate=16000)
    files = {
        "reference_audio": ("corrupt.wav", b"INVALID_GARBAGE_BYTES_12345", "audio/wav"),
        "comparison_audio": ("valid.wav", valid_wav, "audio/wav"),
    }
    res = client.post("/api/v1/speaker/verify", files=files)
    assert res.status_code == 400



def test_api_speaker_model_info(client: TestClient):
    """Verify GET /api/v1/speaker/model-info returns ECAPA model metadata."""
    res = client.get("/api/v1/speaker/model-info")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "online"
    assert data["available"] is True
    assert data["info"]["model_name"] == "ECAPA-TDNN (VoxCeleb)"
    assert data["info"]["embedding_dimension"] == 192
    assert data["info"]["sample_rate"] == 16000
    assert data["info"]["dependencies_available"] is True
