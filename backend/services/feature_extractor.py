"""
VOICEGUARD AI — Audio Feature Extraction Engine
Extracts comprehensive acoustic and spectro-temporal features:
- MFCC (Mel-Frequency Cepstral Coefficients)
- Mel Spectrogram (Log-Mel Power Spectrogram)
- Spectral Centroid
- Spectral Bandwidth
- Spectral Roll-off (85% energy threshold)
- Zero Crossing Rate (ZCR)
- RMS Energy (Root-Mean-Square Energy)

Pure NumPy implementation: Highly optimized, deterministic, zero-dependency.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


def hz_to_mel(hz: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Converts frequency in Hertz to Mel scale."""
    return 2595.0 * np.log10(1.0 + np.asarray(hz) / 700.0)


def mel_to_hz(mel: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Converts Mel scale value to frequency in Hertz."""
    return 700.0 * (10.0 ** (np.asarray(mel) / 2595.0) - 1.0)


def build_mel_filterbank(
    sr: int = 16000,
    n_fft: int = 512,
    n_mels: int = 40,
    fmin: float = 0.0,
    fmax: Optional[float] = None,
) -> np.ndarray:
    """
    Constructs triangular Mel filterbank matrix of shape [n_mels, n_fft // 2 + 1].
    """
    fmax = fmax or float(sr // 2)
    mel_min = hz_to_mel(fmin)
    mel_max = hz_to_mel(fmax)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = mel_to_hz(mel_points)
    bins = np.floor((n_fft + 1) * hz_points / sr).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)

    filterbank = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(1, n_mels + 1):
        f_m_minus = bins[m - 1]
        f_m = bins[m]
        f_m_plus = bins[m + 1]

        if f_m > f_m_minus:
            for k in range(f_m_minus, f_m):
                filterbank[m - 1, k] = (k - f_m_minus) / float(f_m - f_m_minus)
        if f_m_plus > f_m:
            for k in range(f_m, f_m_plus):
                filterbank[m - 1, k] = (f_m_plus - k) / float(f_m_plus - f_m)

    return filterbank


def dct_matrix(n_mfcc: int = 13, n_mels: int = 40) -> np.ndarray:
    """
    Constructs orthonormal Type-II Discrete Cosine Transform basis matrix.
    Shape: [n_mfcc, n_mels].
    """
    k = np.arange(n_mfcc)[:, None]
    n = np.arange(n_mels)[None, :]
    basis = np.cos(np.pi * k * (n + 0.5) / float(n_mels)).astype(np.float32)
    basis[0, :] *= 1.0 / np.sqrt(n_mels)
    basis[1:, :] *= np.sqrt(2.0 / n_mels)
    return basis


@dataclass
class AudioFeatures:
    """Structured container for extracted audio forensic features."""
    sample_rate: int
    num_samples: int
    duration_seconds: float
    num_frames: int

    # Spectral features
    spectral_centroid: Dict[str, Any]
    spectral_bandwidth: Dict[str, Any]
    spectral_rolloff: Dict[str, Any]

    # Time-domain features
    zero_crossing_rate: Dict[str, Any]
    rms_energy: Dict[str, Any]

    # Cepstral & representation features
    mfcc: Dict[str, Any]
    mel_spectrogram: Dict[str, Any]
    spectrogram_matrix: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Complete structured representation."""
        return {
            "sample_rate": self.sample_rate,
            "num_samples": self.num_samples,
            "duration_seconds": round(self.duration_seconds, 3),
            "num_frames": self.num_frames,
            "spectral_centroid": self.spectral_centroid,
            "spectral_bandwidth": self.spectral_bandwidth,
            "spectral_rolloff": self.spectral_rolloff,
            "zero_crossing_rate": self.zero_crossing_rate,
            "rms_energy": self.rms_energy,
            "mfcc": self.mfcc,
            "mel_spectrogram": self.mel_spectrogram,
            "spectrogram": self.spectrogram_matrix,
        }

    def to_summary(self) -> Dict[str, Any]:
        """Clean scalar summary suitable for API telemetry."""
        return {
            "spectral_centroid_hz": self.spectral_centroid.get("mean_hz", 0.0),
            "spectral_bandwidth_hz": self.spectral_bandwidth.get("mean_hz", 0.0),
            "spectral_rolloff_hz": self.spectral_rolloff.get("mean_hz", 0.0),
            "zero_crossing_rate": self.zero_crossing_rate.get("mean", 0.0),
            "rms_energy": self.rms_energy.get("mean", 0.0),
            "mfcc_coefficients_mean": self.mfcc.get("mean_coefficients", []),
            "mel_spectrogram_mean_db": self.mel_spectrogram.get("mean_db", 0.0),
            "num_frames_analyzed": self.num_frames,
        }


class AudioFeatureExtractor:
    """
    Production-grade Audio Feature Extractor for synthetic voice forensics.
    Implements standard acoustic feature extraction for AASIST & RawNet2 front-ends.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        n_fft: int = 512,
        hop_length: int = 160,
        n_mels: int = 40,
        n_mfcc: int = 13,
    ):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.n_mfcc = n_mfcc

        # Cache filterbank and DCT projection matrices
        self._mel_filterbank = build_mel_filterbank(sr=sample_rate, n_fft=n_fft, n_mels=n_mels)
        self._dct_matrix = dct_matrix(n_mfcc=n_mfcc, n_mels=n_mels)
        self._window = 0.5 * (1.0 - np.cos(2.0 * np.pi * np.arange(n_fft) / float(n_fft))).astype(np.float32)
        self._freqs = np.fft.rfftfreq(n_fft, 1.0 / float(sample_rate)).astype(np.float32)

        # Precompute Mel band center frequencies in Hertz
        mel_min = hz_to_mel(0.0)
        mel_max = hz_to_mel(float(sample_rate // 2))
        mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
        hz_points = mel_to_hz(mel_points)
        self._mel_frequencies = [round(float(hz), 1) for hz in hz_points[1:-1]]

    def frame_signal(self, pcm: np.ndarray) -> np.ndarray:
        """
        Frames 1D PCM signal into overlapping windows.
        Pads signal if shorter than n_fft.
        """
        if len(pcm) < self.n_fft:
            pad_width = self.n_fft - len(pcm)
            pcm = np.pad(pcm, (0, pad_width), mode="constant")

        num_frames = 1 + (len(pcm) - self.n_fft) // self.hop_length
        shape = (num_frames, self.n_fft)
        strides = (pcm.strides[0] * self.hop_length, pcm.strides[0])
        frames = np.lib.stride_tricks.as_strided(pcm, shape=shape, strides=strides)
        return frames

    def compute_stft(self, frames: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes magnitude spectrum and power spectrum from framed audio.
        """
        windowed = frames * self._window
        stft = np.fft.rfft(windowed, n=self.n_fft)
        mag = np.abs(stft).astype(np.float32)
        power = (mag ** 2) / float(self.n_fft)
        return mag, power

    def extract_mfcc(self, power: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extracts MFCC coefficients from power spectrum.
        Returns (mfcc_matrix [num_frames, n_mfcc], metadata_dict).
        """
        mel_energy = np.dot(power, self._mel_filterbank.T)
        log_mel = np.log(np.maximum(mel_energy, 1e-10))
        mfcc = np.dot(log_mel, self._dct_matrix.T).astype(np.float32)

        mean_coeff = np.mean(mfcc, axis=0).tolist()
        std_coeff = np.std(mfcc, axis=0).tolist()

        return mfcc, {
            "n_mfcc": self.n_mfcc,
            "shape": list(mfcc.shape),
            "mean_coefficients": [round(float(c), 4) for c in mean_coeff],
            "std_coefficients": [round(float(c), 4) for c in std_coeff],
        }

    def extract_mel_spectrogram(self, power: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extracts Log-Mel power spectrogram in decibels.
        Returns (mel_db [num_frames, n_mels], metadata_dict).
        """
        mel_energy = np.dot(power, self._mel_filterbank.T)
        max_val = np.max(mel_energy) if np.max(mel_energy) > 0 else 1.0
        mel_db = 10.0 * np.log10(np.maximum(mel_energy / max_val, 1e-10)).astype(np.float32)
        mel_db = np.clip(mel_db, -80.0, 0.0)

        return mel_db, {
            "n_mels": self.n_mels,
            "shape": list(mel_db.shape),
            "min_db": round(float(np.min(mel_db)), 2),
            "max_db": round(float(np.max(mel_db)), 2),
            "mean_db": round(float(np.mean(mel_db)), 2),
            "band_energy_summary": [round(float(b), 2) for b in np.mean(mel_db, axis=0)[:8]],
        }

    def extract_spectrogram_matrix(
        self, mel_db: np.ndarray, duration_seconds: float, max_frames: int = 600
    ) -> Dict[str, Any]:
        """
        Extracts formatted 2D Log-Mel Spectrogram matrix with coordinate grids for visualization.
        Downsamples along time dimension if frames exceed max_frames to ensure fast transport
        and 60 FPS HTML5 canvas rendering while preserving acoustic energy distributions.
        """
        num_frames = mel_db.shape[0]
        if num_frames == 0:
            return {
                "matrix": [],
                "num_frames": 0,
                "num_mels": self.n_mels,
                "mel_frequencies": self._mel_frequencies,
                "duration_seconds": round(duration_seconds, 3),
                "time_step_seconds": 0.0,
                "min_db": -80.0,
                "max_db": 0.0,
                "mean_db": -80.0,
                "f_min": 0.0,
                "f_max": float(self.sample_rate // 2),
            }

        if num_frames > max_frames:
            # Average adjacent time frames uniformly into max_frames bins
            stride = num_frames / float(max_frames)
            binned = np.zeros((max_frames, self.n_mels), dtype=np.float32)
            for i in range(max_frames):
                s_idx = int(i * stride)
                e_idx = max(s_idx + 1, int((i + 1) * stride))
                binned[i] = np.mean(mel_db[s_idx:e_idx], axis=0)
            matrix_data = binned
            effective_frames = max_frames
        else:
            matrix_data = mel_db
            effective_frames = num_frames

        # Round to 1 decimal place to minimize JSON payload size
        matrix_rounded = np.round(matrix_data, 1).tolist()
        time_step = duration_seconds / float(effective_frames) if effective_frames > 0 else 0.01

        return {
            "matrix": matrix_rounded,
            "num_frames": effective_frames,
            "num_mels": self.n_mels,
            "mel_frequencies": self._mel_frequencies,
            "duration_seconds": round(duration_seconds, 3),
            "time_step_seconds": round(float(time_step), 4),
            "min_db": round(float(np.min(matrix_data)), 1),
            "max_db": round(float(np.max(matrix_data)), 1),
            "mean_db": round(float(np.mean(matrix_data)), 1),
            "f_min": 0.0,
            "f_max": float(self.sample_rate // 2),
            "sample_rate": self.sample_rate,
            "fft_size": self.n_fft,
            "hop_length": self.hop_length,
        }

    def extract_spectral_centroid(self, mag: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extracts Spectral Centroid per frame: frequency center of mass.
        """
        mag_sum = np.sum(mag, axis=1, keepdims=True) + 1e-10
        centroid = np.sum(mag * self._freqs, axis=1) / mag_sum.squeeze(-1)

        return centroid, {
            "mean_hz": round(float(np.mean(centroid)), 2),
            "min_hz": round(float(np.min(centroid)), 2),
            "max_hz": round(float(np.max(centroid)), 2),
            "std_hz": round(float(np.std(centroid)), 2),
        }

    def extract_spectral_bandwidth(self, mag: np.ndarray, centroid: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extracts Spectral Bandwidth per frame: spread around centroid.
        """
        mag_sum = np.sum(mag, axis=1, keepdims=True) + 1e-10
        diff = self._freqs - centroid[:, None]
        bandwidth = np.sqrt(np.sum((diff ** 2) * mag, axis=1) / mag_sum.squeeze(-1))

        return bandwidth, {
            "mean_hz": round(float(np.mean(bandwidth)), 2),
            "min_hz": round(float(np.min(bandwidth)), 2),
            "max_hz": round(float(np.max(bandwidth)), 2),
            "std_hz": round(float(np.std(bandwidth)), 2),
        }

    def extract_spectral_rolloff(
        self, mag: np.ndarray, roll_percent: float = 0.85
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extracts Spectral Roll-off: frequency below which 85% of energy is concentrated.
        """
        cum_energy = np.cumsum(mag, axis=1)
        threshold = roll_percent * np.sum(mag, axis=1, keepdims=True)
        rolloff_idx = np.argmax(cum_energy >= threshold, axis=1)
        rolloff = self._freqs[rolloff_idx]

        return rolloff, {
            "roll_percent": roll_percent,
            "mean_hz": round(float(np.mean(rolloff)), 2),
            "min_hz": round(float(np.min(rolloff)), 2),
            "max_hz": round(float(np.max(rolloff)), 2),
        }

    def extract_zero_crossing_rate(self, frames: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extracts Zero Crossing Rate (ZCR) per frame.
        """
        signs = np.sign(frames)
        signs[signs == 0] = 1.0
        zcr = np.mean(np.abs(np.diff(signs, axis=1)) > 0, axis=1)

        return zcr, {
            "mean": round(float(np.mean(zcr)), 4),
            "max": round(float(np.max(zcr)), 4),
            "min": round(float(np.min(zcr)), 4),
            "std": round(float(np.std(zcr)), 4),
        }

    def extract_rms_energy(self, frames: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extracts Root-Mean-Square (RMS) Energy per frame.
        """
        rms = np.sqrt(np.mean(frames ** 2, axis=1))

        return rms, {
            "mean": round(float(np.mean(rms)), 4),
            "max": round(float(np.max(rms)), 4),
            "min": round(float(np.min(rms)), 4),
            "std": round(float(np.std(rms)), 4),
        }

    def extract_all(self, pcm: np.ndarray) -> AudioFeatures:
        """
        Extracts all 7 core audio forensic features from 16kHz mono float32 PCM:
        1. MFCC
        2. Mel Spectrogram
        3. Spectral Centroid
        4. Spectral Bandwidth
        5. Spectral Roll-off
        6. Zero Crossing Rate (ZCR)
        7. RMS Energy
        """
        clean_pcm = np.nan_to_num(pcm.astype(np.float32), nan=0.0, posinf=1.0, neginf=-1.0)
        frames = self.frame_signal(clean_pcm)
        num_frames = len(frames)
        duration = float(len(clean_pcm) / self.sample_rate)

        # STFT representation
        mag, power = self.compute_stft(frames)

        # Feature extractions
        _, mfcc_meta = self.extract_mfcc(power)
        mel_db, mel_meta = self.extract_mel_spectrogram(power)
        spectrogram_matrix = self.extract_spectrogram_matrix(mel_db, duration)
        centroid, centroid_meta = self.extract_spectral_centroid(mag)
        _, bandwidth_meta = self.extract_spectral_bandwidth(mag, centroid)
        _, rolloff_meta = self.extract_spectral_rolloff(mag, roll_percent=0.85)
        _, zcr_meta = self.extract_zero_crossing_rate(frames)
        _, rms_meta = self.extract_rms_energy(frames)

        return AudioFeatures(
            sample_rate=self.sample_rate,
            num_samples=len(clean_pcm),
            duration_seconds=duration,
            num_frames=num_frames,
            spectral_centroid=centroid_meta,
            spectral_bandwidth=bandwidth_meta,
            spectral_rolloff=rolloff_meta,
            zero_crossing_rate=zcr_meta,
            rms_energy=rms_meta,
            mfcc=mfcc_meta,
            mel_spectrogram=mel_meta,
            spectrogram_matrix=spectrogram_matrix,
        )

