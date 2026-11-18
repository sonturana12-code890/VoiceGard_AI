"""Authenticated, ephemeral PCM WebSocket audio streaming with live AI voice detection."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Set, Tuple

import numpy as np
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from backend.auth import decode_access_token
from backend.database import get_db
from backend.models import User
from backend.services.audio_segmenter import AudioSegmenter
from backend.services.live_stream_service import (
    CHANNELS,
    SAMPLE_RATE,
    LiveAudioSession,
    run_live_ai_inference,
)
from backend.services.model_manager import ModelManager
from backend.services.prediction_engine import VoicePredictionEngine

logger = logging.getLogger("voiceguard.live_stream")
router = APIRouter(tags=["Live Audio Streaming"])
MAX_AUDIO_CHUNK_BYTES = 32_000
MAX_AUTH_MESSAGE_BYTES = 8_192
AUTH_TIMEOUT_SECONDS = 10


def _resolve_user(db: Session, token: str) -> Tuple[Optional[str], str]:
    claims = decode_access_token(token)
    if not claims or not claims.get("sub"):
        return None, "unauthorized"

    user = db.query(User).filter(User.id == claims["sub"]).first()
    if not user:
        return None, "unauthorized"
    if not user.is_active:
        return None, "forbidden"
    return user.id, ""


def _model_status(preferred_model: str = "AASIST") -> str:
    manager = ModelManager()
    has_aasist = manager.is_model_available("aasist") and manager.get_session("aasist") is not None
    has_rawnet2 = manager.is_model_available("rawnet2") and manager.get_session("rawnet2") is not None
    if preferred_model.upper() == "RAWNET2":
        if has_rawnet2:
            return "RAWNET2 ACTIVE"
        elif has_aasist:
            return "AASIST ACTIVE"
    else:
        if has_aasist:
            return "AASIST ACTIVE"
        elif has_rawnet2:
            return "RAWNET2 ACTIVE"
    return "MODEL UNAVAILABLE"


async def _reject(websocket: WebSocket, code: str, message: str, close_code: int) -> None:
    try:
        await websocket.send_json({"type": "error", "code": code, "message": message})
    finally:
        await websocket.close(code=close_code)


@router.websocket("/api/v1/stream/ws")
async def stream_audio(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    await websocket.accept()
    session: Optional[LiveAudioSession] = None
    send_lock = asyncio.Lock()
    active_inference_tasks: Set[asyncio.Task] = set()

    async def _safe_send(payload: dict) -> bool:
        async with send_lock:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(payload)
                    return True
            except Exception:
                pass
            return False

    try:
        try:
            auth_event = await asyncio.wait_for(
                websocket.receive(), timeout=AUTH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            await _reject(
                websocket,
                "authentication_timeout",
                "Authentication must be completed before streaming audio.",
                4401,
            )
            return

        auth_text = auth_event.get("text")
        if auth_event.get("type") != "websocket.receive" or not auth_text:
            await _reject(
                websocket,
                "invalid_auth_message",
                "The first WebSocket message must be an authentication request.",
                4401,
            )
            return
        if len(auth_text.encode("utf-8")) > MAX_AUTH_MESSAGE_BYTES:
            await _reject(
                websocket,
                "auth_message_too_large",
                "The authentication message is too large.",
                4401,
            )
            return

        try:
            auth_message = json.loads(auth_text)
        except json.JSONDecodeError:
            await _reject(
                websocket,
                "invalid_auth_message",
                "The authentication request is not valid JSON.",
                4401,
            )
            return

        if (
            not isinstance(auth_message, dict)
            or auth_message.get("type") != "auth"
            or auth_message.get("sample_rate") != SAMPLE_RATE
            or auth_message.get("channels") != CHANNELS
            or auth_message.get("encoding") != "pcm_s16le"
        ):
            await _reject(
                websocket,
                "unsupported_audio_format",
                "Stream format must be mono 16 kHz signed 16-bit little-endian PCM.",
                4400,
            )
            return

        # Token Resolution: Check JSON token first, fallback to HttpOnly session cookies
        token = auth_message.get("token")
        if not token or not isinstance(token, str) or not token.strip():
            token = (
                websocket.cookies.get("vg_session")
                or websocket.cookies.get("access_token")
                or websocket.cookies.get("vg_token")
            )

        if not isinstance(token, str) or not token or len(token) > 4096:
            await _reject(
                websocket,
                "unauthorized",
                "A valid account session is required before streaming audio.",
                4401,
            )
            return

        try:
            user_id, auth_error = _resolve_user(db, token)
        finally:
            db.close()
        if not user_id:
            close_code = 4403 if auth_error == "forbidden" else 4401
            message = (
                "This account is not permitted to start a stream."
                if auth_error == "forbidden"
                else "The account session is invalid or expired."
            )
            await _reject(websocket, auth_error, message, close_code)
            return

        # Initialize live audio session and AI inference engines
        requested_model = auth_message.get("model", "AASIST") if isinstance(auth_message, dict) else "AASIST"
        preferred_model = "RAWNET2" if str(requested_model).upper() == "RAWNET2" else "AASIST"
        session = LiveAudioSession()
        model_manager = ModelManager()
        prediction_engine = VoicePredictionEngine(model_manager)
        segmenter = AudioSegmenter(target_samples=64600, sample_rate=SAMPLE_RATE, overlap_seconds=1.0)
        model_status = _model_status(preferred_model)
        inference_enabled = ("ACTIVE" in model_status)

        # Emit READY event
        await _safe_send(
            {
                "type": "ready",
                "session_id": session.session_id,
                "sample_rate": SAMPLE_RATE,
                "channels": CHANNELS,
                "encoding": "pcm_s16le",
                "processing_status": "READY · AI INFERENCE ACTIVE" if inference_enabled else "READY · ACOUSTIC METRICS ONLY",
                "ai_model_status": model_status,
                "detection_status": "WAITING FOR AUDIO",
                "threat_alerts": [],
                "analyzed_windows": 0,
                "last_inference_timestamp": None,
            }
        )

        while True:
            event = await websocket.receive()
            if event.get("type") == "websocket.disconnect":
                break

            chunk = event.get("bytes")
            if chunk is not None:
                if (
                    not chunk
                    or len(chunk) % 2
                    or len(chunk) > MAX_AUDIO_CHUNK_BYTES
                ):
                    await _reject(
                        websocket,
                        "invalid_audio_chunk",
                        "Audio chunks must be non-empty 16-bit PCM and no larger than 1 second.",
                        4400,
                    )
                    break

                # 1. Real-time acoustic telemetry extraction
                metrics = await asyncio.to_thread(session.ingest, chunk)

                current_pred = session.last_prediction
                if current_pred:
                    det_status = current_pred.get("predicted_class", "INCONCLUSIVE")
                    active_alerts = session.threat_alerts
                    proc_status = f"STREAMING · {current_pred.get('selected_model', 'AI')} ACTIVE"
                    active_model_status = current_pred.get("model_status", model_status)
                else:
                    det_status = "WAITING FOR AUDIO"
                    active_alerts = []
                    proc_status = "STREAMING · COLLECTING AUDIO" if session.samples_processed < 32000 else "STREAMING · AI ACTIVE"
                    active_model_status = model_status

                # 2. Emit METRICS event
                await _safe_send(
                    {
                        "type": "metrics",
                        "session_id": session.session_id,
                        "processing_status": proc_status,
                        "ai_model_status": active_model_status,
                        "detection_status": det_status,
                        "acoustic_metrics": metrics,
                        "threat_alerts": active_alerts,
                        "analyzed_windows": session.analyzed_windows,
                        "last_inference_timestamp": session.last_inference_timestamp,
                    }
                )

                # 3. Schedule asynchronous AI voice detection (non-blocking, non-overlapping)
                if inference_enabled and session.should_run_inference():
                    session.mark_inference_started()
                    window_bytes_snapshot = bytes(session.window_pcm)

                    async def _inference_worker(raw_bytes: bytes) -> None:
                        try:
                            def _sync_inference() -> dict:
                                pcm_float32 = np.frombuffer(raw_bytes, dtype="<i2").astype(np.float32) / 32768.0
                                return run_live_ai_inference(
                                    pcm_float32,
                                    segmenter,
                                    prediction_engine,
                                    preferred_model=preferred_model,
                                )

                            pred_result = await asyncio.to_thread(_sync_inference)
                            session.mark_inference_completed(pred_result)

                            # Emit PREDICTION event
                            await _safe_send(
                                {
                                    "type": "prediction",
                                    "session_id": session.session_id,
                                    "predicted_class": pred_result["predicted_class"],
                                    "human_probability": pred_result["human_probability"],
                                    "synthetic_probability": pred_result["synthetic_probability"],
                                    "confidence_score": pred_result["confidence_score"],
                                    "selected_model": pred_result["selected_model"],
                                    "ai_model_status": pred_result.get("model_status", f"{pred_result['selected_model']} ACTIVE"),
                                    "inference_time": pred_result["inference_time"],
                                    "prediction_reliability": pred_result["prediction_reliability"],
                                    "analysis_status": pred_result["analysis_status"],
                                    "threat_alerts": pred_result.get("threat_alerts", []),
                                    "analyzed_windows": session.analyzed_windows,
                                    "last_inference_timestamp": session.last_inference_timestamp,
                                }
                            )
                        except Exception as exc:
                            logger.warning(f"Live background inference worker error: {exc}")
                            session.is_inferring = False
                            err_result = {
                                "predicted_class": "INCONCLUSIVE",
                                "human_probability": None,
                                "synthetic_probability": None,
                                "confidence_score": None,
                                "selected_model": "NONE",
                                "model_status": "INFERENCE ERROR",
                                "inference_time": 0.0,
                                "prediction_reliability": "UNRELIABLE",
                                "analysis_status": "inference_error",
                                "threat_alerts": [],
                            }
                            session.mark_inference_completed(err_result)
                            await _safe_send(
                                {
                                    "type": "prediction",
                                    "session_id": session.session_id,
                                    "predicted_class": "INCONCLUSIVE",
                                    "human_probability": None,
                                    "synthetic_probability": None,
                                    "confidence_score": None,
                                    "selected_model": "NONE",
                                    "ai_model_status": "INFERENCE ERROR",
                                    "inference_time": 0.0,
                                    "prediction_reliability": "UNRELIABLE",
                                    "analysis_status": "inference_error",
                                    "threat_alerts": [],
                                    "analyzed_windows": session.analyzed_windows,
                                    "last_inference_timestamp": session.last_inference_timestamp,
                                }
                            )

                    task = asyncio.create_task(_inference_worker(window_bytes_snapshot))
                    active_inference_tasks.add(task)
                    task.add_done_callback(active_inference_tasks.discard)

                continue

            control_text = event.get("text")
            if not control_text:
                await _reject(
                    websocket,
                    "invalid_message",
                    "Only PCM audio chunks and a stop request are accepted.",
                    4400,
                )
                break
            try:
                control = json.loads(control_text)
            except json.JSONDecodeError:
                await _reject(
                    websocket,
                    "invalid_message",
                    "Control messages must be valid JSON.",
                    4400,
                )
                break

            if isinstance(control, dict) and control.get("type") == "stop":
                await _safe_send(
                    {
                        "type": "stopped",
                        "session_id": session.session_id,
                        "duration_seconds": round(
                            session.samples_processed / SAMPLE_RATE, 3
                        ),
                        "final_status": "stream_stopped",
                        "detection_status": "SESSION ENDED",
                        "analyzed_windows": session.analyzed_windows,
                        "last_inference_timestamp": session.last_inference_timestamp,
                    }
                )
                break

            await _reject(
                websocket,
                "invalid_message",
                "Only PCM audio chunks and a stop request are accepted.",
                4400,
            )
            break
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Live audio WebSocket session failed.")
        try:
            await _reject(
                websocket,
                "stream_error",
                "The live audio session ended because of a processing error.",
                1011,
            )
        except WebSocketDisconnect:
            pass
    finally:
        for t in list(active_inference_tasks):
            if not t.done():
                t.cancel()
        if session is not None:
            session.clear()
        db.close()

