"""
VOICEGUARD AI — Audio Validation Engine
Validates audio file containers, MIME types, extensions, size/duration limits,
header magic bytes, and stream decodability.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set

try:
    import av
except ImportError:
    av = None

ALLOWED_EXTENSIONS: Set[str] = {
    ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".webm", ".opus", ".mpeg", ".mpg"
}

ALLOWED_MIME_TYPES: Set[str] = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3", "video/mpeg", "video/mpg", "audio/mpg",
    "audio/flac", "audio/x-flac",
    "audio/ogg", "audio/vorbis", "application/ogg",
    "audio/mp4", "audio/m4a", "audio/x-m4a",
    "audio/aac", "audio/webm", "audio/opus",
    "application/octet-stream",  # Permitted fallback for raw uploads
}

DEFAULT_MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
DEFAULT_MAX_DURATION_SECONDS: float = 300.0          # 5 minutes
DEFAULT_MIN_DURATION_SECONDS: float = 0.20           # 200 ms


class AudioValidationError(Exception):
    """Raised when audio validation fails with a structured error code."""

    def __init__(self, message: str, error_code: str = "INVALID_AUDIO", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code


@dataclass
class ValidationResult:
    """Standardized validation outcome container."""
    is_valid: bool
    error_code: Optional[str] = None
    message: str = ""
    filename: str = ""
    file_size: int = 0
    format: Optional[str] = None
    channels: Optional[int] = None
    sample_rate: Optional[int] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to clean API response dictionary."""
        if not self.is_valid:
            return {
                "success": False,
                "valid": False,
                "error_code": self.error_code or "INVALID_AUDIO",
                "message": self.message,
                "filename": self.filename,
                "file_size": self.file_size,
            }
        return {
            "success": True,
            "valid": True,
            "filename": self.filename,
            "format": self.format,
            "file_size": self.file_size,
            "duration_seconds": self.duration_seconds,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "message": self.message or "Audio file passed validation.",
            "metadata": self.metadata,
        }


class AudioValidator:
    """
    Robust audio validation engine verifying container integrity,
    file extensions, magic byte signatures, and physical decodability.
    """

    def __init__(
        self,
        max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
        max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
        min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS,
    ):
        self.max_file_size_bytes = max_file_size_bytes
        self.max_duration_seconds = max_duration_seconds
        self.min_duration_seconds = min_duration_seconds

    def validate_file(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: Optional[str] = None,
    ) -> ValidationResult:
        """
        Performs exhaustive validation on audio file bytes.
        Returns a ValidationResult object.
        """
        # 1. Check filename and path security
        if not filename or not filename.strip():
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_FILENAME",
                message="Filename is missing or invalid.",
                filename="",
                file_size=len(file_bytes),
            )

        sanitized_filename = Path(filename).name.strip()
        ext = Path(sanitized_filename).suffix.lower()

        # 2. Extension validation
        if ext not in ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(sorted(ALLOWED_EXTENSIONS))
            return ValidationResult(
                is_valid=False,
                error_code="UNSUPPORTED_FORMAT",
                message=f"Unsupported audio format '{ext}'. Allowed extensions: {allowed_list}",
                filename=sanitized_filename,
                file_size=len(file_bytes),
            )

        # 3. MIME validation (if provided and recognized)
        if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
            # Note: Do not hard-reject octet-stream as browsers often send it
            if not content_type.startswith("audio/"):
                return ValidationResult(
                    is_valid=False,
                    error_code="INVALID_MIME_TYPE",
                    message=f"Unsupported content type '{content_type}'. Expected an audio MIME type.",
                    filename=sanitized_filename,
                    file_size=len(file_bytes),
                )

        # 4. File size validation
        file_size = len(file_bytes)
        if file_size == 0:
            return ValidationResult(
                is_valid=False,
                error_code="EMPTY_AUDIO",
                message="Uploaded file is empty (0 bytes).",
                filename=sanitized_filename,
                file_size=0,
            )

        if file_size > self.max_file_size_bytes:
            mb_size = round(file_size / (1024 * 1024), 2)
            max_mb = round(self.max_file_size_bytes / (1024 * 1024), 2)
            return ValidationResult(
                is_valid=False,
                error_code="FILE_TOO_LARGE",
                message=f"File size exceeds the limit ({mb_size} MB > {max_mb} MB).",
                filename=sanitized_filename,
                file_size=file_size,
            )

        # 5. Magic Byte Inspection
        if file_size < 12:
            return ValidationResult(
                is_valid=False,
                error_code="CORRUPTED_AUDIO",
                message="Audio file is truncated or header is incomplete.",
                filename=sanitized_filename,
                file_size=file_size,
            )

        magic_valid, detected_fmt = self._check_magic_bytes(file_bytes, ext)
        if not magic_valid:
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_AUDIO",
                message=f"File content does not match expected audio signature for '{ext}'.",
                filename=sanitized_filename,
                file_size=file_size,
            )

        # 6. Stream Decodability & Duration Inspection
        try:
            stream_info = self._inspect_and_decode_header(file_bytes, ext)
        except AudioValidationError as ave:
            return ValidationResult(
                is_valid=False,
                error_code=ave.error_code,
                message=ave.message,
                filename=sanitized_filename,
                file_size=file_size,
            )
        except Exception as exc:
            return ValidationResult(
                is_valid=False,
                error_code="CORRUPTED_AUDIO",
                message=f"Failed to decode audio stream: {str(exc)}",
                filename=sanitized_filename,
                file_size=file_size,
            )

        duration = stream_info.get("duration_seconds", 0.0)
        if duration < self.min_duration_seconds:
            return ValidationResult(
                is_valid=False,
                error_code="AUDIO_TOO_SHORT",
                message=(
                    f"Audio duration ({duration:.2f}s) is shorter than minimum required "
                    f"({self.min_duration_seconds:.2f}s)."
                ),
                filename=sanitized_filename,
                file_size=file_size,
                metadata=stream_info,
            )

        if duration > self.max_duration_seconds:
            return ValidationResult(
                is_valid=False,
                error_code="AUDIO_TOO_LONG",
                message=(
                    f"Audio duration ({duration:.2f}s) exceeds maximum allowed limit "
                    f"({self.max_duration_seconds:.2f}s)."
                ),
                filename=sanitized_filename,
                file_size=file_size,
                metadata=stream_info,
            )

        return ValidationResult(
            is_valid=True,
            filename=sanitized_filename,
            format=detected_fmt or ext.lstrip("."),
            file_size=file_size,
            channels=stream_info.get("channels", 1),
            sample_rate=stream_info.get("sample_rate", 16000),
            duration_seconds=duration,
            message="Audio file passed validation.",
            metadata=stream_info,
        )

    def _check_magic_bytes(self, data: bytes, ext: str) -> tuple[bool, str]:
        """Inspects binary file signature to verify audio container type."""
        # WAV / RIFF
        if data.startswith(b"RIFF") and len(data) > 12 and data[8:12] == b"WAVE":
            return True, "wav"

        # FLAC
        if data.startswith(b"fLaC"):
            return True, "flac"

        # OGG
        if data.startswith(b"OggS"):
            return True, "ogg"

        # MP3 (ID3v2 header or MPEG sync word 0xFFE / 0xFFF)
        if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            return True, "mp3"

        # M4A / MP4 container (ftyp at offset 4)
        if len(data) >= 12 and data[4:8] == b"ftyp":
            return True, "m4a"

        # WebM / Matroska (EBML header: 0x1A 0x45 0xDF 0xA3)
        if data.startswith(b"\x1a\x45\xdf\xa3"):
            return True, "webm"

        # MPEG-PS (Program Stream pack start: 0x000001BA or sequence: 0x000001B3)
        if data.startswith(b"\x00\x00\x01\xba") or data.startswith(b"\x00\x00\x01\xb3"):
            return True, "mpeg"

        # MPEG-TS (Sync byte 0x47)
        if len(data) >= 188 and data[0] == 0x47:
            return True, "mpeg"

        # MPEG Audio Elementary Stream (MP1/MP2/MP3 frame sync: 11-12 bits 0xFFE / 0xFFF)
        if ext in {".mpeg", ".mpg"} and len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
            return True, "mpeg"

        # Fallback: if extension matches and container can be opened by PyAV, accept
        if ext in {".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".webm", ".opus", ".mpeg", ".mpg"}:
            return True, ext.lstrip(".")

        return False, "unknown"

    def _inspect_and_decode_header(self, file_bytes: bytes, ext: str) -> Dict[str, Any]:
        """Decodes container header and stream metadata using FFmpeg and PyAV."""
        # 1. Specialized MPEG / MPG container inspection via FFmpegService
        if ext in {".mpeg", ".mpg"}:
            from backend.services.ffmpeg_service import FFmpegService, FFmpegInspectionError
            try:
                info = FFmpegService.inspect_container(file_bytes, filename=f"stream{ext}")
                return info
            except FFmpegInspectionError as fie:
                raise AudioValidationError(fie.message, error_code=fie.error_code) from fie

        # 2. Try native wave module for WAV
        if file_bytes.startswith(b"RIFF") and file_bytes[8:12] == b"WAVE":
            try:
                with wave.open(io.BytesIO(file_bytes), "rb") as wf:
                    channels = wf.getnchannels()
                    sr = wf.getframerate()
                    frames = wf.getnframes()
                    duration = frames / float(sr) if sr > 0 else 0.0
                    return {
                        "channels": channels,
                        "sample_rate": sr,
                        "duration_seconds": round(duration, 3),
                        "format": "wav",
                    }
            except Exception:
                pass  # Fallback to PyAV

        # 3. Try PyAV for general audio streams
        if av is not None:
            with av.open(io.BytesIO(file_bytes)) as container:
                audio_streams = list(container.streams.audio)
                video_streams = list(container.streams.video)

                if not audio_streams:
                    if video_streams:
                        raise AudioValidationError("Uploaded file is a video-only stream without an audio track.", error_code="NO_AUDIO_STREAM")
                    raise AudioValidationError("Uploaded container contains no decodable audio stream.", error_code="NO_AUDIO_STREAM")

                audio_stream = audio_streams[0]
                sample_rate = audio_stream.rate or audio_stream.codec_context.sample_rate
                channels = len(audio_stream.codec_context.layout.channels)
                if audio_stream.duration is not None and audio_stream.time_base is not None:
                    duration = float(audio_stream.duration * audio_stream.time_base)
                elif container.duration is not None:
                    duration = float(container.duration / av.time_base)
                else:
                    duration = 0.0

                raw_codec = (audio_stream.codec_context.name or "").lower()
                from backend.services.ffmpeg_service import FFmpegService
                canonical_codec = FFmpegService.normalize_codec(raw_codec)

                return {
                    "channels": channels,
                    "sample_rate": sample_rate,
                    "duration_seconds": round(duration, 3),
                    "format": ext.lstrip("."),
                    "codec": canonical_codec,
                    "raw_codec": raw_codec,
                }

        raise AudioValidationError("Audio decoder (PyAV) is not available.")

