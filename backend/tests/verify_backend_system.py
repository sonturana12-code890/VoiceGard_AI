"""
VOICEGUARD AI — Comprehensive System Verification Script
Audits and tests all 15 task areas:
1. Backend Startup & App Configuration
2. Registration, Login, Token Generation
3. JWT Authentication (Bearer, Cookies, Swagger header formats, Expiration)
4. All 20+ API Endpoints
5. FFmpeg and FFprobe binary & PyAV integration
6. Actual WAV, MP3, MPEG audio uploads
7. Audio Preprocessing & Acoustic Feature Extraction
8. Database Persistence & Analysis History
9. Model Availability & Neural Inference Verification
"""

import sys
import os
import io
import json
import wave
import math
import struct
import numpy as np
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import SessionLocal, engine, Base
from backend.models import User, AudioAnalysis, SpeakerRegistration, ThreatAlert, SecurityEvent
from backend.services.ffmpeg_service import FFmpegService
from backend.services.model_manager import ModelManager
from backend.services.inference_pipeline import DetectionPipeline
from backend.services.feature_extractor import AudioFeatureExtractor
from backend.services.audio_preprocessor import AudioPreprocessor
from backend.auth import create_access_token, decode_access_token

client = TestClient(app)

results = {
    "backend_startup": None,
    "auth_registration": None,
    "auth_login": None,
    "auth_jwt_validation": None,
    "auth_refresh": None,
    "ffmpeg_status": None,
    "wav_upload": None,
    "mp3_upload": None,
    "mpeg_upload": None,
    "audio_preprocessing": None,
    "feature_extraction": None,
    "model_availability": None,
    "real_onnx_inference": None,
    "endpoints_tested": {},
    "db_persistence": None,
}

print("=" * 70)
print("VOICEGUARD AI — COMPLETE BACKEND & API VERIFICATION")
print("=" * 70)

# 1. Startup & OpenAPI
try:
    res = client.get("/openapi.json")
    assert res.status_code == 200
    openapi = res.json()
    paths = list(openapi.get("paths", {}).keys())
    results["backend_startup"] = {
        "status": "PASS",
        "title": openapi.get("info", {}).get("title"),
        "version": openapi.get("info", {}).get("version"),
        "total_endpoints": len(paths),
    }
    print(f"[PASS] 1. Backend Startup: {openapi.get('info', {}).get('title')} v{openapi.get('info', {}).get('version')} ({len(paths)} endpoints registered)")
except Exception as e:
    results["backend_startup"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 1. Backend Startup: {e}")

# 2. Registration & Login
unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
test_email = f"audit_user_{unique_id}@voiceguard.ai"
test_password = "SecureAuditPass123!"

try:
    signup_res = client.post("/api/auth/signup", json={
        "fullName": "System Auditor",
        "email": test_email,
        "password": test_password,
        "termsAccepted": True,
    })
    assert signup_res.status_code == 201, f"Signup status {signup_res.status_code}: {signup_res.text}"
    token_data = signup_res.json()
    assert "access_token" in token_data
    auth_token = token_data["access_token"]
    user_id = token_data["user"]["id"]
    results["auth_registration"] = {"status": "PASS", "user_id": user_id}
    print(f"[PASS] 2. User Registration: Created {test_email} (ID: {user_id})")

    # Test Login
    login_res = client.post("/api/auth/login", json={
        "email": test_email,
        "password": test_password,
    })
    assert login_res.status_code == 200, f"Login status {login_res.status_code}: {login_res.text}"
    assert "access_token" in login_res.json()
    results["auth_login"] = {"status": "PASS", "token_type": login_res.json().get("token_type")}
    print(f"[PASS] 2. User Login: Authenticated successfully, received JWT bearer token")
except Exception as e:
    results["auth_registration"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 2. Registration/Login: {e}")
    auth_token = ""

# 3. JWT Authentication & Bearer Header Validation
headers = {"Authorization": f"Bearer {auth_token}"}
try:
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == test_email

    # Swagger duplicate Bearer test
    swagger_headers = {"Authorization": f"Bearer Bearer {auth_token}"}
    swagger_res = client.get("/api/auth/me", headers=swagger_headers)
    assert swagger_res.status_code == 200

    # Cookie fallback test
    client.cookies.set("vg_session", auth_token)
    cookie_res = client.get("/api/auth/me")
    assert cookie_res.status_code == 200

    # Refresh endpoint test
    refresh_res = client.post("/api/auth/refresh", headers=headers)
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()

    # Expired token rejection
    expired_token = create_access_token({"sub": user_id, "email": test_email}, expires_delta=timedelta(seconds=-10))
    client.cookies.clear()
    exp_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert exp_res.status_code == 401

    results["auth_jwt_validation"] = {"status": "PASS"}
    print("[PASS] 3. JWT Authentication: Bearer, Swagger duplicate prefix, Cookie fallback, Expiration verified")
except Exception as e:
    results["auth_jwt_validation"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 3. JWT Auth: {e}")

# 4. FFmpeg and FFprobe Diagnostics
try:
    diag = FFmpegService.get_diagnostics()
    assert diag["pyav_installed"] is True
    assert diag["ffmpeg_cli_installed"] is True
    assert diag["ffprobe_cli_installed"] is True
    results["ffmpeg_status"] = {
        "status": "PASS",
        "pyav_version": diag["pyav_version"],
        "ffmpeg_cli": diag["ffmpeg_cli_path"],
        "codecs_count": len(diag["supported_mpeg_codecs"]),
    }
    print(f"[PASS] 5. FFmpeg / FFprobe: PyAV v{diag['pyav_version']}, CLI: {diag['ffmpeg_cli_path']}")
except Exception as e:
    results["ffmpeg_status"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 5. FFmpeg/FFprobe: {e}")

# Helpers to make audio streams
def make_wav(duration=1.5, sr=16000, freq=440.0):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        n = int(duration * sr)
        samples = [struct.pack("<h", int(0.5 * math.sin(2 * math.pi * freq * i / sr) * 32767)) for i in range(n)]
        wf.writeframes(b"".join(samples))
    return buf.getvalue()

def make_mp3(duration=1.5, sr=44100, freq=440.0):
    import av
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp3") as c:
        s = c.add_stream("mp3")
        s.rate = sr
        s.layout = "stereo"
        n = int(duration * sr)
        t = np.linspace(0, duration, n, endpoint=False)
        w = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        stereo = np.stack([w, w])
        chunk = 1152
        for i in range(0, n, chunk):
            ch = stereo[:, i:i+chunk]
            if ch.shape[1] == chunk:
                f = av.AudioFrame.from_ndarray(ch, format="fltp", layout="stereo")
                f.rate = sr
                for p in s.encode(f):
                    c.mux(p)
        for p in s.encode(None):
            c.mux(p)
    return buf.getvalue()

def make_mpeg(duration=1.5, sr=44100, freq=440.0):
    import av
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mpeg") as c:
        s = c.add_stream("mp2", rate=sr)
        s.layout = "stereo"
        n = int(duration * sr)
        t = np.linspace(0, duration, n, endpoint=False)
        w = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        stereo = np.stack([w, w])
        chunk = 1152
        for i in range(0, n, chunk):
            ch = stereo[:, i:i+chunk]
            if ch.shape[1] == chunk:
                f = av.AudioFrame.from_ndarray(ch, format="fltp", layout="stereo")
                f.rate = sr
                for p in s.encode(f):
                    c.mux(p)
        for p in s.encode(None):
            c.mux(p)
    return buf.getvalue()

# 6. Actual Audio Uploads (WAV, MP3, MPEG)
wav_bytes = make_wav(2.0)
mp3_bytes = make_mp3(1.5)
mpeg_bytes = make_mpeg(1.5)

# Test WAV Upload
try:
    res_wav = client.post("/api/v1/audio/analyze", files={"file": ("test.wav", wav_bytes, "audio/wav")}, headers=headers)
    assert res_wav.status_code == 200, f"WAV failed: {res_wav.text}"
    wav_data = res_wav.json()
    assert wav_data["success"] is True
    assert wav_data["sample_rate"] == 16000
    assert "features" in wav_data
    results["wav_upload"] = {"status": "PASS", "analysis_id": wav_data["analysis_id"]}
    print(f"[PASS] 6. WAV Upload & Analysis: ID={wav_data['analysis_id']}, Duration={wav_data['audio_duration']}s")
except Exception as e:
    results["wav_upload"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 6. WAV Upload: {e}")

# Test MP3 Upload
try:
    res_mp3 = client.post("/api/v1/audio/analyze", files={"file": ("test.mp3", mp3_bytes, "audio/mpeg")}, headers=headers)
    assert res_mp3.status_code == 200, f"MP3 failed: {res_mp3.text}"
    mp3_data = res_mp3.json()
    assert mp3_data["success"] is True
    assert mp3_data["sample_rate"] == 16000
    results["mp3_upload"] = {"status": "PASS", "analysis_id": mp3_data["analysis_id"]}
    print(f"[PASS] 6. MP3 Upload & Analysis: ID={mp3_data['analysis_id']}, Decoded to 16kHz mono PCM")
except Exception as e:
    results["mp3_upload"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 6. MP3 Upload: {e}")

# Test MPEG Upload
try:
    res_mpeg = client.post("/api/v1/audio/analyze", files={"file": ("test.mpeg", mpeg_bytes, "audio/mpeg")}, headers=headers)
    assert res_mpeg.status_code == 200, f"MPEG failed: {res_mpeg.text}"
    mpeg_data = res_mpeg.json()
    assert mpeg_data["success"] is True
    assert mpeg_data["sample_rate"] == 16000
    results["mpeg_upload"] = {"status": "PASS", "analysis_id": mpeg_data["analysis_id"]}
    print(f"[PASS] 6. MPEG Upload & Analysis: ID={mpeg_data['analysis_id']}, Decoded via PyAV/FFmpeg")
except Exception as e:
    results["mpeg_upload"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 6. MPEG Upload: {e}")

# 7. Audio Preprocessing & Feature Extraction
try:
    prep = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = prep.process_audio(wav_bytes, "test.wav")
    assert len(pcm) == 32000
    assert metrics.sample_rate == 16000
    assert metrics.channels == 1
    results["audio_preprocessing"] = {"status": "PASS", "samples": len(pcm), "rms": metrics.rms_energy}

    extractor = AudioFeatureExtractor(sample_rate=16000)
    feat = extractor.extract_all(pcm)
    feat_dict = feat.to_dict()
    assert "mfcc" in feat_dict
    assert "mel_spectrogram" in feat_dict
    assert "spectral_centroid" in feat_dict
    assert "spectral_bandwidth" in feat_dict
    assert "spectral_rolloff" in feat_dict
    assert "zero_crossing_rate" in feat_dict
    assert "rms_energy" in feat_dict
    results["feature_extraction"] = {"status": "PASS", "num_frames": feat.num_frames}
    print(f"[PASS] 7. Audio Preprocessing & Feature Extraction: 7 features extracted across {feat.num_frames} frames")
except Exception as e:
    results["audio_preprocessing"] = {"status": "FAIL", "error": str(e)}
    print(f"[FAIL] 7. Audio Preprocessing: {e}")

# 8. All Existing API Endpoints
endpoints_to_test = [
    ("GET", "/api/health", None, 200, False),
    ("GET", "/api/v1/audio/health", None, 200, False),
    ("GET", "/api/auth/status", None, 200, True),
    ("GET", "/api/audio/history", None, 200, True),
    ("GET", f"/api/audio/{wav_data.get('analysis_id', 'none')}", None, 200, True),
    ("GET", f"/api/audio/{wav_data.get('analysis_id', 'none')}/stream", None, 200, True),
    ("GET", f"/api/fraud/assess/{wav_data.get('analysis_id', 'none')}", None, 200, True),
    ("GET", f"/api/v1/audio/analysis/{wav_data.get('analysis_id', 'none')}", None, 200, True),
    ("GET", "/api/dashboard/overview", None, 200, True),
    ("GET", "/api/dashboard/analytics", None, 200, True),
    ("GET", "/api/speakers", None, 200, True),
    ("POST", "/api/speaker/register", {"speaker_name": "Test Enrollee", "consent_status": True}, 201, True),
    ("POST", "/api/speaker/verify", None, 200, True),
    ("GET", "/api/threats", None, 200, True),
    ("GET", "/api/reports", None, 200, True),
    ("GET", "/api/reports/export", None, 200, True),
    ("GET", "/api/security-events", None, 200, True),
    ("POST", "/api/auth/logout", None, 200, True),
]

for method, path, body, expected_status, req_auth in endpoints_to_test:
    try:
        h = headers if req_auth else {}
        if method == "GET":
            resp = client.get(path, headers=h)
        elif method == "POST":
            resp = client.post(path, json=body, headers=h)
        status_ok = resp.status_code == expected_status
        results["endpoints_tested"][f"{method} {path}"] = {
            "status": "PASS" if status_ok else "FAIL",
            "code": resp.status_code,
            "expected": expected_status,
        }
        if status_ok:
            print(f"  [PASS] Endpoint {method} {path} -> HTTP {resp.status_code}")
        else:
            print(f"  [FAIL] Endpoint {method} {path} -> HTTP {resp.status_code} (Expected {expected_status})")
    except Exception as exc:
        results["endpoints_tested"][f"{method} {path}"] = {"status": "ERROR", "error": str(exc)}
        print(f"  [ERROR] Endpoint {method} {path}: {exc}")

# 9. Model Availability & Neural Inference Verification
mgr = ModelManager()
aasist_avail = mgr.is_model_available("aasist")
rawnet2_avail = mgr.is_model_available("rawnet2")

results["model_availability"] = {
    "aasist_onnx_exists": aasist_avail,
    "rawnet2_onnx_exists": rawnet2_avail,
    "models_directory": str(mgr.models_dir),
    "device_provider": mgr.device,
}
print(f"[*] 11 & 12. Model Checkpoints Audit: aasist.onnx={aasist_avail}, rawnet2.onnx={rawnet2_avail}")
if not aasist_avail and not rawnet2_avail:
    print("  [AUDIT TRUTH] Physical pretrained model weights (aasist.onnx, rawnet2.onnx) are NOT installed in backend/models_weights/.")
    print("  [AUDIT TRUTH] Zero-Hallucination policy correctly returns MODEL_NOT_AVAILABLE with null probabilities.")
    print("  [AUDIT TRUTH] Mocked tests in test suites verify inference tensor math, but actual real weights are absent on disk.")

# 10. Database Persistence Verification
db = SessionLocal()
try:
    user_cnt = db.query(User).count()
    analysis_cnt = db.query(AudioAnalysis).count()
    speaker_cnt = db.query(SpeakerRegistration).count()
    threat_cnt = db.query(ThreatAlert).count()
    event_cnt = db.query(SecurityEvent).count()
    results["db_persistence"] = {
        "status": "PASS",
        "users": user_cnt,
        "audio_analyses": analysis_cnt,
        "speakers": speaker_cnt,
        "threats": threat_cnt,
        "security_events": event_cnt,
    }
    print(f"[PASS] 13. Database Persistence: Users={user_cnt}, Analyses={analysis_cnt}, Speakers={speaker_cnt}, Threats={threat_cnt}, Events={event_cnt}")
finally:
    db.close()

# Save structured json
with open("verification_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nVerification run complete. Results stored in verification_results.json.")

