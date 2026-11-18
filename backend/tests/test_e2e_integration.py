"""
VOICEGUARD AI — Master End-to-End Automated Integration Test Suite
Comprehensive testing of Authentication, Multi-Format Audio Ingestion (WAV, MP3, MPEG, MPG),
Container Demuxing, FFmpeg Integration, Zero-Hallucination AI Inference, and API Contracts.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

import io
import math
import struct
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token
from backend.main import app
from backend.services.ffmpeg_service import FFmpegService
from backend.services.model_manager import ModelManager

client = TestClient(app)


# ============================================================================
# SYNTHETIC AUDIO GENERATION HELPERS
# ============================================================================

def make_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000, num_channels: int = 1) -> bytes:
    """Generates valid linear PCM WAV binary."""
    num_samples = int(duration_sec * sample_rate)
    total_data_bytes = num_samples * num_channels * 2

    header = bytearray()
    header.extend(b"RIFF")
    header.extend(struct.pack("<I", total_data_bytes + 36))
    header.extend(b"WAVE")
    header.extend(b"fmt ")
    header.extend(struct.pack("<I", 16))
    header.extend(struct.pack("<H", 1))  # PCM
    header.extend(struct.pack("<H", num_channels))
    header.extend(struct.pack("<I", sample_rate))
    header.extend(struct.pack("<I", sample_rate * num_channels * 2))
    header.extend(struct.pack("<H", num_channels * 2))
    header.extend(struct.pack("<H", 16))
    header.extend(b"data")
    header.extend(struct.pack("<I", total_data_bytes))

    samples = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        val = int(12000.0 * math.sin(2.0 * math.pi * 440.0 * t))
        val = max(-32768, min(32767, val))
        for _ in range(num_channels):
            samples.extend(struct.pack("<h", val))

    return bytes(header + samples)


def make_mpeg_audio_bytes(duration_sec: float = 1.0, sample_rate: int = 44100) -> bytes:
    """Encodes valid MPEG-1/2 Audio Layer 2 (MP2) audio in an MPEG Program Stream container."""
    import av
    out_buf = io.BytesIO()
    with av.open(out_buf, mode="w", format="mpeg") as container:
        stream = container.add_stream("mp2", rate=sample_rate)
        stream.bit_rate = 128000
        num_frames = max(2, int(duration_sec * sample_rate / 1152))

        for f_idx in range(num_frames):
            frame = av.AudioFrame(format="s16", layout="mono", samples=1152)
            frame.sample_rate = sample_rate
            t_start = (f_idx * 1152) / sample_rate
            t = np.linspace(t_start, t_start + 1152 / sample_rate, 1152, endpoint=False)
            sine = (np.sin(2 * np.pi * 440.0 * t) * 16000).astype(np.int16)
            frame.planes[0].update(sine.tobytes())
            for packet in stream.encode(frame):
                container.mux(packet)

        for packet in stream.encode(None):
            container.mux(packet)

    return out_buf.getvalue()


def make_mpeg_video_with_audio_bytes(duration_sec: float = 1.0) -> bytes:
    """Generates an MPEG container holding both a video stream and an audio stream."""
    import av
    out_buf = io.BytesIO()
    with av.open(out_buf, mode="w", format="mpeg") as container:
        v_stream = container.add_stream("mpeg1video", rate=25)
        v_stream.width = 160
        v_stream.height = 120
        v_stream.pix_fmt = "yuv420p"

        a_stream = container.add_stream("mp2", rate=44100)
        a_stream.bit_rate = 128000

        # Video frames
        for i in range(int(duration_sec * 25)):
            v_frame = av.VideoFrame(160, 120, "yuv420p")
            for packet in v_stream.encode(v_frame):
                container.mux(packet)
        for packet in v_stream.encode(None):
            container.mux(packet)

        # Audio frames
        for _ in range(max(2, int(duration_sec * 44100 / 1152))):
            a_frame = av.AudioFrame(format="s16", layout="mono", samples=1152)
            a_frame.sample_rate = 44100
            sine = (np.sin(np.linspace(0, 1, 1152)) * 14000).astype(np.int16)
            a_frame.planes[0].update(sine.tobytes())
            for packet in a_stream.encode(a_frame):
                container.mux(packet)
        for packet in a_stream.encode(None):
            container.mux(packet)

    return out_buf.getvalue()


def make_mpeg_video_only_bytes(duration_sec: float = 0.5) -> bytes:
    """Generates an MPEG container containing video but strictly NO audio streams."""
    import av
    out_buf = io.BytesIO()
    with av.open(out_buf, mode="w", format="mpeg") as container:
        v_stream = container.add_stream("mpeg1video", rate=25)
        v_stream.width = 160
        v_stream.height = 120
        v_stream.pix_fmt = "yuv420p"

        for _ in range(max(1, int(duration_sec * 25))):
            v_frame = av.VideoFrame(160, 120, "yuv420p")
            for packet in v_stream.encode(v_frame):
                container.mux(packet)
        for packet in v_stream.encode(None):
            container.mux(packet)

    return out_buf.getvalue()


# ============================================================================
# 1. AUTHENTICATION AUTOMATED TESTS
# ============================================================================

def test_auth_e2e_registration_and_duplicate():
    """Verifies user registration, duplicate email prevention, and terms enforcement."""
    unique_email = f"e2e_{int(time.time()*1000)}@voiceguard.ai"

    # 1. Registration without terms acceptance must fail
    res_no_terms = client.post("/api/auth/register", json={
        "fullName": "E2E SecOps",
        "email": unique_email,
        "password": "StrongPassword123!",
        "termsAccepted": False,
    })
    assert res_no_terms.status_code == 400
    assert "Terms" in res_no_terms.json()["detail"]

    # 2. Valid registration succeeds and issues JWT
    res_reg = client.post("/api/auth/register", json={
        "fullName": "E2E SecOps",
        "email": unique_email,
        "password": "StrongPassword123!",
        "termsAccepted": True,
        "remember": True,
    })
    assert res_reg.status_code == 201
    data = res_reg.json()
    assert "access_token" in data
    assert data["user"]["email"] == unique_email

    # 3. Duplicate registration is prevented
    res_dup = client.post("/api/auth/register", json={
        "fullName": "Duplicate User",
        "email": unique_email,
        "password": "AnotherPassword456!",
        "termsAccepted": True,
    })
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"]


def test_auth_e2e_login_json_email_and_username():
    """Verifies login via JSON body supporting both email and username keys."""
    unique_email = f"e2e_login_{int(time.time()*1000)}@voiceguard.ai"
    client.post("/api/auth/register", json={
        "fullName": "Login Tester",
        "email": unique_email,
        "password": "StrongPassword123!",
        "termsAccepted": True,
    })

    # JSON login with email
    res_json = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "StrongPassword123!",
        "remember": True,
    })
    assert res_json.status_code == 200
    assert "access_token" in res_json.json()

    # JSON login with username key
    res_user = client.post("/api/auth/login", json={
        "username": unique_email,
        "password": "StrongPassword123!",
        "remember": True,
    })
    assert res_user.status_code == 200
    assert "access_token" in res_user.json()


def test_auth_e2e_invalid_password():
    """Rejects incorrect passwords with HTTP 401."""
    unique_email = f"e2e_pw_{int(time.time()*1000)}@voiceguard.ai"
    client.post("/api/auth/register", json={
        "fullName": "Password Tester",
        "email": unique_email,
        "password": "CorrectPassword123!",
        "termsAccepted": True,
    })

    res = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": "WRONG_PASSWORD_999",
    })
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


def test_auth_e2e_unauthorized_access():
    """Ensures protected endpoints reject requests lacking Authorization Bearer token."""
    unauth_client = TestClient(app)
    unauth_client.cookies.clear()
    res = unauth_client.get("/api/auth/me")
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]


def test_dashboard_redirects_unauthenticated_users_to_login():
    """Ensures the dashboard page itself is protected by the session."""
    unauth_client = TestClient(app)
    unauth_client.cookies.clear()

    res = unauth_client.get("/app", follow_redirects=False)

    assert res.status_code == 303
    assert res.headers["location"] == "/login?auth=login"


def test_dashboard_serves_for_authenticated_user():
    """Ensures a valid HttpOnly session cookie can access the dashboard."""
    auth_client = TestClient(app)
    email = f"dashboard_{int(time.time() * 1000)}@voiceguard.ai"
    signup = auth_client.post("/api/auth/register", json={
        "fullName": "Dashboard Tester",
        "email": email,
        "password": "DashboardTester123!",
        "termsAccepted": True,
    })
    assert signup.status_code == 201

    dashboard = auth_client.get("/app")

    assert dashboard.status_code == 200
    assert 'class="app-layout"' in dashboard.text


def test_auth_e2e_expired_token():
    """Ensures expired tokens are rejected with HTTP 401."""
    expired_token = create_access_token(
        {"sub": "non-existent-id", "email": "expired@voiceguard.ai"},
        expires_delta=timedelta(seconds=-10),
    )
    res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


# ============================================================================
# 2. AUDIO PROCESSING & INGESTION TESTS
# ============================================================================

def get_auth_headers() -> dict:
    """Helper creating a test user and returning Bearer headers."""
    email = f"audio_tester_{int(time.time()*1000)}@voiceguard.ai"
    res = client.post("/api/auth/register", json={
        "fullName": "Audio Test Analyst",
        "email": email,
        "password": "PasswordSafe123!",
        "termsAccepted": True,
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_audio_e2e_valid_wav_upload():
    """Verifies WAV upload, container verification, and audio health."""
    headers = get_auth_headers()
    wav_bytes = make_wav_bytes(duration_sec=2.0, sample_rate=16000)

    res = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("test_sample.wav", wav_bytes, "audio/wav")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["filename"] == "test_sample.wav"
    assert data["audio_information"]["sample_rate"] == 16000
    assert abs(data["audio_information"]["duration"] - 2.0) < 0.1


def test_audio_e2e_valid_mpeg_and_mpg():
    """Verifies both .mpeg and .mpg container decoding and feature calculation."""
    headers = get_auth_headers()
    mpeg_bytes = make_mpeg_audio_bytes(duration_sec=1.2)

    # 1. Test .mpeg
    res_mpeg = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("audio_sample.mpeg", mpeg_bytes, "audio/mpeg")},
    )
    assert res_mpeg.status_code == 200
    assert res_mpeg.json()["success"] is True

    # 2. Test .mpg
    res_mpg = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("audio_sample.mpg", mpeg_bytes, "video/mpeg")},
    )
    assert res_mpg.status_code == 200
    assert res_mpg.json()["success"] is True


def test_audio_e2e_video_with_audio_stream():
    """Verifies that an MPEG video containing an audio stream extracts the audio cleanly."""
    headers = get_auth_headers()
    av_bytes = make_mpeg_video_with_audio_bytes(duration_sec=1.0)

    res = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("broadcast.mpeg", av_bytes, "video/mpeg")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["audio_information"]["channels"] in (1, 2)
    assert data["segments_analyzed"] >= 1


def test_audio_e2e_video_without_audio_stream():
    """Verifies rejection of video-only MPEG files lacking an audio track."""
    headers = get_auth_headers()
    video_only = make_mpeg_video_only_bytes(duration_sec=0.5)

    res = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("silent_video.mpeg", video_only, "video/mpeg")},
    )
    assert res.status_code == 400
    assert "NO_AUDIO_STREAM" in res.json()["detail"]


def test_audio_e2e_unsupported_format():
    """Rejects unapproved file formats like executables."""
    headers = get_auth_headers()
    res = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("malware.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert "UNSUPPORTED_FORMAT" in res.json()["detail"]


def test_audio_e2e_corrupted_audio():
    """Rejects malformed audio containers."""
    headers = get_auth_headers()
    res = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("corrupt.wav", b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00truncated", "audio/wav")},
    )
    assert res.status_code == 400
    assert "CORRUPTED_AUDIO" in res.json()["detail"] or "HEADER" in res.json()["detail"]


def test_audio_e2e_empty_audio():
    """Rejects empty 0-byte uploads."""
    headers = get_auth_headers()
    res = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert res.status_code == 400
    assert "EMPTY_AUDIO" in res.json()["detail"] or "empty" in res.json()["detail"].lower()


def test_audio_e2e_oversized_audio():
    """Rejects files exceeding 25 MB with HTTP 413."""
    headers = get_auth_headers()
    large_payload = b"\x00" * (25 * 1024 * 1024 + 1024)

    res = client.post(
        "/api/v1/audio/analyze",
        headers=headers,
        files={"file": ("large.wav", large_payload, "audio/wav")},
    )
    assert res.status_code == 413


# ============================================================================
# 3. AI VOICE DETECTION & ZERO-HALLUCINATION VERIFICATION
# ============================================================================

def test_ai_e2e_model_status_and_zero_hallucination():
    """Verifies that missing model weights trigger unconfigured status with empirical DSP."""
    headers = get_auth_headers()
    wav_bytes = make_wav_bytes(duration_sec=1.5, sample_rate=16000)

    # 1. Zero-hallucination check when model weights are unconfigured
    res = client.post(
        "/api/v1/audio/analyze?model_name=ECAPA_TDNN",
        headers=headers,
        files={"file": ("speech_sample.wav", wav_bytes, "audio/wav")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["prediction"]["label"] == "INCONCLUSIVE"
    assert data["prediction"]["synthetic_probability"] is None
    assert data["prediction"]["confidence"] is None
    assert data["model"]["inference_completed"] is False
    assert data["model_status"] == "MODEL_NOT_AVAILABLE"
    assert "missing_files" in data
    assert "instructions" in data

    # 2. Check RawNet2 inference when weights are present
    res_raw = client.post(
        "/api/v1/audio/analyze?model_name=RAWNET2",
        headers=headers,
        files={"file": ("speech_sample.wav", wav_bytes, "audio/wav")},
    )
    assert res_raw.status_code == 200
    data_raw = res_raw.json()
    assert data_raw["success"] is True
    assert data_raw["model_status"] == "RAWNET2_ACTIVE"
    assert data_raw["model"]["inference_completed"] is True


def test_ai_e2e_onnx_inference_when_mock_available():
    """Verifies that when an ONNX model is available, real inference execution occurs."""
    headers = get_auth_headers()
    wav_bytes = make_wav_bytes(duration_sec=2.0, sample_rate=16000)

    # Mock ONNX session returning logits [spoof=2.8, human=0.1]
    mock_session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "audio_waveform"
    mock_session.get_inputs.return_value = [mock_input]
    mock_session.run.return_value = [np.array([[2.8, 0.1]], dtype=np.float32)]

    model_mgr = ModelManager()
    with patch.object(model_mgr, "is_model_available", return_value=True):
        with patch.object(model_mgr, "get_session", return_value=mock_session):
            res = client.post(
                "/api/v1/audio/analyze",
                headers=headers,
                files={"file": ("test_spoof.wav", wav_bytes, "audio/wav")},
            )

    assert res.status_code == 200
    data = res.json()
    assert data["prediction"]["label"] == "AI_GENERATED"
    assert data["prediction"]["synthetic_probability"] > 0.90
    assert data["model"]["inference_completed"] is True


# ============================================================================
# 4. FRONTEND-BACKEND & TELEMETRY CONTRACTS
# ============================================================================

def test_frontend_e2e_dashboard_and_history_contracts():
    """Verifies dashboard overview, analytics, security events, and CSV export."""
    headers = get_auth_headers()

    # Overview
    res_ov = client.get("/api/dashboard/overview", headers=headers)
    assert res_ov.status_code == 200
    assert "total_audio_uploads" in res_ov.json()

    # Analytics
    res_an = client.get("/api/dashboard/analytics", headers=headers)
    assert res_an.status_code == 200
    assert "threat_distribution" in res_an.json()

    # Security Events
    res_ev = client.get("/api/security-events", headers=headers)
    assert res_ev.status_code == 200
    assert "events" in res_ev.json()

    # CSV Export
    res_csv = client.get("/api/reports/export", headers=headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Record Type" in res_csv.text or "ID" in res_csv.text


def test_ffmpeg_cli_and_pyav_diagnostics():
    """Verifies that FFmpeg diagnostics report both CLI and PyAV statuses."""
    diag = FFmpegService.get_diagnostics()
    assert "ffmpeg_cli_installed" in diag
    assert "ffprobe_cli_installed" in diag
    assert "pyav_installed" in diag
    assert diag["pyav_installed"] is True
    assert diag["ffmpeg_cli_installed"] is True  # Discovered at user's downloads path!
