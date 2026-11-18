"""
VOICEGUARD AI — Advanced Audio Forensics & Noise Analysis Engine
Production-grade empirical signal forensics module extracting noise characteristics,
SNR in decibels, background noise floor, sample clipping, silence boundaries,
Voice Activity Detection (VAD) segments, and an explainable Audio Quality Score (0-100).

Strict Zero-Hallucination Policy: All metrics are computed directly from PCM signal tensors.
No fabricated or pseudo-random values.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("voiceguard.forensics")


class AudioForensicsService:
    """
    Advanced audio signal forensics engine executing deterministic acoustic diagnostics:
    1. Background Noise Detection & Intensity Estimation
    2. Signal-to-Noise Ratio (SNR in dB) with Reliability Evaluation
    3. Noise Floor Estimation in dBFS
    4. Digital Clipping Detection with Timestamped Interval Mapping
    5. Silence Detection with Contiguous Interval Demarcation
    6. Voice Activity Detection (VAD) separating Speech vs Non-Speech
    7. Explainable Audio Quality Score (0-100) with Metric Breakdown
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: float = 20.0,
        hop_ms: float = 10.0,
        clipping_threshold: float = 0.995,
        hangover_frames: int = 10,
    ):
        self.sample_rate = sample_rate
        self.frame_len = max(1, int(sample_rate * (frame_ms / 1000.0)))  # 320 samples at 16kHz
        self.hop_len = max(1, int(sample_rate * (hop_ms / 1000.0)))      # 160 samples at 16kHz
        self.clipping_threshold = clipping_threshold
        self.hangover_frames = hangover_frames

    def analyze(self, pcm: np.ndarray, sample_rate: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes complete audio forensic evaluation on 1D float32 audio signal.
        """
        sr = sample_rate or self.sample_rate
        frame_len = max(1, int(sr * 0.02))  # 20ms
        hop_len = max(1, int(sr * 0.01))    # 10ms

        if pcm is None or len(pcm) == 0:
            return self._empty_forensics_report(sr)

        # 1. Clean & validate input signal
        has_nan_inf = bool(np.isnan(pcm).any() or np.isinf(pcm).any())
        clean_pcm = np.nan_to_num(pcm, nan=0.0, posinf=1.0, neginf=-1.0).astype(np.float32)
        total_samples = len(clean_pcm)
        duration = float(total_samples / sr)

        # 2. Short-time frame segmentation & RMS power
        frames, frame_times = self._frame_signal(clean_pcm, frame_len, hop_len, sr)
        num_frames = len(frames)

        if num_frames == 0:
            return self._empty_forensics_report(sr, duration=duration)

        frame_rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
        frame_dbfs = 20.0 * np.log10(np.maximum(frame_rms, 1e-7))
        frame_dbfs = np.clip(frame_dbfs, -140.0, 0.0)

        # Global signal stats
        peak_amp = float(np.max(np.abs(clean_pcm)))
        global_rms = float(np.sqrt(np.mean(clean_pcm ** 2) + 1e-12))
        global_dbfs = float(20.0 * math.log10(max(global_rms, 1e-7)))

        # 3. Audio Clipping Detection
        clipping_res = self._detect_clipping(clean_pcm, sr, self.clipping_threshold)

        # 4. Noise Floor Estimation
        noise_floor_dbfs = self._estimate_noise_floor(frame_dbfs)

        # 5. Silence & VAD Detection
        vad_res = self._classify_vad_and_silence(
            frame_rms=frame_rms,
            frame_dbfs=frame_dbfs,
            frame_times=frame_times,
            noise_floor_dbfs=noise_floor_dbfs,
            duration=duration,
            hop_ms=hop_len / sr,
        )

        # 6. Signal-to-Noise Ratio (SNR) Calculation
        snr_res = self._calculate_snr(
            clean_pcm=clean_pcm,
            frames=frames,
            speech_mask=vad_res["speech_frame_mask"],
            noise_floor_dbfs=noise_floor_dbfs,
            duration=duration,
        )

        # 7. Background Noise Analysis
        noise_res = self._detect_background_noise(
            frame_dbfs=frame_dbfs,
            frame_times=frame_times,
            speech_mask=vad_res["speech_frame_mask"],
            noise_floor_dbfs=noise_floor_dbfs,
            duration=duration,
        )

        # 8. Explainable Audio Quality Score (0-100)
        quality_score_res = self._compute_quality_score(
            snr_db=snr_res.get("snr_db"),
            snr_reliable=snr_res.get("is_reliable", False),
            clipping_ratio=clipping_res["clipping_ratio"],
            noise_floor_dbfs=noise_floor_dbfs,
            peak_amplitude=peak_amp,
            global_dbfs=global_dbfs,
            speech_ratio=vad_res["speech_ratio"],
            silence_ratio=vad_res["silence_ratio"],
            duration=duration,
        )

        return {
            "duration_seconds": round(duration, 3),
            "sample_rate": sr,
            "total_samples": total_samples,
            "peak_amplitude": round(peak_amp, 4),
            "global_rms": round(global_rms, 5),
            "global_dbfs": round(global_dbfs, 2),
            "has_nan_inf_artifacts": has_nan_inf,
            "noise_analysis": noise_res,
            "snr_analysis": snr_res,
            "noise_floor": {
                "noise_floor_dbfs": round(noise_floor_dbfs, 2),
                "reference": "16-bit Full Scale Digital (-96 dBFS ideal floor)",
                "interpretation": self._interpret_noise_floor(noise_floor_dbfs),
            },
            "clipping_analysis": clipping_res,
            "silence_analysis": {
                "total_silence_seconds": round(vad_res["total_silence_seconds"], 3),
                "silence_ratio": round(vad_res["silence_ratio"], 4),
                "silence_percentage": round(vad_res["silence_ratio"] * 100.0, 2),
                "silent_segments_count": len(vad_res["silence_segments"]),
                "silent_segments": vad_res["silence_segments"],
            },
            "voice_activity": {
                "total_speech_seconds": round(vad_res["total_speech_seconds"], 3),
                "total_non_speech_seconds": round(vad_res["total_non_speech_seconds"], 3),
                "speech_ratio": round(vad_res["speech_ratio"], 4),
                "non_speech_ratio": round(vad_res["non_speech_ratio"], 4),
                "speech_percentage": round(vad_res["speech_ratio"] * 100.0, 2),
                "non_speech_percentage": round(vad_res["non_speech_ratio"] * 100.0, 2),
                "speech_segments_count": len(vad_res["speech_segments"]),
                "non_speech_segments_count": len(vad_res["non_speech_segments"]),
                "speech_segments": vad_res["speech_segments"],
                "non_speech_segments": vad_res["non_speech_segments"],
            },
            "quality_score": quality_score_res,
        }

    # =========================================================================
    # INTERNAL SIGNAL PROCESSING METHODS
    # =========================================================================

    def _frame_signal(
        self, signal: np.ndarray, frame_len: int, hop_len: int, sr: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Splits 1D signal into overlapping frames and returns times (seconds)."""
        num_samples = len(signal)
        if num_samples < frame_len:
            # Pad with zeros to at least 1 frame
            padded = np.pad(signal, (0, frame_len - num_samples), mode="constant")
            return np.array([padded], dtype=np.float32), np.array([0.0], dtype=np.float32)

        num_frames = 1 + (num_samples - frame_len) // hop_len
        # Strided framing
        shape = (num_frames, frame_len)
        strides = (signal.strides[0] * hop_len, signal.strides[0])
        frames = np.lib.stride_tricks.as_strided(signal, shape=shape, strides=strides)
        frame_times = np.arange(num_frames, dtype=np.float32) * (hop_len / sr)
        return frames, frame_times

    def _detect_clipping(
        self, signal: np.ndarray, sr: int, threshold: float = 0.995
    ) -> Dict[str, Any]:
        """
        Identifies saturated samples (|x| >= threshold) and aggregates into timestamped intervals.
        """
        is_clipped = np.abs(signal) >= threshold
        clipped_indices = np.where(is_clipped)[0]
        clipped_count = int(len(clipped_indices))
        total_samples = len(signal)
        clipping_ratio = float(clipped_count / total_samples) if total_samples > 0 else 0.0

        intervals: List[Dict[str, Any]] = []
        if clipped_count > 0:
            # Cluster clipped samples within 50ms (sr * 0.05 samples)
            cluster_gap = int(sr * 0.05)
            splits = np.where(np.diff(clipped_indices) > cluster_gap)[0] + 1
            clusters = np.split(clipped_indices, splits)

            for c in clusters:
                if len(c) == 0:
                    continue
                start_sec = round(float(c[0] / sr), 3)
                end_sec = round(float(c[-1] / sr), 3)
                dur_sec = round(max(0.001, end_sec - start_sec), 3)
                peak_val = round(float(np.max(np.abs(signal[c]))), 4)
                intervals.append({
                    "start": start_sec,
                    "end": end_sec,
                    "duration": dur_sec,
                    "clipped_samples": int(len(c)),
                    "peak_amplitude": peak_val,
                })

        severity = (
            "None" if clipped_count == 0
            else "Minor" if clipping_ratio < 0.001
            else "Moderate" if clipping_ratio < 0.01
            else "Severe"
        )

        return {
            "has_clipping": bool(clipped_count > 0),
            "clipped_samples_count": clipped_count,
            "clipping_ratio": round(clipping_ratio, 6),
            "clipping_percentage": round(clipping_ratio * 100.0, 3),
            "severity": severity,
            "affected_intervals_count": len(intervals),
            "clipping_intervals": intervals[:50],  # Cap at 50 intervals to prevent JSON bloat
        }

    def _estimate_noise_floor(self, frame_dbfs: np.ndarray) -> float:
        """
        Robustly estimates the acoustic noise floor using the 15th percentile of short-time energies.
        Speech occupies upper energy percentiles; quiet intervals cluster near the 10th-20th percentile.
        """
        if len(frame_dbfs) == 0:
            return -100.0
        # 15th percentile of dBFS distribution
        nf = float(np.percentile(frame_dbfs, 15))
        # Clamp to realistic bounds (-100 dBFS to -10 dBFS)
        return float(np.clip(nf, -100.0, -10.0))

    def _classify_vad_and_silence(
        self,
        frame_rms: np.ndarray,
        frame_dbfs: np.ndarray,
        frame_times: np.ndarray,
        noise_floor_dbfs: float,
        duration: float,
        hop_ms: float,
    ) -> Dict[str, Any]:
        """
        Executes Voice Activity Detection (VAD) and Silence Detection using adaptive energy thresholds
        with morphological hangover smoothing.
        """
        num_frames = len(frame_dbfs)

        # Adaptive thresholds
        # Pure silence threshold: absolute quiet below -55 dBFS or baseline + 3 dB
        silence_thresh_dbfs = max(-65.0, min(-50.0, noise_floor_dbfs + 4.0))
        # Speech threshold: clear acoustic presence above noise floor (+10 dB) or minimum -45 dBFS
        speech_thresh_dbfs = max(-45.0, min(-20.0, noise_floor_dbfs + 10.0))

        raw_silence_mask = frame_dbfs < silence_thresh_dbfs
        raw_speech_mask = frame_dbfs >= speech_thresh_dbfs

        # Apply hangover smoothing (closing short inter-word gaps of <= 100ms)
        hangover = max(2, self.hangover_frames)
        speech_mask = self._smooth_binary_mask(raw_speech_mask, hangover_len=hangover)

        # Silence mask should not overlap smoothed speech
        silence_mask = raw_silence_mask & (~speech_mask)

        # Non-speech mask is simply the complement of speech
        non_speech_mask = ~speech_mask

        # Build contiguous intervals
        speech_segments = self._mask_to_intervals(speech_mask, frame_times, frame_dbfs, hop_ms, duration)
        silence_segments = self._mask_to_intervals(silence_mask, frame_times, frame_dbfs, hop_ms, duration)
        non_speech_segments = self._mask_to_intervals(non_speech_mask, frame_times, frame_dbfs, hop_ms, duration)

        total_speech_sec = sum(s["duration"] for s in speech_segments)
        total_silence_sec = sum(s["duration"] for s in silence_segments)
        total_non_speech_sec = sum(s["duration"] for s in non_speech_segments)

        speech_ratio = float(total_speech_sec / duration) if duration > 0 else 0.0
        silence_ratio = float(total_silence_sec / duration) if duration > 0 else 0.0
        non_speech_ratio = float(total_non_speech_sec / duration) if duration > 0 else 0.0

        return {
            "speech_frame_mask": speech_mask,
            "silence_frame_mask": silence_mask,
            "speech_segments": speech_segments,
            "silence_segments": silence_segments,
            "non_speech_segments": non_speech_segments,
            "total_speech_seconds": total_speech_sec,
            "total_silence_seconds": total_silence_sec,
            "total_non_speech_seconds": total_non_speech_sec,
            "speech_ratio": min(1.0, speech_ratio),
            "silence_ratio": min(1.0, silence_ratio),
            "non_speech_ratio": min(1.0, non_speech_ratio),
        }

    def _smooth_binary_mask(self, mask: np.ndarray, hangover_len: int = 8) -> np.ndarray:
        """Applies hangover smoothing to prevent false chopped speech segments."""
        smoothed = mask.copy()
        n = len(mask)
        # Forward pass hangover: if speech ends, sustain it for hangover_len frames
        active_count = 0
        for i in range(n):
            if mask[i]:
                active_count = hangover_len
                smoothed[i] = True
            elif active_count > 0:
                smoothed[i] = True
                active_count -= 1
        return smoothed

    def _mask_to_intervals(
        self,
        mask: np.ndarray,
        frame_times: np.ndarray,
        frame_dbfs: np.ndarray,
        hop_sec: float,
        total_duration: float,
    ) -> List[Dict[str, Any]]:
        """Converts a boolean frame array into contiguous [start, end] intervals."""
        intervals: List[Dict[str, Any]] = []
        in_segment = False
        start_idx = 0

        for i, val in enumerate(mask):
            if val and not in_segment:
                in_segment = True
                start_idx = i
            elif not val and in_segment:
                in_segment = False
                start_t = round(float(frame_times[start_idx]), 3)
                end_t = round(min(total_duration, float(frame_times[i - 1] + hop_sec)), 3)
                dur = round(max(0.01, end_t - start_t), 3)
                mean_db = round(float(np.mean(frame_dbfs[start_idx:i])), 1)
                intervals.append({
                    "start": start_t,
                    "end": end_t,
                    "duration": dur,
                    "mean_dbfs": mean_db,
                })

        if in_segment:
            start_t = round(float(frame_times[start_idx]), 3)
            end_t = round(total_duration, 3)
            dur = round(max(0.01, end_t - start_t), 3)
            mean_db = round(float(np.mean(frame_dbfs[start_idx:])), 1)
            intervals.append({
                "start": start_t,
                "end": end_t,
                "duration": dur,
                "mean_dbfs": mean_db,
            })

        return intervals

    def _calculate_snr(
        self,
        clean_pcm: np.ndarray,
        frames: np.ndarray,
        speech_mask: np.ndarray,
        noise_floor_dbfs: float,
        duration: float,
    ) -> Dict[str, Any]:
        """
        Calculates empirical Signal-to-Noise Ratio (SNR) in decibels.
        Handles boundary conditions where speech or pause is absent.
        """
        total_frames = len(speech_mask)
        speech_indices = np.where(speech_mask)[0]
        non_speech_indices = np.where(~speech_mask)[0]

        # Case 1: Pure silence / no speech detected
        if len(speech_indices) == 0:
            return {
                "snr_db": None,
                "is_reliable": False,
                "classification": "UNAVAILABLE",
                "interpretation": "SNR cannot be calculated: No active voice or speech detected in the audio file.",
                "speech_power_dbfs": None,
                "noise_power_dbfs": round(noise_floor_dbfs, 2),
                "unreliability_reason": "NO_SPEECH_DETECTED",
            }

        # Compute speech power
        speech_frames = frames[speech_indices]
        speech_power = float(np.mean(speech_frames ** 2))
        speech_power_dbfs = float(10.0 * math.log10(max(speech_power, 1e-12)))

        # Case 2: No pauses / continuous speech throughout entire audio (>98% speech frames)
        if len(non_speech_indices) == 0 or (len(non_speech_indices) / total_frames < 0.02):
            # Estimate noise from lower 10% energy frames as fallback
            frame_powers = np.mean(frames ** 2, axis=1)
            lowest_power = float(np.percentile(frame_powers, 10))
            noise_power = max(lowest_power, 1e-12)
            noise_power_dbfs = float(10.0 * math.log10(noise_power))

            snr_val = float(10.0 * math.log10(max(speech_power / noise_power, 1.0)))
            return {
                "snr_db": round(snr_val, 2),
                "is_reliable": False,
                "classification": self._classify_snr(snr_val),
                "interpretation": f"Approximate SNR: ~{round(snr_val, 1)} dB (Continuous speech without inter-sentence pauses; noise baseline estimated from energy valley).",
                "speech_power_dbfs": round(speech_power_dbfs, 2),
                "noise_power_dbfs": round(noise_power_dbfs, 2),
                "unreliability_reason": "INSUFFICIENT_PAUSE_INTERVALS",
            }

        # Case 3: Standard normal case with both speech and non-speech intervals
        non_speech_frames = frames[non_speech_indices]
        noise_power = float(np.mean(non_speech_frames ** 2))
        noise_power = max(noise_power, 1e-12)
        noise_power_dbfs = float(10.0 * math.log10(noise_power))

        snr_ratio = max(speech_power / noise_power, 1e-6)
        snr_db = float(10.0 * math.log10(snr_ratio))

        classification = self._classify_snr(snr_db)
        interpretation = self._interpret_snr(snr_db, classification)

        return {
            "snr_db": round(snr_db, 2),
            "is_reliable": True,
            "classification": classification,
            "interpretation": interpretation,
            "speech_power_dbfs": round(speech_power_dbfs, 2),
            "noise_power_dbfs": round(noise_power_dbfs, 2),
            "unreliability_reason": None,
        }

    def _classify_snr(self, snr_db: float) -> str:
        if snr_db >= 30.0:
            return "EXCELLENT"
        elif snr_db >= 20.0:
            return "GOOD"
        elif snr_db >= 12.0:
            return "FAIR"
        elif snr_db >= 5.0:
            return "POOR"
        else:
            return "CRITICAL"

    def _interpret_snr(self, snr_db: float, classification: str) -> str:
        if classification == "EXCELLENT":
            return f"Excellent Signal-to-Noise Ratio ({round(snr_db, 1)} dB): Pristine studio-grade acoustic clarity with virtually undetectable background noise."
        elif classification == "GOOD":
            return f"Good Signal-to-Noise Ratio ({round(snr_db, 1)} dB): Clear conversational voice signal with minimal background noise."
        elif classification == "FAIR":
            return f"Fair Signal-to-Noise Ratio ({round(snr_db, 1)} dB): Moderate background noise present (e.g. office ambient, ventilation), voice remains intelligible."
        elif classification == "POOR":
            return f"Poor Signal-to-Noise Ratio ({round(snr_db, 1)} dB): Substantial noise interference (traffic, street, room reverberation) noticeably degrading speech signal."
        else:
            return f"Critical Signal-to-Noise Ratio ({round(snr_db, 1)} dB): Severe noise dominance where background acoustic energy approaches or eclipses speech."

    def _detect_background_noise(
        self,
        frame_dbfs: np.ndarray,
        frame_times: np.ndarray,
        speech_mask: np.ndarray,
        noise_floor_dbfs: float,
        duration: float,
    ) -> Dict[str, Any]:
        """
        Analyzes background noise characteristics and isolates noisy intervals.
        """
        non_speech_mask = ~speech_mask
        non_speech_frames = frame_dbfs[non_speech_mask]

        if len(non_speech_frames) > 0:
            mean_noise_dbfs = float(np.mean(non_speech_frames))
            peak_noise_dbfs = float(np.max(non_speech_frames))
        else:
            mean_noise_dbfs = noise_floor_dbfs
            peak_noise_dbfs = noise_floor_dbfs

        # Noise presence evaluation
        has_noise = bool(mean_noise_dbfs > -60.0)

        # Intensity rating (0.0 to 1.0 continuous scale)
        # -70 dBFS -> 0.0, -20 dBFS -> 1.0
        intensity_val = float(np.clip((mean_noise_dbfs - (-70.0)) / 50.0, 0.0, 1.0))

        if intensity_val < 0.15:
            intensity_label = "Silent / Inaudible"
        elif intensity_val < 0.35:
            intensity_label = "Low (Subtle Ambient)"
        elif intensity_val < 0.60:
            intensity_label = "Moderate (Noticeable)"
        elif intensity_val < 0.80:
            intensity_label = "Elevated (Prominent)"
        else:
            intensity_label = "Severe (Dominant)"

        # Isolate noisy segments: frames in non-speech where energy exceeds baseline + 6 dB
        noisy_frame_mask = non_speech_mask & (frame_dbfs > (noise_floor_dbfs + 6.0))
        noisy_segments = self._mask_to_intervals(
            noisy_frame_mask, frame_times, frame_dbfs, 0.01, duration
        )

        return {
            "has_background_noise": has_noise,
            "noise_detected": has_noise,
            "noise_intensity_score": round(intensity_val, 3),
            "noise_intensity_label": intensity_label,
            "mean_noise_dbfs": round(mean_noise_dbfs, 2),
            "peak_noise_dbfs": round(peak_noise_dbfs, 2),
            "noisy_segments_count": len(noisy_segments),
            "noisy_segments": noisy_segments[:25],  # Limit to 25 intervals for response compactness
        }

    def _interpret_noise_floor(self, nf_dbfs: float) -> str:
        if nf_dbfs < -65.0:
            return "Pristine digital silence / professional studio booth baseline"
        elif nf_dbfs < -50.0:
            return "Quiet indoor acoustic environment"
        elif nf_dbfs < -40.0:
            return "Moderate office or domestic ambient floor"
        elif nf_dbfs < -30.0:
            return "Elevated acoustic noise floor (hiss, HVAC, open window)"
        else:
            return "Severe acoustic floor elevation; potential sensor or line interference"

    def _compute_quality_score(
        self,
        snr_db: Optional[float],
        snr_reliable: bool,
        clipping_ratio: float,
        noise_floor_dbfs: float,
        peak_amplitude: float,
        global_dbfs: float,
        speech_ratio: float,
        silence_ratio: float,
        duration: float,
    ) -> Dict[str, Any]:
        """
        Computes an explainable, deterministic Audio Quality Score (0 to 100).
        Explicitly independent of synthetic voice detection.
        """
        # 1. SNR Component (30 pts)
        if snr_db is None or not snr_reliable:
            # If duration is very short or silence, give conservative score
            if speech_ratio < 0.05:
                snr_pts = 0.0
            else:
                snr_pts = 18.0  # Default neutral credit when SNR is unmeasurable due to continuous speech
        else:
            if snr_db >= 30.0:
                snr_pts = 30.0
            elif snr_db >= 20.0:
                snr_pts = 20.0 + ((snr_db - 20.0) / 10.0) * 10.0
            elif snr_db >= 10.0:
                snr_pts = 10.0 + ((snr_db - 10.0) / 10.0) * 10.0
            elif snr_db >= 0.0:
                snr_pts = (snr_db / 10.0) * 10.0
            else:
                snr_pts = 0.0

        # 2. Clipping Penalty (20 pts)
        if clipping_ratio == 0.0:
            clipping_pts = 20.0
        elif clipping_ratio < 0.0005:
            clipping_pts = 18.0
        elif clipping_ratio < 0.002:
            clipping_pts = 14.0
        elif clipping_ratio < 0.01:
            clipping_pts = 8.0
        else:
            clipping_pts = max(0.0, 20.0 - (clipping_ratio * 100.0 * 5.0))

        # 3. Noise Floor Component (20 pts)
        if noise_floor_dbfs <= -60.0:
            floor_pts = 20.0
        elif noise_floor_dbfs <= -50.0:
            floor_pts = 16.0 + (( -50.0 - noise_floor_dbfs ) / 10.0) * 4.0
        elif noise_floor_dbfs <= -40.0:
            floor_pts = 10.0 + (( -40.0 - noise_floor_dbfs ) / 10.0) * 6.0
        elif noise_floor_dbfs <= -30.0:
            floor_pts = 4.0 + (( -30.0 - noise_floor_dbfs ) / 10.0) * 6.0
        else:
            floor_pts = max(0.0, 4.0 - ((noise_floor_dbfs - (-30.0)) / 10.0) * 4.0)

        # 4. Dynamic Level & Crest Factor (15 pts)
        # Optimal speech broadcast levels: peak 0.3 - 0.95, RMS between -28 dBFS and -14 dBFS
        if peak_amplitude < 0.02 or global_dbfs < -45.0:
            dynamics_pts = 3.0  # Extremely faint or silent
        elif 0.15 <= peak_amplitude <= 0.98 and -28.0 <= global_dbfs <= -12.0:
            dynamics_pts = 15.0 # Ideal level
        else:
            dynamics_pts = 10.0

        # 5. Conversational Speech & Pause Naturalness (15 pts)
        if speech_ratio == 0.0:
            speech_pts = 0.0 # Pure silence
        elif 0.40 <= speech_ratio <= 0.85:
            speech_pts = 15.0 # Natural human conversational pacing
        elif 0.20 <= speech_ratio < 0.40 or 0.85 < speech_ratio <= 0.95:
            speech_pts = 10.0
        else:
            speech_pts = 5.0  # Wall-of-sound non-stop speech or isolated blip

        total_score = round(snr_pts + clipping_pts + floor_pts + dynamics_pts + speech_pts, 1)
        total_score = min(100.0, max(0.0, total_score))

        # Qualitative classification
        if total_score >= 85.0:
            grade = "Studio / Pristine Quality"
            badge = "PRISTINE"
        elif total_score >= 70.0:
            grade = "High Communication Quality"
            badge = "HIGH"
        elif total_score >= 50.0:
            grade = "Moderate / Acceptable Quality"
            badge = "ACCEPTABLE"
        elif total_score >= 30.0:
            grade = "Degraded / Low Quality"
            badge = "DEGRADED"
        else:
            grade = "Severely Compromised Quality"
            badge = "POOR"

        return {
            "overall_score": total_score,
            "grade": grade,
            "badge": badge,
            "breakdown": {
                "snr_component": {
                    "points": round(snr_pts, 1),
                    "max_points": 30.0,
                    "metric": f"{round(snr_db, 1)} dB" if snr_db is not None else "N/A",
                },
                "clipping_component": {
                    "points": round(clipping_pts, 1),
                    "max_points": 20.0,
                    "metric": f"{round(clipping_ratio * 100.0, 3)}% clipped",
                },
                "noise_floor_component": {
                    "points": round(floor_pts, 1),
                    "max_points": 20.0,
                    "metric": f"{round(noise_floor_dbfs, 1)} dBFS",
                },
                "dynamic_range_component": {
                    "points": round(dynamics_pts, 1),
                    "max_points": 15.0,
                    "metric": f"{round(global_dbfs, 1)} dBFS RMS (peak {round(peak_amplitude, 3)})",
                },
                "speech_presence_component": {
                    "points": round(speech_pts, 1),
                    "max_points": 15.0,
                    "metric": f"{round(speech_ratio * 100.0, 1)}% speech / {round(silence_ratio * 100.0, 1)}% silence",
                },
            },
            "disclaimer": (
                "Audio quality score quantifies signal hygiene, transmission integrity, and recording clarity. "
                "It is strictly independent of AI deepfake or spoofing probability. "
                "A studio-quality recording can still be a synthetic clone, and noisy audio can still be an authentic human voice."
            ),
        }

    def _empty_forensics_report(self, sr: int, duration: float = 0.0) -> Dict[str, Any]:
        """Fallback report for empty audio streams."""
        return {
            "duration_seconds": round(duration, 3),
            "sample_rate": sr,
            "total_samples": 0,
            "peak_amplitude": 0.0,
            "global_rms": 0.0,
            "global_dbfs": -100.0,
            "has_nan_inf_artifacts": False,
            "noise_analysis": {
                "has_background_noise": False,
                "noise_detected": False,
                "noise_intensity_score": 0.0,
                "noise_intensity_label": "Silent",
                "mean_noise_dbfs": -100.0,
                "peak_noise_dbfs": -100.0,
                "noisy_segments_count": 0,
                "noisy_segments": [],
            },
            "snr_analysis": {
                "snr_db": None,
                "is_reliable": False,
                "classification": "UNAVAILABLE",
                "interpretation": "Empty audio stream; SNR cannot be determined.",
                "speech_power_dbfs": None,
                "noise_power_dbfs": -100.0,
                "unreliability_reason": "EMPTY_AUDIO",
            },
            "noise_floor": {
                "noise_floor_dbfs": -100.0,
                "reference": "16-bit Full Scale Digital",
                "interpretation": "Digital absolute silence",
            },
            "clipping_analysis": {
                "has_clipping": False,
                "clipped_samples_count": 0,
                "clipping_ratio": 0.0,
                "clipping_percentage": 0.0,
                "severity": "None",
                "affected_intervals_count": 0,
                "clipping_intervals": [],
            },
            "silence_analysis": {
                "total_silence_seconds": 0.0,
                "silence_ratio": 1.0,
                "silence_percentage": 100.0,
                "silent_segments_count": 0,
                "silent_segments": [],
            },
            "voice_activity": {
                "total_speech_seconds": 0.0,
                "total_non_speech_seconds": 0.0,
                "speech_ratio": 0.0,
                "non_speech_ratio": 1.0,
                "speech_percentage": 0.0,
                "non_speech_percentage": 100.0,
                "speech_segments_count": 0,
                "non_speech_segments_count": 0,
                "speech_segments": [],
                "non_speech_segments": [],
            },
            "quality_score": {
                "overall_score": 0.0,
                "grade": "Severely Compromised Quality",
                "badge": "POOR",
                "breakdown": {},
                "disclaimer": "No audio signal detected.",
            },
        }
