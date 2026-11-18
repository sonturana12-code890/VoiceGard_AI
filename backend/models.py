"""
VOICEGUARD AI — Database Models
SQLAlchemy Declarative Models for Users, Audio Analysis, Speakers, Threats, and Security Events.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.database import Base


def get_uuid_str() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=get_uuid_str)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    audio_analyses = relationship(
        "AudioAnalysis", back_populates="user", cascade="all, delete-orphan"
    )
    speaker_registrations = relationship(
        "SpeakerRegistration", back_populates="user", cascade="all, delete-orphan"
    )
    speaker_verification_logs = relationship(
        "SpeakerVerificationLog", back_populates="user", cascade="all, delete-orphan"
    )
    threat_alerts = relationship(
        "ThreatAlert", back_populates="user", cascade="all, delete-orphan"
    )
    security_events = relationship(
        "SecurityEvent", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class AudioAnalysis(Base):
    __tablename__ = "audio_analysis"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=get_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    stored_path = Column(String(512), nullable=True)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    duration_seconds = Column(Float, nullable=True)
    analysis_status = Column(String(50), nullable=False, default="pending")  # pending, completed, failed, AI_MODEL_NOT_CONFIGURED
    synthetic_score = Column(Float, nullable=True)  # Null in Phase 1 (no fake scores)
    detection_result = Column(Text, nullable=True)  # Detailed outcome or AI_MODEL_NOT_CONFIGURED note
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="audio_analyses")

    def __repr__(self) -> str:
        return f"<AudioAnalysis id={self.id} filename={self.filename} status={self.analysis_status}>"


class SpeakerRegistration(Base):
    __tablename__ = "speaker_registrations"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=get_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_id = Column(String(64), nullable=True, index=True)  # Unique user-visible ID, e.g. "SPK-49102"
    speaker_name = Column(String(100), nullable=False)
    consent_status = Column(Boolean, default=False, nullable=False)
    department = Column(String(100), nullable=True)
    clearance_level = Column(String(100), nullable=True)
    reference_audio_path = Column(String(512), nullable=True)
    embedding_reference = Column(String(255), nullable=True)
    voiceprint_embedding = Column(Text, nullable=True)  # Authenticated encrypted 192-dim float32 vector
    voiceprint_status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, INACTIVE, REVOKED
    audio_duration_seconds = Column(Float, nullable=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    user = relationship("User", back_populates="speaker_registrations")

    def __repr__(self) -> str:
        return f"<SpeakerRegistration id={self.id} speaker_id={self.speaker_id} speaker_name={self.speaker_name}>"


class SpeakerVerificationLog(Base):
    __tablename__ = "speaker_verification_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=get_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reference_speaker_id = Column(String(64), nullable=True, index=True)
    reference_speaker_name = Column(String(100), nullable=True)
    reference_filename = Column(String(255), nullable=False)
    comparison_filename = Column(String(255), nullable=False)
    similarity_score = Column(Float, nullable=False)
    verdict = Column(String(32), nullable=False)  # "SAME_SPEAKER", "DIFFERENT_SPEAKER", "INCONCLUSIVE"
    is_same_speaker = Column(Boolean, nullable=False)
    threshold_used = Column(Float, nullable=False)
    model_name = Column(String(100), default="ECAPA-TDNN (VoxCeleb)", nullable=False)
    processing_time_ms = Column(Float, nullable=False)
    audio_quality_warnings = Column(Text, nullable=True)  # JSON string array
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)

    user = relationship("User", back_populates="speaker_verification_logs")

    def __repr__(self) -> str:
        return f"<SpeakerVerificationLog id={self.id} verdict={self.verdict} score={self.similarity_score}>"


class ThreatAlert(Base):
    __tablename__ = "threat_alerts"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=get_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    threat_type = Column(String(100), nullable=False)  # Voice Cloning, Replay Attack, TTS Impersonation, etc.
    risk_level = Column(String(50), nullable=False)    # Low, Medium, High, Critical
    description = Column(Text, nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active, investigating, resolved, dismissed
    analysis_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="threat_alerts")

    def __repr__(self) -> str:
        return f"<ThreatAlert id={self.id} type={self.threat_type} risk={self.risk_level}>"


class SecurityEvent(Base):
    __tablename__ = "security_events"
    __table_args__ = {"extend_existing": True}

    id = Column(String(36), primary_key=True, default=get_uuid_str)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False)  # auth.signup, auth.login, audio.upload, etc.
    event_description = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="security_events")

    def __repr__(self) -> str:
        return f"<SecurityEvent id={self.id} type={self.event_type}>"

