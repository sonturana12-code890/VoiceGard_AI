"""
VOICEGUARD AI — Audio Routes
Endpoints for audio file upload, validation, inspection, and analysis history.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth import get_current_user, log_security_event
from backend.database import get_db
from backend.models import AudioAnalysis, ThreatAlert, User
from backend.schemas import (
    AudioAnalysisResponse,
    AudioHistoryResponse,
    AudioHistoryStats,
    AudioUploadResponse,
    AudioValidateResponse,
    Phase3AudioAnalysisResponse,
    StandaloneForensicsResponse,
)
from backend.services.audio_service import VoiceDetectionService
from backend.services.audio_validator import AudioValidator, AudioValidationError
from backend.services.model_manager import ModelManager
from backend.services.preprocessing_service import (
    MAX_FILE_SIZE_BYTES,
    AudioPreprocessingError,
)
from backend.services.risk_engine import FraudRiskEngine

router = APIRouter(tags=["Audio Analysis"])


@router.post("/api/audio/upload", response_model=AudioUploadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/audio/analyze", response_model=AudioUploadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/analyze", response_model=AudioUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    model_name: str = Query(default="AASIST", description="Neural architecture (AASIST, RawNet2)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accepts an audio file upload, validates container format, checks file size,
    stores safely on disk, and records metadata in SQLite.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing or invalid.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE_BYTES + 1)
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise AudioPreprocessingError("File size exceeds the 25 MB limit.")
        analysis, inference_res, features = VoiceDetectionService.process_and_register_audio(
            db=db,
            user=current_user,
            file_bytes=content,
            original_filename=file.filename,
            content_type=file.content_type or "audio/wav",
            model_name=model_name,
        )

        log_security_event(
            db=db,
            user_id=current_user.id,
            event_type="audio.upload",
            description=f"Uploaded audio '{file.filename}' ({len(content)} bytes) for forensic inspection",
            request=request,
        )

        return AudioUploadResponse(
            message="Audio uploaded and preprocessed successfully. Deepfake inference queued for Phase 2.",
            analysis=AudioAnalysisResponse.model_validate(analysis),
            model_status=inference_res.get("model_status", "AI_MODEL_NOT_CONFIGURED"),
            classification=inference_res.get("classification", "INCONCLUSIVE"),
            acoustic_features=features,
        )
    except AudioPreprocessingError as e:
        msg = str(e)
        if "exceeds" in msg:
            code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        else:
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=code,
            detail=msg,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during audio processing: {str(e)}",
        )


@router.get("/api/audio/history", response_model=AudioHistoryResponse)
@router.get("/api/history", response_model=AudioHistoryResponse)
async def get_audio_history(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve chronologically ordered audio analysis history for the authenticated user."""
    records = (
        db.query(AudioAnalysis)
        .filter(AudioAnalysis.user_id == current_user.id)
        .order_by(AudioAnalysis.created_at.desc())
        .limit(limit)
        .all()
    )
    total_audio_scans = (
        db.query(func.count(AudioAnalysis.id))
        .filter(AudioAnalysis.user_id == current_user.id)
        .scalar()
        or 0
    )
    genuine_voices = (
        db.query(func.count(AudioAnalysis.id))
        .filter(
            AudioAnalysis.user_id == current_user.id,
            AudioAnalysis.analysis_status == "completed",
            AudioAnalysis.synthetic_score <= 0.35,
        )
        .scalar()
        or 0
    )
    ai_generated_voices = (
        db.query(func.count(AudioAnalysis.id))
        .filter(
            AudioAnalysis.user_id == current_user.id,
            AudioAnalysis.analysis_status == "completed",
            AudioAnalysis.synthetic_score >= 0.65,
        )
        .scalar()
        or 0
    )
    inconclusive_voices = (
        db.query(func.count(AudioAnalysis.id))
        .filter(
            AudioAnalysis.user_id == current_user.id,
            AudioAnalysis.analysis_status == "completed",
            AudioAnalysis.synthetic_score > 0.35,
            AudioAnalysis.synthetic_score < 0.65,
        )
        .scalar()
        or 0
    )
    threats_detected = (
        db.query(func.count(ThreatAlert.id))
        .filter(ThreatAlert.user_id == current_user.id)
        .scalar()
        or 0
    )

    return AudioHistoryResponse(
        total=total_audio_scans,
        history=[AudioAnalysisResponse.model_validate(r) for r in records],
        stats=AudioHistoryStats(
            total_audio_scans=total_audio_scans,
            genuine_voices=genuine_voices,
            ai_generated_voices=ai_generated_voices,
            inconclusive_voices=inconclusive_voices,
            threats_detected=threats_detected,
        ),
    )


@router.get("/api/audio/{analysis_id}", response_model=AudioAnalysisResponse)
async def get_audio_detail(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed telemetry for a specific audio analysis record."""
    record = (
        db.query(AudioAnalysis)
        .filter(AudioAnalysis.id == analysis_id, AudioAnalysis.user_id == current_user.id)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis record '{analysis_id}' was not found.",
        )

    return AudioAnalysisResponse.model_validate(record)


@router.get("/api/audio/{analysis_id}/stream")
async def stream_audio_file(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Streams stored audio for local browser playback."""
    record = (
        db.query(AudioAnalysis)
        .filter(AudioAnalysis.id == analysis_id, AudioAnalysis.user_id == current_user.id)
        .first()
    )

    if not record or not record.stored_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found.")

    from pathlib import Path
    path = Path(record.stored_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored audio file is missing on server.")

    return FileResponse(path, media_type=record.file_type, filename=record.filename)


@router.get("/api/fraud/assess/{analysis_id}")
async def assess_fraud_risk(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates fraud risk score for an analyzed audio sample.
    Preserves original Phase 1 endpoint contract while leveraging FraudRiskEngine.
    """
    record = (
        db.query(AudioAnalysis)
        .filter(AudioAnalysis.id == analysis_id, AudioAnalysis.user_id == current_user.id)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found.",
        )

    risk_eval = FraudRiskEngine.assess_risk(
        synthetic_score=record.synthetic_score,
        speaker_verified=None,
        speaker_confidence=None,
    )

    score = record.synthetic_score
    level = "Critical" if (score and score >= 0.9) else "High" if (score and score >= 0.7) else "Guarded" if (score and score >= 0.4) else "Low" if score is not None else "UNASSESSED"

    return {
        "analysis_id": analysis_id,
        "assessment": {
            "risk_score": score,
            "risk_level": level,
            "status": record.analysis_status,
            "details": risk_eval,
            "source": "VoiceGuard FraudRiskEngine (Phase 1 Baseline)",
        },
    }


# ============================================================================
# PHASE 3: ADVANCED DETECTION & PROCESSING PIPELINE ENDPOINTS (/api/v1/audio)
# ============================================================================

@router.post(
    "/api/v1/audio/analyze",
    response_model=Phase3AudioAnalysisResponse,
    status_code=status.HTTP_200_OK,
    tags=["Phase 3 Audio Pipeline"],
)
async def analyze_audio_v1(
    request: Request,
    file: UploadFile = File(...),
    model_name: str = Query(default="AASIST", description="Neural architecture (AASIST, RawNet2, Ensemble)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Phase 3 Audio Detection Pipeline:
    Ingests audio, validates integrity, normalizes sampling, intelligently segments,
    executes neural inference (or unconfigured fallback), and aggregates forensic metrics.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing or invalid.",
        )

    content = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the 25 MB limit. Received {round(len(content)/(1024*1024), 2)} MB.",
        )

    try:
        report = VoiceDetectionService.process_phase3_analysis(
            db=db,
            user=current_user,
            file_bytes=content,
            original_filename=file.filename,
            content_type=file.content_type or "audio/wav",
            model_name=model_name,
        )

        log_security_event(
            db=db,
            user_id=current_user.id,
            event_type="audio.v1_analysis",
            description=f"Phase 3 analysis on '{file.filename}' (status={report.get('status')})",
            request=request,
        )

        if not report.get("success"):
            err_code = report.get("error_code", "INVALID_AUDIO")
            msg = report.get("message", "Validation or preprocessing failed.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"[{err_code}] {msg}",
            )

        return Phase3AudioAnalysisResponse.model_validate(report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Phase 3 detection pipeline error: {str(exc)}",
        )


@router.post(
    "/api/v1/audio/validate",
    response_model=AudioValidateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Phase 3 Audio Pipeline"],
)
async def F12validate_audio_v1(
    file: UploadFile = File(...),
):
    """
    Phase 3 Audio Validation Engine:
    Inspects container integrity, MIME types, duration limits, and stream decodability.
    """
    if not file.filename:
        return AudioValidateResponse(
            success=False,
            valid=False,
            filename="",
            file_size=0,
            message="Filename is missing or invalid.",
            error_code="INVALID_FILENAME",
        )

    content = await file.read(MAX_FILE_SIZE_BYTES + 1)
    val = AudioValidator().validate_file(
        file_bytes=content,
        filename=file.filename,
        content_type=file.content_type,
    )
    return AudioValidateResponse.model_validate(val.to_dict())


@router.get(
    "/api/v1/audio/analysis/{analysis_id}",
    tags=["Phase 3 Audio Pipeline"],
)
async def get_analysis_detail_v1(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves complete Phase 3 forensic report including segment analysis for an audio analysis record.
    """
    record = (
        db.query(AudioAnalysis)
        .filter(AudioAnalysis.id == analysis_id, AudioAnalysis.user_id == current_user.id)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis record '{analysis_id}' was not found.",
        )

    if record.detection_result:
        try:
            stored_data = json.loads(record.detection_result)
            if isinstance(stored_data, dict) and "prediction" in stored_data:
                return stored_data
        except Exception:
            pass

    # Fallback to structured representation
    return {
        "success": True,
        "analysis_id": record.id,
        "filename": record.filename,
        "status": record.analysis_status,
        "prediction": {
            "label": "AI_GENERATED" if (record.synthetic_score and record.synthetic_score >= 0.65) else "HUMAN" if (record.synthetic_score and record.synthetic_score <= 0.35) else "INCONCLUSIVE",
            "human_probability": round(1.0 - record.synthetic_score, 4) if record.synthetic_score is not None else None,
            "synthetic_probability": record.synthetic_score,
            "confidence": record.synthetic_score if record.synthetic_score is not None else None,
        },
        "model": {
            "name": "AASIST",
            "inference_completed": record.synthetic_score is not None,
            "device": ModelManager().device,
            "version": "1.0.0",
        },
        "audio_information": {
            "duration": record.duration_seconds or 0.0,
            "sample_rate": 16000,
            "channels": 1,
        },
        "segments_analyzed": 1,
        "processing_time_seconds": 0.0,
        "segment_analysis": [],
    }


@router.get(
    "/api/v1/audio/{analysis_id}/spectrogram",
    status_code=status.HTTP_200_OK,
    tags=["Phase 3 Audio Pipeline"],
)
async def get_audio_spectrogram(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the 2D Log-Mel Spectrogram matrix and frequency coordinate metadata
    for a previously analyzed audio file.
    """
    record = (
        db.query(AudioAnalysis)
        .filter(AudioAnalysis.id == analysis_id, AudioAnalysis.user_id == current_user.id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID '{analysis_id}' not found.",
        )

    # 1. Check if spectrogram is stored directly in detection_result JSON
    if record.detection_result:
        try:
            det_data = json.loads(record.detection_result)
            if "spectrogram" in det_data and det_data["spectrogram"]:
                return det_data["spectrogram"]
            if "features" in det_data and isinstance(det_data["features"], dict):
                if "spectrogram" in det_data["features"] and det_data["features"]["spectrogram"]:
                    return det_data["features"]["spectrogram"]
        except Exception:
            pass

    # 2. If not stored but audio file is present on disk, extract on-demand
    if record.stored_path:
        from pathlib import Path
        path = Path(record.stored_path)
        if path.exists():
            try:
                content = path.read_bytes()
                from backend.services.audio_preprocessor import AudioPreprocessor
                from backend.services.feature_extractor import AudioFeatureExtractor
                preprocessor = AudioPreprocessor(target_sample_rate=16000)
                pcm, qm = preprocessor.process_audio(content, record.filename)
                extractor = AudioFeatureExtractor(sample_rate=16000, hop_length=160, n_mels=40)
                frames = extractor.frame_signal(pcm)
                _, power = extractor.compute_stft(frames)
                mel_db, _ = extractor.extract_mel_spectrogram(power)
                duration = len(pcm) / 16000.0
                return extractor.extract_spectrogram_matrix(mel_db, duration)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate spectrogram from stored audio: {str(e)}",
                )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Spectrogram data not available for this record.",
    )


@router.post(
    "/api/v1/audio/forensics",
    response_model=StandaloneForensicsResponse,
    status_code=status.HTTP_200_OK,
    tags=["Phase 3 Audio Forensics"],
)
async def analyze_audio_forensics(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Phase 3 Advanced Audio Forensics & Signal Quality Diagnostics Endpoint:
    Extracts empirical background noise metrics, SNR in dB, noise floor in dBFS,
    clipping intervals, silence segments, VAD intervals, and an explainable 0-100 quality score.
    """
    import time
    from backend.services.audio_preprocessor import AudioPreprocessor
    from backend.services.forensics_service import AudioForensicsService

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing or invalid.",
        )

    content = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the 25 MB limit.",
        )

    t0 = time.perf_counter()
    try:
        preprocessor = AudioPreprocessor(target_sample_rate=16000)
        pcm_16k, _ = preprocessor.process_audio(content, file.filename)
        forensics_svc = AudioForensicsService(sample_rate=16000)
        forensics_data = forensics_svc.analyze(pcm_16k, sample_rate=16000)
        elapsed = round(time.perf_counter() - t0, 4)

        return StandaloneForensicsResponse(
            success=True,
            filename=file.filename,
            processing_time_seconds=elapsed,
            forensics=forensics_data,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio forensics computation failed: {str(exc)}",
        )


@router.get(
    "/api/v1/audio/{analysis_id}/forensics",
    status_code=status.HTTP_200_OK,
    tags=["Phase 3 Audio Forensics"],
)
async def get_audio_forensics(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves the complete Audio Forensics and Signal Quality report for a previously analyzed file.
    """
    record = (
        db.query(AudioAnalysis)
        .filter(AudioAnalysis.id == analysis_id, AudioAnalysis.user_id == current_user.id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis with ID '{analysis_id}' not found.",
        )

    # 1. Check if forensics is stored inside detection_result JSON
    if record.detection_result:
        try:
            det_data = json.loads(record.detection_result)
            if "forensics" in det_data and det_data["forensics"]:
                return {
                    "success": True,
                    "analysis_id": analysis_id,
                    "filename": record.filename,
                    "forensics": det_data["forensics"],
                }
        except Exception:
            pass

    # 2. Extract on-demand if file exists on disk
    if record.stored_path:
        from pathlib import Path
        path = Path(record.stored_path)
        if path.exists():
            try:
                content = path.read_bytes()
                from backend.services.audio_preprocessor import AudioPreprocessor
                from backend.services.forensics_service import AudioForensicsService
                preprocessor = AudioPreprocessor(target_sample_rate=16000)
                pcm, _ = preprocessor.process_audio(content, record.filename)
                forensics_svc = AudioForensicsService(sample_rate=16000)
                forensics_data = forensics_svc.analyze(pcm, sample_rate=16000)
                return {
                    "success": True,
                    "analysis_id": analysis_id,
                    "filename": record.filename,
                    "forensics": forensics_data,
                }
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate forensics from stored audio: {str(e)}",
                )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Audio forensics data not available for this record.",
    )


@router.get(
    "/api/v1/audio/health",
    tags=["Phase 3 Audio Pipeline"],
)
async def get_audio_pipeline_health():
    """Returns Phase 3 detection engine health, model status, and device providers."""
    model_mgr = ModelManager()
    from backend.services.ffmpeg_service import FFmpegService
    return {
        "status": "healthy",
        "pipeline_version": "3.0.0",
        "phase_version": "4.0.0",
        "phase": 4,
        "supported_models": ["AASIST", "RawNet2", "ECAPA-TDNN"],
        "supported_formats": ["wav", "mp3", "flac", "ogg", "m4a", "aac", "webm", "opus", "mpeg", "mpg"],
        "target_sample_rate": 16000,
        "expected_input_samples": 64600,
        "models_status": model_mgr.get_status_report(),
        "ffmpeg_status": FFmpegService.get_diagnostics(),
    }

