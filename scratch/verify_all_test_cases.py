import os
import sys
import numpy as np
import io
import wave

# Ensure repo root on path
sys.path.insert(0, os.path.abspath("."))

from backend.services.inference_pipeline import DetectionPipeline
from backend.tests.test_full_pipeline_verification import make_synthetic_vocoder_voice
from fastapi.testclient import TestClient
from backend.main import app

def make_silent_wav(duration_s=2.0, sr=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(np.zeros(int(duration_s * sr), dtype=np.int16).tobytes())
    return buf.getvalue()

def run_tests():
    print("=" * 70)
    print("VOICEGUARD AI - E2E PIPELINE & 4-WAY VERIFICATION (API + INFERENCE)")
    print("=" * 70)

    client = TestClient(app)

    # 1. Authenticate test client to test API endpoint
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
                "fullName": "Verification Analyst",
                "email": "e2e_analyst@voiceguard.ai",
                "password": "StrongSecurityPassword123!",
                "confirmPassword": "StrongSecurityPassword123!",
                "termsAccepted": True,
                "remember": False,
            },
        )
        token = signup_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    test_cases = [
        {
            "id": "TEST 1",
            "name": "Original Human Voice (sontu1.mpeg)",
            "data": open("sontu1.mpeg", "rb").read(),
            "filename": "sontu1.mpeg",
            "content_type": "audio/mpeg",
            "expected_class": "REAL_HUMAN",
            "models": ["RAWNET2", "AASIST"],
        },
        {
            "id": "TEST 2",
            "name": "AI-Generated Cloned Voice (Synthetic Vocoder Audio)",
            "data": make_synthetic_vocoder_voice(duration=2.5, sr=16000),
            "filename": "ai_cloned_voice.wav",
            "content_type": "audio/wav",
            "expected_class": "AI_GENERATED",
            "models": ["RAWNET2"],
        },
        {
            "id": "TEST 3",
            "name": "Different Human Voice (human_test_95.wav)",
            "data": open("backend/uploads/human_test_95.wav", "rb").read(),
            "filename": "human_test_95.wav",
            "content_type": "audio/wav",
            "expected_class": "REAL_HUMAN",
            "models": ["RAWNET2", "AASIST"],
        },
        {
            "id": "TEST 4",
            "name": "Unclear or Low-Confidence Audio (Silence / Low-Energy)",
            "data": make_silent_wav(2.0, 16000),
            "filename": "silent_sample.wav",
            "content_type": "audio/wav",
            "expected_class": "INCONCLUSIVE",
            "models": ["RAWNET2", "AASIST"],
        }
    ]

    all_passed = True
    summary_results = []

    for tc in test_cases:
        print(f"\n>>> Running {tc['id']}: {tc['name']}")
        for model_name in tc["models"]:
            res = client.post(
                f"/api/v1/audio/analyze?model_name={model_name}",
                files={"file": (tc["filename"], tc["data"], tc["content_type"])},
                headers=headers,
            )
            if res.status_code != 200:
                print(f"[{model_name}] API call failed: {res.status_code} {res.text}")
                all_passed = False
                continue

            data = res.json()
            pred_class = data.get("predicted_class")
            label = data.get("prediction", {}).get("label")
            real_prob = data.get("real_probability", 0.0)
            fake_prob = data.get("fake_probability", 0.0)
            confidence = data.get("confidence_score", data.get("confidence", 0.0))
            reliability = data.get("prediction_reliability", "N/A")

            passed = (pred_class == tc["expected_class"])
            status_str = "PASSED" if passed else "FAILED"
            if not passed:
                all_passed = False

            print(
                f"[{model_name}] {status_str}: Predicted='{pred_class}' (Expected='{tc['expected_class']}') | "
                f"Label='{label}' | Real={real_prob*100:.1f}% | Fake={fake_prob*100:.1f}% | "
                f"Confidence={confidence*100:.1f}% | Reliability={reliability}"
            )

            summary_results.append({
                "test": tc["id"],
                "model": model_name,
                "passed": passed,
                "predicted": pred_class,
                "expected": tc["expected_class"],
                "real_pct": f"{real_prob*100:.1f}%",
                "fake_pct": f"{fake_prob*100:.1f}%",
                "label": label,
            })

    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY:")
    for r in summary_results:
        print(f"  {r['test']} [{r['model']}]: {r['predicted']} (Real: {r['real_pct']}, Fake: {r['fake_pct']}) -> {'OK' if r['passed'] else 'FAIL'}")
    print("=" * 70)
    if all_passed:
        print("ALL TEST CASES PASSED SUCCESSFULLY!")
    else:
        print("SOME TEST CASES FAILED - CHECK OUTPUT ABOVE")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
