"""
VOICEGUARD AI — AI Model Manager & Runtime Provider
Manages neural anti-spoofing checkpoints (AASIST / RawNet2 / ECAPA-TDNN),
device selection (CUDA / CPU), session caching, and tensor input validation.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    ort = None

logger = logging.getLogger("voiceguard.model_manager")
MODELS_DIR = Path(__file__).resolve().parent.parent / "models_weights"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_MODELS: Dict[str, str] = {
    "aasist": "aasist.onnx",
    "rawnet2": "rawnet2.onnx",
    "ecapa_tdnn": "ecapa_tdnn.onnx",
}

EXPECTED_INPUT_SAMPLES: int = 64600  # AASIST input tensor width


class ModelNotFoundError(Exception):
    """Raised when requested model checkpoint does not exist on disk."""
    pass


class ModelInferenceError(Exception
):
    """Raised when runtime neural inference fails."""
    pass


class ModelManager:
    """
    Thread-safe Singleton Model Manager caching ONNXRuntime sessions
    with automated CUDA/CPU execution provider selection.
    """

    _instance: Optional[ModelManager] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> ModelManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self) -> None:
        self.models_dir = MODELS_DIR
        self._sessions: Dict[str, Any] = {}
        self._session_lock = threading.Lock()
        self.device = self._select_execution_device()

    def _select_execution_device(self) -> str:
        """Determines best available ONNX Runtime execution provider."""
        if ort is None:
            return "UNAVAILABLE"

        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            # Test CUDA provider instantiation
            try:
                opts = ort.SessionOptions()
                opts.log_severity_level = 3
                return "CUDAExecutionProvider"
            except Exception:
                return "CPUExecutionProvider"
        return "CPUExecutionProvider"

    def get_available_providers(self) -> List[str]:
        if self.device == "CUDAExecutionProvider":
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def is_model_available(self, model_key: str = "aasist") -> bool:
        """Checks if the ONNX checkpoint physically exists on server disk."""
        key = model_key.lower().replace("-", "_")
        filename = SUPPORTED_MODELS.get(key, f"{key}.onnx")
        model_path = self.models_dir / filename
        return model_path.is_file() and model_path.stat().st_size > 1024

    def get_model_path(self, model_key: str = "aasist") -> Optional[Path]:
        key = model_key.lower().replace("-", "_")
        filename = SUPPORTED_MODELS.get(key, f"{key}.onnx")
        path = self.models_dir / filename
        return path if path.is_file() else None

    def get_session(self, model_key: str = "aasist") -> Optional[Any]:
        """
        Retrieves or initializes a cached ONNX InferenceSession for the model.
        Returns None if checkpoint is not installed on disk.
        """
        if ort is None:
            return None

        key = model_key.lower().replace("-", "_")
        with self._session_lock:
            if key in self._sessions:
                return self._sessions[key]

            model_path = self.get_model_path(key)
            if not model_path:
                return None

            try:
                providers = self.get_available_providers()
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = min(4, os.cpu_count() or 1)
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

                session = ort.InferenceSession(
                    str(model_path),
                    sess_options=opts,
                    providers=providers,
                )
                self._sessions[key] = session
                logger.info(f"Loaded ONNX model '{key}' successfully with provider {providers[0]}")
                return session
            except Exception as e:
                logger.error(f"Failed to load ONNX model '{key}': {str(e)}")
                return None

    def run_inference(self, model_key: str, tensor: np.ndarray) -> np.ndarray:
        """
        Executes model inference on a batch of audio windows.
        Expected tensor shape: [batch_size, 64600] float32.
        Returns raw logits array [batch_size, 2].
        """
        session = self.get_session(model_key)
        if session is None:
            raise ModelNotFoundError(
                f"Model checkpoint for '{model_key}' is not installed in '{self.models_dir}'."
            )

        if tensor.ndim == 1:
            tensor = np.expand_dims(tensor, axis=0)

        if tensor.ndim != 2:
            raise ModelInferenceError(
                f"Invalid input tensor dimensions {tensor.shape}. Expected 2D tensor [batch_size, 64600]."
            )

        batch_size, samples = tensor.shape
        if samples != EXPECTED_INPUT_SAMPLES:
            raise ModelInferenceError(
                f"Invalid sample length {samples}. Model '{model_key}' requires exactly {EXPECTED_INPUT_SAMPLES} samples."
            )

        input_tensor = tensor.astype(np.float32)

        try:
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: input_tensor})
            logits = np.array(outputs[0], dtype=np.float32)
            if logits.ndim == 1 and batch_size == 1:
                logits = np.expand_dims(logits, axis=0)
            return logits
        except Exception as e:
            raise ModelInferenceError(f"Inference execution failed on '{model_key}': {str(e)}") from e

    def get_status_report(self) -> Dict[str, Any]:
        """Telemetry report on model availability and device execution."""
        models_status = {}
        for key, fname in SUPPORTED_MODELS.items():
            path = self.models_dir / fname
            exists = path.is_file()
            size = path.stat().st_size if exists else 0
            models_status[key] = {
                "installed": exists,
                "filename": fname,
                "size_bytes": size,
                "active_session": key in self._sessions,
            }

        return {
            "device": self.device,
            "onnxruntime_available": ort is not None,
            "onnxruntime_version": ort.__version__ if ort else None,
            "models_directory": str(self.models_dir),
            "models": models_status,
        }

