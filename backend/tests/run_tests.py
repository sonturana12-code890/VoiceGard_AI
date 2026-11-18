import asyncio
import io
import sys
from pathlib import Path
import wave

# Ensure root is in path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import httpx
import backend.models  # Ensure all SQLAlchemy models are registered
from backend.main import app
from backend.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=test_engine)

def create_sample_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = b"\x00\x00" * int(sample_rate * duration_sec)
        wav_file.writeframes(frames)
    return buf.getvalue()

async def run_all_tests():
    print("[INIT] Starting tests...", flush=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        print("[TEST] 1. Requesting /api/health", flush=True)
        r = await client.get("/api/health")
        print(f"[TEST] 1. Response status: {r.status_code}", flush=True)
        assert r.status_code == 200, f"Health check failed: {r.text}"
        assert r.json()["status"] == "healthy"
        print("[PASS] 1. Health check passed", flush=True)

        # 2. Signup
        print("[TEST] 2. Requesting signup", flush=True)
        signup_payload = {
            "fullName": "Cyber Defense Lead",
            "email": "lead@voiceguard.ai",
            "password": "StrongSecurityPassword123!",
            "termsAccepted": True,
            "remember": False,
        }
        r = await client.post("/api/auth/signup", json=signup_payload)
        print(f"[TEST] 2. Response status: {r.status_code}", flush=True)
        assert r.status_code == 201, f"Signup failed: {r.text}"
        data = r.json()
        assert "access_token" in data
        assert data["user"]["email"] == "lead@voiceguard.ai"
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("[PASS] 2. User registration passed", flush=True)

        # 3. Duplicate email prevention
        r = await client.post("/api/auth/signup", json=signup_payload)
        assert r.status_code == 400, f"Duplicate signup didn't return 400: {r.text}"
        print("[PASS] 3. Duplicate signup prevention passed")

        # 4. Login
        login_payload = {
            "email": "lead@voiceguard.ai",
            "password": "StrongSecurityPassword123!",
        }
        r = await client.post("/api/auth/login", json=login_payload)
        assert r.status_code == 200, f"Login failed: {r.text}"
        assert "access_token" in r.json()
        print("[PASS] 4. User login passed")

        # 5. Invalid credentials
        r = await client.post("/api/auth/login", json={"email": "lead@voiceguard.ai", "password": "WrongPassword"})
        assert r.status_code == 401
        print("[PASS] 5. Invalid credentials rejection passed")

        # 6. Protected /api/auth/me
        r = await client.get("/api/auth/me", headers=headers)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == "lead@voiceguard.ai"
        print("[PASS] 6. Protected user profile passed")

        # 7. Unauthenticated request rejection
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as unauth_client:
            r = await unauth_client.get("/api/auth/me")
            assert r.status_code == 401, f"Expected 401 for unauthenticated client, got {r.status_code}"
            print("[PASS] 7. Unauthenticated request rejection passed")

        # 8. Valid Audio Upload
        wav_bytes = create_sample_wav_bytes(duration_sec=2.0)
        files = {"file": ("forensic_sample.wav", wav_bytes, "audio/wav")}
        r = await client.post("/api/audio/upload", headers=headers, files=files)
        assert r.status_code == 201, f"Audio upload failed: {r.text}"
        upload_data = r.json()
        assert upload_data["analysis"]["analysis_status"] == "AI_MODEL_NOT_CONFIGURED"
        assert upload_data["analysis"]["synthetic_score"] is None
        analysis_id = upload_data["analysis"]["id"]
        print(f"[PASS] 8. Audio upload passed (analysis_id={analysis_id})")

        # 9. Invalid audio upload
        files = {"file": ("malicious.exe", b"MZ fake exe", "application/octet-stream")}
        r = await client.post("/api/audio/upload", headers=headers, files=files)
        assert r.status_code in (400, 422)
        print("[PASS] 9. Unsupported file rejection passed")

        # 10. Audio history
        r = await client.get("/api/audio/history", headers=headers)
        assert r.status_code == 200
        history_data = r.json()
        assert history_data["total"] >= 1
        assert history_data["history"][0]["id"] == analysis_id
        print("[PASS] 10. Audio history retrieval passed")

        # 11. Audio detail
        r = await client.get(f"/api/audio/{analysis_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == analysis_id
        print("[PASS] 11. Audio detail retrieval passed")

        # 12. Speaker registration
        speaker_wav = create_sample_wav_bytes(duration_sec=1.5)
        speaker_data = {
            "speaker_name": "Executive Officer 01",
            "consent_status": "true",
            "department": "Finance Desk",
            "clearance_level": "Secret",
        }
        files = {"file": ("ref.wav", speaker_wav, "audio/wav")}
        r = await client.post("/api/speaker/register", headers=headers, data=speaker_data, files=files)
        assert r.status_code == 201, f"Speaker register failed: {r.text}"
        speaker_id = r.json()["id"]
        print(f"[PASS] 12. Speaker registration passed (speaker_id={speaker_id})")

        # 13. Speaker list
        r = await client.get("/api/speaker/list", headers=headers)
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        print("[PASS] 13. Speaker list passed")

        # 14. Speaker verification interface (Phase 1 contract)
        verify_files = {"file": ("probe.wav", speaker_wav, "audio/wav")}
        r = await client.post("/api/speaker/verify", headers=headers, data={"speaker_id": speaker_id}, files=verify_files)
        assert r.status_code == 200
        v_data = r.json()
        assert v_data["status"] == "AI_MODEL_NOT_CONFIGURED"
        assert v_data["verified"] is False
        assert v_data["confidence_score"] is None
        print("[PASS] 14. Speaker verify interface passed (no fake similarity score)")

        # 15. Dashboard Overview
        r = await client.get("/api/dashboard/overview", headers=headers)
        assert r.status_code == 200
        dash_data = r.json()
        assert dash_data["total_audio_uploads"] >= 1
        assert dash_data["registered_speakers"] >= 1
        print("[PASS] 15. Dashboard overview passed (real database telemetry)")

        # 16. Dashboard Analytics
        r = await client.get("/api/dashboard/analytics", headers=headers)
        assert r.status_code == 200
        print("[PASS] 16. Dashboard analytics passed")

        # 17. Threat Monitoring list
        r = await client.get("/api/threats", headers=headers)
        assert r.status_code == 200
        print("[PASS] 17. Threat monitoring list passed")

        # 18. Reports Generation
        r = await client.get("/api/reports", headers=headers)
        assert r.status_code == 200
        report = r.json()
        assert "report_id" in report
        assert report["total_audios"] >= 1
        print(f"[PASS] 18. Report generation passed (report_id={report['report_id']})")

        # 19. Reports CSV export
        r = await client.get("/api/reports/export", headers=headers)
        assert r.status_code == 200
        assert "forensic_sample.wav" in r.text
        print("[PASS] 19. Reports CSV export passed")

        # 20. Logout
        r = await client.post("/api/auth/logout", headers=headers)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        print("[PASS] 20. User logout passed")

    print("\nALL 20 ENDPOINT TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(run_all_tests())
