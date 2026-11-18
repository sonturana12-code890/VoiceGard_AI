"""
VOICEGUARD AI — Threat Monitoring Routes
Endpoints for querying, reviewing, and managing real-time acoustic threat alerts.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.auth import get_current_user, log_security_event
from backend.database import get_db
from backend.models import ThreatAlert, User
from backend.schemas import (
    ThreatAlertResponse,
    ThreatListResponse,
    ThreatStatusUpdate,
)

router = APIRouter(prefix="/api/threats", tags=["Threat Monitoring"])


@router.get("", response_model=ThreatListResponse)
async def list_threats(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    risk_filter: Optional[str] = Query(default=None, alias="risk"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve threat alerts filtered by status and risk level."""
    query = db.query(ThreatAlert).filter(ThreatAlert.user_id == current_user.id)

    if status_filter:
        query = query.filter(ThreatAlert.status == status_filter)
    if risk_filter:
        query = query.filter(ThreatAlert.risk_level == risk_filter)

    threats = query.order_by(ThreatAlert.created_at.desc()).all()

    return ThreatListResponse(
        total=len(threats),
        threats=[ThreatAlertResponse.model_validate(t) for t in threats],
    )


@router.get("/{threat_id}", response_model=ThreatAlertResponse)
async def get_threat_detail(
    threat_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details for a specific threat alert."""
    threat = (
        db.query(ThreatAlert)
        .filter(ThreatAlert.id == threat_id, ThreatAlert.user_id == current_user.id)
        .first()
    )

    if not threat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Threat alert '{threat_id}' was not found.",
        )

    return ThreatAlertResponse.model_validate(threat)


@router.patch("/{threat_id}/status", response_model=ThreatAlertResponse)
async def update_threat_status(
    threat_id: str,
    body: ThreatStatusUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update incident mitigation status for a threat alert."""
    threat = (
        db.query(ThreatAlert)
        .filter(ThreatAlert.id == threat_id, ThreatAlert.user_id == current_user.id)
        .first()
    )

    if not threat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Threat alert '{threat_id}' was not found.",
        )

    old_status = threat.status
    threat.status = body.status
    db.commit()
    db.refresh(threat)

    log_security_event(
        db,
        current_user.id,
        "threat.status_update",
        f"Updated threat '{threat.threat_type}' status from '{old_status}' to '{body.status}'",
        request,
    )

    return ThreatAlertResponse.model_validate(threat)

