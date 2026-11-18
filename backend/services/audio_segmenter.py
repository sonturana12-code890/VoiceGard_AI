"""
VOICEGUARD AI — Audio Segmentation Engine
Intelligent sliding-window segmentation for deepfake acoustic neural networks (AASIST / RawNet2).
Handles arbitrary durations, short audio wrapping/tiling, configurable overlap,
and timestamp tracking for localized spoof detection.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

DEFAULT_TARGET_SAMPLES: int = 64600  # ~4.0375 seconds at 16,000 Hz (AASIST standard)
DEFAULT_SAMPLE_RATE: int = 16000
DEFAULT_OVERLAP_SECONDS: float = 1.0


@dataclass
class AudioSegment:
    """Represents a single model-compatible audio slice."""
    segment_id: int
    start_time: float
    end_time: float
    samples: np.ndarray
    is_padded: bool = False

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "start": round(self.start_time, 3),
            "end": round(self.end_time, 3),
            "num_samples": len(self.samples),
            "is_padded": self.is_padded,
        }


class AudioSegmenter:
    """
    Splits continuous 1D audio waveform into model-compatible fixed-length windows.
    Standard AASIST input is [batch_size, 64600] float32 at 16kHz.
    """

    def __init__(
        self,
        target_samples: int = DEFAULT_TARGET_SAMPLES,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        overlap_seconds: float = DEFAULT_OVERLAP_SECONDS,
    ):
        self.target_samples = target_samples
        self.sample_rate = sample_rate
        self.overlap_seconds = max(0.0, overlap_seconds)

    def segment(self, pcm: np.ndarray) -> List[AudioSegment]:
        """
        Segments 1D float32 audio array into consecutive windows of exact shape (target_samples,).
        Tracks start and end timestamps in seconds.
        """
        if len(pcm) == 0:
            return []

        pcm = pcm.astype(np.float32)
        total_samples = len(pcm)

        # Case 1: Short audio (< target_samples)
        if total_samples <= self.target_samples:
            duration = float(total_samples / self.sample_rate)
            if total_samples < self.target_samples:
                # ASVspoof / AASIST standard: wrap-around tile until target length is satisfied
                repeat_count = int(math.ceil(self.target_samples / total_samples))
                tiled = np.tile(pcm, repeat_count)[:self.target_samples]
                is_padded = True
            else:
                tiled = pcm
                is_padded = False

            return [
                AudioSegment(
                    segment_id=1,
                    start_time=0.0,
                    end_time=round(duration, 3),
                    samples=tiled.astype(np.float32),
                    is_padded=is_padded,
                )
            ]

        # Case 2: Long audio (> target_samples)
        overlap_samples = int(self.overlap_seconds * self.sample_rate)
        # Avoid zero or negative step
        step_samples = max(1, self.target_samples - overlap_samples)

        segments: List[AudioSegment] = []
        current_idx = 0
        seg_id = 1

        while current_idx + self.target_samples <= total_samples:
            slice_pcm = pcm[current_idx : current_idx + self.target_samples]
            start_sec = current_idx / float(self.sample_rate)
            end_sec = (current_idx + self.target_samples) / float(self.sample_rate)

            segments.append(
                AudioSegment(
                    segment_id=seg_id,
                    start_time=round(start_sec, 3),
                    end_time=round(end_sec, 3),
                    samples=slice_pcm.astype(np.float32),
                    is_padded=False,
                )
            )

            current_idx += step_samples
            seg_id += 1

        # Check tail coverage: if final samples were missed by step stepping
        last_covered_idx = current_idx - step_samples + self.target_samples
        if last_covered_idx < total_samples:
            # Extract final trailing window [total_samples - target_samples : total_samples]
            trailing_start = total_samples - self.target_samples
            trailing_pcm = pcm[trailing_start:total_samples]
            start_sec = trailing_start / float(self.sample_rate)
            end_sec = total_samples / float(self.sample_rate)

            # Only append if not identical to the last segment
            if not segments or start_sec > segments[-1].start_time:
                segments.append(
                    AudioSegment(
                        segment_id=seg_id,
                        start_time=round(start_sec, 3),
                        end_time=round(end_sec, 3),
                        samples=trailing_pcm.astype(np.float32),
                        is_padded=False,
                    )
                )

        return segments

