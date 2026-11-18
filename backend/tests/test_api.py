"""
VOICEGUARD AI — Comprehensive Backend Test Suite
Tests authentication, audio upload, preprocessing, speaker enrollment, dashboard, threats, and reports.
"""

from __future__ import annotations

import io
import wave
import av
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.models
from backend.database import Base, get_db
from backend.auth import hash_password, verify_password
from backend.main import app
from backend.services.risk_engine import FraudRiskEngine
from backend.services.preprocessing_service import (
    AudioPreprocessingError,
    AudioPreprocessingService,
)
from sqlalchemy.pool import StaticPool

# Test SQLite in-memory database with StaticPool so all threads/sessions share the same DB
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app)


def create_sample_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Helper to generate valid 16kHz mono PCM WAV bytes for testing."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        # 1 second of silence (zero bytes)
        frames = b"\x00\x00" * int(sample_rate * duration_sec)
        wav_file.writeframes(frames)
    return buf.getvalue()


def create_sample_flac_bytes() -> bytes:
    output = io.BytesIO()
    container = av.open(output, mode="w", format="flac")
    stream = container.add_stream("flac", rate=16000)
    values = (np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 20000).astype(np.int16)
    frame = av.AudioFrame.from_ndarray(values.reshape(1, -1), format="s16", layout="mono")
    frame.sample_rate = 16000
    for packet in stream.encode(frame):
        container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()
    return output.getvalue()


# ============================================================================
# 1. HEALTH CHECK TEST
# ============================================================================
def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "inference" in data
    assert (
        data["inference"]["synthetic_detection"].startswith("AI_MODEL_NOT_CONFIGURED")
        or data["inference"]["synthetic_detection"] in ("AASIST_ACTIVE", "RAWNET2_ACTIVE")
    )


# ============================================================================
# 2. AUTHENTICATION TESTS
# ============================================================================
TEST_USER_EMAIL = "analyst@voiceguard.ai"
TEST_USER_PASSWORD = "StrongSecurityPassword123!"
auth_token: str = ""


def test_signup_requires_terms_acceptance(client):
    response = client.post("/api/auth/signup", json={
        "fullName": "Terms Tester",
        "email": "terms-check@voiceguard.ai",
        "password": "StrongSecurityPassword123!",
        "termsAccepted": False,
    })
    assert response.status_code == 400
    assert "acceptance is required" in response.json()["detail"]


def test_long_password_hash_and_verification(client):
    password = "A" * 100
    password_hash = hash_password(password)
    assert verify_password(password, password_hash)
    assert not verify_password(password + "B", password_hash)


def test_user_signup(client):
    global auth_token
    payload = {
        "fullName": "Cyber Defense Analyst",
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "termsAccepted": True,
        "remember": False,
    }
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == TEST_USER_EMAIL
    assert data["user"]["full_name"] == "Cyber Defense Analyst"
    assert "password" not in data["user"]
    auth_token = data["access_token"]


def test_duplicate_signup_prevention(client):
    payload = {
        "fullName": "Another User",
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "termsAccepted": True,
    }
    response = client.post("/api/auth/signup", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_user_login(client):
    payload = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == TEST_USER_EMAIL


def test_invalid_login_credentials(client):
    payload = {
        "email": TEST_USER_EMAIL,
        "password": "WrongPassword999!",
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_get_current_user_profile(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == TEST_USER_EMAIL


def test_protected_endpoint_without_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


# ============================================================================
# 3. AUDIO UPLOAD & HISTORY TESTS
# ============================================================================
uploaded_analysis_id: str = ""


def test_audio_upload_valid_wav(client):
    global uploaded_analysis_id
    headers = {"Authorization": f"Bearer {auth_token}"}
    wav_bytes = create_sample_wav_bytes(duration_sec=2.0)

    files = {"file": ("test_sample.wav", wav_bytes, "audio/wav")}
    response = client.post("/api/audio/upload", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()
    assert "analysis" in data
    assert data["analysis"]["filename"] == "test_sample.wav"
    assert data["analysis"]["analysis_status"] in ("AI_MODEL_NOT_CONFIGURED", "completed")
    uploaded_analysis_id = data["analysis"]["id"]


def test_audio_upload_invalid_extension(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    files = {"file": ("document.pdf", b"%PDF-1.4 fake pdf data", "application/pdf")}
    response = client.post("/api/audio/upload", headers=headers, files=files)
    assert response.status_code in (400, 422)
    assert "Unsupported audio format" in response.json()["detail"]


def test_corrupt_compressed_audio_is_rejected():
    payload = b"ID3" + bytes(range(1, 256)) * 4
    with pytest.raises(AudioPreprocessingError, match="could not be decoded"):
        AudioPreprocessingService.decode_and_extract_features(payload, "corrupt.mp3")


def test_compressed_audio_is_decoded_before_feature_extraction():
    metadata, features, tensor = AudioPreprocessingService.decode_and_extract_features(
        create_sample_flac_bytes(), "sample.flac"
    )
    assert metadata["sample_rate"] == 16000
    assert metadata["duration_seconds"] == pytest.approx(1.0, abs=0.1)
    assert features["rms_energy"] > 0
    assert tensor.shape == (1, 64600)


def test_audio_upload_empty_file(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    files = {"file": ("empty.wav", b"", "audio/wav")}
    response = client.post("/api/audio/upload", headers=headers, files=files)
    assert response.status_code in (400, 422)
    assert "empty" in response.json()["detail"].lower()


def test_audio_history(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/audio/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["history"][0]["id"] == uploaded_analysis_id
    assert data["stats"]["total_audio_scans"] == data["total"]
    assert data["stats"]["genuine_voices"] + data["stats"]["ai_generated_voices"] <= data["total"]
    assert data["stats"]["genuine_voices"] + data["stats"]["ai_generated_voices"] + data["stats"]["inconclusive_voices"] <= data["total"]
    assert data["stats"]["threats_detected"] >= 0


def test_live_audio_websocket_authenticates_and_processes_pcm(client):
    with client.websocket_connect("/api/v1/stream/ws") as websocket:
        websocket.send_json({
            "type": "auth",
            "token": auth_token,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        })
        ready = websocket.receive_json()
        assert ready["type"] == "ready"
        assert ready["sample_rate"] == 16000
        assert ready["channels"] == 1
        assert ready["detection_status"] in ("INCONCLUSIVE", "WAITING FOR AUDIO")
        assert ready["threat_alerts"] == []

        pcm_chunk = np.full(3200, 16384, dtype="<i2").tobytes()
        websocket.send_bytes(pcm_chunk)
        metrics = websocket.receive_json()
        assert metrics["type"] == "metrics"
        assert metrics["acoustic_metrics"]["sample_count"] == 3200
        assert metrics["acoustic_metrics"]["input_level_percent"] == pytest.approx(50.0, abs=0.1)
        assert metrics["acoustic_metrics"]["duration_seconds"] == pytest.approx(0.2)
        assert metrics["detection_status"] in ("INCONCLUSIVE", "WAITING FOR AUDIO")

        websocket.send_json({"type": "stop"})
        stopped = websocket.receive_json()
        assert stopped["type"] == "stopped"
        assert stopped["duration_seconds"] == pytest.approx(0.2)


def test_live_audio_websocket_rejects_invalid_authentication(client):
    with client.websocket_connect("/api/v1/stream/ws") as websocket:
        websocket.send_json({
            "type": "auth",
            "token": "invalid-token",
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        })
        error = websocket.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "unauthorized"


def test_audio_detail_by_id(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get(f"/api/audio/{uploaded_analysis_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == uploaded_analysis_id
    assert data["filename"] == "test_sample.wav"


# ============================================================================
# 4. SPEAKER REGISTRATION & VERIFICATION TESTS
# ============================================================================
registered_speaker_id: str = ""


def test_speaker_registration(client):
    global registered_speaker_id
    headers = {"Authorization": f"Bearer {auth_token}"}
    wav_bytes = create_sample_wav_bytes(duration_sec=1.5)

    data = {
        "speaker_name": "Executive Officer 01",
        "consent_status": "true",
        "department": "Finance",
        "clearance_level": "Level 4",
    }
    files = {"file": ("ref_voice.wav", wav_bytes, "audio/wav")}

    response = client.post("/api/speaker/register", headers=headers, data=data, files=files)
    assert response.status_code == 201
    resp_data = response.json()
    assert resp_data["speaker_name"] == "Executive Officer 01"
    assert resp_data["consent_status"] is True
    registered_speaker_id = resp_data["id"]


def test_speaker_registration_requires_explicit_consent(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    wav_bytes = create_sample_wav_bytes(duration_sec=1.0)
    response = client.post(
        "/api/speaker/register",
        headers=headers,
        data={"speaker_name": "No Consent Speaker"},
        files={"file": ("reference.wav", wav_bytes, "audio/wav")},
    )
    assert response.status_code == 400
    assert "explicit speaker consent" in response.json()["detail"]


def test_speaker_list(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/speaker/list", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(s["id"] == registered_speaker_id for s in data["speakers"])


def test_speaker_verify_phase_1(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    wav_bytes = create_sample_wav_bytes(duration_sec=1.0)

    data = {"speaker_id": registered_speaker_id}
    files = {"file": ("probe_voice.wav", wav_bytes, "audio/wav")}

    response = client.post("/api/speaker/verify", headers=headers, data=data, files=files)
    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data["speaker_id"] == registered_speaker_id
    assert resp_data["status"] == "AI_MODEL_NOT_CONFIGURED"
    assert resp_data["verified"] is False
    assert resp_data["confidence_score"] is None


# ============================================================================
# 5. DASHBOARD APIS TESTS
# ============================================================================
def test_dashboard_overview(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/dashboard/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_audio_uploads"] >= 1
    assert data["registered_speakers"] >= 1
    assert "recent_activity" in data


def test_dashboard_analytics(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/dashboard/analytics", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "analysis_status_counts" in data


def test_dashboard_recent_activity_response_contracts(client):
    headers = {"Authorization": f"Bearer {auth_token}"}

    response = client.get("/api/dashboard/recent-activity", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    response = client.get("/api/security-events", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json()["events"], list)


@pytest.mark.parametrize(
    ("synthetic_score", "expected_level"),
    [(0.9, "Critical"), (0.7, "High"), (0.4, "Medium"), (0.2, "Low")],
)
def test_fraud_risk_uses_normalized_model_probability(synthetic_score, expected_level):
    assessment = FraudRiskEngine.assess_risk(synthetic_score=synthetic_score)
    assert assessment["risk_level"] == expected_level


# ============================================================================
# 6. THREAT MONITORING APIS TESTS
# ============================================================================
def test_threat_list_empty_initially(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/threats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["threats"], list)


# ============================================================================
# 7. REPORTS APIS TESTS
# ============================================================================
def test_generate_report(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/reports", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "report_id" in data
    assert data["total_audios"] >= 1
    assert data["user_email"] == TEST_USER_EMAIL


def test_export_report_csv(client):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/reports/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    csv_text = response.text
    assert "Record Type,ID,Timestamp (UTC),Status/Risk,Resource/File,Details" in csv_text
    assert "test_sample.wav" in csv_text

