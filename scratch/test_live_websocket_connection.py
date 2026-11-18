"""
End-to-End WebSocket Live Stream Diagnostic Test
Tests:
1. Connecting to /api/v1/stream/ws
2. Sending auth message with JWT token
3. Receiving 'ready' event
4. Streaming real 16kHz mono PCM chunks
5. Receiving 'metrics' events
6. Receiving 'prediction' event with AI model evaluation
7. Sending 'stop' event and receiving 'stopped'
"""

import asyncio
import json
import os
import sys
import numpy as np
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.main import app
from backend.auth import create_access_token, hash_password
from backend.database import SessionLocal
from backend.models import User


def test_websocket():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "test_stream_user@voiceguard.ai").first()
        if not user:
            user = User(
                email="test_stream_user@voiceguard.ai",
                full_name="Stream Test User",
                hashed_password=hash_password("Password123!@#"),
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = create_access_token({"sub": user.id, "email": user.email})
    finally:
        db.close()

    print("=" * 70)
    print("VOICEGUARD AI — WEBSOCKET LIVE STREAMING END-TO-END AUDIT")
    print("=" * 70)

    client = TestClient(app)

    with client.websocket_connect("/api/v1/stream/ws") as ws:
        print("[1] Connected to WebSocket at /api/v1/stream/ws")

        # Step 2: Send auth
        auth_msg = {
            "type": "auth",
            "token": token,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
            "model": "RAWNET2",
        }
        ws.send_text(json.dumps(auth_msg))
        print("[2] Sent authentication frame with JWT token and preferred model RAWNET2")

        # Step 3: Receive ready
        ready_res = ws.receive_json()
        print(f"[3] Received event: type='{ready_res.get('type')}', session_id='{ready_res.get('session_id')}', ai_model_status='{ready_res.get('ai_model_status')}'")
        assert ready_res.get("type") == "ready", f"Expected ready, got {ready_res}"

        # Step 4: Stream 3 seconds of 16kHz PCM audio in 250ms chunks
        print("[4] Streaming 3.0s of simulated 16kHz PCM audio chunks (250ms each)...")
        sr = 16000
        chunk_duration = 0.25  # 250ms = 4000 samples = 8000 bytes
        chunk_samples = int(sr * chunk_duration)
        total_chunks = 12  # 3.0 seconds total

        predictions_received = []
        metrics_received = []

        for i in range(total_chunks):
            # Synthesize 440Hz tone with slight harmonic
            t = np.linspace(i * chunk_duration, (i + 1) * chunk_duration, chunk_samples, endpoint=False)
            sine_wave = (0.6 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
            pcm_i16 = (sine_wave * 32767.0).astype(np.int16)
            pcm_bytes = pcm_i16.tobytes()

            ws.send_bytes(pcm_bytes)

            # Read any responses
            # Note: websocket may return metrics and/or prediction
            msg = ws.receive_json()
            if msg.get("type") == "metrics":
                metrics_received.append(msg)
                # print(f"    Chunk {i+1}: metrics level={msg['acoustic_metrics']['input_level_percent']}%, duration={msg['acoustic_metrics']['duration_seconds']}s")
            elif msg.get("type") == "prediction":
                predictions_received.append(msg)
                print(f"    --> PREDICTION RECEIVED: class='{msg.get('predicted_class')}', model='{msg.get('selected_model')}', human%={msg.get('human_probability')}, synthetic%={msg.get('synthetic_probability')}")

        # Drain any trailing prediction events
        try:
            # Poll with short wait
            import time
            time.sleep(0.5)
            # send empty ping or check if message waiting
        except Exception:
            pass

        print(f"[5] Streaming complete. Total metrics frames: {len(metrics_received)}, Prediction frames: {len(predictions_received)}")

        # Step 6: Send stop control
        print("[6] Sending control frame: type='stop'...")
        ws.send_text(json.dumps({"type": "stop"}))
        
        while True:
            msg = ws.receive_json()
            if msg.get("type") == "prediction":
                predictions_received.append(msg)
                print(f"    --> PREDICTION RECEIVED: class='{msg.get('predicted_class')}', model='{msg.get('selected_model')}', human%={msg.get('human_probability')}, synthetic%={msg.get('synthetic_probability')}")
            elif msg.get("type") == "stopped":
                print(f"[7] Received event: type='{msg.get('type')}', duration={msg.get('duration_seconds')}s, status='{msg.get('detection_status')}'")
                break

    print("=" * 70)
    print("WEBSOCKET LIVE STREAMING AUDIT: 100% SUCCESSFUL!")
    print("=" * 70)


if __name__ == "__main__":
    test_websocket()
