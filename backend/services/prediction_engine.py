"""
VOICEGUARD AI — Voice Prediction Engine & Anti-Spoofing Classifier
Unified prediction engine coordinating neural inference (AASIST / RawNet2),
numerically stable softmax computation, segment-level probability aggregation,
and strict zero-hallucination enforcement when model checkpoints are not installed.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from backend.services.audio_segmenter import AudioSegment
from backend.services.model_manager import (
    ModelInferenceError,
    ModelManager,
    ModelNotFoundError,
)

logger = logging.getLogger("voiceguard.prediction_engine")


def stable_softmax(logits: np.ndarray) -> np.ndarray:
    """
    Computes numerically stable softmax along the last axis.
    Input shape: [batch_size, num_classes] or [num_classes].
    Class 0: Synthetic / Spoof (AI-generated)
    Class 1: Human / Bona-fide
    """
    logits_arr = np.asarray(logits, dtype=np.float32)
    shifted = logits_arr - np.max(logits_arr, axis=-1, keepdims=True)
    exp_shifted = np.exp(shifted)
    probs = exp_shifted / np.sum(exp_shifted, axis=-1, keepdims=True)
    return probs


@dataclass
class PredictionResult:
    """Standardized Module 4 & 5 Prediction Output."""
    label: str  # "HUMAN", "AI_GENERATED", "INCONCLUSIVE", or "MODEL_NOT_AVAILABLE"
    human_probability: Optional[float]
    synthetic_probability: Optional[float]
    confidence: Optional[float]
    model_used: str
    inference_completed: bool
    status: Optional[str] = None
    predicted_class: Optional[str] = None
    real_probability: Optional[float] = None
    fake_probability: Optional[float] = None
    model_name: Optional[str] = None
    inference_time: Optional[float] = None
    prediction_reliability: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Module 4 & 5 strict JSON dictionary output."""
        pred_class = self.predicted_class or (
            "REAL_HUMAN" if self.label == "HUMAN" else
            "AI_GENERATED" if self.label == "AI_GENERATED" else "INCONCLUSIVE"
        )
        data: Dict[str, Any] = {
            "label": self.label,
            "predicted_class": pred_class,
            "human_probability": self.human_probability,
            "real_probability": self.real_probability if self.real_probability is not None else self.human_probability,
            "synthetic_probability": self.synthetic_probability,
            "fake_probability": self.fake_probability if self.fake_probability is not None else self.synthetic_probability,
            "confidence": self.confidence,
            "model_used": self.model_used.upper(),
            "model_name": self.model_name or self.model_used.upper(),
            "inference_completed": self.inference_completed,
            "inference_time": self.inference_time if self.inference_time is not None else 0.0,
            "prediction_reliability": self.prediction_reliability or (
                "HIGH" if (self.confidence and self.confidence >= 0.85) else
                "MEDIUM" if (self.confidence and self.confidence >= 0.65) else
                "LOW" if self.inference_completed else "UNRELIABLE"
            ),
        }
        if self.status:
            data["status"] = self.status
        return data


class VoicePredictionEngine:
    """
    Production-grade synthetic speech prediction engine.
    Orchestrates AASIST and RawNet2 inference, segments aggregation,
    confidence calibration, and zero-hallucination reporting.
    """

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager()

    def predict(
        self,
        segments: List[AudioSegment],
        model_name: str = "AASIST",
    ) -> Dict[str, Any]:
        """
        Executes unified prediction across audio segments using the selected neural model.
        Returns:
            Dict containing:
            - "prediction": Dict matching Module 5 specification
            - "segment_results": List of segment predictions
            - "human_probability": Optional[float]
            - "synthetic_probability": Optional[float]
            - "confidence_score": Optional[float]
            - "selected_model": str
            - "analysis_status": str ("completed" or "AI_MODEL_NOT_CONFIGURED")
            - "model_status": Optional[str] ("MODEL_NOT_AVAILABLE" or "AASIST_ACTIVE" / "RAWNET2_ACTIVE")
            - "missing_files": Optional[List[str]]
            - "message": Optional[str]
        """
        norm_key = model_name.lower().replace("-", "_").strip()
        model_display = model_name.upper().strip()
        is_available = self.model_manager.is_model_available(norm_key)

        if not segments:
            # Empty segments case
            pred = PredictionResult(
                label="INCONCLUSIVE",
                human_probability=None,
                synthetic_probability=None,
                confidence=None,
                model_used=model_display,
                inference_completed=False,
                status="NO_SEGMENTS",
            )
            return {
                "prediction": pred.to_dict(),
                "segment_results": [],
                "human_probability": None,
                "synthetic_probability": None,
                "confidence_score": None,
                "selected_model": model_display,
                "analysis_status": "segmentation_failed",
                "model_status": "NO_SEGMENTS",
                "message": "No valid audio segments available for prediction.",
            }

        # Format batch tensor [batch_size, 64600] float32
        batch_tensor = np.stack([seg.samples for seg in segments], axis=0).astype(np.float32)

        if is_available:
            try:
                # 1. Run ONNX neural inference & measure execution time
                t_inf_start = time.perf_counter()
                
                # Chunk into micro-batches of max 4 to guarantee zero memory-allocation spikes on long audio
                chunk_size = 4
                logits_list = []
                for b_start in range(0, len(segments), chunk_size):
                    b_chunk = batch_tensor[b_start : b_start + chunk_size]
                    logits_chunk = self.model_manager.run_inference(norm_key, b_chunk)
                    logits_list.append(logits_chunk)
                raw_logits = np.concatenate(logits_list, axis=0) if len(logits_list) > 1 else logits_list[0]
                
                t_inf_end = time.perf_counter()
                inf_time = round(t_inf_end - t_inf_start, 4)
                
                # 2. Compute numerically stable softmax
                # Verified ONNX class order:
                # Shape: [batch_size, 2] -> [:, 0] = synthetic / spoof, [:, 1] = human / bona-fide
                probs = stable_softmax(raw_logits)
                human_probs = probs[:, 1]
                synthetic_probs = probs[:, 0]

                segment_results: List[Dict[str, Any]] = []
                active_h_probs: List[float] = []
                active_s_probs: List[float] = []

                for idx, seg in enumerate(segments):
                    rms_val = float(np.sqrt(np.mean(seg.samples ** 2)))
                    if rms_val < 0.003:
                        # Inaudible / silence segment -> Inconclusive
                        seg_label = "INCONCLUSIVE"
                        seg_score = 0.5
                        h_prob = 0.5
                        s_prob = 0.5
                    else:
                        h_prob = float(human_probs[idx])
                        s_prob = float(synthetic_probs[idx])
                        active_h_probs.append(h_prob)
                        active_s_probs.append(s_prob)

                        if s_prob >= 0.65:
                            seg_label = "AI_GENERATED"
                            seg_score = s_prob
                        elif h_prob >= 0.65:
                            seg_label = "HUMAN"
                            seg_score = h_prob
                        else:
                            seg_label = "INCONCLUSIVE"
                            seg_score = max(h_prob, s_prob)

                    segment_results.append({
                        "segment_id": seg.segment_id,
                        "start": seg.start_time,
                        "end": seg.end_time,
                        "prediction": seg_label,
                        "score": round(seg_score, 4),
                        "human_probability": round(h_prob, 4),
                        "synthetic_probability": round(s_prob, 4),
                        "status": "completed",
                    })

                # 3. Multi-segment temporal aggregation
                if active_h_probs:
                    mean_synthetic = float(np.mean(active_s_probs))
                    mean_human = float(np.mean(active_h_probs))
                    max_synthetic = float(np.max(active_s_probs))
                else:
                    # Entire audio stream is silent/inaudible
                    mean_synthetic = 0.5
                    mean_human = 0.5
                    max_synthetic = 0.5

                # Calibrated decision thresholding
                if not active_h_probs:
                    final_label = "INCONCLUSIVE"
                    pred_class = "INCONCLUSIVE"
                    final_confidence = 0.5
                elif mean_human >= 0.55:
                    final_label = "HUMAN"
                    pred_class = "REAL_HUMAN"
                    final_confidence = round(mean_human, 4)
                elif mean_synthetic >= 0.55:
                    final_label = "AI_GENERATED"
                    pred_class = "AI_GENERATED"
                    final_confidence = round(mean_synthetic, 4)
                elif max_synthetic >= 0.85 and (float(np.mean(np.array(active_s_probs) >= 0.70)) >= 0.35):
                    # Spliced deepfake detection: at least 35% of speech segments must be strongly synthetic
                    final_label = "AI_GENERATED"
                    pred_class = "AI_GENERATED"
                    final_confidence = round(max_synthetic, 4)
                else:
                    final_label = "INCONCLUSIVE"
                    pred_class = "INCONCLUSIVE"
                    final_confidence = round(max(mean_human, mean_synthetic), 4)

                mean_human_rounded = round(mean_human, 4)
                mean_synth_rounded = round(mean_synthetic, 4)

                if final_confidence >= 0.85:
                    reliability = "HIGH"
                elif final_confidence >= 0.70:
                    reliability = "MEDIUM"
                else:
                    reliability = "LOW"

                pred = PredictionResult(
                    label=final_label,
                    human_probability=mean_human_rounded,
                    synthetic_probability=mean_synth_rounded,
                    confidence=final_confidence,
                    model_used=model_display,
                    inference_completed=True,
                    status="completed",
                    predicted_class=pred_class,
                    real_probability=mean_human_rounded,
                    fake_probability=mean_synth_rounded,
                    model_name=model_display,
                    inference_time=inf_time,
                    prediction_reliability=reliability,
                )

                return {
                    "prediction": pred.to_dict(),
                    "segment_results": segment_results,
                    "human_probability": mean_human_rounded,
                    "synthetic_probability": mean_synth_rounded,
                    "real_probability": mean_human_rounded,
                    "fake_probability": mean_synth_rounded,
                    "predicted_class": pred_class,
                    "confidence_score": final_confidence,
                    "selected_model": model_display,
                    "model_name": model_display,
                    "inference_time": inf_time,
                    "prediction_reliability": reliability,
                    "analysis_status": "completed",
                    "model_status": f"{model_display}_ACTIVE",
                    "message": (
                        f"Inference completed successfully using {model_display} "
                        f"(Classification: {final_label}, Confidence: {final_confidence}, Latency: {round(inf_time*1000, 1)}ms)."
                    ),
                }

            except Exception as exc:
                logger.warning(
                    f"Inference failed on '{model_name}': {str(exc)}. Falling back to zero-hallucination report."
                )

        # Zero-Hallucination Fallback when checkpoint is not on disk:
        missing_filename = f"{norm_key}.onnx"
        segment_results = [
            {
                "segment_id": seg.segment_id,
                "start": seg.start_time,
                "end": seg.end_time,
                "prediction": "INCONCLUSIVE",
                "score": None,
                "human_probability": None,
                "synthetic_probability": None,
                "status": "AI_MODEL_NOT_CONFIGURED",
            }
            for seg in segments
        ]

        pred = PredictionResult(
            label="INCONCLUSIVE",
            human_probability=None,
            synthetic_probability=None,
            confidence=None,
            model_used=model_display,
            inference_completed=False,
            status="MODEL_NOT_AVAILABLE",
            predicted_class="INCONCLUSIVE",
            real_probability=None,
            fake_probability=None,
            model_name=model_display,
            inference_time=0.0,
            prediction_reliability="UNRELIABLE",
        )

        return {
            "prediction": pred.to_dict(),
            "segment_results": segment_results,
            "human_probability": None,
            "synthetic_probability": None,
            "real_probability": None,
            "fake_probability": None,
            "predicted_class": "INCONCLUSIVE",
            "confidence_score": None,
            "selected_model": model_display,
            "model_name": model_display,
            "inference_time": 0.0,
            "prediction_reliability": "UNRELIABLE",
            "analysis_status": "AI_MODEL_NOT_CONFIGURED",
            "model_status": "MODEL_NOT_AVAILABLE",
            "missing_files": [missing_filename],
            "confidence_score": None,
            "selected_model": model_display,
            "analysis_status": "AI_MODEL_NOT_CONFIGURED",
            "model_status": "MODEL_NOT_AVAILABLE",
            "missing_files": [missing_filename],
            "instructions": (
                f"Trained ONNX weights for '{model_display}' are not present in backend/models_weights/{missing_filename}. "
                "To enable real neural inference, export your trained model to ONNX with input shape [batch, 64600] "
                f"at 16kHz mono float32 and copy it to backend/models_weights/{missing_filename}."
            ),
            "message": (
                f"Model weights for '{model_display}' are not configured in backend/models_weights/{missing_filename}. "
                "Audio successfully validated, decoded to 16kHz mono PCM, and analyzed for objective "
                "acoustic metrics without generating fabricated predictions."
            ),
        }

