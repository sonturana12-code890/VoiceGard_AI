"""
VOICEGUARD AI — Speaker Verification & Biometric Voiceprint Routes
Comprehensive speaker enrollment, biometric voiceprint management, 1:1 identity
verification, and persistent verification history.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

logger = logging.getLogger("voiceguard.speaker_routes")

from backend.auth import get_current_user, log_security_event
from backend.database import get_db
from backend.models import SpeakerRegistration, SpeakerVerificationLog, User, get_utc_now
from backend.schemas import (
    SpeakerEnrollResponse,
    SpeakerListResponse,
    SpeakerProfileListResponse,
    SpeakerProfileResponse,
    SpeakerResponse,
    SpeakerVerificationHistoryItem,
    SpeakerVerificationHistoryResponse,
    SpeakerVerificationResponse,
    SpeakerVerifyResponse,
)
from backend.services.biometric_security import (
    decrypt_embedding,
    encrypt_embedding,
    generate_speaker_id,
    validate_speaker_id,
)
from backend.services.ecapa_service import (
    DEFAULT_VERIFICATION_THRESHOLD,
    ECAPAInferenceError,
    ECAPAModelError,
    ECAPAService,
)
from backend.services.preprocessing_service import (
    MAX_FILE_SIZE_BYTES,
    AudioPreprocessingError,
    AudioPreprocessingService,
)

router = APIRouter(tags=["Speaker Verification"])


# ============================================================================
# MODULE 1 & 2: SPEAKER ENROLLMENT & BIOMETRIC PROFILE MANAGEMENT
# ============================================================================

@router.post(
    "/api/v1/speaker/enroll",
    response_model=SpeakerEnrollResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll new biometric voiceprint profile with consent",
)
async def enroll_speaker(
    request: Request,
    speaker_name: str = Form(..., description="Speaker full name (2-100 characters)"),
    speaker_id: Optional[str] = Form(default=None, description="Custom speaker ID (e.g. SPK-10294); auto-generated if omitted"),
    consent: bool = Form(default=False, description="Explicit user consent to store biometric voiceprint"),
    consent_status: Optional[bool] = Form(default=None),
    department: Optional[str] = Form(default=None, description="Organizational unit or department"),
    clearance_level: Optional[str] = Form(default=None, description="Security clearance tier"),
    file: UploadFile = File(..., description="Reference speech audio sample (16 kHz mono recommended, max 25 MB)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Module 1: Speaker Enrollment.
    Validates audio quality, extracts a 192-dimensional ECAPA-TDNN embedding, L2-normalizes it,
    encrypts the embedding token using PBKDF2-HMAC-SHA256, and stores the biometric profile.
    Mandates explicit consent and guarantees raw recordings are discarded immediately after feature extraction.
    """
    name = speaker_name.strip()
    if len(name) < 2 or len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Speaker name must be between 2 and 100 characters.",
        )

    # Consent validation
    effective_consent = bool(consent or (consent_status is True))
    if not effective_consent:
        logger.warning(f"Speaker enrollment rejected for '{name}': biometric consent not granted.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biometric voice enrollment requires explicit speaker consent.",
        )

    # File validation
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reference audio file is required for speaker enrollment.",
        )

    content = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Enrollment audio file size exceeds the 25 MB limit.",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enrollment audio file is empty (0 bytes).",
        )

    try:
        AudioPreprocessingService.validate_file_metadata(file.filename, len(content), file.content_type)
    except AudioPreprocessingError as ape:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ape))

    # Speaker ID handling & duplicate check
    if speaker_id and speaker_id.strip():
        spk_id = speaker_id.strip()
        if not validate_speaker_id(spk_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Speaker ID must be 3-64 characters consisting of letters, digits, hyphens, or underscores.",
            )
    else:
        spk_id = generate_speaker_id("SPK")

    existing = (
        db.query(SpeakerRegistration)
        .filter(
            SpeakerRegistration.user_id == current_user.id,
            (SpeakerRegistration.speaker_id == spk_id) | (SpeakerRegistration.id == spk_id),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A speaker profile with ID '{spk_id}' already exists for your account.",
        )

    # ECAPA-TDNN Embedding Extraction
    ecapa = ECAPAService()
    try:
        norm_emb, audio_info, quality_warnings = ecapa.extract_embedding(
            content, filename=file.filename, label="Enrollment audio"
        )
    except ECAPAInferenceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ECAPAModelError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Biometric embedding extraction failed: {str(e)}",
        )

    # Authenticated Encryption of Voiceprint Embedding
    encrypted_token = encrypt_embedding(norm_emb)
    duration = float(audio_info.get("duration_seconds") or 0.0)

    # Persist profile with encrypted embedding; do not retain raw recording
    registration = SpeakerRegistration(
        user_id=current_user.id,
        speaker_id=spk_id,
        speaker_name=name,
        consent_status=True,
        department=department.strip() if department else None,
        clearance_level=clearance_level.strip() if clearance_level else None,
        reference_audio_path=None,  # Discarded per GDPR/biometric privacy mandate
        embedding_reference="ECAPA_VOXCELEB_192D",
        voiceprint_embedding=encrypted_token,
        voiceprint_status="ACTIVE",
        audio_duration_seconds=duration,
        verification_count=0,
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)

    log_security_event(
        db,
        current_user.id,
        "speaker.enroll",
        f"Enrolled biometric voiceprint: '{name}' (ID: {spk_id}, Duration: {round(duration, 2)}s, Dimension: 192)",
        request,
    )
    logger.info(f"Speaker enrolled: '{name}' (ID: {spk_id}, User: {current_user.id})")

    return SpeakerEnrollResponse(
        id=registration.id,
        speaker_id=registration.speaker_id,
        speaker_name=registration.speaker_name,
        consent_status=registration.consent_status,
        department=registration.department,
        clearance_level=registration.clearance_level,
        voiceprint_status=registration.voiceprint_status,
        embedding_dimension=192,
        audio_duration_seconds=registration.audio_duration_seconds,
        audio_quality_warnings=quality_warnings,
        created_at=registration.created_at,
        message="Biometric voiceprint enrolled successfully.",
        consent_verified=True,
    )


@router.get(
    "/api/v1/speaker/profiles",
    response_model=SpeakerProfileListResponse,
    summary="List all enrolled biometric profiles for authenticated user",
)
async def list_speaker_profiles(
    search: Optional[str] = Query(default=None, description="Search by name, ID, or department"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="Filter by status (ACTIVE, etc.)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Module 2: Voiceprint Management.
    Returns paginated list of biometric speaker profiles owned strictly by the current user.
    Never exposes raw floating-point embeddings.
    """
    query = db.query(SpeakerRegistration).filter(SpeakerRegistration.user_id == current_user.id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (SpeakerRegistration.speaker_name.ilike(term))
            | (SpeakerRegistration.speaker_id.ilike(term))
            | (SpeakerRegistration.department.ilike(term))
        )
    if status_filter and status_filter.strip():
        query = query.filter(SpeakerRegistration.voiceprint_status == status_filter.strip().upper())

    total = query.count()
    records = query.order_by(SpeakerRegistration.created_at.desc()).offset(offset).limit(limit).all()

    # Backfill speaker_id for any legacy records
    for r in records:
        if not r.speaker_id:
            r.speaker_id = f"SPK-{r.id[:8].upper()}"

    return SpeakerProfileListResponse(
        total=total,
        profiles=[SpeakerProfileResponse.model_validate(r) for r in records],
    )


@router.get(
    "/api/v1/speaker/profiles/{speaker_id}",
    response_model=SpeakerProfileResponse,
    summary="Get single biometric speaker profile details",
)
async def get_speaker_profile(
    speaker_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Module 2: View Profile.
    Fetches an enrolled speaker profile by speaker_id or database ID.
    Enforces user-specific ownership isolation.
    """
    profile = (
        db.query(SpeakerRegistration)
        .filter(
            SpeakerRegistration.user_id == current_user.id,
            (SpeakerRegistration.speaker_id == speaker_id) | (SpeakerRegistration.id == speaker_id),
        )
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Speaker profile '{speaker_id}' not found.",
        )

    if not profile.speaker_id:
        profile.speaker_id = f"SPK-{profile.id[:8].upper()}"

    return SpeakerProfileResponse.model_validate(profile)


@router.delete(
    "/api/v1/speaker/profiles/{speaker_id}",
    summary="Delete an enrolled biometric speaker voiceprint profile",
)
async def delete_speaker_profile(
    speaker_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Module 2: Delete Voiceprint.
    Permanently revokes and removes a speaker's voiceprint embedding.
    Ensures strict cross-user isolation and logs the security audit event.
    """
    profile = (
        db.query(SpeakerRegistration)
        .filter(
            SpeakerRegistration.user_id == current_user.id,
            (SpeakerRegistration.speaker_id == speaker_id) | (SpeakerRegistration.id == speaker_id),
        )
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Speaker profile '{speaker_id}' not found.",
        )

    deleted_id = profile.speaker_id or profile.id
    name = profile.speaker_name

    db.delete(profile)
    db.commit()

    log_security_event(
        db,
        current_user.id,
        "speaker.delete_profile",
        f"Deleted biometric voiceprint profile: '{name}' (ID: {deleted_id})",
        request,
    )
    logger.info(f"Speaker profile deleted: '{name}' (ID: {deleted_id}, User: {current_user.id})")

    return {
        "success": True,
        "message": f"Biometric voiceprint profile '{deleted_id}' ({name}) deleted successfully.",
        "deleted_speaker_id": deleted_id,
    }


# ============================================================================
# MODULE 3 & 4: ADVANCED SPEAKER COMPARISON & VERIFICATION HISTORY
# ============================================================================

@router.get(
    "/api/v1/speaker/model-info",
    tags=["Speaker Verification"],
    summary="Get ECAPA-TDNN model telemetry and operational status",
)
async def get_speaker_model_info():
    """Returns diagnostic telemetry and operational readiness of the ECAPA-TDNN verification engine."""
    service = ECAPAService()
    available = service.is_available()
    info = service.get_model_info()
    return {
        "status": "online" if available else "unavailable",
        "available": available,
        "info": info,
    }


@router.post(
    "/api/v1/speaker/verify",
    response_model=SpeakerVerificationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Speaker Verification"],
    summary="1:1 Biometric Speaker Verification (Dual Audio or Profile-to-Audio)",
)
async def verify_speakers_v1(
    request: Request,
    reference_audio: Optional[UploadFile] = File(default=None, description="Reference biometric speech recording"),
    comparison_audio: Optional[UploadFile] = File(default=None, description="Comparison speech recording to verify"),
    speaker_id: Optional[str] = Form(default=None, description="Enrolled speaker profile ID"),
    threshold: Optional[float] = Query(default=None, ge=-1.0, le=1.0, description="Cosine decision threshold"),
    form_threshold: Optional[float] = Form(default=None, alias="threshold"),
    db: Session = Depends(get_db),
):
    """
    Module 3 & 4: Advanced Speaker Comparison & Verification History.
    Compares probe audio against either an enrolled profile's decrypted 192-D embedding OR
    a secondary reference audio file. Returns cosine similarity, verdict (SAME_SPEAKER,
    DIFFERENT_SPEAKER, INCONCLUSIVE), quality warnings, and logs to persistent history.
    """
    effective_threshold = (
        form_threshold if form_threshold is not None
        else (threshold if threshold is not None else DEFAULT_VERIFICATION_THRESHOLD)
    )

    if not comparison_audio or not comparison_audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comparison audio file is required.",
        )

    cmp_bytes = await comparison_audio.read(MAX_FILE_SIZE_BYTES + 1)
    if len(cmp_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Comparison audio file size exceeds the 25 MB limit.",
        )
    if len(cmp_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comparison audio file is empty (0 bytes).",
        )

    # Optional authentication check
    caller_user: Optional[User] = None
    try:
        caller_user = await get_current_user(request=request, bearer=None, db=db)
    except Exception:
        caller_user = None

    ecapa = ECAPAService()
    ref_spk_id: Optional[str] = None
    ref_spk_name: Optional[str] = None
    ref_display_name: str = "reference.wav"

    try:
        # Case A: Verification against Enrolled Profile ID
        if speaker_id and speaker_id.strip():
            clean_spk_id = speaker_id.strip()
            profile_query = db.query(SpeakerRegistration).filter(
                (SpeakerRegistration.speaker_id == clean_spk_id) | (SpeakerRegistration.id == clean_spk_id)
            )
            if caller_user:
                profile_query = profile_query.filter(SpeakerRegistration.user_id == caller_user.id)
            profile = profile_query.first()

            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Enrolled speaker profile '{clean_spk_id}' not found.",
                )

            if not profile.voiceprint_embedding:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Speaker profile '{clean_spk_id}' does not have an enrolled voiceprint embedding.",
                )

            ref_embedding = decrypt_embedding(profile.voiceprint_embedding)
            ref_spk_id = profile.speaker_id or profile.id
            ref_spk_name = profile.speaker_name
            ref_display_name = f"Profile: {ref_spk_name} ({ref_spk_id})"

            result = ecapa.verify_embedding_vs_audio(
                reference_embedding=ref_embedding,
                comparison_audio=cmp_bytes,
                cmp_filename=comparison_audio.filename,
                threshold=effective_threshold,
                ref_info={
                    "source": "enrolled_profile",
                    "speaker_id": ref_spk_id,
                    "speaker_name": ref_spk_name,
                    "audio_duration_seconds": profile.audio_duration_seconds,
                },
            )

            # Update profile telemetry
            profile.verification_count = (profile.verification_count or 0) + 1
            profile.last_verified_at = get_utc_now()
            db.commit()

        # Case B: Verification against Dual Audio Upload
        elif reference_audio and reference_audio.filename:
            ref_bytes = await reference_audio.read(MAX_FILE_SIZE_BYTES + 1)
            if len(ref_bytes) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Reference audio file size exceeds the 25 MB limit.",
                )
            if len(ref_bytes) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reference audio file is empty (0 bytes).",
                )
            ref_display_name = reference_audio.filename

            result = ecapa.verify_speakers(
                reference_audio=ref_bytes,
                comparison_audio=cmp_bytes,
                ref_filename=reference_audio.filename,
                cmp_filename=comparison_audio.filename,
                threshold=effective_threshold,
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either an enrolled 'speaker_id' or a 'reference_audio' file must be provided.",
            )

        # Module 4: Persist verification log if user session exists
        if caller_user:
            try:
                log_entry = SpeakerVerificationLog(
                    user_id=caller_user.id,
                    reference_speaker_id=ref_spk_id,
                    reference_speaker_name=ref_spk_name,
                    reference_filename=ref_display_name,
                    comparison_filename=comparison_audio.filename,
                    similarity_score=result.cosine_similarity,
                    verdict=result.verdict,
                    is_same_speaker=result.is_same_speaker,
                    threshold_used=effective_threshold,
                    model_name=result.model_name,
                    processing_time_ms=round(result.processing_time * 1000, 2),
                    audio_quality_warnings=json.dumps(result.audio_quality_warnings),
                )
                db.add(log_entry)
                db.commit()

                log_security_event(
                    db,
                    caller_user.id,
                    "speaker.v1_verify",
                    f"Verified speaker: ref='{ref_display_name}', cmp='{comparison_audio.filename}' (verdict={result.verdict}, sim={result.cosine_similarity:.3f})",
                    request,
                )
            except Exception as log_exc:
                logger.warning(f"Unable to write verification history log: {log_exc}")

        resp_dict = result.to_dict()
        resp_dict["speaker_id"] = ref_spk_id
        resp_dict["speaker_name"] = ref_spk_name
        return SpeakerVerificationResponse.model_validate(resp_dict)

    except (ECAPAInferenceError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ECAPAModelError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Speaker model unavailable: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speaker verification unhandled error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Speaker verification pipeline error: {str(e)}")


@router.get(
    "/api/v1/speaker/history",
    response_model=SpeakerVerificationHistoryResponse,
    summary="Get verification history with search, verdict, and date filtering",
)
async def get_speaker_history(
    search: Optional[str] = Query(default=None, description="Search by file name or speaker name/ID"),
    verdict: Optional[str] = Query(default=None, description="Filter by verdict (SAME_SPEAKER, DIFFERENT_SPEAKER, INCONCLUSIVE)"),
    start_date: Optional[str] = Query(default=None, description="Filter records starting from ISO date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Filter records up to ISO date (YYYY-MM-DD)"),
    speaker_id: Optional[str] = Query(default=None, description="Filter by enrolled speaker ID"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Module 4: Verification History.
    Retrieves the persistent verification audit log for the current authenticated user.
    """
    query = db.query(SpeakerVerificationLog).filter(SpeakerVerificationLog.user_id == current_user.id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (SpeakerVerificationLog.reference_filename.ilike(term))
            | (SpeakerVerificationLog.comparison_filename.ilike(term))
            | (SpeakerVerificationLog.reference_speaker_name.ilike(term))
            | (SpeakerVerificationLog.reference_speaker_id.ilike(term))
        )
    if verdict and verdict.strip():
        query = query.filter(SpeakerVerificationLog.verdict == verdict.strip().upper())
    if speaker_id and speaker_id.strip():
        query = query.filter(SpeakerVerificationLog.reference_speaker_id == speaker_id.strip())
    if start_date and start_date.strip():
        try:
            dt_start = datetime.fromisoformat(start_date.strip()).replace(tzinfo=timezone.utc)
            query = query.filter(SpeakerVerificationLog.created_at >= dt_start)
        except Exception:
            pass
    if end_date and end_date.strip():
        try:
            dt_end = datetime.fromisoformat(end_date.strip()).replace(tzinfo=timezone.utc)
            query = query.filter(SpeakerVerificationLog.created_at <= dt_end)
        except Exception:
            pass

    total = query.count()
    all_records = query.all()

    same_count = sum(1 for r in all_records if r.verdict == "SAME_SPEAKER")
    diff_count = sum(1 for r in all_records if r.verdict == "DIFFERENT_SPEAKER")
    incon_count = sum(1 for r in all_records if r.verdict == "INCONCLUSIVE")
    avg_sim = round(sum(r.similarity_score for r in all_records) / max(total, 1), 4) if total > 0 else 0.0

    paginated = query.order_by(SpeakerVerificationLog.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for r in paginated:
        warnings = []
        if r.audio_quality_warnings:
            try:
                warnings = json.loads(r.audio_quality_warnings)
            except Exception:
                warnings = [r.audio_quality_warnings]
        items.append(
            SpeakerVerificationHistoryItem(
                id=r.id,
                reference_speaker_id=r.reference_speaker_id,
                reference_speaker_name=r.reference_speaker_name,
                reference_filename=r.reference_filename,
                comparison_filename=r.comparison_filename,
                similarity_score=r.similarity_score,
                verdict=r.verdict,
                is_same_speaker=r.is_same_speaker,
                threshold_used=r.threshold_used,
                model_name=r.model_name,
                processing_time_ms=r.processing_time_ms,
                audio_quality_warnings=warnings,
                created_at=r.created_at,
            )
        )

    return SpeakerVerificationHistoryResponse(
        total=total,
        same_speaker_count=same_count,
        different_speaker_count=diff_count,
        inconclusive_count=incon_count,
        average_similarity=avg_sim,
        items=items,
    )


@router.delete(
    "/api/v1/speaker/history/{verification_id}",
    summary="Delete a single verification history record",
)
async def delete_history_record(
    verification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes an individual verification history entry owned by current user."""
    record = (
        db.query(SpeakerVerificationLog)
        .filter(
            SpeakerVerificationLog.id == verification_id,
            SpeakerVerificationLog.user_id == current_user.id,
        )
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification record '{verification_id}' not found.",
        )
    db.delete(record)
    db.commit()
    return {"success": True, "message": f"Verification record '{verification_id}' deleted successfully."}


@router.delete(
    "/api/v1/speaker/history",
    summary="Clear all verification history records for current user",
)
async def clear_speaker_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Purges all verification history entries owned by the current authenticated user."""
    deleted_count = (
        db.query(SpeakerVerificationLog)
        .filter(SpeakerVerificationLog.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"success": True, "message": "Verification history cleared.", "deleted_count": deleted_count}


@router.get(
    "/api/v1/speaker/history/export",
    summary="Export speaker verification history as CSV",
)
@router.get(
    "/api/v1/speaker/history/csv",
    summary="Export speaker verification history as CSV",
)
async def export_speaker_history_csv(
    search: Optional[str] = Query(default=None),
    verdict: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Module 4: Export History as CSV.
    Streams an RFC 4180-compliant CSV containing the user's historical verification events.
    """
    query = db.query(SpeakerVerificationLog).filter(SpeakerVerificationLog.user_id == current_user.id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (SpeakerVerificationLog.reference_filename.ilike(term))
            | (SpeakerVerificationLog.comparison_filename.ilike(term))
            | (SpeakerVerificationLog.reference_speaker_name.ilike(term))
            | (SpeakerVerificationLog.reference_speaker_id.ilike(term))
        )
    if verdict and verdict.strip():
        query = query.filter(SpeakerVerificationLog.verdict == verdict.strip().upper())

    records = query.order_by(SpeakerVerificationLog.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Verification ID",
        "Timestamp (UTC)",
        "Speaker ID",
        "Speaker Name",
        "Reference Audio",
        "Comparison Audio",
        "Cosine Similarity",
        "Verdict",
        "Is Same Speaker",
        "Threshold Used",
        "Backbone Model",
        "Latency (ms)",
    ])
    for r in records:
        writer.writerow([
            r.id,
            r.created_at.isoformat() if r.created_at else "",
            r.reference_speaker_id or "N/A",
            r.reference_speaker_name or "N/A",
            r.reference_filename,
            r.comparison_filename,
            round(r.similarity_score, 4),
            r.verdict,
            "TRUE" if r.is_same_speaker else "FALSE",
            round(r.threshold_used, 4),
            r.model_name,
            round(r.processing_time_ms, 2),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=speaker_verification_history.csv"},
    )


# ============================================================================
# LEGACY COMPATIBILITY ROUTE ALIASES
# ============================================================================

@router.post("/api/speaker/register", response_model=SpeakerResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/speakers/register", response_model=SpeakerResponse, status_code=status.HTTP_201_CREATED)
async def register_speaker_legacy(
    request: Request,
    speaker_name: str = Form(...),
    consent_status: bool = Form(default=False),
    department: Optional[str] = Form(default=None),
    clearance_level: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy registration endpoint backward compatibility."""
    name = speaker_name.strip()
    if len(name) < 2 or len(name) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Speaker name must be between 2 and 100 characters.",
        )
    if not consent_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biometric voice enrollment requires explicit speaker consent.",
        )

    encrypted_token = None
    duration = None
    if file and file.filename:
        content = await file.read(MAX_FILE_SIZE_BYTES + 1)
        AudioPreprocessingService.validate_file_metadata(file.filename, len(content), file.content_type)
        ecapa = ECAPAService()
        try:
            norm_emb, audio_info, _ = ecapa.extract_embedding(content, filename=file.filename)
            encrypted_token = encrypt_embedding(norm_emb)
            duration = float(audio_info.get("duration_seconds") or 0.0)
        except Exception:
            pass

    spk_id = generate_speaker_id("SPK")
    registration = SpeakerRegistration(
        user_id=current_user.id,
        speaker_id=spk_id,
        speaker_name=name,
        consent_status=consent_status,
        department=department.strip() if department else None,
        clearance_level=clearance_level.strip() if clearance_level else None,
        voiceprint_embedding=None,
        voiceprint_status="ACTIVE",
        audio_duration_seconds=None,
        embedding_reference="PENDING_PHASE_2_ECAPA",
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)
    return SpeakerResponse.model_validate(registration)


@router.post("/api/speaker/verify", response_model=SpeakerVerifyResponse)
@router.post("/api/speakers/verify", response_model=SpeakerVerifyResponse)
async def verify_speaker_legacy(
    request: Request,
    speaker_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Legacy verification endpoint for Phase 1 contract compatibility.
    Always explicitly returns AI_MODEL_NOT_CONFIGURED without fabricating confidence scores.
    For production 1:1 biometric comparison, use POST /api/v1/speaker/verify.
    """
    speaker = (
        db.query(SpeakerRegistration)
        .filter(
            SpeakerRegistration.user_id == current_user.id,
            (SpeakerRegistration.speaker_id == speaker_id) | (SpeakerRegistration.id == speaker_id),
        )
        .first()
    )
    if not speaker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Registered speaker '{speaker_id}' not found.")

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio verification file is required.")

    content = await file.read(MAX_FILE_SIZE_BYTES + 1)
    AudioPreprocessingService.validate_file_metadata(file.filename, len(content), file.content_type)

    return SpeakerVerifyResponse(
        speaker_id=speaker.id,
        speaker_name=speaker.speaker_name,
        verified=False,
        status="AI_MODEL_NOT_CONFIGURED",
        message="Speaker verification model (ECAPA-TDNN) is queued for Phase 2. No similarity score fabricated.",
        confidence_score=None,
        verification_model="ECAPA-TDNN (Pending Phase 2)",
    )


@router.get("/api/speaker/list", response_model=SpeakerListResponse)
@router.get("/api/speakers", response_model=SpeakerListResponse)
async def list_speakers_legacy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy speaker list endpoint backward compatibility."""
    speakers = (
        db.query(SpeakerRegistration)
        .filter(SpeakerRegistration.user_id == current_user.id)
        .order_by(SpeakerRegistration.created_at.desc())
        .all()
    )
    return SpeakerListResponse(
        total=len(speakers),
        speakers=[SpeakerResponse.model_validate(s) for s in speakers],
    )
