"""
VOICEGUARD AI — Advanced Audio Preprocessing Engine
Decodes audio to PCM float32, downmixes to mono, normalizes sample rate,
performs amplitude scaling, detects silence/clipping, and extracts
acoustic quality telemetry for neural anti-spoofing models (AASIST / RawNet2).
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import io
import math
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

try:
    import av
except ImportError:
    av = None

TARGET_SAMPLE_RATE_DEFAULT: int = 16000
EXPECTED_AASIST_SAMPLES: int = 64600  # ~4.0375 seconds at 16kHz


class AudioPreprocessingError(Exception):
    """Raised when audio decoding, resampling, or feature extraction fails."""
    pass


@dataclass
class AudioQualityMetrics:
    """Quantitative acoustic metrics describing audio stream quality."""
    duration_seconds: float
    sample_rate: int
    channels: int
    peak_amplitude: float
    rms_energy: float
    silence_ratio: float
    clipping_ratio: float
    is_clipped: bool
    is_silent: bool
    is_low_volume: bool
    spectral_centroid_hz: float
    high_frequency_ratio: float
    pitch_stability: float
    has_nan_or_inf: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration": round(self.duration_seconds, 3),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "peak_amplitude": round(self.peak_amplitude, 4),
            "rms_energy": round(self.rms_energy, 4),
            "silence_ratio": round(self.silence_ratio, 4),
            "clipping_ratio": round(self.clipping_ratio, 4),
            "is_clipped": self.is_clipped,
            "is_silent": self.is_silent,
            "is_low_volume": self.is_low_volume,
            "spectral_centroid_hz": round(self.spectral_centroid_hz, 1),
            "high_frequency_ratio": round(self.high_frequency_ratio, 4),
            "pitch_stability": round(self.pitch_stability, 4),
        }


class AudioPreprocessor:
    """
    Production-grade audio preprocessor for neural speech anti-spoofing.
    Converts arbitrary multi-format audio into model-ready 16kHz mono PCM float32 arrays.
    """

    def __init__(self, target_sample_rate: int = TARGET_SAMPLE_RATE_DEFAULT):
        self.target_sample_rate = target_sample_rate

    def decode_to_pcm(self, file_bytes: bytes, filename: str) -> Tuple[np.ndarray, int, int]:
        """
        Decodes arbitrary audio bytes (WAV, MP3, FLAC, OGG, M4A) to float32 samples [-1.0, 1.0].
        Returns (samples, original_sample_rate, original_channels).
        """
        if not file_bytes:
            raise AudioPreprocessingError("Cannot decode empty audio byte stream.")

        is_wav = file_bytes.startswith(b"RIFF") and len(file_bytes) > 36 and file_bytes[8:12] == b"WAVE"
        if is_wav:
            try:
                with wave.open(io.BytesIO(file_bytes), "rb") as wf:
                    channels = wf.getnchannels()
                    sr = wf.getframerate()
                    sampwidth = wf.getsampwidth()
                    frames = wf.getnframes()
                    raw_data = wf.readframes(frames)

                    if sampwidth == 2:  # 16-bit signed PCM
                        pcm = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                    elif sampwidth == 1:  # 8-bit unsigned PCM
                        pcm = (np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                    elif sampwidth == 4:  # 32-bit float or int PCM
                        try:
                            pcm = np.frombuffer(raw_data, dtype=np.float32)
                        except ValueError:
                            pcm = np.frombuffer(raw_data, dtype=np.int32).astype(np.float32) / 2147483648.0
                    else:
                        pcm = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0

                    if channels > 1 and len(pcm) >= channels:
                        pcm = pcm.reshape(-1, channels).mean(axis=1)

                    return pcm, sr, channels
            except (wave.Error, EOFError) as e:
                # Fallback to PyAV if wave module parsing fails
                pass

        # MPEG / MPG dedicated decoding via FFmpegService
        ext = Path(filename).suffix.lower()
        if ext in {".mpeg", ".mpg"}:
            from backend.services.ffmpeg_service import FFmpegService, FFmpegInspectionError
            try:
                pcm, sr, ch = FFmpegService.decode_to_pcm(file_bytes, target_sr=self.target_sample_rate)
                return pcm, sr, ch
            except FFmpegInspectionError as fie:
                raise AudioPreprocessingError(fie.message) from fie

        if av is None:
            raise AudioPreprocessingError("PyAV is required for decoding non-WAV audio.")

        try:
            with av.open(io.BytesIO(file_bytes)) as container:
                audio_stream = next(iter(container.streams.audio), None)
                if audio_stream is None:
                    if len(container.streams.video) > 0:
                        raise AudioPreprocessingError("Uploaded file is a video-only stream without an audio track.")
                    raise AudioPreprocessingError("Uploaded file contains no audio stream.")

                orig_sr = audio_stream.rate or audio_stream.codec_context.sample_rate
                orig_channels = len(audio_stream.codec_context.layout.channels)

                # Decode to float mono
                resampler = av.AudioResampler(format="fltp", layout="mono", rate=orig_sr)
                frames_list = []
                for frame in container.decode(audio_stream):
                    frames_list.extend(resampler.resample(frame))
                frames_list.extend(resampler.resample(None))

                if not frames_list:
                    raise AudioPreprocessingError("No audio samples could be decoded from stream.")

                pcm = np.concatenate([f.to_ndarray().reshape(-1) for f in frames_list]).astype(np.float32)
                return pcm, orig_sr, orig_channels
        except AudioPreprocessingError:
            raise
        except Exception as e:
            # Fallback to FFmpegService CLI/demuxer before giving up
            from backend.services.ffmpeg_service import FFmpegService, FFmpegInspectionError
            try:
                pcm, sr, ch = FFmpegService.decode_to_pcm(file_bytes, target_sr=self.target_sample_rate)
                return pcm, sr, ch
            except Exception:
                pass
            raise AudioPreprocessingError(f"Corrupted or unsupported audio stream: {str(e)}") from e

    def resample_pcm(self, pcm: np.ndarray, source_sr: int, target_sr: Optional[int] = None) -> np.ndarray:
        """
        Resamples 1D float32 PCM samples to target sample rate using linear interpolation.
        Preserves waveform integrity and relative phase.
        """
        target_sr = target_sr or self.target_sample_rate
        if source_sr == target_sr or len(pcm) == 0:
            return pcm.astype(np.float32)

        target_length = max(1, int(len(pcm) * target_sr / source_sr))
        x_old = np.linspace(0.0, 1.0, len(pcm), endpoint=False)
        x_new = np.linspace(0.0, 1.0, target_length, endpoint=False)
        resampled = np.interp(x_new, x_old, pcm).astype(np.float32)
        return resampled

    def normalize_amplitude(self, pcm: np.ndarray, peak_target: float = 0.98) -> np.ndarray:
        """
        Non-destructive amplitude scaling.
        Avoids clipping while preserving subtle synthetic vocoder noise and artifacts.
        """
        if len(pcm) == 0:
            return pcm

        peak = float(np.max(np.abs(pcm)))
        # Only scale down if signal exceeds 1.0 (clipping hazard)
        if peak > 1.0:
            return (pcm / peak * peak_target).astype(np.float32)

        # If signal is excessively weak (< 0.05) and not complete silence, safely boost headroom
        if 1e-4 < peak < 0.05:
            # Gentle 12dB boost without destroying dynamic range
            boost_factor = min(4.0, peak_target / peak)
            return (pcm * boost_factor).astype(np.float32)

        return pcm.astype(np.float32)

    def analyze_quality(self, pcm: np.ndarray, sample_rate: int, original_channels: int = 1) -> AudioQualityMetrics:
        """
        Extracts comprehensive acoustic and signal quality metrics.
        """
        num_samples = len(pcm)
        duration = float(num_samples / sample_rate) if sample_rate > 0 else 0.0

        has_nan_or_inf = bool(np.isnan(pcm).any() or np.isinf(pcm).any())
        clean_pcm = np.nan_to_num(pcm, nan=0.0, posinf=1.0, neginf=-1.0) if has_nan_or_inf else pcm

        if num_samples == 0:
            return AudioQualityMetrics(
                duration_seconds=0.0,
                sample_rate=sample_rate,
                channels=original_channels,
                peak_amplitude=0.0,
                rms_energy=0.0,
                silence_ratio=1.0,
                clipping_ratio=0.0,
                is_clipped=False,
                is_silent=True,
                is_low_volume=True,
                spectral_centroid_hz=0.0,
                high_frequency_ratio=0.0,
                pitch_stability=0.0,
                has_nan_or_inf=has_nan_or_inf,
            )

        peak_amplitude = float(np.max(np.abs(clean_pcm)))
        rms_energy = float(np.sqrt(np.mean(clean_pcm ** 2)))

        # Clipping detection: samples near or exceeding digital full scale
        clipping_samples = int(np.sum(np.abs(clean_pcm) >= 0.995))
        clipping_ratio = float(clipping_samples / num_samples)
        is_clipped = bool(clipping_ratio > 0.005)

        # Silence ratio: frame-based power analysis (20ms frames)
        frame_len = max(1, int(sample_rate * 0.02))  # 20ms
        num_frames = num_samples // frame_len
        if num_frames > 0:
            frames = clean_pcm[:num_frames * frame_len].reshape(num_frames, frame_len)
            frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))
            silent_frames = np.sum(frame_rms < 0.01)
            silence_ratio = float(silent_frames / num_frames)
        else:
            silence_ratio = 1.0 if rms_energy < 0.01 else 0.0

        is_silent = bool(rms_energy < 1e-4 or silence_ratio >= 0.98)
        is_low_volume = bool(rms_energy < 0.01)

        # FFT Spectral Centroid & High Frequency Power Ratio (up to 2 seconds for efficiency)
        fft_samples = min(num_samples, sample_rate * 2)
        fft_vals = np.abs(np.fft.rfft(clean_pcm[:fft_samples]))
        freqs = np.fft.rfftfreq(fft_samples, 1.0 / sample_rate)
        fft_sum = float(np.sum(fft_vals))

        if fft_sum > 0:
            spectral_centroid = float(np.sum(freqs * fft_vals) / fft_sum)
            hf_cutoff = 4000.0  # 4 kHz boundary for synthetic artifact analysis
            hf_energy = float(np.sum(fft_vals[freqs >= hf_cutoff]))
            hf_ratio = float(hf_energy / fft_sum)
        else:
            spectral_centroid = 0.0
            hf_ratio = 0.0

        # Pitch stability via autocorrelation (pitch lags: 50 Hz - 500 Hz)
        autocorr_len = min(num_samples, sample_rate // 4)
        if autocorr_len > 320:
            segment = clean_pcm[:autocorr_len]
            corr = np.correlate(segment, segment, mode="full")
            corr = corr[len(corr) // 2:]
            # Human vocal fundamental frequencies typically between 50Hz and 500Hz
            lag_min = max(1, int(sample_rate / 500.0))
            lag_max = min(len(corr) - 1, int(sample_rate / 50.0))
            if lag_max > lag_min and corr[0] > 0:
                pitch_stability = float(np.max(corr[lag_min:lag_max]) / (corr[0] + 1e-8))
            else:
                pitch_stability = 0.0
        else:
            pitch_stability = 0.0

        return AudioQualityMetrics(
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=original_channels,
            peak_amplitude=peak_amplitude,
            rms_energy=rms_energy,
            silence_ratio=silence_ratio,
            clipping_ratio=clipping_ratio,
            is_clipped=is_clipped,
            is_silent=is_silent,
            is_low_volume=is_low_volume,
            spectral_centroid_hz=spectral_centroid,
            high_frequency_ratio=hf_ratio,
            pitch_stability=pitch_stability,
            has_nan_or_inf=has_nan_or_inf,
        )

    def process_audio(
        self,
        file_bytes: bytes,
        filename: str,
        target_sr: Optional[int] = None,
    ) -> Tuple[np.ndarray, AudioQualityMetrics]:
        """
        Full preprocessing pipeline:
        1. Decode to PCM
        2. Validate waveform integrity
        3. Resample to target rate (16kHz)
        4. Normalize amplitude safely
        5. Extract acoustic quality telemetry
        """
        raw_pcm, orig_sr, orig_channels = self.decode_to_pcm(file_bytes, filename)

        if len(raw_pcm) == 0:
            raise AudioPreprocessingError("Audio decoded to an empty waveform (0 samples).")

        if np.isnan(raw_pcm).any() or np.isinf(raw_pcm).any():
            raw_pcm = np.nan_to_num(raw_pcm, nan=0.0, posinf=1.0, neginf=-1.0)

        target_sr = target_sr or self.target_sample_rate
        resampled_pcm = self.resample_pcm(raw_pcm, orig_sr, target_sr)
        normalized_pcm = self.normalize_amplitude(resampled_pcm)
        metrics = self.analyze_quality(normalized_pcm, target_sr, orig_channels)

        return normalized_pcm, metrics

