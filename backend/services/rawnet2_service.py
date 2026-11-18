"""
VOICEGUARD AI — RawNet2 Anti-Spoofing Service
Production-grade neural inference service for RawNet2 synthetic voice detection.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.

Architecture:
- Front-End: SincNet analytical filterbank (20 filters, 1024 length)
- Residual Blocks: 6 residual blocks with Filter-wise Feature Map (FMS) attention
- Recurrent: 3-layer GRU (1024 hidden units)
- Classification: 1024 -> 1024 -> 2 classes
- Output Classes: Index 0 = Bona-fide (Real Human), Index 1 = Spoof (Synthetic AI)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

logger = logging.getLogger("voiceguard.rawnet2_service")

MODELS_DIR = Path(__file__).resolve().parent.parent / "models_weights"
RAWNET2_ONNX_PATH = MODELS_DIR / "rawnet2.onnx"
EXPECTED_SAMPLES: int = 64600
SAMPLE_RATE: int = 16000


class RawNet2ModelError(Exception):
    """Raised when RawNet2 model loading, validation, or checkpoint check fails."""
    pass


class RawNet2InferenceError(Exception):
    """Raised when RawNet2 neural inference fails at runtime."""
    pass


@dataclass
class RawNet2InferenceResult:
    """Structured result of RawNet2 neural inference."""
    predicted_class: str  # "REAL_HUMAN", "AI_GENERATED", or "INCONCLUSIVE"
    real_probability: float
    fake_probability: float
    confidence: float
    raw_logits: List[float]
    inference_time_ms: float
    prediction_reliability: str  # "HIGH", "MEDIUM", "LOW"
    model_name: str = "RAWNET2"
    model_status: str = "RAWNET2_ACTIVE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predicted_class": self.predicted_class,
            "real_probability": round(self.real_probability, 4),
            "fake_probability": round(self.fake_probability, 4),
            "human_probability": round(self.real_probability, 4),
            "synthetic_probability": round(self.fake_probability, 4),
            "confidence": round(self.confidence, 4),
            "raw_logits": [round(float(l), 4) for l in self.raw_logits],
            "inference_time": round(self.inference_time_ms / 1000.0, 4),
            "inference_time_ms": round(self.inference_time_ms, 2),
            "prediction_reliability": self.prediction_reliability,
            "model_name": self.model_name,
            "model_status": self.model_status,
        }


def stable_softmax(logits: np.ndarray) -> np.ndarray:
    """Numerically stable softmax along last dimension."""
    shifted = logits - np.max(logits, axis=-1, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


class RawNet2Service:
    """
    Manages RawNet2 model loading, validation, and production inference.
    Thread-safe execution using ONNX Runtime with CPU/CUDA provider selection.
    """

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.model_path = Path(model_path) if model_path else RAWNET2_ONNX_PATH
        self._session: Optional[Any] = None
        self._input_name: Optional[str] = None
        self._output_name: Optional[str] = None
        self._device: str = "UNAVAILABLE"

    def is_available(self) -> bool:
        """Checks whether the RawNet2 ONNX model file exists and is non-empty."""
        return self.model_path.is_file() and self.model_path.stat().st_size > 1024

    def get_model_info(self) -> Dict[str, Any]:
        """Returns metadata about the RawNet2 model."""
        exists = self.is_available()
        size_bytes = self.model_path.stat().st_size if exists else 0
        return {
            "model_name": "RAWNET2",
            "installed": exists,
            "model_path": str(self.model_path),
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "expected_samples": EXPECTED_SAMPLES,
            "sample_rate": SAMPLE_RATE,
            "input_shape": ["batch_size", EXPECTED_SAMPLES],
            "output_classes": ["REAL_HUMAN", "AI_GENERATED"],
            "session_active": self._session is not None,
            "device": self._device,
        }

    def initialize_session(self) -> Any:
        """Loads and caches the ONNX Runtime session."""
        if self._session is not None:
            return self._session

        if ort is None:
            raise RawNet2ModelError("onnxruntime is not installed in the environment.")

        if not self.is_available():
            raise RawNet2ModelError(
                f"RawNet2 ONNX checkpoint not found at: {self.model_path}. "
                "Export checkpoint using scripts/export_rawnet2_to_onnx.py first."
            )

        try:
            available_providers = ort.get_available_providers()
            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if "CUDAExecutionProvider" in available_providers
                else ["CPUExecutionProvider"]
            )

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = min(4, os.cpu_count() or 1)
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.log_severity_level = 3

            session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=providers,
            )
            self._session = session
            self._input_name = session.get_inputs()[0].name
            self._output_name = session.get_outputs()[0].name
            self._device = providers[0]
            logger.info(
                f"RawNet2 ONNX session initialized successfully ({providers[0]}). "
                f"Input: {self._input_name}, Output: {self._output_name}"
            )
            return self._session
        except Exception as e:
            logger.error(f"Failed to initialize RawNet2 ONNX session: {e}")
            raise RawNet2ModelError(f"RawNet2 initialization error: {e}") from e

    def predict(self, waveform: np.ndarray) -> RawNet2InferenceResult:
        """
        Runs RawNet2 anti-spoofing inference on an input audio waveform.
        Accepts 1D array of 64,600 samples or 2D array [batch, 64600].
        """
        session = self.initialize_session()

        arr = np.asarray(waveform, dtype=np.float32)
        if arr.ndim == 1:
            arr = np.expand_dims(arr, axis=0)

        if arr.ndim != 2:
            raise RawNet2InferenceError(
                f"Invalid waveform dimensions: {arr.shape}. Expected [64600] or [batch, 64600]."
            )

        batch_size, samples = arr.shape
        if samples != EXPECTED_SAMPLES:
            raise RawNet2InferenceError(
                f"Invalid sample length {samples}. RawNet2 expects exactly {EXPECTED_SAMPLES} samples (at 16 kHz)."
            )

        try:
            t0 = time.perf_counter()
            outputs = session.run(None, {self._input_name: arr})
            t1 = time.perf_counter()
            latency_ms = (t1 - t0) * 1000.0

            logits = np.array(outputs[0], dtype=np.float32)
            if logits.ndim == 1 and batch_size == 1:
                logits = np.expand_dims(logits, axis=0)

            # Compute stable softmax: Index 0 = Synthetic / Spoof, Index 1 = Real Human
            probs = stable_softmax(logits)

            # For batch, aggregate or take first
            real_prob = float(np.mean(probs[:, 1]))
            fake_prob = float(np.mean(probs[:, 0]))

            # Calibrated classification
            if fake_prob >= 0.65:
                pred_class = "AI_GENERATED"
                conf = fake_prob
            elif real_prob >= 0.65:
                pred_class = "REAL_HUMAN"
                conf = real_prob
            else:
                pred_class = "INCONCLUSIVE"
                conf = max(real_prob, fake_prob)

            if conf >= 0.85:
                reliability = "HIGH"
            elif conf >= 0.70:
                reliability = "MEDIUM"
            else:
                reliability = "LOW"

            return RawNet2InferenceResult(
                predicted_class=pred_class,
                real_probability=real_prob,
                fake_probability=fake_prob,
                confidence=conf,
                raw_logits=logits[0].tolist(),
                inference_time_ms=latency_ms,
                prediction_reliability=reliability,
            )

        except Exception as e:
            logger.error(f"RawNet2 inference forward pass failed: {e}")
            raise RawNet2InferenceError(f"RawNet2 forward execution error: {e}") from e
