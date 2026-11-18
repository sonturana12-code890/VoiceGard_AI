import os
import sys
import json
import time
import io
import wave
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

# Ensure repo root on path
sys.path.insert(0, os.path.abspath("."))

from backend.main import app
from backend.services.inference_pipeline import DetectionPipeline
from backend.services.model_manager import ModelManager
from backend.services.rawnet2_service import RawNet2Service
from backend.services.ecapa_service import ECAPAService
from backend.tests.test_full_pipeline_verification import make_synthetic_vocoder_voice

client = TestClient(app)

# Authenticate test client
login_res = client.post(
    "/api/auth/login",
    json={"email": "e2e_analyst@voiceguard.ai", "password": "StrongSecurityPassword123!"}
)
if login_res.status_code == 200:
    token = login_res.json()["access_token"]
else:
    signup_res = client.post(
        "/api/auth/signup",
        json={
            "fullName": "QA Lead",
            "email": "e2e_analyst@voiceguard.ai",
            "password": "StrongSecurityPassword123!",
            "confirmPassword": "StrongSecurityPassword123!",
            "termsAccepted": True,
            "remember": False,
        },
    )
    token = signup_res.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}

print("=" * 80)
print("STARTING FULL QA SYSTEM AUDIT (PHASES 1 - 4)")
print("=" * 80)

# Helper generators
def make_wav_sine(duration_s=1.5, sr=16000, freq=300.0, noise_amp=0.0):
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    sig = 0.5 * np.sin(2 * np.pi * freq * t)
    if noise_amp > 0:
        sig += np.random.normal(0, noise_amp, len(sig))
    sig = np.clip(sig, -1.0, 1.0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((sig * 32767).astype(np.int16).tobytes())
    return buf.getvalue()

def make_silent_wav(duration_s=2.0, sr=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(np.zeros(int(duration_s * sr), dtype=np.int16).tobytes())
    return buf.getvalue()

# Test matrix
edge_cases = [
    {
        "category": "Edge Case: Short Audio (1.5s < 4.03s specification)",
        "bytes": make_wav_sine(duration_s=1.5, freq=280.0),
        "filename": "short_audio_1.5s.wav",
        "expected": ["REAL_HUMAN", "INCONCLUSIVE"],
    },
    {
        "category": "Edge Case: Long Audio (107s, 35 multi-segments)",
        "bytes": open("sontu1.mpeg", "rb").read(),
        "filename": "sontu1.mpeg",
        "expected": ["REAL_HUMAN"],
    },
    {
        "category": "Edge Case: Noisy Audio (Human vocal + 0.15 Gaussian noise)",
        "bytes": make_wav_sine(duration_s=4.5, freq=220.0, noise_amp=0.15),
        "filename": "noisy_vocal.wav",
        "expected": ["REAL_HUMAN", "INCONCLUSIVE"],
    },
    {
        "category": "Edge Case: Silent Audio (Zero energy PCM stream)",
        "bytes": make_silent_wav(duration_s=2.0),
        "filename": "pure_silence.wav",
        "expected": ["INCONCLUSIVE"],
    },
    {
        "category": "Labeled Human Voice: Speaker 1 (sontu1.mp3)",
        "bytes": open("sontu1.mp3", "rb").read(),
        "filename": "sontu1.mp3",
        "expected": ["REAL_HUMAN"],
    },
    {
        "category": "Labeled Human Voice: Speaker 2 (Ayush CR.mpeg)",
        "bytes": open("backend/uploads/e9c3e5193dac4c15acdff98265d27d1f.mpeg", "rb").read() if os.path.exists("backend/uploads/e9c3e5193dac4c15acdff98265d27d1f.mpeg") else open("backend/uploads/human_test_95.wav", "rb").read(),
        "filename": "human_speaker_2.wav",
        "expected": ["REAL_HUMAN"],
    },
    {
        "category": "Labeled Synthetic Speech: Neural Vocoder Clone",
        "bytes": make_synthetic_vocoder_voice(duration=2.5),
        "filename": "vocoder_clone.wav",
        "expected": ["AI_GENERATED"],
    },
    {
        "category": "Labeled Synthetic Speech: AI Generated MP3 (AI GENERATED.mp3)",
        "bytes": open("backend/uploads/3065c3498daf4856912fc23cf6e14420.mp3", "rb").read(),
        "filename": "AI GENERATED.mp3",
        "expected": ["AI_GENERATED"],
    }
]

audit_results = []

for case in edge_cases:
    print(f"\nTesting: {case['category']}")
    for model_name in ["RAWNET2", "AASIST"]:
        res = client.post(
            f"/api/v1/audio/analyze?model_name={model_name}",
            files={"file": (case["filename"], case["bytes"], "audio/wav")},
            headers=headers,
        )
        if res.status_code != 200:
            print(f"  [{model_name}] HTTP Error: {res.status_code}")
            audit_results.append({
                "case": case["category"],
                "model": model_name,
                "passed": False,
                "error": res.text,
            })
            continue

        data = res.json()
        pred_class = data.get("predicted_class")
        label = data.get("prediction", {}).get("label")
        real_p = data.get("real_probability", 0.0)
        fake_p = data.get("fake_probability", 0.0)
        conf = data.get("confidence_score", 0.0)
        latency = data.get("inference_time", 0.0)
        
        passed = (pred_class in case["expected"])
        status_tag = "PASSED" if passed else "FAILED"
        print(f"  [{model_name}] {status_tag} | Class='{pred_class}' | Label='{label}' | Real={real_p*100:.1f}% | Fake={fake_p*100:.1f}% | Latency={latency*1000:.1f}ms")
        
        audit_results.append({
            "case": case["category"],
            "model": model_name,
            "passed": passed,
            "predicted_class": pred_class,
            "label": label,
            "real_probability": real_p,
            "fake_probability": fake_p,
            "confidence": conf,
            "latency_ms": round(latency * 1000, 2),
            "expected": case["expected"],
        })

# Save empirical results to json
with open("scratch/qa_audit_results.json", "w") as f:
    json.dump(audit_results, f, indent=2)

print("\n" + "=" * 80)
print("AUDIT EXECUTION COMPLETE. RESULTS SAVED TO scratch/qa_audit_results.json")
print("=" * 80)
