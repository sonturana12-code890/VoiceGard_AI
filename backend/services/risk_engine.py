"""
VOICEGUARD AI — Modular Fraud Risk Assessment Engine
Evaluates synthetic detection evidence, speaker verification, and contextual factors.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class FraudRiskEngine:
    """
    Evaluates cybersecurity risk level for voice channels.
    Combines synthetic speech detection, biometric speaker verification,
    and contextual transaction sensitivity.
    """

    @staticmethod
    def assess_risk(
        synthetic_score: Optional[float] = None,
        speaker_verified: Optional[bool] = None,
        speaker_confidence: Optional[float] = None,
        transaction_amount: Optional[float] = None,
        protocol_type: Optional[str] = "SIP",
        geo_spoofing_detected: bool = False,
    ) -> Dict[str, Any]:
        """
        Calculates an objective risk score when empirical model outputs are provided.
        In Phase 1, if model outputs are absent, clearly reports an incomplete assessment
        rather than inventing probabilities.
        """
        # If no synthetic score is available, do not fabricate scores.
        if synthetic_score is None:
            return {
                "assessment_status": "INCOMPLETE_ASSESSMENT",
                "risk_level": "UNASSESSED",
                "confidence_score": None,
                "summary": "Voice analysis model is not configured. Risk cannot be calculated without empirical model outputs.",
                "factors": {
                    "synthetic_speech_model": "NOT_CONFIGURED",
                    "speaker_verification_model": "NOT_CONFIGURED",
                    "geo_spoofing_flag": geo_spoofing_detected,
                },
                "recommended_action": "ENFORCE_MANUAL_OUT_OF_BAND_VERIFICATION",
                "action_protocol": "Step-up FIDO2 / hardware token authentication required."
            }

        # When real model output is present (Phase 2):
        # Model probabilities are normalized from 0.0 (genuine) to 1.0 (synthetic).
        risk_level = "Low"
        factors = []

        if synthetic_score >= 0.85:
            risk_level = "Critical"
            factors.append("High probability of neural voice cloning artifact.")
        elif synthetic_score >= 0.60:
            risk_level = "High"
            factors.append("Moderate synthetic jitter and spectral anomalies detected.")
        elif synthetic_score >= 0.35:
            risk_level = "Medium"
            factors.append("Acoustic anomalies present; potential voice changer or spliced audio.")
        else:
            risk_level = "Low"
            factors.append("Acoustic features consistent with biological human vocal tract.")

        if speaker_verified is False:
            if risk_level in ("Low", "Medium"):
                risk_level = "High"
            factors.append("Claimed speaker voiceprint does not match registered biometrics.")

        if geo_spoofing_detected:
            factors.append("SIP carrier signalling origin does not match expected subscriber geography.")

        return {
            "assessment_status": "COMPLETED",
            "risk_level": risk_level,
            "synthetic_score": synthetic_score,
            "factors": factors,
            "recommended_action": (
                "Quarantine voice channel and enforce step-up authentication"
                if risk_level in ("High", "Critical")
                else "Allow transaction to proceed with standard monitoring"
            ),
        }

