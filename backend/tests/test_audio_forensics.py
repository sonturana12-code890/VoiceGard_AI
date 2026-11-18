"""
VOICEGUARD AI — Audio Forensics & Signal Quality Analysis Tests
Unit & Integration tests verifying all Phase 3 Forensics capabilities:
- Background Noise Detection & Intensity
- Signal-to-Noise Ratio (SNR in dB) & Reliability Handling
- Noise Floor Estimation in dBFS
- Audio Clipping Detection & Interval Mapping
- Silence Detection & Interval Mapping
- Voice Activity Detection (VAD) Speech vs Non-Speech
- Explainable Audio Quality Score (0-100) & Disclaimers
- Standalone Forensics API Endpoints & Pipeline Integration
"""

import io
import math
import wave
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.forensics_service import AudioForensicsService
from backend.services.inference_pipeline import DetectionPipeline
from backend.schemas import StandaloneForensicsResponse, Phase3AudioAnalysisResponse


def create_test_wav(
    duration: float = 3.0,
    sample_rate: int = 16000,
    has_speech: bool = True,
    noise_level: float = 0.001,
    clipped: bool = False,
) -> bytes:
    """Helper to generate in-memory synthetic 16-bit PCM WAV."""
    total_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, total_samples, endpoint=False)
    sig = np.random.normal(0, noise_level, total_samples).astype(np.float32)

    if has_speech:
        # Add a burst of speech-like harmonics in the middle second (1.0s to 2.0s)
        burst_start = int(sample_rate * 1.0)
        burst_end = int(sample_rate * 2.0)
        t_burst = t[burst_start:burst_end]
        burst = (
            0.4 * np.sin(2 * np.pi * 300 * t_burst)
            + 0.2 * np.sin(2 * np.pi * 600 * t_burst)
            + 0.1 * np.sin(2 * np.pi * 1200 * t_burst)
        ).astype(np.float32)
        sig[burst_start:burst_end] += burst

    if clipped:
        sig = sig * 3.0  # Force digital clipping

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
# 1. UNIT TESTS: AudioForensicsService
# ============================================================================

def test_forensics_clean_speech_burst():
    """Verify clean speech with pauses: high SNR, quiet noise floor, accurate VAD."""
    sr = 16000
    svc = AudioForensicsService(sample_rate=sr)

    # 4s audio: silence -> 1.5s tone -> silence
    t = np.linspace(0, 4.0, sr * 4, endpoint=False)
    sig = np.random.normal(0, 0.0005, sr * 4).astype(np.float32)
    sig[sr * 1 : int(sr * 2.5)] += (0.5 * np.sin(2 * np.pi * 400 * t[sr * 1 : int(sr * 2.5)])).astype(np.float32)

    rep = svc.analyze(sig, sr)

    assert rep["duration_seconds"] == 4.0
    assert rep["noise_floor"]["noise_floor_dbfs"] < -50.0

    # SNR checks
    assert rep["snr_analysis"]["is_reliable"] is True
    assert rep["snr_analysis"]["snr_db"] > 25.0
    assert rep["snr_analysis"]["classification"] in ["EXCELLENT", "GOOD"]

    # VAD checks
    vad = rep["voice_activity"]
    assert vad["speech_segments_count"] >= 1
    assert 1.4 <= vad["total_speech_seconds"] <= 1.8  # 1.5s tone + hangover
    assert vad["speech_percentage"] > 25.0

    # Silence checks
    sil = rep["silence_analysis"]
    assert sil["silent_segments_count"] >= 1
    assert sil["total_silence_seconds"] > 1.5

    # Clipping checks
    assert rep["clipping_analysis"]["has_clipping"] is False
    assert rep["clipping_analysis"]["clipped_samples_count"] == 0

    # Quality score
    q = rep["quality_score"]
    assert q["overall_score"] >= 80.0
    assert q["badge"] in ["PRISTINE", "HIGH"]
    assert "strictly independent" in q["disclaimer"].lower()


def test_forensics_noisy_environment():
    """Verify heavy background noise: elevated noise floor, low SNR, lower quality score."""
    sr = 16000
    svc = AudioForensicsService(sample_rate=sr)

    t = np.linspace(0, 3.0, sr * 3, endpoint=False)
    # Intense Gaussian noise (-20 dBFS approx)
    sig = np.random.normal(0, 0.15, sr * 3).astype(np.float32)
    # Weak tone
    sig[sr * 1 : sr * 2] += (0.2 * np.sin(2 * np.pi * 350 * t[sr * 1 : sr * 2])).astype(np.float32)

    rep = svc.analyze(sig, sr)

    assert rep["noise_analysis"]["has_background_noise"] is True
    assert rep["noise_analysis"]["noise_intensity_score"] > 0.4
    assert rep["noise_floor"]["noise_floor_dbfs"] > -40.0

    # SNR should be low or fair
    if rep["snr_analysis"]["is_reliable"]:
        assert rep["snr_analysis"]["snr_db"] < 15.0

    # Quality score penalized
    assert rep["quality_score"]["overall_score"] < 70.0


def test_forensics_pure_silence():
    """Verify pure zero audio: 100% silence, SNR unreliability handled gracefully."""
    sr = 16000
    svc = AudioForensicsService(sample_rate=sr)
    sig = np.zeros(sr * 3, dtype=np.float32)

    rep = svc.analyze(sig, sr)

    assert rep["silence_analysis"]["silence_ratio"] == 1.0
    assert rep["silence_analysis"]["silence_percentage"] == 100.0
    assert rep["silence_analysis"]["total_silence_seconds"] == 3.0

    # VAD speech should be 0
    assert rep["voice_activity"]["total_speech_seconds"] == 0.0

    # SNR must be marked unreliable
    assert rep["snr_analysis"]["snr_db"] is None
    assert rep["snr_analysis"]["is_reliable"] is False
    assert rep["snr_analysis"]["unreliability_reason"] == "NO_SPEECH_DETECTED"

    # Clipping is 0
    assert rep["clipping_analysis"]["has_clipping"] is False


def test_forensics_hard_clipping():
    """Verify clipped audio: sample count, intervals, severity, quality penalty."""
    sr = 16000
    svc = AudioForensicsService(sample_rate=sr)

    t = np.linspace(0, 2.0, sr * 2, endpoint=False)
    # Sine wave forced to 2.0 amplitude, clipped to 1.0
    sig = (np.sin(2 * np.pi * 440 * t) * 2.0).astype(np.float32)
    sig = np.clip(sig, -1.0, 1.0)

    rep = svc.analyze(sig, sr)

    clip = rep["clipping_analysis"]
    assert clip["has_clipping"] is True
    assert clip["clipped_samples_count"] > 1000
    assert clip["clipping_percentage"] > 10.0
    assert clip["severity"] == "Severe"
    assert len(clip["clipping_intervals"]) >= 1

    # Check interval structure
    first_int = clip["clipping_intervals"][0]
    assert "start" in first_int and "end" in first_int and "clipped_samples" in first_int

    # Quality score clipping component severely penalized
    assert rep["quality_score"]["breakdown"]["clipping_component"]["points"] < 5.0


def test_forensics_continuous_speech_no_pauses():
    """Verify continuous unpaused speech: SNR handles lack of noise frames."""
    sr = 16000
    svc = AudioForensicsService(sample_rate=sr)

    t = np.linspace(0, 2.5, int(sr * 2.5), endpoint=False)
    # Continuous high-energy signal throughout entire 2.5 seconds
    sig = (0.5 * np.sin(2 * np.pi * 400 * t)).astype(np.float32)

    rep = svc.analyze(sig, sr)

    assert rep["voice_activity"]["speech_ratio"] > 0.95
    # Unreliability handled with INSUFFICIENT_PAUSE_INTERVALS
    assert rep["snr_analysis"]["unreliability_reason"] == "INSUFFICIENT_PAUSE_INTERVALS"
    assert rep["snr_analysis"]["is_reliable"] is False


def test_forensics_empty_and_nan_signals():
    """Verify edge cases like empty array and NaN values do not crash."""
    svc = AudioForensicsService(sample_rate=16000)

    # Empty
    empty_rep = svc.analyze(np.array([], dtype=np.float32))
    assert empty_rep["total_samples"] == 0
    assert empty_rep["quality_score"]["overall_score"] == 0.0

    # NaN / Inf
    dirty_sig = np.array([0.1, np.nan, 0.2, np.inf, -np.inf, 0.3], dtype=np.float32)
    dirty_rep = svc.analyze(dirty_sig)
    assert dirty_rep["has_nan_inf_artifacts"] is True


# ============================================================================
# 2. INTEGRATION TESTS: DetectionPipeline & API Endpoints
# ============================================================================

def test_pipeline_attaches_forensics():
    """Verify DetectionPipeline embeds forensics into standard analysis report."""
    wav_bytes = create_test_wav(duration=2.5, has_speech=True)
    pipeline = DetectionPipeline()

    report = pipeline.analyze_audio(
        file_bytes=wav_bytes,
        filename="test_pipeline_forensics.wav",
        content_type="audio/wav",
    )

    assert report["success"] is True
    assert "forensics" in report
    forensics = report["forensics"]
    assert forensics is not None
    assert "snr_analysis" in forensics
    assert "noise_floor" in forensics
    assert "clipping_analysis" in forensics
    assert "silence_analysis" in forensics
    assert "voice_activity" in forensics
    assert "quality_score" in forensics

    # Validate against Pydantic schema
    validated = Phase3AudioAnalysisResponse.model_validate(report)
    assert validated.forensics is not None
    assert validated.forensics.quality_score.overall_score > 0.0


def get_test_auth_headers(client: TestClient) -> dict:
    signup_res = client.post("/api/auth/signup", json={
        "fullName": "Forensics Engineer",
        "email": "forensics_engineer@voiceguard.ai",
        "password": "ForensicsPassword123!",
        "termsAccepted": True,
    })
    if signup_res.status_code == 200 and "access_token" in signup_res.json():
        token = signup_res.json()["access_token"]
    else:
        login_res = client.post("/api/auth/login", json={
            "email": "forensics_engineer@voiceguard.ai",
            "password": "ForensicsPassword123!",
        })
        token = login_res.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def test_api_standalone_forensics_endpoint():
    """Verify POST /api/v1/audio/forensics standalone endpoint."""
    client = TestClient(app)
    headers = get_test_auth_headers(client)

    wav_bytes = create_test_wav(duration=2.0, has_speech=True)

    resp = client.post(
        "/api/v1/audio/forensics",
        files={"file": ("test_standalone.wav", io.BytesIO(wav_bytes), "audio/wav")},
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["filename"] == "test_standalone.wav"
    assert "forensics" in data
    assert data["forensics"]["snr_analysis"]["is_reliable"] is True
    assert data["forensics"]["quality_score"]["overall_score"] > 0

    # Check Pydantic model validity
    validated = StandaloneForensicsResponse.model_validate(data)
    assert validated.forensics.duration_seconds > 0.0


def test_api_get_forensics_by_analysis_id():
    """Verify GET /api/v1/audio/{analysis_id}/forensics endpoint."""
    client = TestClient(app)
    headers = get_test_auth_headers(client)

    wav_bytes = create_test_wav(duration=2.0, has_speech=True)

    # Run full Phase 3 analysis first
    analyze_resp = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("test_saved.wav", io.BytesIO(wav_bytes), "audio/wav")},
        headers=headers,
    )
    assert analyze_resp.status_code == 200
    analysis_id = analyze_resp.json()["analysis_id"]

    # Now retrieve via dedicated forensics endpoint
    get_resp = client.get(f"/api/v1/audio/{analysis_id}/forensics", headers=headers)
    assert get_resp.status_code == 200
    res_data = get_resp.json()
    assert res_data["success"] is True
    assert res_data["analysis_id"] == analysis_id
    assert "forensics" in res_data
    assert res_data["forensics"]["quality_score"]["overall_score"] > 0
