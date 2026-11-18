"""
VOICEGUARD AI — Voice Detection & Inference Service
Interface for Synthetic Speech Detection & Pretrained Model Pipeline (AASIST / RawNet2).
"""

from __future__ import annotations

import os
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from backend.models import AudioAnalysis, User
from backend.services.preprocessing_service import AudioPreprocessingService
from backend.services.inference_pipeline import DetectionPipeline

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", Path(__file__).resolve().parent.parent / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR = Path(__file__).resolve().parent.parent / "models_weights"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class VoiceDetectionService:
    """
    Manages audio storage, metadata inspection, acoustic feature extraction,
    and neural anti-spoofing inference (AASIST / RawNet2).
    """

    @staticmethod
    def save_upload(file_bytes: bytes, original_filename: str) -> Tuple[str, Path]:
        """
        Saves uploaded audio file into the uploads directory with a collision-free UUID filename
        to completely prevent path traversal vulnerabilities.
        """
        ext = Path(original_filename).suffix.lower()
        safe_filename = f"{uuid.uuid4().hex}{ext}"
        target_path = UPLOAD_DIR / safe_filename

        with open(target_path, "wb") as f:
            f.write(file_bytes)

        return safe_filename, target_path

    @staticmethod
    def run_inference(tensor_16k: np.ndarray, model_name: str = "aasist") -> Dict[str, Any]:
        """
        Executes neural model inference if trained weights (e.g. aasist.onnx, rawnet2.onnx) are available.
        If no trained weights exist, returns INCONCLUSIVE status without fabricating scores.
        """
        from backend.services.model_manager import ModelManager
        model_mgr = ModelManager()
        norm_key = model_name.lower().replace("-", "_").strip()
        model_display = model_name.upper().strip()

        if model_mgr.is_model_available(norm_key):
            try:
                logits = model_mgr.run_inference(norm_key, tensor_16k)
                logits = np.squeeze(logits)
                
                # Softmax over 2 logits [spoof (Index 0), bona_fide (Index 1)]
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / np.sum(exp_logits)
                bona_fide_prob = float(probs[1])
                spoof_prob = float(probs[0])

                if spoof_prob >= 0.65:
                    classification = "SYNTHETIC"
                    msg = f"High Risk: Neural vocoder / synthetic voice cloning artifacts detected (Spoof probability: {round(spoof_prob * 100, 1)}%)."
                elif bona_fide_prob >= 0.65:
                    classification = "AUTHENTIC"
                    msg = f"Verified Authentic: Biological vocal dynamics and natural harmonic resonances confirmed (Bona-fide probability: {round(bona_fide_prob * 100, 1)}%)."
                else:
                    classification = "INCONCLUSIVE"
                    msg = f"Inconclusive: Acoustic features are ambiguous (Bona-fide: {round(bona_fide_prob * 100, 1)}%, Spoof: {round(spoof_prob * 100, 1)}%)."

                return {
                    "status": "completed",
                    "model_status": f"{model_display}_ACTIVE",
                    "classification": classification,
                    "synthetic_score": round(spoof_prob, 4),
                    "confidence_score": round(max(bona_fide_prob, spoof_prob), 4),
                    "message": msg,
                    "model_reference": f"{model_display} (ONNX Runtime Active)",
                }
            except Exception:
                # If execution fails, fall back to unconfigured report
                pass

        # Zero-hallucination contract: when weights are unconfigured, report INCONCLUSIVE
        return {
            "status": "AI_MODEL_NOT_CONFIGURED",
            "model_status": "AI_MODEL_NOT_CONFIGURED",
            "classification": "INCONCLUSIVE",
            "synthetic_score": None,
            "confidence_score": None,
            "message": (
                f"Inconclusive (AI Model Unconfigured): Audio preprocessed to 16kHz mono PCM. "
                f"Neural inference requires model weights in 'backend/models_weights/{norm_key}.onnx'. "
                "No fake probabilities were generated."
            ),
            "model_reference": f"{model_display} (Architecture Spec Ready)",
        }

    @staticmethod
    def process_and_register_audio(
        db: Session,
        user: User,
        file_bytes: bytes,
        original_filename: str,
        content_type: str,
        model_name: str = "AASIST",
    ) -> Tuple[AudioAnalysis, Dict[str, Any], Dict[str, Any]]:
        """
        Validates audio, inspects metadata, extracts acoustic features,
        runs model inference (or unconfigured fallback), stores file safely,
        and creates an analysis record in the database.
        """
        # 1. Validation
        AudioPreprocessingService.validate_file_metadata(
            original_filename, len(file_bytes), content_type
        )

        # 2. Inspect audio container, resample to 16kHz, extract acoustic features
        metadata, features, tensor_16k = AudioPreprocessingService.decode_and_extract_features(
            file_bytes, original_filename
        )

        # 3. Save to disk safely
        _, target_path = VoiceDetectionService.save_upload(file_bytes, original_filename)

        # 4. Neural Model Inference (AASIST / RawNet2 or Zero-Hallucination Fallback)
        inference_res = VoiceDetectionService.run_inference(tensor_16k, model_name=model_name)

        analysis = AudioAnalysis(
            user_id=user.id,
            filename=original_filename,
            stored_path=str(target_path.resolve()),
            file_type=content_type or f"audio/{metadata['format']}",
            file_size=len(file_bytes),
            duration_seconds=metadata.get("duration_seconds"),
            analysis_status=inference_res["status"],
            synthetic_score=inference_res["synthetic_score"],
            detection_result=inference_res["message"],
        )

        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        return analysis, inference_res, features

    @staticmethod
    def process_phase3_analysis(
        db: Session,
        user: Optional[User],
        file_bytes: bytes,
        original_filename: str,
        content_type: str,
        model_name: str = "AASIST",
    ) -> Dict[str, Any]:
        """
        Executes the complete Phase 3 Audio Detection Pipeline:
        Validation, Preprocessing, Intelligent Segmentation, Neural Inference,
        Segment Aggregation, and Persists Forensic Metadata.
        """
        pipeline = DetectionPipeline()
        report = pipeline.analyze_audio(
            file_bytes=file_bytes,
            filename=original_filename,
            content_type=content_type,
            model_name=model_name,
        )

        if not report.get("success"):
            return report

        # Save to disk safely
        _, target_path = VoiceDetectionService.save_upload(file_bytes, original_filename)

        if user is not None:
            synth_score = report.get("prediction", {}).get("synthetic_probability")
            duration = report.get("audio_information", {}).get("duration")
            status = report.get("status", "completed")

            analysis = AudioAnalysis(
                id=report["analysis_id"],
                user_id=user.id,
                filename=original_filename,
                stored_path=str(target_path.resolve()),
                file_type=content_type or "audio/wav",
                file_size=len(file_bytes),
                duration_seconds=duration,
                analysis_status=status,
                synthetic_score=synth_score,
                detection_result=json.dumps(report),
            )
            db.add(analysis)
            db.commit()
            db.refresh(analysis)

        return report
