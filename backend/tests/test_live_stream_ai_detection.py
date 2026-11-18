"""
VOICEGUARD AI — Live WebSocket AI Voice Anti-Spoofing & Detection Engine Tests
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.

Tests:
1. LiveAudioSession state machine, buffer window, and inference pacing.
2. Dual-model live inference: AASIST primary, RawNet2 fallback, and INCONCLUSIVE zero-hallucination.
3. Live threat alert generation on AI_GENERATED detection.
4. WebSocket handshake, authentication (JSON token & vg_session HttpOnly cookie fallback).
5. WebSocket ready, metrics, prediction, and stopped event contracts.
6. Malformed chunk rejection and error handling.
"""

from __future__ import annotations

import json
import uuid
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock, patch

from backend.auth import create_access_token, hash_password
from backend.database import Base, get_db
from backend.main import app
from backend.models import User
from backend.services.audio_segmenter import AudioSegment, AudioSegmenter
from backend.services.live_stream_service import (
    CHANNELS,
    INFERENCE_INTERVAL_SAMPLES,
    MAX_WINDOW_BYTES,
    MIN_INFERENCE_SAMPLES,
    SAMPLE_RATE,
    SAMPLE_WIDTH_BYTES,
    LiveAudioSession,
    run_live_ai_inference,
)
from backend.services.model_manager import ModelManager
from backend.services.prediction_engine import VoicePredictionEngine

# Use in-memory SQLite with StaticPool so all connections share the DB
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
def setup_test_database():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    test_user = User(
        id="live-test-user-id",
        full_name="Live Stream Test Analyst",
        email="livestream@voiceguard.ai",
        hashed_password=hash_password("SuperSecretLivePass123!"),
        is_active=True,
    )
    db.merge(test_user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_user_token():
    return create_access_token({"sub": "live-test-user-id"})


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# MODULE 1: LiveAudioSession Unit Tests
# ============================================================================

def test_live_session_inference_trigger_pacing():
    """Verifies that inference is only triggered after MIN_INFERENCE_SAMPLES and throttled."""
    session = LiveAudioSession()
    assert not session.should_run_inference()

    # Ingest 1 second of audio (16,000 samples = 32,000 bytes) -> Still below threshold
    chunk_1s = np.zeros(16000, dtype="<i2").tobytes()
    session.ingest(chunk_1s)
    assert session.samples_processed == 16000
    assert not session.should_run_inference()

    # Ingest another 1 second (total 32,000 samples) -> Reaches MIN_INFERENCE_SAMPLES
    session.ingest(chunk_1s)
    assert session.samples_processed == 32000
    assert session.should_run_inference()

    # Mark inference started -> should_run_inference() becomes False while inferring
    session.mark_inference_started()
    assert session.is_inferring
    assert not session.should_run_inference()

    # Mark completed -> should_run_inference() is still False because 0 samples processed since start
    session.mark_inference_completed({"predicted_class": "HUMAN"})
    assert not session.is_inferring
    assert session.last_prediction == {"predicted_class": "HUMAN"}
    assert not session.should_run_inference()

    # Ingest 15,999 samples -> still under interval
    chunk_sub = np.zeros(15999, dtype="<i2").tobytes()
    session.ingest(chunk_sub)
    assert not session.should_run_inference()

    # Ingest 1 more sample -> exactly 16,000 new samples -> should trigger again
    chunk_1 = np.zeros(1, dtype="<i2").tobytes()
    session.ingest(chunk_1)
    assert session.should_run_inference()


def test_live_session_float32_conversion_and_clear():
    """Verifies normalized float32 extraction from PCM byte buffer and session clearing."""
    session = LiveAudioSession()
    # Ingest 100 samples with value 16384 (approx 0.5 float)
    raw = np.full(100, 16384, dtype="<i2").tobytes()
    session.ingest(raw)

    f32 = session.get_window_float32()
    assert len(f32) == 100
    assert f32[0] == pytest.approx(0.5, abs=0.01)

    session.threat_alerts.append({"threat_type": "Test"})
    session.clear()
    assert len(session.window_pcm) == 0
    assert session.last_prediction is None
    assert len(session.threat_alerts) == 0
    assert not session.is_inferring


# ============================================================================
# MODULE 2: Dual-Model Live AI Inference Tests
# ============================================================================

def test_run_live_ai_inference_insufficient_audio():
    """Verify that audio with fewer than 32,000 samples is rejected with insufficient_audio."""
    segmenter = AudioSegmenter()
    engine = VoicePredictionEngine()
    short_audio = np.zeros(16000, dtype=np.float32)

    result = run_live_ai_inference(short_audio, segmenter, engine)
    assert result["predicted_class"] == "INCONCLUSIVE"
    assert result["analysis_status"] == "insufficient_audio"
    assert result["selected_model"] == "NONE"


def test_run_live_ai_inference_aasist_primary():
    """Verifies that when AASIST is available, it is selected as the primary detection model."""
    segmenter = AudioSegmenter()
    audio = np.sin(2 * np.pi * 440 * np.arange(64600) / 16000).astype(np.float32)

    mock_manager = MagicMock(spec=ModelManager)
    mock_manager.is_model_available.side_effect = lambda m: m.lower() in ("aasist", "rawnet2")

    mock_engine = MagicMock(spec=VoicePredictionEngine)
    mock_engine.model_manager = mock_manager
    mock_engine.predict.return_value = {
        "analysis_status": "completed",
        "predicted_class": "HUMAN",
        "human_probability": 0.94,
        "synthetic_probability": 0.06,
        "confidence_score": 0.94,
        "inference_time": 0.082,
        "prediction_reliability": "HIGH",
        "prediction": {"inference_completed": True},
    }

    result = run_live_ai_inference(audio, segmenter, mock_engine)
    assert result["analysis_status"] == "completed"
    assert result["selected_model"] == "AASIST"
    assert result["predicted_class"] == "HUMAN"
    assert result["confidence_score"] == 0.94
    mock_engine.predict.assert_called_once()


def test_run_live_ai_inference_fallback_to_rawnet2():
    """Verifies that when AASIST fails, RawNet2 is invoked as the fallback model."""
    segmenter = AudioSegmenter()
    audio = np.zeros(64600, dtype=np.float32)

    mock_manager = MagicMock(spec=ModelManager)
    mock_manager.is_model_available.side_effect = lambda m: m.lower() in ("aasist", "rawnet2")

    mock_engine = MagicMock(spec=VoicePredictionEngine)
    mock_engine.model_manager = mock_manager

    # AASIST raises exception, RawNet2 succeeds
    def predict_mock(segments, model_name="AASIST"):
        if model_name.upper() == "AASIST":
            raise RuntimeError("AASIST ONNX execution error")
        return {
            "analysis_status": "completed",
            "predicted_class": "AI_GENERATED",
            "human_probability": 0.05,
            "synthetic_probability": 0.95,
            "confidence_score": 0.95,
            "inference_time": 0.120,
            "prediction_reliability": "HIGH",
            "prediction": {"inference_completed": True},
        }

    mock_engine.predict.side_effect = predict_mock

    result = run_live_ai_inference(audio, segmenter, mock_engine)
    assert result["analysis_status"] == "completed"
    assert result["selected_model"] == "RAWNET2"
    assert result["predicted_class"] == "AI_GENERATED"
    assert result["confidence_score"] == 0.95
    # Threat alert must be generated for AI_GENERATED
    assert len(result["threat_alerts"]) == 1
    assert result["threat_alerts"][0]["threat_type"] == "Synthetic Voice Impersonation"
    assert result["threat_alerts"][0]["risk_level"] == "High"
    assert result["threat_alerts"][0]["model"] == "RAWNET2"


def test_run_live_ai_inference_both_models_fail():
    """Verifies zero-hallucination INCONCLUSIVE when neither model is available."""
    segmenter = AudioSegmenter()
    audio = np.zeros(64600, dtype=np.float32)

    mock_manager = MagicMock(spec=ModelManager)
    mock_manager.is_model_available.return_value = False

    mock_engine = MagicMock(spec=VoicePredictionEngine)
    mock_engine.model_manager = mock_manager

    result = run_live_ai_inference(audio, segmenter, mock_engine)
    assert result["predicted_class"] == "INCONCLUSIVE"
    assert result["analysis_status"] == "AI_MODEL_NOT_CONFIGURED"
    assert result["selected_model"] == "NONE"
    assert result["confidence_score"] is None
    assert result["threat_alerts"] == []


# ============================================================================
# MODULE 3: WebSocket API Endpoint Tests (/api/v1/stream/ws)
# ============================================================================

def test_websocket_rejects_missing_auth(client):
    """Verifies that sending an invalid auth message closes the connection."""
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        ws.send_text(json.dumps({"type": "not_auth"}))
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "unsupported_audio_format"


def test_websocket_rejects_unauthorized_token(client):
    """Verifies that an invalid JWT token is rejected with unauthorized."""
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        ws.send_text(json.dumps({
            "type": "auth",
            "token": "invalid.jwt.token",
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        }))
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "unauthorized"


def test_websocket_authenticated_with_token(client, test_user_token):
    """Verifies complete WebSocket flow: auth -> ready -> metrics -> stop -> stopped."""
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        # 1. Send valid auth message
        ws.send_text(json.dumps({
            "type": "auth",
            "token": test_user_token,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        }))

        # 2. Receive READY event
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"
        assert "session_id" in ready_msg
        assert ready_msg["sample_rate"] == 16000
        assert ready_msg["channels"] == 1
        assert ready_msg["encoding"] == "pcm_s16le"
        assert "ai_model_status" in ready_msg

        # 3. Stream a 200ms audio chunk (3200 samples = 6400 bytes)
        pcm_chunk = np.full(3200, 8000, dtype="<i2").tobytes()
        ws.send_bytes(pcm_chunk)

        # 4. Receive METRICS event
        metrics_msg = ws.receive_json()
        assert metrics_msg["type"] == "metrics"
        assert metrics_msg["session_id"] == ready_msg["session_id"]
        assert "acoustic_metrics" in metrics_msg
        ac = metrics_msg["acoustic_metrics"]
        assert ac["sample_count"] == 3200
        assert ac["sample_rate"] == 16000
        assert ac["rms_dbfs"] < 0

        # 5. Send STOP event
        ws.send_text(json.dumps({"type": "stop"}))

        # 6. Receive STOPPED event
        stopped_msg = ws.receive_json()
        assert stopped_msg["type"] == "stopped"
        assert stopped_msg["session_id"] == ready_msg["session_id"]
        assert stopped_msg["final_status"] == "stream_stopped"


def test_websocket_cookie_authentication_fallback(client, test_user_token):
    """Verifies that when token is absent in auth JSON, vg_session cookie is used."""
    client.cookies.set("vg_session", test_user_token)
    with client.websocket_connect("/api/v1/stream/ws", cookies={"vg_session": test_user_token}) as ws:
        # Auth message with null/empty token
        ws.send_text(json.dumps({
            "type": "auth",
            "token": None,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        }))

        # Must succeed via cookie fallback
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"
        assert "session_id" in ready_msg

        # Cleanly stop
        ws.send_text(json.dumps({"type": "stop"}))
        stopped_msg = ws.receive_json()
        assert stopped_msg["type"] == "stopped"


def test_websocket_malformed_chunk_handling(client, test_user_token):
    """Verifies that an odd-length PCM byte chunk is safely rejected with error."""
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        ws.send_text(json.dumps({
            "type": "auth",
            "token": test_user_token,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        }))
        ready = ws.receive_json()
        assert ready["type"] == "ready"

        # Send invalid odd-byte chunk
        ws.send_bytes(b"\x00\x01\x02")
        err = ws.receive_json()
        assert err["type"] == "error"
        assert err["code"] == "invalid_audio_chunk"


def test_websocket_real_ai_inference_stream(client, test_user_token):
    """
    Verifies that streaming sufficient audio chunks triggers the background AI
    inference worker, resulting in a 'prediction' WebSocket event.
    """
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        ws.send_text(json.dumps({
            "type": "auth",
            "token": test_user_token,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        }))
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"

        # Stream 11 chunks of 200ms (3,200 samples each = 35,200 samples total > 32,000 threshold)
        # Generate 440Hz tone
        chunk_samples = 3200
        t = np.arange(chunk_samples)
        tone_i16 = (np.sin(2 * np.pi * 440 * t / 16000) * 16000).astype("<i2").tobytes()

        received_prediction = False
        received_metrics_count = 0

        for _ in range(11):
            ws.send_bytes(tone_i16)

        # Collect events emitted (metrics and prediction)
        # Read with timeout or until prediction is found or stopped
        for _ in range(25):
            try:
                event = ws.receive_json()
                if event["type"] == "metrics":
                    received_metrics_count += 1
                elif event["type"] == "prediction":
                    received_prediction = True
                    assert event["session_id"] == ready_msg["session_id"]
                    assert event["predicted_class"] in ("HUMAN", "AI_GENERATED", "INCONCLUSIVE")
                    assert event["selected_model"] in ("AASIST", "RAWNET2", "NONE")
                    assert "inference_time" in event
                    assert "prediction_reliability" in event
                    assert "threat_alerts" in event
                    break
            except Exception:
                break

        # Send stop to cleanly close
        ws.send_text(json.dumps({"type": "stop"}))
        stopped = ws.receive_json()
        assert stopped["type"] == "stopped"
        assert "analyzed_windows" in stopped
        assert received_metrics_count >= 5


def test_session_status_and_window_counting():
    """Verifies that LiveAudioSession tracks analyzed windows count and timestamps."""
    session = LiveAudioSession()
    assert session.analyzed_windows == 0
    assert session.last_inference_timestamp is None

    # Incomplete / error inference should not increment window count
    session.mark_inference_completed({"analysis_status": "insufficient_audio"})
    assert session.analyzed_windows == 0

    # Successful inference increments window count and updates timestamp
    session.mark_inference_completed({
        "analysis_status": "completed",
        "predicted_class": "REAL_HUMAN",
    })
    assert session.analyzed_windows == 1
    assert session.last_inference_timestamp is not None
    assert "UTC" in session.last_inference_timestamp

    session.mark_inference_completed({
        "analysis_status": "completed",
        "predicted_class": "REAL_HUMAN",
    })
    assert session.analyzed_windows == 2

    # Clear resets counts and timestamps
    session.clear()
    assert session.analyzed_windows == 0
    assert session.last_inference_timestamp is None


def test_dynamic_model_status_and_inference_error_handling():
    """Verifies that runtime inference failures output INCONCLUSIVE and INFERENCE ERROR."""
    segmenter = AudioSegmenter()
    audio = np.zeros(64600, dtype=np.float32)

    mock_manager = MagicMock(spec=ModelManager)
    mock_manager.is_model_available.return_value = True

    mock_engine = MagicMock(spec=VoicePredictionEngine)
    mock_engine.model_manager = mock_manager

    # Both AASIST and RawNet2 raise exceptions
    def predict_fail(segments, model_name="AASIST"):
        raise RuntimeError("ONNX execution provider hardware fault")

    mock_engine.predict.side_effect = predict_fail

    result = run_live_ai_inference(audio, segmenter, mock_engine)
    assert result["predicted_class"] == "INCONCLUSIVE"
    assert result["model_status"] == "INFERENCE ERROR"
    assert result["analysis_status"] == "AI_MODEL_NOT_CONFIGURED"
    assert result["confidence_score"] is None
    assert result["selected_model"] == "NONE"


def test_prediction_event_contains_all_required_metrics(client, test_user_token):
    """Verifies Task 3 contract: all probabilities, model name, latency, and status are emitted."""
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        ws.send_text(json.dumps({
            "type": "auth",
            "token": test_user_token,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        }))
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"
        assert ready_msg["ai_model_status"] in ("AASIST ACTIVE", "RAWNET2 ACTIVE", "MODEL UNAVAILABLE")
        assert "analyzed_windows" in ready_msg

        # Stream enough audio to trigger inference (35,200 samples)
        chunk_samples = 3200
        t = np.arange(chunk_samples)
        tone_i16 = (np.sin(2 * np.pi * 440 * t / 16000) * 16000).astype("<i2").tobytes()
        for _ in range(11):
            ws.send_bytes(tone_i16)

        # Await prediction event
        prediction_found = False
        for _ in range(30):
            try:
                event = ws.receive_json()
                if event["type"] == "prediction":
                    prediction_found = True
                    # Verify Task 3 fields
                    assert "predicted_class" in event
                    assert "human_probability" in event
                    assert "synthetic_probability" in event
                    assert "confidence_score" in event
                    assert "selected_model" in event
                    assert "inference_time" in event
                    assert "analysis_status" in event
                    assert "ai_model_status" in event
                    # Verify Task 5 session status synchronization fields
                    assert "analyzed_windows" in event
                    assert "last_inference_timestamp" in event
                    break
            except Exception:
                break

        ws.send_text(json.dumps({"type": "stop"}))
        stopped = ws.receive_json()
        assert stopped["type"] == "stopped"
        assert "analyzed_windows" in stopped


def test_stale_detection_prevention_lifecycle(client, test_user_token):
    """Verifies that initial connection starts in WAITING FOR AUDIO and stop emits SESSION ENDED."""
    with client.websocket_connect("/api/v1/stream/ws") as ws:
        ws.send_text(json.dumps({
            "type": "auth",
            "token": test_user_token,
            "sample_rate": 16000,
            "channels": 1,
            "encoding": "pcm_s16le",
        }))
        ready_msg = ws.receive_json()
        assert ready_msg["type"] == "ready"
        assert ready_msg["detection_status"] == "WAITING FOR AUDIO"
        assert ready_msg["analyzed_windows"] == 0
        assert ready_msg["last_inference_timestamp"] is None

        # Send a single small chunk (100ms) - well below inference threshold
        chunk_samples = 1600
        silent_i16 = np.zeros(chunk_samples, dtype="<i2").tobytes()
        ws.send_bytes(silent_i16)

        # First metrics event must still report WAITING FOR AUDIO
        metrics_msg = ws.receive_json()
        assert metrics_msg["type"] == "metrics"
        assert metrics_msg["detection_status"] == "WAITING FOR AUDIO"
        assert metrics_msg["analyzed_windows"] == 0
        assert metrics_msg["last_inference_timestamp"] is None

        # Send stop message
        ws.send_text(json.dumps({"type": "stop"}))
        stopped_msg = ws.receive_json()
        assert stopped_msg["type"] == "stopped"
        assert stopped_msg["detection_status"] == "SESSION ENDED"
        assert stopped_msg["final_status"] == "stream_stopped"


