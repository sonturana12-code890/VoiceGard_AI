"""
VOICEGUARD AI — In-Memory Acoustic Telemetry & Live AI Detection Service
Coordinates real-time PCM ingestion, acoustic metrics extraction,
AudioSegmenter fixed-window slicing (64,600 samples), and dual-model
neural inference (AASIST primary with RawNet2 fallback).
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from backend.services.audio_segmenter import AudioSegment, AudioSegmenter
from backend.services.prediction_engine import VoicePredictionEngine

logger = logging.getLogger("voiceguard.live_stream_service")

SAMPLE_RATE: int = 16_000
CHANNELS: int = 1
SAMPLE_WIDTH_BYTES: int = 2
SLIDING_WINDOW_SECONDS: int = 5
MAX_WINDOW_BYTES: int = SAMPLE_RATE * SAMPLE_WIDTH_BYTES * SLIDING_WINDOW_SECONDS

# Minimum samples required before triggering neural inference (2.0 seconds = 32,000 samples)
MIN_INFERENCE_SAMPLES: int = 32_000
# Throttle interval between consecutive inferences (1.0 second = 16,000 samples)
INFERENCE_INTERVAL_SAMPLES: int = 16_000


@dataclass
class LiveAudioSession:
    """Manages ephemeral in-memory state and audio buffers for a live WebSocket connection."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    samples_processed: int = 0
    window_pcm: bytearray = field(default_factory=bytearray)
    last_inference_samples: int = 0
    is_inferring: bool = False
    last_prediction: Optional[Dict[str, Any]] = None
    threat_alerts: List[Dict[str, Any]] = field(default_factory=list)
    analyzed_windows: int = 0
    last_inference_timestamp: Optional[str] = None

    def ingest(self, pcm_s16le: bytes) -> Dict[str, Any]:
        """
        Ingests a 16-bit PCM chunk, appends to the rolling window buffer,
        and extracts real-time acoustic telemetry.
        """
        if not pcm_s16le or len(pcm_s16le) % SAMPLE_WIDTH_BYTES:
            raise ValueError("Audio chunks must contain 16-bit PCM samples.")

        samples_i16 = np.frombuffer(pcm_s16le, dtype="<i2")
        samples = samples_i16.astype(np.float32) / 32768.0
        self.samples_processed += int(samples.size)

        self.window_pcm.extend(pcm_s16le)
        if len(self.window_pcm) > MAX_WINDOW_BYTES:
            del self.window_pcm[:-MAX_WINDOW_BYTES]

        rms = float(np.sqrt(np.mean(np.square(samples))))
        peak = float(np.max(np.abs(samples)))
        clipped_ratio = float(np.mean(np.abs(samples_i16) >= 32760))
        if peak == 0:
            rms_dbfs = -120.0
            peak_dbfs = -120.0
        else:
            rms_dbfs = 20.0 * math.log10(max(rms, 1e-6))
            peak_dbfs = 20.0 * math.log10(max(peak, 1e-6))

        if clipped_ratio > 0.01:
            signal_quality = "clipped"
        elif rms < 0.003:
            signal_quality = "quiet"
        else:
            signal_quality = "usable"

        # Forensic real-time acoustic features: ZCR and Spectral Centroid
        signs = np.sign(samples)
        signs[signs == 0] = 1.0
        zcr = float(np.mean(np.abs(np.diff(signs)) > 0)) if samples.size > 1 else 0.0

        if samples.size >= 256:
            fft_mag = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
            freqs = np.fft.rfftfreq(len(samples), d=1.0 / SAMPLE_RATE)
            mag_sum = float(np.sum(fft_mag))
            spectral_centroid = float(np.sum(fft_mag * freqs) / (mag_sum + 1e-10)) if mag_sum > 0 else 0.0
        else:
            spectral_centroid = 0.0

        return {
            "sample_rate": SAMPLE_RATE,
            "channels": CHANNELS,
            "sample_count": int(samples.size),
            "input_level_percent": round(min(rms * 100.0, 100.0), 2),
            "peak_level_percent": round(min(peak * 100.0, 100.0), 2),
            "rms_dbfs": round(rms_dbfs, 2),
            "peak_dbfs": round(peak_dbfs, 2),
            "zero_crossing_rate": round(zcr, 4),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "clipped_sample_ratio": round(clipped_ratio, 6),
            "signal_quality": signal_quality,
            "duration_seconds": round(self.samples_processed / SAMPLE_RATE, 3),
            "window_duration_seconds": round(
                len(self.window_pcm) / SAMPLE_WIDTH_BYTES / SAMPLE_RATE, 3
            ),
        }

    def should_run_inference(self) -> bool:
        """
        Determines whether the session has accumulated sufficient audio samples
        and whether enough new samples have been ingested since the last inference.
        """
        if self.is_inferring:
            return False
        available_samples = len(self.window_pcm) // SAMPLE_WIDTH_BYTES
        if available_samples < MIN_INFERENCE_SAMPLES:
            return False
        if (self.samples_processed - self.last_inference_samples) < INFERENCE_INTERVAL_SAMPLES:
            return False
        return True

    def get_window_float32(self) -> np.ndarray:
        """Converts the rolling PCM16 bytearray window into normalized float32."""
        if not self.window_pcm:
            return np.empty(0, dtype=np.float32)
        return np.frombuffer(self.window_pcm, dtype="<i2").astype(np.float32) / 32768.0

    def mark_inference_started(self) -> None:
        self.is_inferring = True
        self.last_inference_samples = self.samples_processed

    def mark_inference_completed(self, result: Dict[str, Any]) -> None:
        self.is_inferring = False
        self.last_prediction = result
        self.threat_alerts = result.get("threat_alerts", [])
        if result.get("analysis_status") == "completed":
            self.analyzed_windows += 1
            self.last_inference_timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    def clear(self) -> None:
        """Cleans up all in-memory buffers when connection terminates."""
        self.window_pcm.clear()
        self.is_inferring = False
        self.last_prediction = None
        self.threat_alerts.clear()
        self.analyzed_windows = 0
        self.last_inference_timestamp = None


def run_live_ai_inference(
    pcm_float32: np.ndarray,
    segmenter: AudioSegmenter,
    prediction_engine: VoicePredictionEngine,
    preferred_model: str = "AASIST",
) -> Dict[str, Any]:
    """
    Executes real-time AI synthetic voice detection on 1D float32 audio.
    Slices into model-compatible 64,600 sample windows using AudioSegmenter.
    Attempts preferred_model first (default AASIST), falling back to secondary (RawNet2).
    Preserves HUMAN, AI_GENERATED, and INCONCLUSIVE classifications.
    Never fabricates predictions.
    """
    if pcm_float32.size < MIN_INFERENCE_SAMPLES:
        return {
            "predicted_class": "INCONCLUSIVE",
            "human_probability": None,
            "synthetic_probability": None,
            "confidence_score": None,
            "selected_model": "NONE",
            "inference_time": 0.0,
            "prediction_reliability": "LOW",
            "analysis_status": "insufficient_audio",
            "threat_alerts": [],
        }

    segments = segmenter.segment(pcm_float32)
    if not segments:
        return {
            "predicted_class": "INCONCLUSIVE",
            "human_probability": None,
            "synthetic_probability": None,
            "confidence_score": None,
            "selected_model": "NONE",
            "inference_time": 0.0,
            "prediction_reliability": "LOW",
            "analysis_status": "segmentation_failed",
            "threat_alerts": [],
        }

    selected_model = "NONE"
    prediction_dict: Optional[Dict[str, Any]] = None
    aasist_failed = False
    rawnet2_failed = False

    # Dynamic model prioritization: try preferred model first, then fallback
    order = ["RAWNET2", "AASIST"] if preferred_model.upper() == "RAWNET2" else ["AASIST", "RAWNET2"]

    for model_candidate in order:
        model_key = model_candidate.lower()
        if prediction_engine.model_manager.is_model_available(model_key):
            try:
                res = prediction_engine.predict(segments, model_name=model_candidate)
                if (
                    res.get("analysis_status") == "completed"
                    and res.get("prediction", {}).get("inference_completed")
                ):
                    prediction_dict = res
                    selected_model = model_candidate
                    break
                else:
                    if model_candidate == "AASIST":
                        aasist_failed = True
                    else:
                        rawnet2_failed = True
            except Exception as exc:
                logger.warning(f"Live {model_candidate} inference failed: {exc}. Attempting fallback.")
                if model_candidate == "AASIST":
                    aasist_failed = True
                else:
                    rawnet2_failed = True

    # Step 3: Handle results or total failure
    if prediction_dict is not None and selected_model != "NONE":
        pred_meta = prediction_dict.get("prediction", {})
        pred_class = prediction_dict.get("predicted_class") or pred_meta.get("predicted_class") or "INCONCLUSIVE"
        human_prob = prediction_dict.get("human_probability")
        synth_prob = prediction_dict.get("synthetic_probability")
        conf_score = prediction_dict.get("confidence_score")
        inf_time = prediction_dict.get("inference_time", 0.0)
        reliability = prediction_dict.get("prediction_reliability", "MEDIUM")

        threat_alerts: List[Dict[str, Any]] = []
        if pred_class == "AI_GENERATED":
            threat_alerts.append({
                "threat_type": "Synthetic Voice Impersonation",
                "risk_level": "High" if (conf_score or 0.0) >= 0.85 else "Medium",
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "status": "Active Threat",
                "confidence": conf_score,
                "model": selected_model,
            })

        return {
            "predicted_class": pred_class,
            "human_probability": human_prob,
            "synthetic_probability": synth_prob,
            "confidence_score": conf_score,
            "selected_model": selected_model,
            "model_status": f"{selected_model} ACTIVE",
            "inference_time": inf_time,
            "prediction_reliability": reliability,
            "analysis_status": "completed",
            "threat_alerts": threat_alerts,
        }

    # Step 4: Both models unavailable or failed -> Return zero-hallucination INCONCLUSIVE
    logger.warning("Both AASIST and RawNet2 live inference unavailable or failed.")
    err_status = "INFERENCE ERROR" if (aasist_failed or rawnet2_failed) else "MODEL UNAVAILABLE"
    return {
        "predicted_class": "INCONCLUSIVE",
        "human_probability": None,
        "synthetic_probability": None,
        "confidence_score": None,
        "selected_model": "NONE",
        "model_status": err_status,
        "inference_time": 0.0,
        "prediction_reliability": "UNRELIABLE",
        "analysis_status": "AI_MODEL_NOT_CONFIGURED",
        "threat_alerts": [],
    }

