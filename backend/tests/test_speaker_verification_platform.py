"""
VOICEGUARD AI — Speaker Verification & Voiceprint Management Platform Test Suite
Tests for:
- Speaker Enrollment (Module 1)
- Biometric Voiceprint Management & Cross-User Isolation (Module 2)
- Advanced 1:1 Speaker Comparison with Dual Audio and Profile-to-Audio (Module 3)
- Verification Audit History, Search, Filters, and CSV Export (Module 4)
- Security, Authorization, and Biometric Privacy Mandates (Module 6)
- API Schemas and Contracts (Module 7)
"""

from __future__ import annotations

import io
import math
import wave
from datetime import datetime, timezone
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.auth import create_access_token, hash_password
from backend.database import get_db
from backend.main import app
from backend.models import SpeakerRegistration, SpeakerVerificationLog, User
from backend.services.biometric_security import decrypt_embedding, encrypt_embedding
from backend.services.ecapa_service import ECAPAService


def make_test_wav(
    duration_s: float = 2.0,
    sample_rate: int = 16000,
    fundamental_hz: float = 180.0,
    harmonic_weights: tuple = (1.0, 0.5, 0.25),
    phase_shift: float = 0.0,
) -> bytes:
    """Generates synthetic multi-harmonic PCM speech recording."""
    n_samples = int(duration_s * sample_rate)
    t = np.linspace(0.0, duration_s, n_samples, endpoint=False, dtype=np.float32)

    signal = np.zeros(n_samples, dtype=np.float32)
    for harmonic_idx, weight in enumerate(harmonic_weights, start=1):
        freq = fundamental_hz * harmonic_idx
        signal += weight * np.sin(2.0 * np.pi * freq * t + phase_shift * harmonic_idx)

    # Normalize to avoid clipping and simulate speech amplitude
    max_amp = float(np.max(np.abs(signal))) or 1.0
    signal = (signal / max_amp) * 0.75

    pcm_int16 = (signal * 32767.0).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_int16.tobytes())

    return buffer.getvalue()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_users():
    """Seeds two isolated users for cross-user security and tenant isolation testing."""
    db_gen = app.dependency_overrides.get(get_db, get_db)()
    db = next(db_gen)

    u1_email = f"speaker_user1_{datetime.now(timezone.utc).timestamp()}@voiceguard.ai"
    u2_email = f"speaker_user2_{datetime.now(timezone.utc).timestamp()}@voiceguard.ai"

    pw_hash = hash_password("VoiceGuard@2026!")

    user1 = User(full_name="Agent Alpha", email=u1_email, hashed_password=pw_hash, is_active=True)
    user2 = User(full_name="Agent Beta", email=u2_email, hashed_password=pw_hash, is_active=True)

    db.add(user1)
    db.add(user2)
    db.commit()
    db.refresh(user1)
    db.refresh(user2)

    token1 = create_access_token({"sub": user1.id, "email": user1.email})
    token2 = create_access_token({"sub": user2.id, "email": user2.email})

    user1_id = user1.id
    user1_email = user1.email
    user2_id = user2.id
    user2_email = user2.email

    try:
        next(db_gen)
    except (StopIteration, Exception):
        pass

    return {
        "user1": {"id": user1_id, "email": user1_email, "token": token1},
        "user2": {"id": user2_id, "email": user2_email, "token": token2},
    }


# ============================================================================
# MODULE 1: SPEAKER ENROLLMENT TESTS
# ============================================================================

def test_speaker_enrollment_success(client: TestClient, auth_users):
    """Enrolls speaker with audio, explicit consent, and extracts genuine ECAPA-TDNN embedding."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}
    audio_bytes = make_test_wav(duration_s=2.5, fundamental_hz=160.0)

    files = {"file": ("enroll_alex.wav", audio_bytes, "audio/wav")}
    data = {
        "speaker_name": "Alexander Hayes",
        "speaker_id": "SPK-HAYES-01",
        "consent": "true",
        "department": "Cyber Defense Operations",
        "clearance_level": "Tier-3",
    }

    res = client.post("/api/v1/speaker/enroll", headers=headers, data=data, files=files)
    assert res.status_code == 201, res.text
    body = res.json()

    assert body["speaker_id"] == "SPK-HAYES-01"
    assert body["speaker_name"] == "Alexander Hayes"
    assert body["voiceprint_status"] == "ACTIVE"
    assert body["embedding_dimension"] == 192
    assert body["consent_verified"] is True
    assert body["audio_duration_seconds"] > 2.0
    assert "raw_embedding" not in body  # Mandate: never expose raw embeddings


def test_speaker_enrollment_requires_consent(client: TestClient, auth_users):
    """Rejects enrollment when explicit biometric consent is missing."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}
    audio_bytes = make_test_wav(duration_s=2.0)

    files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
    data = {
        "speaker_name": "No Consent User",
        "consent": "false",
    }

    res = client.post("/api/v1/speaker/enroll", headers=headers, data=data, files=files)
    assert res.status_code == 400
    assert "consent" in res.json()["detail"].lower()


def test_speaker_enrollment_duplicate_speaker_id_rejected(client: TestClient, auth_users):
    """Prevents duplicate speaker ID registration under the same user account."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}
    audio_bytes = make_test_wav(duration_s=2.0)

    files1 = {"file": ("sample1.wav", audio_bytes, "audio/wav")}
    data1 = {"speaker_name": "First Enrollee", "speaker_id": "SPK-DUP-001", "consent": "true"}
    res1 = client.post("/api/v1/speaker/enroll", headers=headers, data=data1, files=files1)
    assert res1.status_code == 201

    files2 = {"file": ("sample2.wav", audio_bytes, "audio/wav")}
    data2 = {"speaker_name": "Second Enrollee", "speaker_id": "SPK-DUP-001", "consent": "true"}
    res2 = client.post("/api/v1/speaker/enroll", headers=headers, data=data2, files=files2)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


def test_speaker_enrollment_corrupted_audio_rejected(client: TestClient, auth_users):
    """Rejects corrupted audio file during enrollment with HTTP 400."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}
    files = {"file": ("bad.wav", b"RIFF????WAVEfmt NOT_VALID_PCM_AUDIO", "audio/wav")}
    data = {"speaker_name": "Corrupt Audio Enrollee", "consent": "true"}

    res = client.post("/api/v1/speaker/enroll", headers=headers, data=data, files=files)
    assert res.status_code == 400


# ============================================================================
# MODULE 2: VOICEPRINT MANAGEMENT & CROSS-USER ISOLATION TESTS
# ============================================================================

def test_list_speaker_profiles_and_search(client: TestClient, auth_users):
    """Verifies listing and searching enrolled profiles with pagination."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}
    wav_data = make_test_wav(duration_s=2.0, fundamental_hz=175.0)

    # Enroll profile
    files = {"file": ("aud.wav", wav_data, "audio/wav")}
    client.post(
        "/api/v1/speaker/enroll",
        headers=headers,
        data={"speaker_name": "Marcus Vance", "speaker_id": "SPK-MARCUS", "department": "Executive Sec", "consent": "true"},
        files=files,
    )

    # List profiles
    res = client.get("/api/v1/speaker/profiles", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    found = any(p["speaker_id"] == "SPK-MARCUS" for p in body["profiles"])
    assert found is True

    # Search by name
    res_search = client.get("/api/v1/speaker/profiles?search=Marcus", headers=headers)
    assert res_search.status_code == 200
    search_body = res_search.json()
    assert search_body["total"] >= 1
    assert search_body["profiles"][0]["speaker_name"] == "Marcus Vance"


def test_cross_user_voiceprint_isolation(client: TestClient, auth_users):
    """Mandate: User B cannot access, view, or delete User A's biometric voiceprint profile."""
    u1 = auth_users["user1"]
    u2 = auth_users["user2"]

    h1 = {"Authorization": f"Bearer {u1['token']}"}
    h2 = {"Authorization": f"Bearer {u2['token']}"}

    wav_data = make_test_wav(duration_s=2.0, fundamental_hz=190.0)

    # User 1 enrolls profile
    res_enroll = client.post(
        "/api/v1/speaker/enroll",
        headers=h1,
        data={"speaker_name": "Classified Speaker", "speaker_id": "SPK-SECRET-01", "consent": "true"},
        files={"file": ("classified.wav", wav_data, "audio/wav")},
    )
    assert res_enroll.status_code == 201

    # User 2 tries to GET User 1's profile -> 404
    res_get = client.get("/api/v1/speaker/profiles/SPK-SECRET-01", headers=h2)
    assert res_get.status_code == 404

    # User 2 tries to DELETE User 1's profile -> 404
    res_del = client.delete("/api/v1/speaker/profiles/SPK-SECRET-01", headers=h2)
    assert res_del.status_code == 404

    # User 1 CAN delete their own profile -> 200
    res_del_ok = client.delete("/api/v1/speaker/profiles/SPK-SECRET-01", headers=h1)
    assert res_del_ok.status_code == 200


# ============================================================================
# MODULE 3: ADVANCED 1:1 COMPARISON (DUAL AUDIO & PROFILE-TO-AUDIO)
# ============================================================================

def test_verify_against_enrolled_profile_same_speaker(client: TestClient, auth_users):
    """Authenticates probe audio against pre-enrolled biometric profile embedding."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}

    enroll_wav = make_test_wav(duration_s=2.5, fundamental_hz=165.0)
    probe_wav = make_test_wav(duration_s=2.5, fundamental_hz=165.0, phase_shift=0.4)

    # 1. Enroll speaker
    client.post(
        "/api/v1/speaker/enroll",
        headers=headers,
        data={"speaker_name": "Chief Analyst", "speaker_id": "SPK-CHIEF", "consent": "true"},
        files={"file": ("enroll.wav", enroll_wav, "audio/wav")},
    )

    # 2. Verify probe audio against enrolled profile
    files = {"comparison_audio": ("probe.wav", probe_wav, "audio/wav")}
    data = {"speaker_id": "SPK-CHIEF", "threshold": 0.25}

    res = client.post("/api/v1/speaker/verify", headers=headers, data=data, files=files)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["success"] is True
    assert body["is_same_speaker"] is True
    assert body["verification_status"] == "SAME_SPEAKER"
    assert body["cosine_similarity"] > 0.80
    assert body["speaker_id"] == "SPK-CHIEF"
    assert body["model_name"] == "ECAPA-TDNN (VoxCeleb)"


def test_verify_against_enrolled_profile_different_speaker(client: TestClient, auth_users):
    """Detects speaker mismatch when probe audio differs from enrolled profile."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}

    enroll_wav = make_test_wav(duration_s=2.5, fundamental_hz=120.0)  # Low pitch voice
    probe_wav = make_test_wav(duration_s=2.5, fundamental_hz=380.0)   # High pitch voice

    client.post(
        "/api/v1/speaker/enroll",
        headers=headers,
        data={"speaker_name": "Enrolled Low Voice", "speaker_id": "SPK-LOW-VOICE", "consent": "true"},
        files={"file": ("enroll_low.wav", enroll_wav, "audio/wav")},
    )

    files = {"comparison_audio": ("probe_high.wav", probe_wav, "audio/wav")}
    data = {"speaker_id": "SPK-LOW-VOICE", "threshold": 0.75}

    res = client.post("/api/v1/speaker/verify", headers=headers, data=data, files=files)
    assert res.status_code == 200
    body = res.json()

    assert body["is_same_speaker"] is False
    assert body["verification_status"] == "DIFFERENT_SPEAKER"


# ============================================================================
# MODULE 4: VERIFICATION HISTORY, SEARCH, FILTERS, & CSV EXPORT
# ============================================================================

def test_verification_history_lifecycle_and_csv_export(client: TestClient, auth_users):
    """Tests verification log persistence, search, verdict filtering, and CSV export."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}

    ref_wav = make_test_wav(duration_s=2.0, fundamental_hz=160.0)
    cmp_wav = make_test_wav(duration_s=2.0, fundamental_hz=160.0, phase_shift=0.3)

    # Perform a verification
    files = {
        "reference_audio": ("officer_ref.wav", ref_wav, "audio/wav"),
        "comparison_audio": ("caller_cmp.wav", cmp_wav, "audio/wav"),
    }
    v_res = client.post("/api/v1/speaker/verify?threshold=0.25", headers=headers, files=files)
    assert v_res.status_code == 200

    # Retrieve history
    hist_res = client.get("/api/v1/speaker/history", headers=headers)
    assert hist_res.status_code == 200
    hist_body = hist_res.json()

    assert hist_body["total"] >= 1
    assert hist_body["same_speaker_count"] >= 1
    recent_entry = hist_body["items"][0]
    assert recent_entry["verdict"] == "SAME_SPEAKER"
    assert recent_entry["threshold_used"] == 0.25

    # Filter history by verdict
    filter_res = client.get("/api/v1/speaker/history?verdict=SAME_SPEAKER", headers=headers)
    assert filter_res.status_code == 200
    assert all(item["verdict"] == "SAME_SPEAKER" for item in filter_res.json()["items"])

    # Export CSV
    csv_res = client.get("/api/v1/speaker/history/export", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    csv_text = csv_res.text
    assert "Verification ID,Timestamp (UTC),Speaker ID" in csv_text
    assert "SAME_SPEAKER" in csv_text

    # Delete single history record
    del_res = client.delete(f"/api/v1/speaker/history/{recent_entry['id']}", headers=headers)
    assert del_res.status_code == 200


def test_clear_all_verification_history(client: TestClient, auth_users):
    """Purges entire verification history for the authenticated user."""
    u1 = auth_users["user1"]
    headers = {"Authorization": f"Bearer {u1['token']}"}

    clear_res = client.delete("/api/v1/speaker/history", headers=headers)
    assert clear_res.status_code == 200
    assert clear_res.json()["success"] is True

    # Check that history is now empty
    hist_res = client.get("/api/v1/speaker/history", headers=headers)
    assert hist_res.status_code == 200
    assert hist_res.json()["total"] == 0
