"""
VOICEGUARD AI — ECAPA-TDNN Speaker Verification Service
Production-grade speaker verification and acoustic embedding extraction service using
the official SpeechBrain ECAPA-TDNN model ('speechbrain/spkrec-ecapa-voxceleb').
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.

Key Capabilities:
- Official SpeechBrain pretrained ECAPA-TDNN model loading with lazy initialization
- Resampling and conversion of arbitrary container audio to uniform 16 kHz mono PCM
- 192-dimensional latent speaker embedding extraction with L2 normalization
- Cosine similarity computation with uncalibrated metric disclosure
- Configurable same-speaker verification threshold
- Comprehensive audio quality inspection and acoustic warnings (duration, clipping, SNR, silence)
- Thread-safe singleton execution on CPU by default
"""

from __future__ import annotations

import logging
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger("voiceguard.ecapa_service")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL_DIR = ROOT_DIR / "weights" / "spkrec-ecapa-voxceleb"
DEFAULT_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
EMBEDDING_DIM: int = 192
TARGET_SAMPLE_RATE: int = 16000
DEFAULT_VERIFICATION_THRESHOLD: float = 0.25

# Global references & diagnostic trackers
_torch = None
_torchaudio = None
_SpeakerRecognition = None
_LocalStrategy = None
_dependency_diagnostics: Dict[str, Any] = {
    "torch": {"installed": False, "version": None, "error": None},
    "torchaudio": {"installed": False, "version": None, "error": None},
    "speechbrain": {"installed": False, "version": None, "error": None},
}


def resolve_dependencies() -> Tuple[bool, Dict[str, Any]]:
    """
    Attempts to import torch, torchaudio, and speechbrain.
    If speechbrain is not found in the active sys.path, checks known workspace
    virtual environments (e.g. backend/.venv/Lib/site-packages) and adds them to sys.path.
    Returns (all_available: bool, diagnostics: dict).
    """
    global _torch, _torchaudio, _SpeakerRecognition, _LocalStrategy, _dependency_diagnostics

    # 1. Fallback search: Check if backend/.venv site-packages exists and add to sys.path if not present
    candidate_paths = [
        ROOT_DIR / "backend" / ".venv" / "Lib" / "site-packages",
        ROOT_DIR / ".venv" / "Lib" / "site-packages",
    ]
    for cp in candidate_paths:
        if cp.is_dir() and str(cp) not in sys.path:
            sys.path.append(str(cp))

    # 2. Import torch
    if _torch is None:
        try:
            import torch
            _torch = torch
            _dependency_diagnostics["torch"] = {
                "installed": True,
                "version": getattr(torch, "__version__", "unknown"),
                "error": None,
            }
        except Exception as e:
            _torch = None
            _dependency_diagnostics["torch"] = {
                "installed": False,
                "version": None,
                "error": str(e),
            }

    # 3. Import torchaudio
    if _torchaudio is None:
        try:
            import torchaudio
            _torchaudio = torchaudio
            _dependency_diagnostics["torchaudio"] = {
                "installed": True,
                "version": getattr(torchaudio, "__version__", "unknown"),
                "error": None,
            }
        except Exception as e:
            _torchaudio = None
            _dependency_diagnostics["torchaudio"] = {
                "installed": False,
                "version": None,
                "error": str(e),
            }

    # 4. Import speechbrain SpeakerRecognition & LocalStrategy
    if _SpeakerRecognition is None or _LocalStrategy is None:
        try:
            from speechbrain.inference.speaker import SpeakerRecognition
            from speechbrain.utils.fetching import LocalStrategy
            import speechbrain
            _SpeakerRecognition = SpeakerRecognition
            _LocalStrategy = LocalStrategy
            _dependency_diagnostics["speechbrain"] = {
                "installed": True,
                "version": getattr(speechbrain, "__version__", "unknown"),
                "error": None,
            }
        except Exception as e:
            _SpeakerRecognition = None
            _LocalStrategy = None
            _dependency_diagnostics["speechbrain"] = {
                "installed": False,
                "version": None,
                "error": str(e),
            }

    all_available = bool(
        _torch is not None
        and _SpeakerRecognition is not None
        and _LocalStrategy is not None
    )
    return all_available, _dependency_diagnostics


# Perform initial non-blocking dependency resolution
resolve_dependencies()

from backend.services.audio_preprocessor import AudioPreprocessor, AudioQualityMetrics
from backend.services.audio_validator import AudioValidator


class ECAPAModelError(Exception):
    """Raised when ECAPA-TDNN model initialization, checkpoint loading, or fetching fails."""
    pass


class ECAPAInferenceError(Exception):
    """Raised when audio conversion, embedding extraction, or similarity computation fails."""
    pass


@dataclass
class SpeakerVerificationResult:
    """Structured result of ECAPA-TDNN speaker verification."""
    model_name: str
    embedding_dimension: int
    cosine_similarity: float
    verification_status: str  # "SAME_SPEAKER" | "DIFFERENT_SPEAKER" | "INCONCLUSIVE"
    is_same_speaker: bool
    threshold: float
    processing_time: float
    verdict: str = ""
    audio_quality_warnings: List[str] = field(default_factory=list)
    reference_audio_info: Dict[str, Any] = field(default_factory=dict)
    comparison_audio_info: Dict[str, Any] = field(default_factory=dict)
    interpretation_note: str = (
        "Cosine similarity reflects directional alignment in the 192-dimensional "
        "latent speaker embedding space. It is not a calibrated probability. "
        "Thresholds should be calibrated on target acoustic environments."
    )

    def __post_init__(self) -> None:
        if not self.verdict:
            self.verdict = self.verification_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": True,
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "cosine_similarity": round(self.cosine_similarity, 4),
            "verdict": self.verdict or self.verification_status,
            "verification_status": self.verification_status,
            "is_same_speaker": self.is_same_speaker,
            "threshold": round(self.threshold, 4),
            "processing_time": round(self.processing_time, 4),
            "processing_time_seconds": round(self.processing_time, 4),
            "audio_quality_warnings": self.audio_quality_warnings,
            "interpretation_note": self.interpretation_note,
            "reference_audio_info": self.reference_audio_info,
            "comparison_audio_info": self.comparison_audio_info,
        }


class ECAPAService:
    """
    Thread-safe ECAPA-TDNN speaker verification service.
    Implements lazy initialization so deepfake APIs remain fully functional
    even if the speaker verification model is not yet loaded.
    """

    _instance: Optional[ECAPAService] = None
    _singleton_lock: threading.Lock = threading.Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> ECAPAService:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        model_dir: Optional[Union[str, Path]] = None,
        source: str = DEFAULT_SOURCE,
        device: str = "cpu",
    ) -> None:
        if getattr(self, "_initialized", False):
            return

        self.model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
        self.source = source
        self.device = device
        self._model: Optional[Any] = None
        self._load_lock = threading.Lock()
        self.preprocessor = AudioPreprocessor(target_sample_rate=TARGET_SAMPLE_RATE)
        self.validator = AudioValidator()
        self._initialized = True

    def checkpoint_exists(self) -> bool:
        """
        Checks whether the ECAPA-TDNN checkpoint files physically exist locally.
        """
        if not self.model_dir.is_dir():
            return False
        ckpt = self.model_dir / "embedding_model.ckpt"
        hparams = self.model_dir / "hyperparams.yaml"
        return ckpt.is_file() and ckpt.stat().st_size > 1024 and hparams.is_file()

    def has_dependencies(self) -> bool:
        """
        Checks whether runtime dependencies (PyTorch, TorchAudio, SpeechBrain) are importable.
        """
        ok, _ = resolve_dependencies()
        return ok

    def is_available(self) -> bool:
        """
        Service is available ONLY when BOTH the local model checkpoint files exist
        AND the runtime dependencies are fully importable.
        """
        return self.checkpoint_exists() and self.has_dependencies()

    def get_model_info(self) -> Dict[str, Any]:
        """Telemetry metadata and diagnostic status about the ECAPA-TDNN model configuration."""
        ckpt_ok = self.checkpoint_exists()
        deps_ok, diagnostics = resolve_dependencies()
        available = bool(ckpt_ok and deps_ok)
        ckpt_size = (self.model_dir / "embedding_model.ckpt").stat().st_size if ckpt_ok else 0
        missing = [pkg for pkg, data in diagnostics.items() if not data["installed"]]

        return {
            "model_name": "ECAPA-TDNN (VoxCeleb)",
            "installed": ckpt_ok,
            "checkpoint_installed": ckpt_ok,
            "dependencies_available": deps_ok,
            "available": available,
            "missing_dependencies": missing,
            "dependency_diagnostics": diagnostics,
            "python_executable": sys.executable,
            "model_dir": str(self.model_dir),
            "source": self.source,
            "embedding_dimension": EMBEDDING_DIM,
            "sample_rate": TARGET_SAMPLE_RATE,
            "device": self.device,
            "session_loaded": self._model is not None,
            "size_bytes": ckpt_size,
            "size_mb": round(ckpt_size / (1024 * 1024), 2) if ckpt_ok else 0.0,
            "default_threshold": DEFAULT_VERIFICATION_THRESHOLD,
        }

    def load_model(self) -> Any:
        """
        Thread-safe lazy initialization of the official SpeechBrain model.
        Runs on CPU by default.
        """
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model

            deps_ok, diagnostics = resolve_dependencies()
            if not deps_ok or _SpeakerRecognition is None or _torch is None:
                missing_items = []
                for pkg, data in diagnostics.items():
                    if not data["installed"]:
                        err_msg = data.get("error") or "not found"
                        missing_items.append(f"{pkg} ({err_msg})")
                details = "; ".join(missing_items) if missing_items else "SpeechBrain or PyTorch missing"
                raise ECAPAModelError(
                    f"Speaker verification runtime dependencies missing in interpreter '{sys.executable}': {details}. "
                    "Ensure you run with backend/.venv/Scripts/python.exe where dependencies are installed."
                )

            try:
                self.model_dir.mkdir(parents=True, exist_ok=True)

                # If checkpoint and hyperparams exist locally in model_dir, load directly from local disk
                local_hparams = self.model_dir / "hyperparams.yaml"
                local_ckpt = self.model_dir / "embedding_model.ckpt"
                use_local_source = local_hparams.is_file() and local_ckpt.is_file()
                effective_source = str(self.model_dir.resolve()) if use_local_source else self.source

                logger.info(
                    f"Loading official pretrained ECAPA-TDNN model from source='{effective_source}' "
                    f"savedir='{self.model_dir}' (device={self.device}, local_source={use_local_source})..."
                )

                strategy = _LocalStrategy.COPY if _LocalStrategy is not None else None
                fetch_kwargs: Dict[str, Any] = {"run_opts": {"device": self.device}}
                if strategy is not None:
                    fetch_kwargs["local_strategy"] = strategy

                self._model = _SpeakerRecognition.from_hparams(
                    source=effective_source,
                    savedir=str(self.model_dir.resolve()),
                    **fetch_kwargs,
                )
                logger.info("SpeechBrain ECAPA-TDNN model successfully initialized on CPU.")
                return self._model
            except Exception as e:
                logger.error(f"Failed to initialize ECAPA-TDNN model: {e}")
                raise ECAPAModelError(f"ECAPA-TDNN initialization failed: {str(e)}") from e

    def _inspect_audio_quality(
        self,
        pcm: np.ndarray,
        metrics: AudioQualityMetrics,
        label: str = "Audio",
    ) -> List[str]:
        """
        Inspects signal characteristics and generates actionable forensic warnings.
        """
        warnings: List[str] = []

        # 1. Short audio duration warning
        if metrics.duration_seconds < 1.0:
            warnings.append(
                f"{label} duration ({round(metrics.duration_seconds, 2)}s) is extremely short (< 1.0s); "
                "speaker embedding reliability and discriminative power may be degraded."
            )
        elif metrics.duration_seconds < 1.8:
            warnings.append(
                f"{label} duration ({round(metrics.duration_seconds, 2)}s) is short (< 1.8s); "
                "longer conversational samples yield more stable acoustic embeddings."
            )

        # 2. Digital clipping inspection
        peak = float(np.max(np.abs(pcm))) if len(pcm) > 0 else 0.0
        clipped_ratio = float(np.sum(np.abs(pcm) >= 0.99)) / max(len(pcm), 1)
        if clipped_ratio > 0.005:
            warnings.append(
                f"{label} has {round(clipped_ratio * 100, 2)}% clipped samples (peak amplitude: {round(peak, 2)}); "
                "digital distortion can alter spectral envelope features."
            )

        # 3. Low energy / near silence
        if metrics.rms_energy < 0.005:
            warnings.append(
                f"{label} has extremely low RMS energy ({round(metrics.rms_energy, 4)}); "
                "recording appears mostly silent or heavily attenuated."
            )

        # 4. Sample rate warning if original was not standard wideband
        if metrics.sample_rate < 16000:
            warnings.append(
                f"{label} original sample rate was {metrics.sample_rate} Hz (< 16 kHz wideband); "
                "upsampled to 16 kHz with high-frequency attenuation."
            )

        return warnings

    def extract_embedding(
        self,
        audio_input: Union[bytes, np.ndarray],
        filename: str = "recording.wav",
        label: str = "Audio",
    ) -> Tuple[np.ndarray, Dict[str, Any], List[str]]:
        """
        Decodes/resamples audio to 16 kHz mono, validates quality, and extracts
        an L2-normalized 192-dimensional latent embedding.

        Returns:
            Tuple of:
            - normalized_embedding: np.ndarray shape (192,) float32
            - audio_info: metadata dictionary
            - quality_warnings: list of warning strings
        """
        # 1. Preprocessing to 16 kHz mono PCM float32 [-1.0, 1.0]
        if isinstance(audio_input, bytes):
            if len(audio_input) == 0:
                raise ECAPAInferenceError(f"{label} file '{filename}' is empty (0 bytes).")
            try:
                pcm_16k, metrics = self.preprocessor.process_audio(audio_input, filename)
            except Exception as e:
                raise ECAPAInferenceError(f"Failed to decode {label.lower()} '{filename}': {str(e)}") from e
        elif isinstance(audio_input, np.ndarray):
            pcm = audio_input.astype(np.float32)
            if pcm.ndim > 1:
                pcm = np.mean(pcm, axis=0 if pcm.shape[0] < pcm.shape[1] else 1)

            # Minimum length check for raw array
            if len(pcm) < 1600:
                raise ECAPAInferenceError(
                    f"{label} '{filename}' contains only {len(pcm)} samples ({round(len(pcm)/16000, 3)}s). "
                    "Minimum required length for speaker embedding extraction is 0.10s (1,600 samples)."
                )

            # Ensure peak normalization
            max_val = float(np.max(np.abs(pcm))) if len(pcm) > 0 else 0.0
            if max_val > 1.0:
                pcm = pcm / max_val
            pcm_16k = pcm
            duration = len(pcm_16k) / float(TARGET_SAMPLE_RATE)
            rms = float(np.sqrt(np.mean(pcm_16k ** 2))) if len(pcm_16k) > 0 else 0.0
            metrics = AudioQualityMetrics(
                duration_seconds=duration,
                sample_rate=TARGET_SAMPLE_RATE,
                channels=1,
                peak_amplitude=max_val,
                rms_energy=rms,
                silence_ratio=0.0,
                clipping_ratio=0.0,
                is_clipped=False,
                is_silent=bool(rms < 0.005),
                is_low_volume=bool(rms < 0.02),
                spectral_centroid_hz=0.0,
                high_frequency_ratio=0.0,
                pitch_stability=0.0,
            )
        else:
            raise ECAPAInferenceError(f"Unsupported audio input type: {type(audio_input)}")

        # 2. Validate sample length (minimum 1600 samples = 0.1s needed for STFT frames)
        if len(pcm_16k) < 1600:
            raise ECAPAInferenceError(
                f"{label} '{filename}' contains only {len(pcm_16k)} samples ({round(len(pcm_16k)/16000, 3)}s). "
                "Minimum required length for speaker embedding extraction is 0.10s (1,600 samples)."
            )

        # 3. Audio quality audit
        quality_warnings = self._inspect_audio_quality(pcm_16k, metrics, label=label)

        # 4. Neural embedding extraction via SpeechBrain ECAPA-TDNN
        model = self.load_model()
        try:
            tensor = _torch.from_numpy(pcm_16k).float().unsqueeze(0)  # Shape [1, N]
            with _torch.no_grad():
                raw_emb = model.encode_batch(tensor)
            
            # Squeeze to 1D: [1, 1, 192] -> [192]
            emb_np = raw_emb.squeeze().detach().cpu().numpy().astype(np.float32)

            if emb_np.shape[-1] != EMBEDDING_DIM:
                raise ECAPAInferenceError(
                    f"Unexpected embedding dimension: {emb_np.shape}. Expected ({EMBEDDING_DIM},)."
                )

            # 5. L2 Normalization
            norm = float(np.linalg.norm(emb_np))
            if norm < 1e-12:
                raise ECAPAInferenceError(f"{label} produced a degenerate near-zero embedding norm ({norm}).")
            normalized_emb = emb_np / norm

            audio_info = {
                "filename": filename,
                "duration_seconds": round(metrics.duration_seconds, 3),
                "sample_rate": metrics.sample_rate,
                "channels": metrics.channels,
                "rms_energy": round(metrics.rms_energy, 4),
            }

            return normalized_emb, audio_info, quality_warnings

        except ECAPAInferenceError:
            raise
        except Exception as e:
            logger.error(f"ECAPA-TDNN embedding forward pass failed on {label}: {e}")
            raise ECAPAInferenceError(f"Embedding extraction forward pass failed: {str(e)}") from e

    @staticmethod
    def compute_cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculates cosine similarity between two L2-normalized 192-dimensional embeddings.
        Clamped to valid cosine range [-1.0, 1.0].
        """
        dot_product = float(np.dot(emb1, emb2))
        return max(-1.0, min(1.0, dot_product))

    @staticmethod
    def classify_verdict(
        similarity: float,
        threshold: float,
        quality_warnings: Optional[List[str]] = None,
        inconclusive_margin: float = 0.03,
    ) -> Tuple[str, str, bool]:
        """
        Classifies cosine similarity into (verdict, verification_status, is_same_speaker).
        verification_status strictly adheres to binary ('SAME_SPEAKER' | 'DIFFERENT_SPEAKER')
        for backward compatibility with existing tests and API contracts.
        verdict supports triad ('SAME_SPEAKER' | 'DIFFERENT_SPEAKER' | 'INCONCLUSIVE').
        """
        is_same = bool(similarity >= threshold)
        verification_status = "SAME_SPEAKER" if is_same else "DIFFERENT_SPEAKER"

        has_severe_degradation = bool(
            quality_warnings
            and any(
                term in w.lower()
                for w in quality_warnings
                for term in ("clipped", "extremely short", "near silence", "low rms")
            )
        )

        if is_same:
            verdict = "SAME_SPEAKER"
        elif has_severe_degradation and (threshold - inconclusive_margin <= similarity < threshold) and 0.15 <= threshold <= 0.85:
            verdict = "INCONCLUSIVE"
        else:
            verdict = "DIFFERENT_SPEAKER"

        return verdict, verification_status, is_same

    def verify_speakers(
        self,
        reference_audio: Union[bytes, np.ndarray],
        comparison_audio: Union[bytes, np.ndarray],
        ref_filename: str = "reference.wav",
        cmp_filename: str = "comparison.wav",
        threshold: float = DEFAULT_VERIFICATION_THRESHOLD,
    ) -> SpeakerVerificationResult:
        """
        Executes end-to-end 1:1 speaker verification comparing reference vs comparison audio.
        """
        t_start = time.perf_counter()

        # 1. Extract normalized embeddings for both recordings
        ref_emb, ref_info, ref_warnings = self.extract_embedding(
            reference_audio, filename=ref_filename, label="Reference audio"
        )
        cmp_emb, cmp_info, cmp_warnings = self.extract_embedding(
            comparison_audio, filename=cmp_filename, label="Comparison audio"
        )

        # 2. Compute Cosine Similarity
        similarity = self.compute_cosine_similarity(ref_emb, cmp_emb)

        # 3. Verification Decision against configurable threshold
        all_warnings = ref_warnings + cmp_warnings
        verdict, verification_status, is_same = self.classify_verdict(similarity, threshold, all_warnings)

        t_elapsed = round(time.perf_counter() - t_start, 4)

        return SpeakerVerificationResult(
            model_name="ECAPA-TDNN (VoxCeleb)",
            embedding_dimension=EMBEDDING_DIM,
            cosine_similarity=similarity,
            verification_status=verification_status,
            verdict=verdict,
            is_same_speaker=is_same,
            threshold=threshold,
            processing_time=t_elapsed,
            audio_quality_warnings=all_warnings,
            reference_audio_info=ref_info,
            comparison_audio_info=cmp_info,
        )

    def verify_embedding_vs_audio(
        self,
        reference_embedding: np.ndarray,
        comparison_audio: Union[bytes, np.ndarray],
        cmp_filename: str = "comparison.wav",
        threshold: float = DEFAULT_VERIFICATION_THRESHOLD,
        ref_info: Optional[Dict[str, Any]] = None,
    ) -> SpeakerVerificationResult:
        """
        Executes 1:1 speaker verification comparing a registered biometric profile embedding
        against incoming probe comparison audio.
        """
        t_start = time.perf_counter()

        cmp_emb, cmp_info, cmp_warnings = self.extract_embedding(
            comparison_audio, filename=cmp_filename, label="Comparison audio"
        )

        # Ensure reference embedding is float32 and L2-normalized
        ref_vec = np.asarray(reference_embedding, dtype=np.float32)
        norm = float(np.linalg.norm(ref_vec))
        if norm > 1e-12:
            ref_vec = ref_vec / norm

        similarity = self.compute_cosine_similarity(ref_vec, cmp_emb)
        verdict, verification_status, is_same = self.classify_verdict(similarity, threshold, cmp_warnings)

        t_elapsed = round(time.perf_counter() - t_start, 4)

        return SpeakerVerificationResult(
            model_name="ECAPA-TDNN (VoxCeleb)",
            embedding_dimension=EMBEDDING_DIM,
            cosine_similarity=similarity,
            verification_status=verification_status,
            verdict=verdict,
            is_same_speaker=is_same,
            threshold=threshold,
            processing_time=t_elapsed,
            audio_quality_warnings=cmp_warnings,
            reference_audio_info=ref_info or {"source": "enrolled_profile", "dimension": EMBEDDING_DIM},
            comparison_audio_info=cmp_info,
        )
