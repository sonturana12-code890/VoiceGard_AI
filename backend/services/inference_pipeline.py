"""
VOICEGUARD AI — Production Audio Detection & Inference Pipeline
Centralized orchestrator executing the full audio forensic pipeline:
Validation -> Decoding -> Preprocessing -> Feature Extraction -> Segmentation -> Neural Inference -> Aggregation -> Forensic Reporting.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from backend.services.audio_preprocessor import (
    AudioPreprocessingError,
    AudioPreprocessor,
    AudioQualityMetrics,
)
from backend.services.audio_segmenter import AudioSegment, AudioSegmenter
from backend.services.audio_validator import (
    AudioValidationError,
    AudioValidator,
    ValidationResult,
)
from backend.services.feature_extractor import AudioFeatureExtractor, AudioFeatures
from backend.services.forensics_service import AudioForensicsService
from backend.services.model_manager import (
    ModelInferenceError,
    ModelManager,
    ModelNotFoundError,
)
from backend.services.prediction_engine import VoicePredictionEngine

logger = logging.getLogger("voiceguard.inference_pipeline")


class DetectionPipeline:
    """
    Production-grade detection pipeline coordinating end-to-end synthetic voice detection.
    Integrates audio preprocessing, acoustic feature extraction (MFCC, Mel Spectrogram, etc.),
    intelligent segmentation, neural inference (AASIST / RawNet2), and structured reporting.
    Enforces strict zero-hallucination policy when model checkpoints are not installed.
    """

    def __init__(
        self,
        validator: Optional[AudioValidator] = None,
        preprocessor: Optional[AudioPreprocessor] = None,
        segmenter: Optional[AudioSegmenter] = None,
        model_manager: Optional[ModelManager] = None,
        feature_extractor: Optional[AudioFeatureExtractor] = None,
        prediction_engine: Optional[VoicePredictionEngine] = None,
        forensics_service: Optional[AudioForensicsService] = None,
    ):
        self.validator = validator or AudioValidator()
        self.preprocessor = preprocessor or AudioPreprocessor(target_sample_rate=16000)
        self.segmenter = segmenter or AudioSegmenter(target_samples=64600, sample_rate=16000, overlap_seconds=1.0)
        self.model_manager = model_manager or ModelManager()
        self.feature_extractor = feature_extractor or AudioFeatureExtractor(sample_rate=16000)
        self.prediction_engine = prediction_engine or VoicePredictionEngine(model_manager=self.model_manager)
        self.forensics_service = forensics_service or AudioForensicsService(sample_rate=16000)

    def analyze_audio(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
        model_name: str = "AASIST",
        analysis_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes complete detection workflow from raw file bytes to forensic report.
        """
        start_time = time.perf_counter()
        analysis_uuid = analysis_id or str(uuid.uuid4())
        model_display = model_name.upper().strip()

        # 1. Validation
        val_result: ValidationResult = self.validator.validate_file(file_bytes, filename, content_type)
        if not val_result.is_valid:
            elapsed = round(time.perf_counter() - start_time, 4)
            return {
                "success": False,
                "analysis_id": analysis_uuid,
                "filename": filename,
                "status": "validation_failed",
                "analysis_status": "validation_failed",
                "error_code": val_result.error_code,
                "message": val_result.message,
                "processing_time": elapsed,
                "processing_time_seconds": elapsed,
            }

        # 2. Decoding & Acoustic Preprocessing
        try:
            pcm_16k, quality_metrics = self.preprocessor.process_audio(file_bytes, filename)
        except AudioPreprocessingError as ape:
            elapsed = round(time.perf_counter() - start_time, 4)
            return {
                "success": False,
                "analysis_id": analysis_uuid,
                "filename": filename,
                "status": "preprocessing_failed",
                "analysis_status": "preprocessing_failed",
                "error_code": "PREPROCESSING_ERROR",
                "message": str(ape),
                "processing_time": elapsed,
                "processing_time_seconds": elapsed,
            }

        # 3. Audio Feature Extraction (Module 2: MFCC, Mel Spectrogram, Centroid, ZCR, RMS, Bandwidth, Roll-off)
        try:
            extracted_features: AudioFeatures = self.feature_extractor.extract_all(pcm_16k)
            features_dict = extracted_features.to_dict()
            spectrogram_dict = extracted_features.spectrogram_matrix
        except Exception as feat_err:
            logger.warning(f"Feature extraction failed: {str(feat_err)}, using fallback features")
            features_dict = {
                "spectral_centroid": {"mean_hz": quality_metrics.spectral_centroid_hz},
                "rms_energy": {"mean": quality_metrics.rms_energy},
                "zero_crossing_rate": {"mean": 0.0},
                "spectral_bandwidth": {"mean_hz": 0.0},
                "spectral_rolloff": {"mean_hz": 0.0},
                "mfcc": {"n_mfcc": 13, "mean_coefficients": []},
                "mel_spectrogram": {"n_mels": 40, "mean_db": 0.0},
            }
            spectrogram_dict = None

        # 3b. Advanced Audio Forensics & Signal Quality Analysis (Phase 3 Engine)
        try:
            forensics_dict = self.forensics_service.analyze(pcm_16k, sample_rate=16000)
        except Exception as fore_err:
            logger.warning(f"Forensics analysis failed: {str(fore_err)}, using fallback forensics")
            forensics_dict = None

        # 4. Intelligent Audio Segmentation
        segments: List[AudioSegment] = self.segmenter.segment(pcm_16k)
        if not segments:
            elapsed = round(time.perf_counter() - start_time, 4)
            return {
                "success": False,
                "analysis_id": analysis_uuid,
                "filename": filename,
                "status": "segmentation_failed",
                "analysis_status": "segmentation_failed",
                "error_code": "NO_SEGMENTS",
                "message": "Audio stream produced zero usable segments.",
                "processing_time": elapsed,
                "processing_time_seconds": elapsed,
            }

        # 5. Prediction Execution (Module 3, 4, 5)
        pred_report = self.prediction_engine.predict(segments=segments, model_name=model_name)

        elapsed = round(time.perf_counter() - start_time, 4)
        is_completed = pred_report["prediction"]["inference_completed"]
        status_val = "completed" if is_completed else "AI_MODEL_NOT_CONFIGURED"

        # 6. Structured Forensic Report Assembly (Module 4 & 6)
        report: Dict[str, Any] = {
            "success": True,
            "analysis_id": analysis_uuid,
            "filename": filename,
            "audio_duration": round(quality_metrics.duration_seconds, 3),
            "sample_rate": quality_metrics.sample_rate,
            "channel_count": quality_metrics.channels,
            "selected_model": model_display,
            "model_name": model_display,
            "human_probability": pred_report["human_probability"],
            "synthetic_probability": pred_report["synthetic_probability"],
            "real_probability": pred_report.get("real_probability", pred_report["human_probability"]),
            "fake_probability": pred_report.get("fake_probability", pred_report["synthetic_probability"]),
            "predicted_class": pred_report.get("predicted_class", pred_report["prediction"].get("predicted_class", "INCONCLUSIVE")),
            "confidence_score": pred_report["confidence_score"],
            "inference_time": pred_report.get("inference_time", 0.0),
            "prediction_reliability": pred_report.get("prediction_reliability", "UNRELIABLE"),
            "model_status": pred_report.get("model_status", f"{model_display}_ACTIVE" if is_completed else "MODEL_NOT_AVAILABLE"),
            "processing_time": elapsed,
            "processing_time_seconds": elapsed,
            "analysis_status": status_val,
            "status": status_val,
            "prediction": pred_report["prediction"],
            "model": {
                "name": model_display,
                "inference_completed": is_completed,
                "device": self.model_manager.device,
                "version": "1.0.0",
                "inference_time": pred_report.get("inference_time", 0.0),
            },
            "features": features_dict,
            "spectrogram": spectrogram_dict,
            "forensics": forensics_dict,
            "audio_information": quality_metrics.to_dict(),
            "segments_analyzed": len(segments),
            "segment_analysis": pred_report["segment_results"],
        }

        if not is_completed:
            report["model_status"] = pred_report.get("model_status", "MODEL_NOT_AVAILABLE")
            report["missing_files"] = pred_report.get("missing_files", [f"{model_name.lower()}.onnx"])
            report["instructions"] = pred_report.get("instructions", "")
            report["message"] = pred_report.get("message", "")

        return report
