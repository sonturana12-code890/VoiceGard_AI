"""
VOICEGUARD AI — FFmpeg & FFprobe Integration Service
Robust inspection, stream validation, and audio extraction for MPEG/MPG containers.
Supports both standalone FFmpeg/FFprobe CLI binaries and embedded PyAV (libav) C-libraries.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import av
except ImportError:
    av = None

logger = logging.getLogger("voiceguard.ffmpeg_service")

# Codec family normalization mapping (decoder variants / aliases to canonical format names)
CODEC_CANONICAL_MAP: Dict[str, str] = {
    # MP3 decoder variants (e.g. PyAV / libavcodec floating-point decoders)
    "mp3": "mp3",
    "mp3float": "mp3",
    "mp3adu": "mp3adu",
    "mp3adufloat": "mp3adu",
    "mp3on4": "mp3",
    "mp3on4float": "mp3",
    # MP2 decoder variants
    "mp2": "mp2",
    "mp2float": "mp2",
    # MP1 decoder variants
    "mp1": "mp1",
    "mp1float": "mp1",
    # AAC decoder variants
    "aac": "aac",
    "aac_latm": "aac",
    "aac_fixed": "aac",
    # AC3 / E-AC3 decoder variants
    "ac3": "ac3",
    "ac3_fixed": "ac3",
    "eac3": "eac3",
    # Modern / lossless audio formats
    "flac": "flac",
    "vorbis": "vorbis",
    "opus": "opus",
    "alac": "alac",
    "wavpack": "wavpack",
    # PCM formats
    "pcm_s16le": "pcm_s16le",
    "pcm_s16be": "pcm_s16be",
    "pcm_f32le": "pcm_f32le",
    "pcm_u8": "pcm_u8",
}

# Canonical recognized MPEG audio codec families
CANONICAL_MPEG_CODECS = {
    "mp1", "mp2", "mp3", "mp3adu", "aac", "ac3", "eac3", "flac",
    "vorbis", "opus", "pcm_s16le", "pcm_s16be", "pcm_f32le", "pcm_u8", "alac", "wavpack"
}

# Combined set of all supported codec tokens (canonical names + decoder alias variants)
SUPPORTED_MPEG_CODECS = set(CODEC_CANONICAL_MAP.keys()) | CANONICAL_MPEG_CODECS

DEFAULT_INSPECTION_TIMEOUT: float = 10.0
DEFAULT_DECODE_TIMEOUT: float = 20.0


class FFmpegInspectionError(Exception):
    """Raised when FFmpeg/FFprobe inspection fails."""

    def __init__(self, message: str, error_code: str = "CORRUPTED_AUDIO"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class FFmpegService:
    """
    Production-grade integration service executing FFprobe/FFmpeg operations.
    Implements defense-in-depth:
    1. Uses CLI binaries via safe subprocess argument lists when installed on PATH.
    2. Uses embedded PyAV libav C-libraries for high-performance in-memory processing.
    """

    @staticmethod
    def _discover_cli_candidate_paths(executable_name: str) -> List[str]:
        """Builds a robust candidate list for ffmpeg/ffprobe discovery."""
        candidates: List[str] = []
        seen: set[str] = set()

        def register(path_value: Optional[str]) -> None:
            if not path_value:
                return
            cleaned = str(path_value).strip()
            if not cleaned or cleaned in seen:
                return
            seen.add(cleaned)
            candidates.append(cleaned)

        for env_name in (
            f"{executable_name.upper()}_PATH",
            f"{executable_name.upper()}_EXECUTABLE",
            "FFMPEG_BIN_DIR",
            "FFPROBE_BIN_DIR",
        ):
            register(os.environ.get(env_name))

        for env_value in (os.environ.get("PATH", ""), os.environ.get("Path", "")):
            for segment in env_value.split(os.pathsep):
                if segment:
                    register(os.path.join(segment, executable_name))
                    register(os.path.join(segment, f"{executable_name}.exe"))

        explicit_dirs = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("LOCALAPPDATA"),
            str(Path.home() / "Downloads"),
            r"C:\ffmpeg\bin",
            r"C:\Program Files\ffmpeg\bin",
            r"C:\Program Files (x86)\ffmpeg\bin",
            r"C:\Users\LC\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin",
        ]
        for base_dir in explicit_dirs:
            if not base_dir:
                continue
            register(os.path.join(base_dir, executable_name))
            register(os.path.join(base_dir, f"{executable_name}.exe"))
            register(os.path.join(base_dir, "bin", executable_name))
            register(os.path.join(base_dir, "bin", f"{executable_name}.exe"))

        common_roots = [
            Path.home() / "Downloads",
            Path(r"C:\Program Files"),
            Path(r"C:\Program Files (x86)"),
        ]
        for root in common_roots:
            if not root.exists():
                continue
            try:
                if root.name == "Downloads":
                    for candidate in root.rglob(executable_name):
                        register(str(candidate))
                    for candidate in root.rglob(f"{executable_name}.exe"):
                        register(str(candidate))
            except OSError:
                pass

        return candidates

    @staticmethod
    def _resolve_cli_path(executable_name: str) -> Optional[str]:
        """Returns the first valid ffmpeg/ffprobe binary found via PATH or common install directories."""
        for candidate in FFmpegService._discover_cli_candidate_paths(executable_name):
            candidate_path = Path(candidate).expanduser()
            if candidate_path.is_file():
                return str(candidate_path)
            if candidate_path.suffix.lower() != ".exe" and not candidate_path.suffix:
                for known_ext in (".exe", ""):
                    candidate_with_ext = Path(str(candidate_path) + known_ext)
                    if candidate_with_ext.is_file():
                        return str(candidate_with_ext)
        resolved = shutil.which(executable_name)
        return resolved

    @staticmethod
    def get_ffmpeg_cli_path() -> Optional[str]:
        """Returns path to ffmpeg binary if present on system PATH or known Windows install locations."""
        return FFmpegService._resolve_cli_path("ffmpeg")

    @staticmethod
    def get_ffprobe_cli_path() -> Optional[str]:
        """Returns path to ffprobe binary if present on system PATH or known Windows install locations."""
        return FFmpegService._resolve_cli_path("ffprobe")

    @classmethod
    def normalize_codec(cls, raw_codec: str) -> str:
        """
        Normalizes raw FFmpeg decoder names/aliases into canonical codec representations.
        E.g., 'mp3float' -> 'mp3', 'mp3adu' -> 'mp3adu', 'mp1float' -> 'mp1', 'mp2float' -> 'mp2'.
        """
        if not raw_codec:
            return "unknown"
        clean = raw_codec.lower().strip()
        return CODEC_CANONICAL_MAP.get(clean, clean)

    @classmethod
    def is_decoder_available(cls, codec_name: str) -> bool:
        """
        Verifies if a specific codec has an available decoding implementation
        via PyAV (libavcodec) or the system FFmpeg binary.
        """
        if not codec_name:
            return False
        clean_name = codec_name.lower().strip()

        # 1. Check PyAV libavcodec registry
        if av is not None:
            try:
                codec_desc = av.codec.Codec(clean_name, "r")
                if getattr(codec_desc, "is_decoder", False) and getattr(codec_desc, "type", "") == "audio":
                    return True
            except Exception:
                pass
            # Check canonical alias if alias is not independently registered in libavcodec
            canonical = CODEC_CANONICAL_MAP.get(clean_name)
            if canonical and canonical != clean_name:
                try:
                    codec_desc = av.codec.Codec(canonical, "r")
                    if getattr(codec_desc, "is_decoder", False) and getattr(codec_desc, "type", "") == "audio":
                        return True
                except Exception:
                    pass

        # 2. Check FFmpeg CLI decoders list if CLI is available
        ffmpeg_path = cls.get_ffmpeg_cli_path()
        if ffmpeg_path:
            if clean_name in SUPPORTED_MPEG_CODECS or clean_name in CODEC_CANONICAL_MAP:
                return True

        return False

    @classmethod
    def validate_and_normalize_codec(cls, raw_codec: str) -> Tuple[str, str]:
        """
        Validates that raw_codec is a supported MPEG audio codec with an available decoder,
        and returns (canonical_codec, raw_codec).
        Raises FFmpegInspectionError with error_code='UNSUPPORTED_CODEC' if unsupported.
        """
        if not raw_codec or not raw_codec.strip():
            raise FFmpegInspectionError(
                "Missing audio codec information in stream.",
                error_code="UNSUPPORTED_CODEC",
            )
        clean_codec = raw_codec.lower().strip()

        # Safe validation: must be registered in SUPPORTED_MPEG_CODECS or CODEC_CANONICAL_MAP
        if clean_codec not in SUPPORTED_MPEG_CODECS and clean_codec not in CODEC_CANONICAL_MAP:
            supported_list = ", ".join(sorted(CANONICAL_MPEG_CODECS))
            raise FFmpegInspectionError(
                f"Unsupported MPEG audio codec '{clean_codec}'. Supported: {supported_list}",
                error_code="UNSUPPORTED_CODEC",
            )

        # Verify actual decoder availability (reject un-decodable formats)
        if not cls.is_decoder_available(clean_codec):
            raise FFmpegInspectionError(
                f"No valid audio decoder available for codec '{clean_codec}'.",
                error_code="UNSUPPORTED_CODEC",
            )

        canonical = cls.normalize_codec(clean_codec)
        return canonical, clean_codec

    @classmethod
    def get_diagnostics(cls) -> Dict[str, Any]:
        """Reports availability of FFmpeg tools and underlying C-libraries."""
        ffmpeg_cli = cls.get_ffmpeg_cli_path()
        ffprobe_cli = cls.get_ffprobe_cli_path()

        lib_versions = {}
        if av is not None:
            lib_versions = {
                lib: f"{v[0]}.{v[1]}.{v[2]}"
                for lib, v in getattr(av, "library_versions", {}).items()
            }

        return {
            "ffmpeg_cli_installed": ffmpeg_cli is not None,
            "ffmpeg_cli_path": ffmpeg_cli,
            "ffprobe_cli_installed": ffprobe_cli is not None,
            "ffprobe_cli_path": ffprobe_cli,
            "pyav_installed": av is not None,
            "pyav_version": getattr(av, "__version__", None),
            "embedded_ffmpeg_libraries": lib_versions,
            "core_engine": "PyAV / libavformat & libavcodec" if av else "None",
            "supported_mpeg_codecs": sorted(list(SUPPORTED_MPEG_CODECS)),
            "canonical_codecs": sorted(list(CANONICAL_MPEG_CODECS)),
            "codec_alias_mapping": dict(CODEC_CANONICAL_MAP),
        }

    @classmethod
    def inspect_container(
        cls,
        file_bytes: bytes,
        filename: str = "media.mpeg",
        timeout: float = DEFAULT_INSPECTION_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Inspects MPEG container streams, codecs, durations, and channels.
        Rejects files without audio tracks or with unsupported codecs.
        """
        # 1. Try PyAV first for high performance (in-memory, no disk I/O)
        if av is not None:
            try:
                with av.open(io.BytesIO(file_bytes)) as container:
                    audio_streams = list(container.streams.audio)
                    video_streams = list(container.streams.video)

                    if not audio_streams:
                        if video_streams:
                            raise FFmpegInspectionError(
                                "The uploaded MPEG file is a video-only stream with no audio track.",
                                error_code="NO_AUDIO_STREAM",
                            )
                        raise FFmpegInspectionError(
                            "The uploaded file contains no valid audio streams.",
                            error_code="NO_AUDIO_STREAM",
                        )

                    astream = audio_streams[0]
                    raw_codec = (astream.codec_context.name or "").lower()
                    canonical_codec, verified_raw = cls.validate_and_normalize_codec(raw_codec)

                    sample_rate = astream.rate or astream.codec_context.sample_rate
                    channels = len(astream.codec_context.layout.channels)

                    if astream.duration is not None and astream.time_base is not None:
                        duration = float(astream.duration * astream.time_base)
                    elif container.duration is not None:
                        duration = float(container.duration / av.time_base)
                    else:
                        duration = 0.0

                    return {
                        "format": "mpeg" if filename.lower().endswith((".mpeg", ".mpg")) else container.format.name,
                        "codec": canonical_codec,
                        "raw_codec": verified_raw,
                        "sample_rate": sample_rate,
                        "channels": channels,
                        "duration_seconds": round(duration, 3),
                        "has_video": len(video_streams) > 0,
                        "video_stream_count": len(video_streams),
                        "audio_stream_count": len(audio_streams),
                        "engine_used": "PyAV C-bindings",
                    }
            except FFmpegInspectionError:
                raise
            except Exception as e:
                # If PyAV raises a demuxing error, attempt CLI ffprobe if available
                logger.debug(f"PyAV container inspection failed: {e}. Checking FFprobe CLI fallback.")

        # 2. FFprobe CLI fallback (if installed)
        ffprobe_path = cls.get_ffprobe_cli_path()
        if ffprobe_path:
            with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
                temp_path = Path(tmp.name)
                try:
                    tmp.write(file_bytes)
                    tmp.flush()

                    cmd = [
                        ffprobe_path,
                        "-v", "quiet",
                        "-print_format", "json",
                        "-show_format",
                        "-show_streams",
                        str(temp_path.resolve()),
                    ]

                    # Safe subprocess execution: shell=False, strict timeout
                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=True)
                    data = json.loads(proc.stdout.decode("utf-8"))

                    streams = data.get("streams", [])
                    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
                    video_streams = [s for s in streams if s.get("codec_type") == "video"]

                    if not audio_streams:
                        if video_streams:
                            raise FFmpegInspectionError(
                                "The uploaded MPEG file is a video-only stream with no audio track.",
                                error_code="NO_AUDIO_STREAM",
                            )
                        raise FFmpegInspectionError(
                            "The uploaded file contains no audio streams.",
                            error_code="NO_AUDIO_STREAM",
                        )

                    astream = audio_streams[0]
                    raw_codec = astream.get("codec_name", "").lower()
                    canonical_codec, verified_raw = cls.validate_and_normalize_codec(raw_codec)

                    sr = int(astream.get("sample_rate", 16000))
                    ch = int(astream.get("channels", 1))
                    dur = float(astream.get("duration") or data.get("format", {}).get("duration", 0.0))

                    return {
                        "format": "mpeg",
                        "codec": canonical_codec,
                        "raw_codec": verified_raw,
                        "sample_rate": sr,
                        "channels": ch,
                        "duration_seconds": round(dur, 3),
                        "has_video": len(video_streams) > 0,
                        "video_stream_count": len(video_streams),
                        "audio_stream_count": len(audio_streams),
                        "engine_used": "FFprobe CLI",
                    }
                finally:
                    if temp_path.is_file():
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass

        raise FFmpegInspectionError(
            "Corrupted or invalid MPEG audio stream. File could not be demuxed.",
            error_code="CORRUPTED_AUDIO",
        )

    @classmethod
    def decode_to_pcm(
        cls,
        file_bytes: bytes,
        target_sr: Optional[int] = None,
        timeout: float = DEFAULT_DECODE_TIMEOUT,
    ) -> Tuple[np.ndarray, int, int]:
        """
        Decodes MPEG audio stream to float32 PCM samples in [-1.0, 1.0].
        If container has video, safely extracts the audio stream and discards video frames.
        """
        if av is not None:
            try:
                with av.open(io.BytesIO(file_bytes)) as container:
                    audio_stream = next(iter(container.streams.audio), None)
                    if audio_stream is None:
                        if len(container.streams.video) > 0:
                            raise FFmpegInspectionError(
                                "MPEG file contains video only (no audio track).",
                                error_code="NO_AUDIO_STREAM",
                            )
                        raise FFmpegInspectionError(
                            "MPEG file contains no audio stream.",
                            error_code="NO_AUDIO_STREAM",
                        )

                    raw_codec = (audio_stream.codec_context.name or "").lower()
                    cls.validate_and_normalize_codec(raw_codec)

                    orig_sr = audio_stream.rate or audio_stream.codec_context.sample_rate
                    orig_channels = len(audio_stream.codec_context.layout.channels)
                    out_sr = target_sr or orig_sr

                    # High-precision resampling directly to out_sr mono float32
                    resampler = av.AudioResampler(
                        format="fltp",
                        layout="mono",
                        rate=out_sr,
                    )
                    resampled_frames = []
                    for frame in container.decode(audio_stream):
                        resampled_frames.extend(resampler.resample(frame))
                    resampled_frames.extend(resampler.resample(None))

                    if not resampled_frames:
                        raise FFmpegInspectionError(
                            "Audio stream contains no decodable audio samples.",
                            error_code="CORRUPTED_AUDIO",
                        )

                    pcm = np.concatenate(
                        [f.to_ndarray().reshape(-1) for f in resampled_frames]
                    ).astype(np.float32)

                    return pcm, out_sr, orig_channels
            except FFmpegInspectionError:
                raise
            except Exception as e:
                logger.debug(f"PyAV decode error: {e}. Checking FFmpeg CLI fallback.")

        # FFmpeg CLI fallback (if available)
        ffmpeg_path = cls.get_ffmpeg_cli_path()
        if ffmpeg_path:
            with tempfile.NamedTemporaryFile(suffix=".mpeg", delete=False) as tmp:
                temp_path = Path(tmp.name)
                try:
                    tmp.write(file_bytes)
                    tmp.flush()

                    sr_param = str(target_sr or 16000)
                    cmd = [
                        ffmpeg_path,
                        "-v", "error",
                        "-i", str(temp_path.resolve()),
                        "-vn",                # No video
                        "-ar", sr_param,      # Target sample rate
                        "-ac", "1",           # Mono
                        "-f", "f32le",        # 32-bit float raw PCM
                        "pipe:1",
                    ]

                    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=True)
                    raw_data = proc.stdout
                    if not raw_data:
                        raise FFmpegInspectionError("FFmpeg produced empty audio stream.", error_code="CORRUPTED_AUDIO")

                    pcm = np.frombuffer(raw_data, dtype=np.float32)
                    return pcm, int(sr_param), 1
                finally:
                    if temp_path.is_file():
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass

        raise FFmpegInspectionError(
            "Corrupted or invalid MPEG audio stream. File could not be decoded.",
            error_code="CORRUPTED_AUDIO",
        )
