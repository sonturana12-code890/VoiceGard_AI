"""
VOICEGUARD AI — Dashboard Routes
Telemetry, overview metrics, analytics aggregations, and audit logs from real database records.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import (
    AudioAnalysis,
    SecurityEvent,
    SpeakerRegistration,
    ThreatAlert,
    User,
)
from backend.schemas import (
    DashboardAnalyticsResponse,
    DashboardOverviewResponse,
    SecurityEventResponse,
)

router = APIRouter(tags=["Dashboard"])


@router.get("/api/dashboard/overview", response_model=DashboardOverviewResponse)
@router.get("/api/dashboard", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Computes dashboard metrics from actual SQLite database records.
    Returns real counts or zero when no records exist (never invents numbers).
    """
    total_uploads = (
        db.query(func.count(AudioAnalysis.id))
        .filter(AudioAnalysis.user_id == current_user.id)
        .scalar() or 0
    )

    completed = (
        db.query(func.count(AudioAnalysis.id))
        .filter(
            AudioAnalysis.user_id == current_user.id,
            AudioAnalysis.analysis_status == "completed",
        )
        .scalar() or 0
    )

    pending = (
        db.query(func.count(AudioAnalysis.id))
        .filter(
            AudioAnalysis.user_id == current_user.id,
            AudioAnalysis.analysis_status.in_(["pending", "AI_MODEL_NOT_CONFIGURED"]),
        )
        .scalar() or 0
    )

    speakers = (
        db.query(func.count(SpeakerRegistration.id))
        .filter(SpeakerRegistration.user_id == current_user.id)
        .scalar() or 0
    )

    threats = (
        db.query(func.count(ThreatAlert.id))
        .filter(ThreatAlert.user_id == current_user.id)
        .scalar() or 0
    )

    recent_events = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.user_id == current_user.id)
        .order_by(SecurityEvent.created_at.desc())
        .limit(10)
        .all()
    )

    return DashboardOverviewResponse(
        total_audio_uploads=total_uploads,
        completed_analyses=completed,
        pending_analyses=pending,
        registered_speakers=speakers,
        threat_alerts=threats,
        recent_activity=[SecurityEventResponse.model_validate(e) for e in recent_events],
    )


@router.get("/api/dashboard/analytics", response_model=DashboardAnalyticsResponse)
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregates threat and analysis telemetry across actual user records."""
    # Threat types
    threat_rows = (
        db.query(ThreatAlert.threat_type, func.count(ThreatAlert.id))
        .filter(ThreatAlert.user_id == current_user.id)
        .group_by(ThreatAlert.threat_type)
        .all()
    )
    threat_dist = {row[0]: row[1] for row in threat_rows}

    # Risk levels
    risk_rows = (
        db.query(ThreatAlert.risk_level, func.count(ThreatAlert.id))
        .filter(ThreatAlert.user_id == current_user.id)
        .group_by(ThreatAlert.risk_level)
        .all()
    )
    risk_counts = {row[0]: row[1] for row in risk_rows}

    # Status counts
    status_rows = (
        db.query(AudioAnalysis.analysis_status, func.count(AudioAnalysis.id))
        .filter(AudioAnalysis.user_id == current_user.id)
        .group_by(AudioAnalysis.analysis_status)
        .all()
    )
    status_counts = {row[0]: row[1] for row in status_rows}

    return DashboardAnalyticsResponse(
        threat_distribution=threat_dist,
        risk_level_counts=risk_counts,
        analysis_status_counts=status_counts,
        daily_volume=[],
    )


@router.get("/api/security-events", response_model=Dict[str, List[Dict[str, Any]]])
async def get_recent_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch audit event log for the current user."""
    events = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.user_id == current_user.id)
        .order_by(SecurityEvent.created_at.desc())
        .limit(50)
        .all()
    )
    return {"events": [SecurityEventResponse.model_validate(e).model_dump() for e in events]}


@router.get("/api/dashboard/recent-activity", response_model=List[SecurityEventResponse])
async def get_dashboard_recent_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    events = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.user_id == current_user.id)
        .order_by(SecurityEvent.created_at.desc())
        .limit(50)
        .all()
    )
    return [SecurityEventResponse.model_validate(event) for event in events]

