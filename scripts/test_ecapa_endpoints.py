"""
Test ECAPA-TDNN endpoints directly
"""
import io
import math
import struct
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from backend.main import app

def make_wav(freq: float = 200.0, duration_s: float = 2.0) -> bytes:
    b = io.BytesIO()
    with wave.open(b, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        n = int(16000 * duration_s)
        frames = []
        for i in range(n):
            val = int(0.5 * 32767 * math.sin(2 * math.pi * freq * i / 16000))
            frames.append(struct.pack('<h', val))
        wf.writeframes(b''.join(frames))
    return b.getvalue()

def main():
    client = TestClient(app)

    # 1. Test GET /api/v1/speaker/model-info
    r_info = client.get('/api/v1/speaker/model-info')
    print("GET /api/v1/speaker/model-info Status:", r_info.status_code)
    data_info = r_info.json()
    print("Model Info Available:", data_info.get("available"))
    print("Model Info Status:", data_info.get("status"))
    print("Model Info Dependencies:", data_info.get("info", {}).get("dependencies_available"))
    print("Model Info Python:", data_info.get("info", {}).get("python_executable"))
    assert r_info.status_code == 200
    assert data_info.get("status") == "online"
    assert data_info.get("available") is True

    # 2. Test POST /api/v1/speaker/verify with identical voice sample
    wav1 = make_wav(200.0, 2.5)
    wav2 = make_wav(200.0, 2.5)
    r_verify = client.post(
        '/api/v1/speaker/verify?threshold=0.25',
        files={
            'reference_audio': ('ref.wav', wav1, 'audio/wav'),
            'comparison_audio': ('cmp.wav', wav2, 'audio/wav'),
        }
    )
    print("\nPOST /api/v1/speaker/verify Status:", r_verify.status_code)
    data_verify = r_verify.json()
    print("Verification Success:", data_verify.get("success"))
    print("Model Name:", data_verify.get("model_name"))
    print("Embedding Dimension:", data_verify.get("embedding_dimension"))
    print("Cosine Similarity:", data_verify.get("cosine_similarity"))
    print("Verification Status:", data_verify.get("verification_status"))
    print("Is Same Speaker:", data_verify.get("is_same_speaker"))
    print("Processing Time:", data_verify.get("processing_time"))
    print("Quality Warnings:", data_verify.get("audio_quality_warnings"))
    assert r_verify.status_code == 200
    assert data_verify.get("success") is True
    assert data_verify.get("verification_status") == "SAME_SPEAKER"
    assert data_verify.get("is_same_speaker") is True
    assert data_verify.get("cosine_similarity") >= 0.99

    print("\nALL ECAPA ENDPOINT CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
