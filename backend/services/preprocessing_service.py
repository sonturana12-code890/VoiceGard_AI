"""
VOICEGUARD AI — Audio Preprocessing & Acoustic Feature Extraction Service
Validates container headers, decodes PCM audio, downmixes to mono,
resamples to 16kHz target spec, and extracts spectro-temporal features for AASIST/RawNet2.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import av
import numpy as np


ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".webm", ".opus", ".mpeg", ".mpg"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
TARGET_SAMPLE_RATE = 16000
EXPECTED_AASIST_SAMPLES = 64600  # ~4.0375 seconds


class AudioPreprocessingError(Exception):
    """Custom exception raised when audio validation or preprocessing fails."""
    pass


class AudioPreprocessingService:
    """
    Validates audio files, extracts acoustic container metadata,
    decodes PCM streams, and produces normalized tensors prepared for AASIST pipeline.
    """

    @staticmethod
    def validate_file_metadata(filename: str, file_size: int, content_type: Optional[str] = None) -> None:
        """Validate filename extension and byte size."""
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise AudioPreprocessingError(
                f"Unsupported audio format '{ext}'. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        if file_size <= 0:
            raise AudioPreprocessingError("Uploaded file is empty (0 bytes).")

        if file_size > MAX_FILE_SIZE_BYTES:
            raise AudioPreprocessingError(
                f"File size exceeds the 25 MB limit. Size received: {file_size / (1024 * 1024):.2f} MB"
            )

    @staticmethod
    def inspect_audio_stream(file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Inspects audio byte stream, verifies container headers,
        and extracts duration and sampling properties.
        """
        if len(file_bytes) < 12:
            raise AudioPreprocessingError("Audio file is too small or truncated.")

        ext = Path(filename).suffix.lower()
        metadata: Dict[str, Any] = {
            "format": ext.lstrip("."),
            "size_bytes": len(file_bytes),
            "channels": 1,
            "sample_rate": TARGET_SAMPLE_RATE,
            "duration_seconds": 0.0,
            "is_mono": True,
            "is_standard_sample_rate": False,
        }

        # Check for genuine RIFF WAV
        if file_bytes.startswith(b"RIFF") and len(file_bytes) > 36 and file_bytes[8:12] == b"WAVE":
            try:
                with wave.open(io.BytesIO(file_bytes), "rb") as wav_file:
                    channels = wav_file.getnchannels()
                    sample_rate = wav_file.getframerate()
                    frames = wav_file.getnframes()
                    duration = frames / float(sample_rate) if sample_rate > 0 else 0.0

                    metadata.update({
                        "format": "wav",
                        "channels": channels,
                        "sample_rate": sample_rate,
                        "duration_seconds": round(duration, 3),
                        "is_mono": channels == 1,
                        "is_standard_sample_rate": sample_rate in (16000, 44100, 48000),
                    })
                    return metadata
            except (wave.Error, EOFError) as e:
                raise AudioPreprocessingError("Corrupted or invalid WAV audio stream.") from e

        # MPEG / MPG container specialized inspection
        if ext in {".mpeg", ".mpg"}:
            from backend.services.ffmpeg_service import FFmpegService, FFmpegInspectionError
            try:
                info = FFmpegService.inspect_container(file_bytes, filename=f"stream{ext}")
                metadata.update({
                    "format": "mpeg",
                    "channels": info.get("channels", 1),
                    "sample_rate": info.get("sample_rate", TARGET_SAMPLE_RATE),
                    "duration_seconds": info.get("duration_seconds", 0.0),
                    "is_mono": info.get("channels", 1) == 1,
                    "is_standard_sample_rate": info.get("sample_rate") in (16000, 44100, 48000),
                    "codec": info.get("codec"),
                })
                return metadata
            except FFmpegInspectionError as fie:
                raise AudioPreprocessingError(fie.message) from fie

        try:
            with av.open(io.BytesIO(file_bytes)) as container:
                audio_stream = next(iter(container.streams.audio), None)
                if audio_stream is None:
                    if len(container.streams.video) > 0:
                        raise AudioPreprocessingError("The uploaded file is a video-only stream with no audio track.")
                    raise AudioPreprocessingError("The uploaded file contains no audio stream.")

                sample_rate = audio_stream.rate or audio_stream.codec_context.sample_rate
                layout = audio_stream.codec_context.layout
                channel_count = len(layout.channels) if layout else 1
                if audio_stream.duration is not None and audio_stream.time_base is not None:
                    duration = float(audio_stream.duration * audio_stream.time_base)
                elif container.duration is not None:
                    duration = float(container.duration / av.time_base)
                else:
                    duration = 0.0

                metadata.update({
                    "format": ext.lstrip("."),
                    "channels": channel_count,
                    "sample_rate": sample_rate,
                    "duration_seconds": round(duration, 3),
                    "is_mono": channel_count == 1,
                    "is_standard_sample_rate": sample_rate in (16000, 44100, 48000),
                })
                return metadata
        except AudioPreprocessingError:
            raise
        except (av.error.FFmpegError, OSError, ValueError) as e:
            raise AudioPreprocessingError(
                "Corrupted or unsupported audio stream; the file could not be decoded."
            ) from e

    @staticmethod
    def decode_and_extract_features(file_bytes: bytes, filename: str) -> Tuple[Dict[str, Any], Dict[str, Any], np.ndarray]:
        """
        Decodes audio samples, resamples to 16kHz mono PCM, extracts objective
        acoustic features, and formats a [1, 64600] float32 array for neural models.
        """
        metadata = AudioPreprocessingService.inspect_audio_stream(file_bytes, filename)
        samples = np.zeros(EXPECTED_AASIST_SAMPLES, dtype=np.float32)

        # 1. Decode PCM samples from WAV container if present
        ext = Path(filename).suffix.lower()
        is_wav = file_bytes.startswith(b"RIFF") and len(file_bytes) > 36 and file_bytes[8:12] == b"WAVE"

        if ext in {".mpeg", ".mpg"}:
            from backend.services.ffmpeg_service import FFmpegService, FFmpegInspectionError
            try:
                samples, _, _ = FFmpegService.decode_to_pcm(file_bytes, target_sr=TARGET_SAMPLE_RATE)
            except FFmpegInspectionError as fie:
                raise AudioPreprocessingError(fie.message) from fie
        elif is_wav:
            try:
                with wave.open(io.BytesIO(file_bytes), "rb") as wav_file:
                    channels = wav_file.getnchannels()
                    sample_rate = wav_file.getframerate()
                    sampwidth = wav_file.getsampwidth()
                    frames = wav_file.getnframes()
                    raw_data = wav_file.readframes(frames)

                    if sampwidth == 2:  # 16-bit signed PCM
                        pcm = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                    elif sampwidth == 1:  # 8-bit unsigned PCM
                        pcm = (np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                    elif sampwidth == 4:  # 32-bit float or int PCM
                        pcm = np.frombuffer(raw_data, dtype=np.float32)
                    else:
                        pcm = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0

                    # Downmix multi-channel to mono
                    if channels > 1 and len(pcm) >= channels:
                        pcm = pcm.reshape(-1, channels).mean(axis=1)

                    # Resample to 16,000 Hz if needed
                    if sample_rate != TARGET_SAMPLE_RATE and len(pcm) > 0:
                        target_len = max(1, int(len(pcm) * TARGET_SAMPLE_RATE / sample_rate))
                        x_old = np.linspace(0, 1, len(pcm))
                        x_new = np.linspace(0, 1, target_len)
                        pcm = np.interp(x_new, x_old, pcm).astype(np.float32)

                    samples = pcm
            except (wave.Error, EOFError) as e:
                raise AudioPreprocessingError("Corrupted or invalid WAV audio stream.") from e
        else:
            try:
                with av.open(io.BytesIO(file_bytes)) as container:
                    audio_stream = next(iter(container.streams.audio), None)
                    if audio_stream is None:
                        if len(container.streams.video) > 0:
                            raise AudioPreprocessingError("The uploaded file is a video-only stream with no audio track.")
                        raise AudioPreprocessingError("The uploaded file contains no audio stream.")

                    resampler = av.AudioResampler(
                        format="fltp", layout="mono", rate=TARGET_SAMPLE_RATE
                    )
                    resampled_frames = []
                    for frame in container.decode(audio_stream):
                        resampled_frames.extend(resampler.resample(frame))
                    resampled_frames.extend(resampler.resample(None))

                    if not resampled_frames:
                        raise AudioPreprocessingError("The audio stream contains no decodable samples.")

                    samples = np.concatenate(
                        [frame.to_ndarray().reshape(-1) for frame in resampled_frames]
                    ).astype(np.float32)
            except AudioPreprocessingError:
                raise
            except (av.error.FFmpegError, OSError, ValueError) as e:
                raise AudioPreprocessingError(
                    "Corrupted or unsupported audio stream; the file could not be decoded."
                ) from e

        # 2. Extract Acoustic Features
        num_samples = len(samples)
        if num_samples > 0:
            rms_energy = float(np.sqrt(np.mean(samples ** 2)))
            zero_crossing_rate = float(np.mean(np.abs(np.diff(np.sign(samples))) > 0)) if num_samples > 1 else 0.0
            
            # FFT Spectral Centroid & High-Frequency Power Ratio
            fft_vals = np.abs(np.fft.rfft(samples[:min(num_samples, 32000)]))
            freqs = np.fft.rfftfreq(min(num_samples, 32000), 1.0 / TARGET_SAMPLE_RATE)
            fft_sum = float(np.sum(fft_vals))
            
            if fft_sum > 0:
                spectral_centroid = float(np.sum(freqs * fft_vals) / fft_sum)
                hf_energy = float(np.sum(fft_vals[freqs >= 4000]))
                hf_ratio = float(hf_energy / fft_sum)
            else:
                spectral_centroid = 0.0
                hf_ratio = 0.0

            # Pitch stability via autocorrelation
            autocorr_len = min(num_samples, 4000)
            if autocorr_len > 320:
                segment = samples[:autocorr_len]
                corr = np.correlate(segment, segment, mode='full')
                corr = corr[len(corr)//2:]
                # Peak between 50Hz and 500Hz (samples 32 to 320 at 16kHz)
                peak_corr = float(np.max(corr[32:320]) / (corr[0] + 1e-8)) if corr[0] > 0 else 0.0
            else:
                peak_corr = 0.0
        else:
            rms_energy = 0.0
            zero_crossing_rate = 0.0
            spectral_centroid = 0.0
            hf_ratio = 0.0
            peak_corr = 0.0

        features = {
            "rms_energy": round(rms_energy, 4),
            "zero_crossing_rate": round(zero_crossing_rate, 4),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "high_frequency_ratio": round(hf_ratio, 4),
            "pitch_autocorr_peak": round(peak_corr, 4),
            "target_sample_rate": TARGET_SAMPLE_RATE,
            "target_channels": 1,
            "spec": "AASIST-L / 16kHz Mono PCM",
        }

        # 3. Format into fixed 64,600-sample tensor [1, 64600]
        if len(samples) < EXPECTED_AASIST_SAMPLES:
            if len(samples) == 0:
                tensor_16k = np.zeros((1, EXPECTED_AASIST_SAMPLES), dtype=np.float32)
            else:
                # Tile/loop audio to reach 64600 samples
                repeat_factor = int(np.ceil(EXPECTED_AASIST_SAMPLES / len(samples)))
                tiled = np.tile(samples, repeat_factor)[:EXPECTED_AASIST_SAMPLES]
                tensor_16k = tiled.reshape(1, EXPECTED_AASIST_SAMPLES).astype(np.float32)
        else:
            # Center-crop 64600 samples
            start = (len(samples) - EXPECTED_AASIST_SAMPLES) // 2
            tensor_16k = samples[start:start + EXPECTED_AASIST_SAMPLES].reshape(1, EXPECTED_AASIST_SAMPLES).astype(np.float32)

        return metadata, features, tensor_16k
