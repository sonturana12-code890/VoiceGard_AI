"""
VOICEGUARD AI — Pydantic Schemas
Data Validation & Serialization Schemas for API Requests & Responses.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ============================================================================
# USER & AUTH SCHEMAS
# ============================================================================

class UserSignup(BaseModel):
    fullName: str = Field(..., validation_alias=AliasChoices("fullName", "full_name"), min_length=2, max_length=100, description="User full name")
    email: str = Field(..., max_length=255, description="Valid corporate or user email")
    password: str = Field(..., min_length=12, max_length=128, description="Strong password")
    termsAccepted: bool = Field(default=False, validation_alias=AliasChoices("termsAccepted", "terms"), description="Terms and Privacy Notice acceptance")
    remember: bool = Field(default=False, description="Remember login session")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        trimmed = v.strip().lower()
        if not EMAIL_REGEX.match(trimmed):
            raise ValueError("Invalid email address format.")
        return trimmed

    @field_validator("fullName")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return trimmed

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters long.")
        if not any(ch.isupper() for ch in v):
            raise ValueError("Password must include at least one uppercase letter.")
        if not any(ch.islower() for ch in v):
            raise ValueError("Password must include at least one lowercase letter.")
        if not any(ch.isdigit() for ch in v):
            raise ValueError("Password must include at least one number.")
        return v


class UserLogin(BaseModel):
    email: Optional[str] = Field(default=None, max_length=255, description="Registered email address")
    username: Optional[str] = Field(default=None, max_length=255, description="Registered email/username (OAuth2 compatible)")
    password: str = Field(..., min_length=1, max_length=128, description="User password")
    remember: bool = Field(default=False, description="Persist session for 30 days")

    @model_validator(mode="before")
    @classmethod
    def resolve_email_or_username(cls, data: Any) -> Any:
        if isinstance(data, dict):
            identifier = data.get("email") or data.get("username")
            if not identifier:
                raise ValueError("Email or username is required.")
            trimmed = str(identifier).strip().lower()
            data["email"] = trimmed
            data["username"] = trimmed
        return data


class UserResponse(BaseModel):
    id: str
    fullName: str = Field(
        validation_alias=AliasChoices("fullName", "full_name"),
        serialization_alias="fullName",
    )
    email: str
    is_active: bool
    created_at: datetime

    @computed_field
    def full_name(self) -> str:
        return self.fullName

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ProfileUpdate(BaseModel):
    fullName: str = Field(..., min_length=2, max_length=100)


class PasswordUpdate(BaseModel):
    currentPassword: str = Field(..., min_length=8, max_length=128)
    newPassword: str = Field(..., min_length=8, max_length=128)


# ============================================================================
# AUDIO SCHEMAS
# ============================================================================

class AudioAnalysisResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    duration_seconds: Optional[float] = None
    analysis_status: str
    synthetic_score: Optional[float] = None
    detection_result: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AudioUploadResponse(BaseModel):
    message: str
    analysis: AudioAnalysisResponse
    model_status: str = "AI_MODEL_NOT_CONFIGURED"
    classification: Optional[str] = "INCONCLUSIVE"
    acoustic_features: Optional[Dict[str, Any]] = None


class AudioHistoryStats(BaseModel):
    total_audio_scans: int
    genuine_voices: int
    ai_generated_voices: int
    inconclusive_voices: int
    threats_detected: int


class AudioHistoryResponse(BaseModel):
    total: int
    history: List[AudioAnalysisResponse]
    stats: AudioHistoryStats


# ============================================================================
# PHASE 3: ADVANCED DETECTION & FORENSICS SCHEMAS
# ============================================================================

class AudioValidateResponse(BaseModel):
    success: bool
    valid: bool
    filename: str
    format: Optional[str] = None
    file_size: int
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    message: str
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SegmentAnalysisItem(BaseModel):
    segment_id: int
    start: float
    end: float
    prediction: str
    score: Optional[float] = None
    human_probability: Optional[float] = None
    synthetic_probability: Optional[float] = None
    status: str = "completed"


class PredictionDetails(BaseModel):
    label: str
    human_probability: Optional[float] = None
    synthetic_probability: Optional[float] = None
    confidence: Optional[float] = None
    model_used: Optional[str] = None
    inference_completed: Optional[bool] = None
    status: Optional[str] = None

    # Module 4 Explicit Standardized Attributes
    predicted_class: Optional[str] = None
    real_probability: Optional[float] = None
    fake_probability: Optional[float] = None
    model_name: Optional[str] = None
    inference_time: Optional[float] = None
    prediction_reliability: Optional[str] = None


class ModelDetails(BaseModel):
    name: str
    inference_completed: bool
    device: Optional[str] = "CPUExecutionProvider"
    version: Optional[str] = "1.0.0"


class AudioInformation(BaseModel):
    duration: float
    sample_rate: int
    channels: int
    peak_amplitude: Optional[float] = None
    rms_energy: Optional[float] = None
    silence_ratio: Optional[float] = None
    clipping_ratio: Optional[float] = None
    is_clipped: Optional[bool] = None
    is_silent: Optional[bool] = None
    is_low_volume: Optional[bool] = None
    spectral_centroid_hz: Optional[float] = None
    high_frequency_ratio: Optional[float] = None
    pitch_stability: Optional[float] = None


class ClippingInterval(BaseModel):
    start: float
    end: float
    duration: float
    clipped_samples: int
    peak_amplitude: float


class ClippingAnalysisDetails(BaseModel):
    has_clipping: bool
    clipped_samples_count: int
    clipping_ratio: float
    clipping_percentage: float
    severity: str
    affected_intervals_count: int
    clipping_intervals: List[ClippingInterval] = []


class TimeInterval(BaseModel):
    start: float
    end: float
    duration: float
    mean_dbfs: Optional[float] = None


class SilenceAnalysisDetails(BaseModel):
    total_silence_seconds: float
    silence_ratio: float
    silence_percentage: float
    silent_segments_count: int
    silent_segments: List[TimeInterval] = []


class VoiceActivityDetails(BaseModel):
    total_speech_seconds: float
    total_non_speech_seconds: float
    speech_ratio: float
    non_speech_ratio: float
    speech_percentage: float
    non_speech_percentage: float
    speech_segments_count: int
    non_speech_segments_count: int
    speech_segments: List[TimeInterval] = []
    non_speech_segments: List[TimeInterval] = []


class SnrAnalysisDetails(BaseModel):
    snr_db: Optional[float] = None
    is_reliable: bool
    classification: str
    interpretation: str
    speech_power_dbfs: Optional[float] = None
    noise_power_dbfs: Optional[float] = None
    unreliability_reason: Optional[str] = None


class NoiseFloorDetails(BaseModel):
    noise_floor_dbfs: float
    reference: str
    interpretation: str


class NoiseAnalysisDetails(BaseModel):
    has_background_noise: bool
    noise_detected: bool
    noise_intensity_score: float
    noise_intensity_label: str
    mean_noise_dbfs: float
    peak_noise_dbfs: float
    noisy_segments_count: int
    noisy_segments: List[TimeInterval] = []


class QualityScoreComponent(BaseModel):
    points: float
    max_points: float
    metric: str


class QualityScoreDetails(BaseModel):
    overall_score: float
    grade: str
    badge: str
    breakdown: Dict[str, QualityScoreComponent] = {}
    disclaimer: str


class AudioForensicsDetails(BaseModel):
    duration_seconds: float
    sample_rate: int
    total_samples: int
    peak_amplitude: float
    global_rms: float
    global_dbfs: float
    has_nan_inf_artifacts: bool = False
    noise_analysis: NoiseAnalysisDetails
    snr_analysis: SnrAnalysisDetails
    noise_floor: NoiseFloorDetails
    clipping_analysis: ClippingAnalysisDetails
    silence_analysis: SilenceAnalysisDetails
    voice_activity: VoiceActivityDetails
    quality_score: QualityScoreDetails

    model_config = ConfigDict(extra="ignore")


class StandaloneForensicsResponse(BaseModel):
    success: bool
    filename: str
    processing_time_seconds: float
    forensics: AudioForensicsDetails

    model_config = ConfigDict(extra="ignore")


class Phase3AudioAnalysisResponse(BaseModel):
    success: bool
    analysis_id: str
    filename: str
    status: str
    model_status: Optional[str] = None
    prediction: PredictionDetails
    model: ModelDetails
    audio_information: AudioInformation
    segments_analyzed: int
    processing_time_seconds: float
    segment_analysis: List[SegmentAnalysisItem]
    missing_files: Optional[List[str]] = None
    instructions: Optional[str] = None
    message: Optional[str] = None

    # Module 6 & Phase 4 Extended Analysis Fields
    audio_duration: Optional[float] = None
    sample_rate: Optional[int] = None
    channel_count: Optional[int] = None
    selected_model: Optional[str] = None
    human_probability: Optional[float] = None
    synthetic_probability: Optional[float] = None
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None
    analysis_status: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    spectrogram: Optional[Dict[str, Any]] = None
    forensics: Optional[AudioForensicsDetails] = None

    # Module 4 Standard Prediction Output Attributes
    predicted_class: Optional[str] = None
    real_probability: Optional[float] = None
    fake_probability: Optional[float] = None
    model_name: Optional[str] = None
    inference_time: Optional[float] = None
    prediction_reliability: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class Phase4AudioAnalysisResponse(Phase3AudioAnalysisResponse):
    """Phase 4 Advanced Real-Time Voice Analysis & Deepfake Detection Response Schema."""
    pass


# ============================================================================
# SPEAKER REGISTRATION & VERIFICATION SCHEMAS
# ============================================================================

class SpeakerRegisterRequest(BaseModel):
    speaker_name: str = Field(..., min_length=2, max_length=100)
    consent_status: bool = Field(default=False, description="Explicit biometric consent confirmed")
    department: Optional[str] = Field(default=None, max_length=100)
    clearance_level: Optional[str] = Field(default=None, max_length=100)


class SpeakerResponse(BaseModel):
    id: str
    speaker_name: str
    consent_status: bool
    department: Optional[str] = None
    clearance_level: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpeakerListResponse(BaseModel):
    total: int
    speakers: List[SpeakerResponse]


class SpeakerVerifyResponse(BaseModel):
    speaker_id: str
    speaker_name: str
    verified: bool
    status: str
    message: str
    confidence_score: Optional[float] = None
    verification_model: str = "ECAPA-TDNN (Pending Phase 2)"


class SpeakerVerificationResponse(BaseModel):
    """
    Production ECAPA-TDNN 1:1 Speaker Verification Output Schema.
    Exposes cosine similarity in the 192-dim latent space with explicit
    uncalibrated disclosure and audio quality warnings.
    """
    success: bool = True
    model_name: str = "ECAPA-TDNN (VoxCeleb)"
    embedding_dimension: int = 192
    cosine_similarity: float
    verdict: Optional[str] = None  # "SAME_SPEAKER" | "DIFFERENT_SPEAKER" | "INCONCLUSIVE"
    verification_status: str  # "SAME_SPEAKER" | "DIFFERENT_SPEAKER" | "INCONCLUSIVE"
    is_same_speaker: bool
    threshold: float
    processing_time: float
    processing_time_seconds: float
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = None
    audio_quality_warnings: List[str] = Field(default_factory=list)
    interpretation_note: str = (
        "Cosine similarity reflects directional alignment in the 192-dimensional "
        "latent speaker embedding space. It is not a calibrated probability. "
        "Thresholds should be calibrated on target acoustic environments."
    )
    reference_audio_info: Optional[Dict[str, Any]] = None
    comparison_audio_info: Optional[Dict[str, Any]] = None


class SpeakerEnrollResponse(BaseModel):
    """Enrollment confirmation response with biometric voiceprint metadata."""
    id: str
    speaker_id: str
    speaker_name: str
    consent_status: bool
    department: Optional[str] = None
    clearance_level: Optional[str] = None
    voiceprint_status: str = "ACTIVE"
    embedding_dimension: int = 192
    audio_duration_seconds: Optional[float] = None
    audio_quality_warnings: List[str] = Field(default_factory=list)
    created_at: datetime
    message: str = "Biometric voiceprint enrolled successfully."
    consent_verified: bool = True

    model_config = ConfigDict(from_attributes=True)


class SpeakerProfileResponse(BaseModel):
    """Enrolled biometric voiceprint profile details (never exposes raw embedding vector)."""
    id: str
    speaker_id: str
    speaker_name: str
    consent_status: bool
    department: Optional[str] = None
    clearance_level: Optional[str] = None
    voiceprint_status: str = "ACTIVE"
    audio_duration_seconds: Optional[float] = None
    verification_count: int = 0
    last_verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SpeakerProfileListResponse(BaseModel):
    """List of enrolled speaker biometric profiles owned by authenticated user."""
    total: int
    profiles: List[SpeakerProfileResponse]


class SpeakerVerificationHistoryItem(BaseModel):
    """Individual verification history record."""
    id: str
    reference_speaker_id: Optional[str] = None
    reference_speaker_name: Optional[str] = None
    reference_filename: str
    comparison_filename: str
    similarity_score: float
    verdict: str
    is_same_speaker: bool
    threshold_used: float
    model_name: str = "ECAPA-TDNN (VoxCeleb)"
    processing_time_ms: float
    audio_quality_warnings: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpeakerVerificationHistoryResponse(BaseModel):
    """Paginated verification history log with summary statistics."""
    total: int
    same_speaker_count: int = 0
    different_speaker_count: int = 0
    inconclusive_count: int = 0
    average_similarity: float = 0.0
    items: List[SpeakerVerificationHistoryItem]


# ============================================================================
# THREAT ALERT & MONITORING SCHEMAS
# ============================================================================

class ThreatAlertResponse(BaseModel):
    id: str
    threat_type: str
    risk_level: str
    description: str
    status: str
    analysis_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ThreatStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(active|investigating|resolved|dismissed)$")


class ThreatListResponse(BaseModel):
    total: int
    threats: List[ThreatAlertResponse]


# ============================================================================
# SECURITY EVENT SCHEMAS
# ============================================================================

class SecurityEventResponse(BaseModel):
    id: str
    event_type: str
    event_description: str
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityEventListResponse(BaseModel):
    total: int
    events: List[SecurityEventResponse]


# ============================================================================
# DASHBOARD SCHEMAS
# ============================================================================

class DashboardOverviewResponse(BaseModel):
    total_audio_uploads: int
    completed_analyses: int
    pending_analyses: int
    registered_speakers: int
    threat_alerts: int
    recent_activity: List[SecurityEventResponse]


class DashboardAnalyticsResponse(BaseModel):
    threat_distribution: Dict[str, int]
    risk_level_counts: Dict[str, int]
    analysis_status_counts: Dict[str, int]
    daily_volume: List[Dict[str, Any]]


# ============================================================================
# REPORT SCHEMAS
# ============================================================================

class ReportResponse(BaseModel):
    report_id: str
    generated_at: datetime
    user_email: str
    total_audios: int
    total_threats: int
    total_speakers: int
    summary: Dict[str, Any]
    analyses: List[AudioAnalysisResponse]
    threats: List[ThreatAlertResponse]
