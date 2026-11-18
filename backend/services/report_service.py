"""
VOICEGUARD AI — Reporting Service
Aggregates actual database records to generate forensic security reports.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.models import AudioAnalysis, SpeakerRegistration, ThreatAlert, User


class ReportService:
    """Generates structured forensic reports and CSV exports from actual database telemetry."""

    @staticmethod
    def generate_user_report(db: Session, user: User) -> Dict[str, Any]:
        """Collects all real records for the user and computes metrics."""
        analyses = (
            db.query(AudioAnalysis)
            .filter(AudioAnalysis.user_id == user.id)
            .order_by(AudioAnalysis.created_at.desc())
            .all()
        )

        threats = (
            db.query(ThreatAlert)
            .filter(ThreatAlert.user_id == user.id)
            .order_by(ThreatAlert.created_at.desc())
            .all()
        )

        speakers = (
            db.query(SpeakerRegistration)
            .filter(SpeakerRegistration.user_id == user.id)
            .order_by(SpeakerRegistration.created_at.desc())
            .all()
        )

        # Compute status distribution
        status_counts: Dict[str, int] = {}
        for a in analyses:
            status_counts[a.analysis_status] = status_counts.get(a.analysis_status, 0) + 1

        # Compute risk distribution
        threat_distribution: Dict[str, int] = {}
        for t in threats:
            threat_distribution[t.risk_level] = threat_distribution.get(t.risk_level, 0) + 1

        return {
            "report_id": f"REP-{user.id[:8].upper()}-{int(datetime.now(timezone.utc).timestamp())}",
            "generated_at": datetime.now(timezone.utc),
            "user_email": user.email,
            "user_name": user.full_name,
            "total_audios": len(analyses),
            "total_threats": len(threats),
            "total_speakers": len(speakers),
            "summary": {
                "analysis_status_breakdown": status_counts,
                "threat_risk_breakdown": threat_distribution,
                "model_status": "Phase 1 Baseline (AI models pending configuration)",
            },
            "analyses": analyses,
            "threats": threats,
        }

    @staticmethod
    def export_csv(db: Session, user: User) -> str:
        """Exports user analysis history and threat alerts as a clean CSV string."""
        analyses = (
            db.query(AudioAnalysis)
            .filter(AudioAnalysis.user_id == user.id)
            .order_by(AudioAnalysis.created_at.desc())
            .all()
        )

        threats = (
            db.query(ThreatAlert)
            .filter(ThreatAlert.user_id == user.id)
            .order_by(ThreatAlert.created_at.desc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Record Type", "ID", "Timestamp (UTC)", "Status/Risk", "Resource/File", "Details"])

        for a in analyses:
            writer.writerow([
                "audio_analysis",
                a.id,
                a.created_at.isoformat() if a.created_at else "",
                a.analysis_status,
                a.filename,
                a.detection_result or "",
            ])

        for t in threats:
            writer.writerow([
                "threat_alert",
                t.id,
                t.created_at.isoformat() if t.created_at else "",
                t.risk_level,
                t.threat_type,
                t.description,
            ])

        return output.getvalue()

