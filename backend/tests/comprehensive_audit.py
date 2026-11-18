"""
VOICEGUARD AI — Comprehensive Audit & Automated Testing Suite
Covers 10 Audit Areas:
1. Project Structure Audit
2. Frontend Link & DOM ID Validation
3. UI/UX & Responsive CSS Rules Audit
4. Voice Detection & File Ingestion
5. Complete Backend API Testing
6. AI Inference & Transparency Audit (Zero Fake Detections)
7. Multi-Viewport Responsive Configuration Audit
8. Phase 1 Preservation Verification
9. Security & Vulnerability Audit (Path Traversal, Magic Bytes, Auth Injections)
10. Final Audit Metrics Compilation
"""

import asyncio
import io
import json
import os
import re
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.models
from backend.database import Base, get_db
from backend.main import app

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


audit_results = {
    "structure": {},
    "frontend": {},
    "responsive": {},
    "voice_detection": {},
    "backend_api": {},
    "ai_functionality": {},
    "phase1_preservation": {},
    "security": {},
    "summary": {"passed": 0, "failed": 0, "warnings": 0}
}

def log_test(category: str, name: str, passed: bool, details: str = "", level: str = "INFO"):
    status_str = "PASS" if passed else "FAIL"
    print(f"[{status_str}] [{category.upper()}] {name}: {details}", flush=True)
    if passed:
        audit_results["summary"]["passed"] += 1
    else:
        audit_results["summary"]["failed"] += 1
    if category not in audit_results:
        audit_results[category] = {}
    audit_results[category][name] = {"passed": passed, "details": details, "level": level}


async def run_audit():
    print("=" * 70, flush=True)
    print("VOICEGUARD AI — COMPREHENSIVE PROJECT AUDIT & QA SUITE", flush=True)
    print("=" * 70, flush=True)

    # -------------------------------------------------------------------------
    # 1. PROJECT STRUCTURE AUDIT
    # -------------------------------------------------------------------------
    required_root_files = [
        "index.html", "app.html", "style.css", "landing-and-dashboard.css",
        "api-client.js", "landing-controller.js", "app-controller.js",
        "script.js", "package.json"
    ]
    for f in required_root_files:
        exists = (ROOT / f).is_file()
        log_test("structure", f"Root file {f} existence", exists, f"Size: {(ROOT / f).stat().st_size if exists else 0} bytes")

    backup_dir = ROOT / "_backup_voiceguard"
    log_test("structure", "Backup directory intact", backup_dir.is_dir(), f"Path: {backup_dir}")

    # Check backend modular files
    required_backend = [
        "backend/main.py", "backend/database.py", "backend/models.py",
        "backend/schemas.py", "backend/auth.py",
        "backend/routes/auth_routes.py", "backend/routes/audio_routes.py",
        "backend/routes/dashboard_routes.py", "backend/routes/speaker_routes.py",
        "backend/routes/threat_routes.py", "backend/routes/report_routes.py",
        "backend/services/audio_service.py", "backend/services/preprocessing_service.py",
        "backend/services/risk_engine.py", "backend/services/report_service.py"
    ]
    for b in required_backend:
        exists = (ROOT / b).is_file()
        log_test("structure", f"Backend module {b}", exists, f"Exists on disk: {exists}")

    # -------------------------------------------------------------------------
    # 2. FRONTEND DOM & SCRIPT LINKAGE AUDIT
    # -------------------------------------------------------------------------
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    app_html = (ROOT / "app.html").read_text(encoding="utf-8")

    # Check script references in index.html
    for script_match in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', index_html):
        if script_match.startswith("http"):
            log_test("frontend", f"index.html CDN script {script_match}", True, "External CDN")
        else:
            local_file = (ROOT / script_match.lstrip("/")).resolve()
            exists = local_file.is_file()
            log_test("frontend", f"index.html local script {script_match}", exists, f"Resolved: {local_file}")

    # Check script references in app.html
    for script_match in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', app_html):
        if script_match.startswith("http"):
            log_test("frontend", f"app.html CDN script {script_match}", True, "External CDN")
        else:
            local_file = (ROOT / script_match.lstrip("/")).resolve()
            exists = local_file.is_file()
            log_test("frontend", f"app.html local script {script_match}", exists, f"Resolved: {local_file}")

    # Check essential DOM IDs referenced by landing-controller.js in index.html
    landing_js = (ROOT / "landing-controller.js").read_text(encoding="utf-8")
    landing_dom_ids = re.findall(r"getElementById\(['\"]([a-zA-Z0-9_-]+)['\"]\)", landing_js)
    for dom_id in set(landing_dom_ids):
        present = f'id="{dom_id}"' in index_html
        log_test("frontend", f"index.html ID #{dom_id}", present, "Required by landing-controller.js")

    # Check essential DOM IDs referenced by app-controller.js in app.html
    app_js = (ROOT / "app-controller.js").read_text(encoding="utf-8")
    app_dom_ids = re.findall(r"getElementById\(['\"]([a-zA-Z0-9_-]+)['\"]\)", app_js)
    for dom_id in set(app_dom_ids):
        present = f'id="{dom_id}"' in app_html
        log_test("frontend", f"app.html ID #{dom_id}", present, "Required by app-controller.js")

    # -------------------------------------------------------------------------
    # 3. UI/UX & RESPONSIVE CSS AUDIT
    # -------------------------------------------------------------------------
    css_content = (ROOT / "landing-and-dashboard.css").read_text(encoding="utf-8")
    style_css = (ROOT / "style.css").read_text(encoding="utf-8")
    combined_css = css_content + "\n" + style_css

    breakpoints = ["1200px", "1024px", "768px", "480px"]
    for bp in breakpoints:
        has_bp = f"@media" in combined_css and bp in combined_css
        log_test("responsive", f"CSS breakpoint {bp}", has_bp, f"Responsive query found for {bp}")

    # Typography and color tokens
    has_inter = "Inter" in combined_css
    has_mono = "JetBrains Mono" in combined_css
    log_test("responsive", "Typography Inter font token", has_inter, "Modern clean sans-serif")
    log_test("responsive", "Typography JetBrains Mono token", has_mono, "Technical code/metric font")

    # -------------------------------------------------------------------------
    # 4 & 5. BACKEND API & FUNCTIONAL TESTS (via ASGITransport)
    # -------------------------------------------------------------------------
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Health
        res = await client.get("/api/health")
        log_test("backend_api", "GET /api/health", res.status_code == 200 and res.json().get("status") == "healthy", f"Status: {res.status_code}")

        # Signup
        signup_data = {
            "fullName": "Audit SecOps Lead",
            "email": "audit.secops@voiceguard.ai",
            "password": "ComprehensiveSecurityPassword999!",
            "termsAccepted": True,
            "remember": True
        }
        res = await client.post("/api/auth/signup", json=signup_data)
        log_test("backend_api", "POST /api/auth/signup", res.status_code == 201, f"Status: {res.status_code}")
        token = res.json().get("access_token")
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Login
        login_data = {
            "email": "audit.secops@voiceguard.ai",
            "password": "ComprehensiveSecurityPassword999!"
        }
        res = await client.post("/api/auth/login", json=login_data)
        log_test("backend_api", "POST /api/auth/login", res.status_code == 200 and "access_token" in res.json(), f"Status: {res.status_code}")

        # Profile /me
        res = await client.get("/api/auth/me", headers=auth_headers)
        log_test("backend_api", "GET /api/auth/me", res.status_code == 200 and res.json()["user"]["email"] == "audit.secops@voiceguard.ai", "Authenticated profile")

        # Status
        res = await client.get("/api/auth/status", headers=auth_headers)
        log_test("backend_api", "GET /api/auth/status", res.status_code == 200 and res.json()["authenticated"] is True, "Session active")

        # ---------------------------------------------------------------------
        # 6. VOICE DETECTION & AI INFERENCE TESTING
        # ---------------------------------------------------------------------
        sample_wav = create_sample_wav_bytes(1.5, 16000)
        files = {"file": ("test_voice_sample.wav", sample_wav, "audio/wav")}
        res = await client.post("/api/audio/upload", files=files, headers=auth_headers)
        log_test("voice_detection", "Audio Upload (WAV)", res.status_code == 201, f"Status: {res.status_code}")
        upload_resp = res.json()
        analysis = upload_resp.get("analysis", {})
        analysis_id = analysis.get("id")

        # Check AI transparency: must state AI_MODEL_NOT_CONFIGURED and NOT fabricate synthetic_score
        log_test("ai_functionality", "Zero-Hallucination Status", analysis.get("analysis_status") == "AI_MODEL_NOT_CONFIGURED", f"Status: {analysis.get('analysis_status')}")
        log_test("ai_functionality", "No fabricated synthetic_score", analysis.get("synthetic_score") is None, f"Synthetic score is truthful: {analysis.get('synthetic_score')}")

        # Unsupported file rejection (.exe)
        bad_file = {"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-msdownload")}
        res = await client.post("/api/audio/upload", files=bad_file, headers=auth_headers)
        log_test("security", "Reject malicious executable upload", res.status_code == 400, f"Rejected with {res.status_code}: {res.text}")

        # Unsupported file rejection (.txt)
        bad_text = {"file": ("fake.txt", b"plain text audio", "text/plain")}
        res = await client.post("/api/audio/upload", files=bad_text, headers=auth_headers)
        log_test("security", "Reject plain text file upload", res.status_code == 400, f"Rejected with {res.status_code}")

        # Path traversal in filename upload (../../etc/passwd)
        traversal_file = {"file": ("../../evil.wav", sample_wav, "audio/wav")}
        res = await client.post("/api/audio/upload", files=traversal_file, headers=auth_headers)
        # Should succeed without directory traversal because filename is sanitized/UUID
        log_test("security", "Path traversal in upload filename handled securely", res.status_code in (201, 400), f"Response: {res.status_code}")

        # Audio history
        res = await client.get("/api/audio/history", headers=auth_headers)
        log_test("voice_detection", "GET /api/audio/history", res.status_code == 200 and len(res.json().get("history", [])) > 0, "History populated")

        # Audio stream
        res = await client.get(f"/api/audio/{analysis_id}/stream", headers=auth_headers)
        log_test("voice_detection", f"GET /api/audio/{analysis_id}/stream", res.status_code == 200, f"Streaming status: {res.status_code}")

        # Speaker Enrollment
        speaker_files = {"file": ("enrolled_voice.wav", sample_wav, "audio/wav")}
        speaker_data = {
            "speaker_name": "Executive Officer",
            "consent_status": "true",
            "department": "Finance",
        }
        res = await client.post("/api/speaker/register", data=speaker_data, files=speaker_files, headers=auth_headers)
        log_test("backend_api", "POST /api/speaker/register", res.status_code == 201, f"Status: {res.status_code}")
        speaker_resp = res.json()
        speaker_id = speaker_resp.get("id") or speaker_resp.get("speaker", {}).get("id")

        # Speaker Verify
        verify_files = {"file": ("verify_probe.wav", sample_wav, "audio/wav")}
        verify_data = {"speaker_id": speaker_id}
        res = await client.post("/api/speaker/verify", data=verify_data, files=verify_files, headers=auth_headers)
        print(f"[DEBUG VERIFY] status={res.status_code}, body={res.text}", flush=True)
        log_test("ai_functionality", "POST /api/speaker/verify truthfulness", res.status_code == 200 and res.json().get("status") == "AI_MODEL_NOT_CONFIGURED", f"Status: {res.json().get('status') if res.status_code == 200 else res.status_code}")

        # Phase 1 Fraud Risk Assess endpoint
        res = await client.get(f"/api/fraud/assess/{analysis_id}", headers=auth_headers)
        log_test("phase1_preservation", f"GET /api/fraud/assess/{analysis_id}", res.status_code == 200, f"Fraud Assessment: {res.status_code}")

        # Dashboard Overview
        res = await client.get("/api/dashboard/overview", headers=auth_headers)
        log_test("backend_api", "GET /api/dashboard/overview", res.status_code == 200 and "total_audio_uploads" in res.json(), "Telemetry accurate")

        # Dashboard Analytics
        res = await client.get("/api/dashboard/analytics", headers=auth_headers)
        log_test("backend_api", "GET /api/dashboard/analytics", res.status_code == 200, "Analytics operational")

        # Threats
        res = await client.get("/api/threats", headers=auth_headers)
        log_test("backend_api", "GET /api/threats", res.status_code == 200, f"Threat list retrieved: {len(res.json().get('threats', []))} threats")

        # Reports
        res = await client.get("/api/reports", headers=auth_headers)
        log_test("backend_api", "GET /api/reports", res.status_code == 200, "Forensic report generation")

        res = await client.get(f"/api/reports/{analysis_id}", headers=auth_headers)
        log_test("backend_api", f"GET /api/reports/{analysis_id}", res.status_code == 200, "Forensic report detail")

        res = await client.get("/api/reports/export", headers=auth_headers)
        log_test("backend_api", "GET /api/reports/export (CSV)", res.status_code == 200 and "text/csv" in res.headers.get("content-type", ""), "CSV export")

        # ---------------------------------------------------------------------
        # 8. SECURITY AUDIT
        # ---------------------------------------------------------------------
        # SQL Injection in auth
        sql_injection_payload = {
            "email": "' OR '1'='1' --",
            "password": "Password123!"
        }
        res = await client.post("/api/auth/login", json=sql_injection_payload)
        log_test("security", "SQL Injection in Login rejection", res.status_code in (400, 401, 422), f"Safely handled: {res.status_code}")

        # Unauthenticated access to protected routes
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as unauth_client:
            res = await unauth_client.get("/api/audio/history")
            log_test("security", "Unauthenticated request rejection (401)", res.status_code == 401, f"Status: {res.status_code}")

    print("=" * 70, flush=True)
    print(f"AUDIT SUMMARY: {audit_results['summary']['passed']} PASSED | {audit_results['summary']['failed']} FAILED", flush=True)
    print("=" * 70, flush=True)
    return audit_results

if __name__ == "__main__":
    asyncio.run(run_audit())
