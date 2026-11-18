"""
VOICEGUARD AI — Reports Routes
Endpoints for generating and exporting forensic voice defense reports.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db
from backend.models import User
from backend.schemas import ReportResponse
from backend.services.report_service import ReportService

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("", response_model=ReportResponse)
async def generate_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generates an up-to-date summary report from actual SQLite records."""
    report_data = ReportService.generate_user_report(db, current_user)
    return report_data


@router.get("/export")
async def export_report_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exports all user analysis history and threat alerts as a downloadable CSV file."""
    csv_content = ReportService.export_csv(db, current_user)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="voiceguard-forensic-report.csv"'},
    )


@router.get("/{report_id}")
async def get_report_by_id(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the generated forensic report for the authenticated user."""
    return ReportService.generate_user_report(db, current_user)

