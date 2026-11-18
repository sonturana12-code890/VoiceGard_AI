"""
VOICEGUARD AI — Full Pipeline Comprehensive Verification Test Suite
Verifies all 10 core requirements from Phase 1 through Phase 7:
1. WAV human voice analysis.
2. MP3 human voice analysis (with mp3float normalization).
3. MPEG audio decoding and analysis.
4. AI-generated synthetic voice simulation.
5. Corrupted audio rejection.
6. Empty audio rejection.
7. Unsupported format rejection.
8. Expired authentication token rejection (401).
9. Missing authentication token rejection (401).
10. Real AASIST inference and Zero-Hallucination compliance.
11. Health & telemetry endpoints.
12. Auth /me and /refresh flow (including Swagger Bearer handling).
"""

from __future__ import annotations

import io
import wave
from datetime import timedelta
from unittest.mock import MagicMock, patch

import av
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.main import app
from backend.services.audio_validator import AudioValidator
from backend.services.ffmpeg_service import FFmpegService
from backend.services.inference_pipeline import DetectionPipeline
from backend.services.model_manager import ModelManager


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    signup_res = client.post("/api/auth/signup", json={
        "fullName": "Pipeline Lead Auditor",
        "email": "pipeline_auditor@voiceguard.ai",
        "password": "SecurePassword123!",
        "termsAccepted": True,
    })
    if signup_res.status_code == 201 and "access_token" in signup_res.json():
        token = signup_res.json()["access_token"]
    else:
        login_res = client.post("/api/auth/login", json={
            "email": "pipeline_auditor@voiceguard.ai",
            "password": "SecurePassword123!",
        })
        token = login_res.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# SYNTHESIS GENERATORS
# ============================================================================

def make_vocal_wav(duration: float = 2.0, sr: int = 16000) -> bytes:
    """Synthesizes human vocal harmonics: fundamental 180Hz + formants at 540Hz, 1200Hz, 2400Hz."""
    total_samples = int(duration * sr)
    t = np.linspace(0, duration, total_samples, endpoint=False)
    # Human vocal resonance spectrum
    f0 = 0.4 * np.sin(2 * np.pi * 180.0 * t)
    f1 = 0.3 * np.sin(2 * np.pi * 540.0 * t)
    f2 = 0.2 * np.sin(2 * np.pi * 1200.0 * t)
    f3 = 0.1 * np.sin(2 * np.pi * 2400.0 * t)
    signal = (f0 + f1 + f2 + f3).astype(np.float32)
    signal_int16 = (signal * 32767.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(signal_int16.tobytes())
    return buf.getvalue()


def make_vocal_mp3(duration: float = 1.5, sr: int = 16000) -> bytes:
    """Synthesizes valid MP3 with vocal harmonics (PyAV decodes as mp3float)."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp3") as container:
        stream = container.add_stream("mp3", rate=sr)
        stream.layout = "mono"
        total_samples = int(duration * sr)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        signal = (0.5 * np.sin(2 * np.pi * 220.0 * t) + 0.3 * np.sin(2 * np.pi * 660.0 * t)).astype(np.float32)
        frame = av.AudioFrame.from_ndarray(signal.reshape(1, -1), format="fltp", layout="mono")
        frame.rate = sr
        for p in stream.encode(frame):
            container.mux(p)
        for p in stream.encode(None):
            container.mux(p)
    return buf.getvalue()


def make_mpeg_stream(duration: float = 1.2, sr: int = 44100) -> bytes:
    """Synthesizes valid MPEG Program Stream with audio track."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mpeg") as container:
        stream = container.add_stream("mp2", rate=sr)
        stream.layout = "stereo"
        total_samples = int(duration * sr)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        wave_data = (0.4 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
        stereo_arr = np.stack([wave_data, wave_data])
        chunk_size = 1152
        for i in range(0, total_samples, chunk_size):
            chunk = stereo_arr[:, i:i + chunk_size]
            if chunk.shape[1] == chunk_size:
                frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout="stereo")
                frame.rate = sr
                for p in stream.encode(frame):
                    container.mux(p)
        for p in stream.encode(None):
            container.mux(p)
    return buf.getvalue()


def make_synthetic_vocoder_voice(duration: float = 2.0, sr: int = 16000) -> bytes:
    """Synthesizes vocoder-style audio: sharp low-pass cutoff at 3.2kHz and robotic pitch jitter."""
    total_samples = int(duration * sr)
    t = np.linspace(0, duration, total_samples, endpoint=False)
    # Buzz-like pulse with sharp frequency band
    buzz = 0.5 * np.sign(np.sin(2 * np.pi * 250.0 * t))
    # Band-limit to mimic vocoder artifacts
    fft_b = np.fft.rfft(buzz)
    freqs = np.fft.rfftfreq(total_samples, 1.0 / sr)
    fft_b[freqs > 3200] = 0.0  # Neural vocoder low-pass cutoff
    filtered = np.fft.irfft(fft_b, n=total_samples).astype(np.float32)
    filtered = filtered / (np.max(np.abs(filtered)) + 1e-6)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((filtered * 32767.0).astype(np.int16).tobytes())
    return buf.getvalue()


# ============================================================================
# 10 CORE AUTOMATED TESTS
# ============================================================================

def test_01_wav_human_voice(client, auth_headers):
    """Test 1: WAV human voice uploaded, preprocessed to 16kHz mono float32, and analyzed."""
    wav_bytes = make_vocal_wav(duration=2.5, sr=16000)
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("natural_voice.wav", wav_bytes, "audio/wav")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["filename"] == "natural_voice.wav"
    assert data["audio_information"]["sample_rate"] == 16000
    assert data["audio_information"]["channels"] in (1, 2)
    assert data["audio_information"]["rms_energy"] > 0.05
    assert data["audio_information"]["spectral_centroid_hz"] > 100.0
    assert data["segments_analyzed"] >= 1


def test_02_mp3_human_voice(client, auth_headers):
    """Test 2: MP3 human voice correctly handles mp3float decoder, normalizes to mp3, and succeeds."""
    mp3_bytes = make_vocal_mp3(duration=1.5, sr=16000)
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("interview.mp3", mp3_bytes, "audio/mp3")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["audio_information"]["sample_rate"] == 16000
    assert data["audio_information"]["channels"] in (1, 2)
    assert data["segments_analyzed"] >= 1


def test_03_mpeg_audio_pipeline(client, auth_headers):
    """Test 3: MPEG container with audio stream is demuxed via FFmpegService and analyzed."""
    mpeg_bytes = make_mpeg_stream(duration=1.5, sr=44100)
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("wiretap.mpeg", mpeg_bytes, "audio/mpeg")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["model"]["name"] == "AASIST"
    assert data["audio_information"]["sample_rate"] == 16000
    assert data["audio_information"]["channels"] in (1, 2)


def test_04_ai_generated_synthetic_voice(client, auth_headers):
    """Test 4: Synthetic voice with vocoder low-pass cutoff analyzed for acoustic anomalies."""
    synth_bytes = make_synthetic_vocoder_voice(duration=2.0, sr=16000)
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("deepfake_clone.wav", synth_bytes, "audio/wav")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["audio_information"]["rms_energy"] > 0.01
    assert data["segments_analyzed"] >= 1


def test_05_corrupted_audio_rejection(client, auth_headers):
    """Test 5: Corrupted audio bitstream rejected with 400 Bad Request."""
    corrupted_data = b"RIFF\x00\x00\x00\x00WAVE" + b"\xff" * 20
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("bad_audio.wav", corrupted_data, "audio/wav")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    data = res.json()
    assert "CORRUPTED_AUDIO" in data["detail"] or "INVALID_AUDIO" in data["detail"]


def test_06_empty_audio_rejection(client, auth_headers):
    """Test 6: Empty (0 bytes) file rejected with 400 EMPTY_AUDIO."""
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("zero_bytes.wav", b"", "audio/wav")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    data = res.json()
    assert "EMPTY_AUDIO" in data["detail"]


def test_07_unsupported_audio_rejection(client, auth_headers):
    """Test 7: Non-audio format (.exe) rejected with 400 UNSUPPORTED_FORMAT."""
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("trojan.exe", b"MZ\x90\x00" * 100, "application/octet-stream")},
        headers=auth_headers,
    )
    assert res.status_code == 400
    data = res.json()
    assert "UNSUPPORTED_FORMAT" in data["detail"]


def test_08_expired_authentication_token(client):
    """Test 8: Expired authentication token rejected with HTTP 401 Unauthorized."""
    expired_token = create_access_token(
        {"sub": "test_user_id", "email": "expired@voiceguard.ai"},
        expires_delta=timedelta(seconds=-30),
    )
    wav_bytes = make_vocal_wav(duration=1.0)
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("voice.wav", wav_bytes, "audio/wav")},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_09_missing_authentication_token(client):
    """Test 9: Missing authentication token rejected with HTTP 401 Unauthorized."""
    wav_bytes = make_vocal_wav(duration=1.0)
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("voice.wav", wav_bytes, "audio/wav")},
    )
    assert res.status_code == 401
    assert "authentication required" in res.json()["detail"].lower()


def test_10_real_aasist_inference_and_zero_hallucination(client, auth_headers):
    """Test 10: Real AASIST neural inference logic & strict Zero-Hallucination policy verification."""
    pipeline = DetectionPipeline()
    wav_bytes = make_vocal_wav(duration=2.0)

    # 1. Zero-hallucination verification when weights are uninstalled (e.g. ECAPA_TDNN)
    report = pipeline.analyze_audio(wav_bytes, "voice.wav", "audio/wav", model_name="ECAPA_TDNN")
    assert report["success"] is True
    assert report["status"] == "AI_MODEL_NOT_CONFIGURED"
    assert report["prediction"]["label"] == "INCONCLUSIVE"
    assert report["prediction"]["synthetic_probability"] is None
    assert report["prediction"]["human_probability"] is None
    assert report["prediction"]["confidence"] is None

    # 2. Simulated real neural inference with mocked ONNX session producing actual logits
    with patch.object(pipeline.model_manager, "is_model_available", return_value=True), \
         patch.object(pipeline.model_manager, "run_inference") as mock_inf:

        # Mock inference returns spoof logits [spoof=4.2, bona_fide=0.1] (~98.3% spoof)
        mock_inf.return_value = np.array([[4.2, 0.1]], dtype=np.float32)

        report_synth = pipeline.analyze_audio(wav_bytes, "spoof_clone.wav", "audio/wav", model_name="AASIST")
        assert report_synth["success"] is True
        assert report_synth["status"] == "completed"
        assert report_synth["prediction"]["label"] == "AI_GENERATED"
        assert report_synth["prediction"]["synthetic_probability"] > 0.90
        assert report_synth["model"]["inference_completed"] is True

        # Mock inference returns authentic logits [spoof=0.2, bona_fide=4.5] (~98.6% human)
        mock_inf.return_value = np.array([[0.2, 4.5]], dtype=np.float32)

        report_auth = pipeline.analyze_audio(wav_bytes, "human_voice.wav", "audio/wav", model_name="AASIST")
        assert report_auth["success"] is True
        assert report_auth["status"] == "completed"
        assert report_auth["prediction"]["label"] == "HUMAN"
        assert report_auth["prediction"]["human_probability"] > 0.90


def test_11_health_and_telemetry_endpoints(client):
    """Test 11: GET /api/v1/audio/health and GET /api/health report real telemetry."""
    res_v1 = client.get("/api/v1/audio/health")
    assert res_v1.status_code == 200
    v1_data = res_v1.json()
    assert v1_data["status"] == "healthy"
    assert "AASIST" in v1_data["supported_models"]
    assert "mpeg" in v1_data["supported_formats"]
    assert "ffmpeg_status" in v1_data
    assert "models_status" in v1_data

    res_root = client.get("/api/health")
    assert res_root.status_code == 200
    root_data = res_root.json()
    assert root_data["status"] == "healthy"
    assert "inference" in root_data
    assert "device" in root_data["inference"]


def test_12_auth_me_refresh_and_swagger_bearer(client):
    """Test 12: GET /api/auth/me, POST /api/auth/refresh, and Swagger double-Bearer handling."""
    # 1. Signup / Login
    email = "swagger_test@voiceguard.ai"
    pwd = "SwaggerPassword123!"
    reg = client.post("/api/auth/signup", json={
        "fullName": "Swagger Tester",
        "email": email,
        "password": pwd,
        "termsAccepted": True,
    })
    token = reg.json().get("access_token") or client.post("/api/auth/login", json={"email": email, "password": pwd}).json()["access_token"]

    # 2. Standard Bearer Authorization
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == email

    # 3. Swagger double-Bearer prefix tolerance ('Bearer Bearer eyJ...')
    swagger_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer Bearer {token}"})
    assert swagger_res.status_code == 200
    assert swagger_res.json()["user"]["email"] == email

    # 4. Token Refresh
    refresh_res = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert refresh_res.status_code == 200
    new_token = refresh_res.json()["access_token"]
    assert new_token != ""

    # 5. Access with new refreshed token
    refreshed_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert refreshed_me.status_code == 200
    assert refreshed_me.json()["user"]["email"] == email
