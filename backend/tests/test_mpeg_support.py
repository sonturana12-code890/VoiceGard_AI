"""
VOICEGUARD AI — MPEG & MPG Audio Pipeline Verification Test Suite
Comprehensive testing for MPEG-1/2 Audio, Program Stream (.mpeg, .mpg),
Audio extraction from MPEG AV streams, video-only rejection, and codec handling.
Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense.
"""

from __future__ import annotations

import io
import wave
from unittest.mock import MagicMock, patch

import av
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.audio_preprocessor import AudioPreprocessor
from backend.services.audio_validator import AudioValidator, ValidationResult
from backend.services.ffmpeg_service import (
    FFmpegInspectionError,
    FFmpegService,
    SUPPORTED_MPEG_CODECS,
    CANONICAL_MPEG_CODECS,
    CODEC_CANONICAL_MAP,
)
from backend.services.inference_pipeline import DetectionPipeline
from backend.tests.test_api import (
    TestingSessionLocal,
    override_get_db,
    test_engine,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    signup_res = client.post("/api/auth/signup", json={
        "fullName": "MPEG Testing Lead",
        "email": "mpeg_tester@voiceguard.ai",
        "password": "MpegSecurePassword123!",
        "termsAccepted": True,
    })
    if signup_res.status_code == 200 and "access_token" in signup_res.json():
        token = signup_res.json()["access_token"]
    else:
        login_res = client.post("/api/auth/login", json={
            "email": "mpeg_tester@voiceguard.ai",
            "password": "MpegSecurePassword123!",
        })
        token = login_res.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# SYNTHESIS HELPERS
# ============================================================================

def make_mpeg_audio(duration: float = 1.5, sr: int = 44100, freq: float = 440.0) -> bytes:
    """Encodes valid MPEG-1/2 Audio (MP2 in MPEG container)."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mpeg") as container:
        stream = container.add_stream("mp2", rate=sr)
        stream.layout = "stereo"
        total_samples = int(duration * sr)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        wave_data = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        stereo_arr = np.stack([wave_data, wave_data])
        chunk_size = 1152
        for i in range(0, total_samples, chunk_size):
            chunk = stereo_arr[:, i:i+chunk_size]
            if chunk.shape[1] == chunk_size:
                frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout="stereo")
                frame.rate = sr
                for p in stream.encode(frame):
                    container.mux(p)
        for p in stream.encode(None):
            container.mux(p)
    return buf.getvalue()


def make_mp3_audio(duration: float = 1.0, sr: int = 16000, freq: float = 440.0) -> bytes:
    """Encodes valid MP3 audio stream (decoded as mp3float in PyAV/libavcodec)."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mp3") as container:
        stream = container.add_stream("mp3", rate=sr)
        stream.layout = "mono"
        total_samples = int(duration * sr)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        wave_data = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        frame = av.AudioFrame.from_ndarray(wave_data.reshape(1, -1), format="fltp", layout="mono")
        frame.rate = sr
        for p in stream.encode(frame):
            container.mux(p)
        for p in stream.encode(None):
            container.mux(p)
    return buf.getvalue()


def make_mpeg_av(duration: float = 1.0, sr: int = 44100, freq: float = 440.0) -> bytes:
    """Encodes an MPEG container containing BOTH a video stream and an audio stream."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mpeg") as container:
        vstream = container.add_stream("mpeg1video", rate=25)
        vstream.width = 64
        vstream.height = 64
        vstream.pix_fmt = "yuv420p"

        astream = container.add_stream("mp2", rate=sr)
        astream.layout = "stereo"

        # Write 1 video frame
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        vframe = av.VideoFrame.from_ndarray(img, format="rgb24")
        for p in vstream.encode(vframe):
            container.mux(p)

        # Write audio frames
        total_samples = int(duration * sr)
        t = np.linspace(0, duration, total_samples, endpoint=False)
        wave_data = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        stereo_arr = np.stack([wave_data, wave_data])
        chunk_size = 1152
        for i in range(0, total_samples, chunk_size):
            chunk = stereo_arr[:, i:i+chunk_size]
            if chunk.shape[1] == chunk_size:
                frame = av.AudioFrame.from_ndarray(chunk, format="fltp", layout="stereo")
                frame.rate = sr
                for p in astream.encode(frame):
                    container.mux(p)

        for p in astream.encode(None):
            container.mux(p)
        for p in vstream.encode(None):
            container.mux(p)
    return buf.getvalue()


def make_mpeg_video_only(duration: float = 1.0) -> bytes:
    """Encodes an MPEG video container WITHOUT any audio stream."""
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="mpeg") as container:
        vstream = container.add_stream("mpeg1video", rate=25)
        vstream.width = 64
        vstream.height = 64
        vstream.pix_fmt = "yuv420p"

        img = np.zeros((64, 64, 3), dtype=np.uint8)
        num_frames = max(1, int(duration * 25))
        for _ in range(num_frames):
            vframe = av.VideoFrame.from_ndarray(img, format="rgb24")
            for p in vstream.encode(vframe):
                container.mux(p)
        for p in vstream.encode(None):
            container.mux(p)
    return buf.getvalue()


# ============================================================================
# 9 MPEG EXTENSION TEST CASES
# ============================================================================

def test_01_valid_mpeg_audio():
    """Test 1: Valid .mpeg audio file validation, decoding, and feature extraction."""
    mpeg_data = make_mpeg_audio(duration=1.5, sr=44100, freq=440.0)
    validator = AudioValidator()
    res = validator.validate_file(mpeg_data, "call_intercept.mpeg", "audio/mpeg")

    assert res.is_valid is True
    assert res.format == "mpeg"
    assert res.channels == 2
    assert res.sample_rate == 44100
    assert abs(res.duration_seconds - 1.5) < 0.1

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(mpeg_data, "call_intercept.mpeg")
    assert metrics.sample_rate == 16000
    assert metrics.channels == 2
    assert pcm.ndim == 1
    assert len(pcm) > 0


def test_02_valid_mpg_audio():
    """Test 2: Valid .mpg audio file validation, decoding, and preprocessing."""
    mpg_data = make_mpeg_audio(duration=1.2, sr=44100, freq=500.0)
    validator = AudioValidator()
    res = validator.validate_file(mpg_data, "recording.mpg", "video/mpeg")

    assert res.is_valid is True
    assert res.format == "mpeg"

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    pcm, metrics = preprocessor.process_audio(mpg_data, "recording.mpg")
    assert metrics.sample_rate == 16000
    assert abs(metrics.duration_seconds - 1.2) < 0.1


def test_03_mpeg_video_with_audio_stream():
    """Test 3: MPEG video container with audio stream extracts audio and ignores video track."""
    av_data = make_mpeg_av(duration=1.0, sr=44100, freq=600.0)
    validator = AudioValidator()
    res = validator.validate_file(av_data, "broadcast.mpeg", "video/mpeg")

    assert res.is_valid is True
    assert res.metadata.get("has_video") is True
    assert res.metadata.get("audio_stream_count") >= 1

    pcm, orig_sr, orig_ch = FFmpegService.decode_to_pcm(av_data, target_sr=16000)
    assert pcm.ndim == 1
    assert len(pcm) > 0


def test_04_mpeg_video_without_audio_stream():
    """Test 4: Video-only MPEG files (no audio track) are rejected with NO_AUDIO_STREAM."""
    video_only = make_mpeg_video_only(duration=1.0)
    validator = AudioValidator()
    res = validator.validate_file(video_only, "silent_surveillance.mpeg", "video/mpeg")

    assert res.is_valid is False
    assert res.error_code == "NO_AUDIO_STREAM"
    assert "video-only" in res.message.lower() or "no audio" in res.message.lower()


def test_05_corrupted_mpeg_file():
    """Test 5: Truncated or corrupted MPEG streams are rejected with CORRUPTED_AUDIO."""
    # Program stream pack start code followed by invalid garbage
    corrupted_data = b"\x00\x00\x01\xba" + b"\xff" * 30
    validator = AudioValidator()
    res = validator.validate_file(corrupted_data, "corrupted.mpeg", "audio/mpeg")

    assert res.is_valid is False
    assert res.error_code in ("CORRUPTED_AUDIO", "INVALID_AUDIO")


def test_06_unsupported_mpeg_codec():
    """Test 6: MPEG files with unsupported audio codecs are rejected with UNSUPPORTED_CODEC."""
    dummy_data = make_mpeg_audio(duration=0.5)

    # Mock FFmpeg inspection returning an unsupported codec
    with patch("backend.services.ffmpeg_service.av.open") as mock_open:
        mock_container = MagicMock()
        mock_astream = MagicMock()
        mock_astream.codec_context.name = "experimental_unsupported_codec_xyz"
        mock_container.streams.audio = [mock_astream]
        mock_container.streams.video = []
        mock_open.return_value.__enter__.return_value = mock_container

        with pytest.raises(FFmpegInspectionError) as exc_info:
            FFmpegService.inspect_container(dummy_data, "bad_codec.mpeg")
        assert exc_info.value.error_code == "UNSUPPORTED_CODEC"


def test_07_empty_mpeg_file():
    """Test 7: 0-byte MPEG files are rejected with EMPTY_AUDIO."""
    validator = AudioValidator()
    res = validator.validate_file(b"", "empty.mpg", "audio/mpeg")

    assert res.is_valid is False
    assert res.error_code == "EMPTY_AUDIO"


def test_08_oversized_mpeg_file():
    """Test 8: Files exceeding 25 MB limit are rejected with FILE_TOO_LARGE."""
    oversized = b"\x00\x00\x01\xba" + b"0" * (25 * 1024 * 1024 + 1024)
    validator = AudioValidator()
    res = validator.validate_file(oversized, "huge.mpeg", "audio/mpeg")

    assert res.is_valid is False
    assert res.error_code == "FILE_TOO_LARGE"


def test_09_existing_wav_and_mp3_compatibility(client, auth_headers):
    """Test 9: Verify existing WAV, MP3, and new MPEG endpoints all function seamlessly."""
    # 1. Test WAV
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    wav_bytes = wav_buf.getvalue()

    res_wav = client.post(
        "/api/v1/audio/validate",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert res_wav.status_code == 200
    assert res_wav.json()["valid"] is True
    assert res_wav.json()["format"] == "wav"

    # 2. Test MPEG through /api/v1/audio/validate
    mpeg_bytes = make_mpeg_audio(duration=1.0)
    res_mpeg_val = client.post(
        "/api/v1/audio/validate",
        files={"file": ("intercept.mpeg", mpeg_bytes, "audio/mpeg")},
    )
    assert res_mpeg_val.status_code == 200
    assert res_mpeg_val.json()["valid"] is True
    assert res_mpeg_val.json()["format"] == "mpeg"

    # 3. Test MPEG through /api/v1/audio/analyze
    res_mpeg_an = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("intercept.mpeg", mpeg_bytes, "audio/mpeg")},
        headers=auth_headers,
    )
    assert res_mpeg_an.status_code == 200
    report = res_mpeg_an.json()
    assert report["success"] is True
    assert "prediction" in report
    assert report["audio_information"]["channels"] == 2
    assert report["segments_analyzed"] >= 1

    # 4. Test Health Endpoint reports MPEG support
    health_res = client.get("/api/v1/audio/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert "mpeg" in health_data["supported_formats"]
    assert "mpg" in health_data["supported_formats"]
    assert "ffmpeg_status" in health_data


def test_10_ffmpeg_cli_discovery_from_environment(monkeypatch, tmp_path):
    """Test: CLI discovery respects explicit environment overrides and common Windows paths."""
    fake_ffmpeg = tmp_path / "ffmpeg.exe"
    fake_ffprobe = tmp_path / "ffprobe.exe"
    fake_ffmpeg.write_bytes(b"fake ffmpeg")
    fake_ffprobe.write_bytes(b"fake ffprobe")

    monkeypatch.setenv("FFMPEG_PATH", str(fake_ffmpeg))
    monkeypatch.setenv("FFPROBE_PATH", str(fake_ffprobe))
    monkeypatch.delenv("PATH", raising=False)

    assert FFmpegService.get_ffmpeg_cli_path() == str(fake_ffmpeg)
    assert FFmpegService.get_ffprobe_cli_path() == str(fake_ffprobe)


def test_11_mp3_with_mp3float_decoder(client, auth_headers):
    """Test 11: MP3 audio decoded via mp3float is normalized to mp3, validated, and preprocessed."""
    mp3_data = make_mp3_audio(duration=1.2, sr=16000, freq=440.0)

    # 1. FFmpeg inspection recognizes mp3float and normalizes to mp3
    info = FFmpegService.inspect_container(mp3_data, "sample.mpeg")
    assert info["codec"] == "mp3"
    assert info["raw_codec"] == "mp3float"
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    assert abs(info["duration_seconds"] - 1.2) < 0.2

    # 2. FFmpeg decoding yields 16kHz mono float32 PCM
    pcm, sr, ch = FFmpegService.decode_to_pcm(mp3_data, target_sr=16000)
    assert pcm.dtype == np.float32
    assert pcm.ndim == 1
    assert sr == 16000
    assert ch == 1
    assert len(pcm) > 0

    # 3. AudioValidator accepts mp3_data under both .mpeg and .mp3 extensions
    val_mpeg = AudioValidator().validate_file(mp3_data, "sample.mpeg", "audio/mpeg")
    assert val_mpeg.is_valid is True
    assert val_mpeg.metadata.get("codec") == "mp3"
    assert val_mpeg.metadata.get("raw_codec") == "mp3float"

    val_mp3 = AudioValidator().validate_file(mp3_data, "sample.mp3", "audio/mp3")
    assert val_mp3.is_valid is True
    assert val_mp3.metadata.get("codec") == "mp3"

    # 4. Pipeline analysis via POST /api/v1/audio/analyze succeeds with 200 OK
    res = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("sample.mpeg", mp3_data, "audio/mpeg")},
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["model"]["name"] == "AASIST"
    assert body["segments_analyzed"] >= 1


def test_12_mp3_with_mp3_decoder():
    """Test 12: MP3 codec name without float suffix is properly validated and preserved."""
    assert FFmpegService.normalize_codec("mp3") == "mp3"
    assert FFmpegService.is_decoder_available("mp3") is True
    canonical, raw = FFmpegService.validate_and_normalize_codec("mp3")
    assert canonical == "mp3"
    assert raw == "mp3"

    # Mock container stream reporting exact codec_context.name = "mp3"
    dummy_data = make_mp3_audio(duration=0.5)
    with patch("backend.services.ffmpeg_service.av.open") as mock_open:
        mock_container = MagicMock()
        mock_astream = MagicMock()
        mock_astream.codec_context.name = "mp3"
        mock_astream.rate = 16000
        mock_astream.codec_context.sample_rate = 16000
        mock_astream.codec_context.layout.channels = [1]
        mock_astream.duration = 8000
        mock_astream.time_base = 1.0 / 16000.0
        mock_container.streams.audio = [mock_astream]
        mock_container.streams.video = []
        mock_container.format.name = "mp3"
        mock_open.return_value.__enter__.return_value = mock_container

        info = FFmpegService.inspect_container(dummy_data, "standard.mp3")
        assert info["codec"] == "mp3"
        assert info["raw_codec"] == "mp3"


def test_13_mp3adu_and_float_variants():
    """Test 13: Normalization and validation for mp3adu, mp3adufloat, mp1float, mp2float."""
    # mp3adu and float alias
    can_adu, raw_adu = FFmpegService.validate_and_normalize_codec("mp3adu")
    assert can_adu == "mp3adu"
    assert raw_adu == "mp3adu"

    can_aduf, raw_aduf = FFmpegService.validate_and_normalize_codec("mp3adufloat")
    assert can_aduf == "mp3adu"
    assert raw_aduf == "mp3adufloat"

    # mp1 and float alias
    can_mp1, raw_mp1 = FFmpegService.validate_and_normalize_codec("mp1float")
    assert can_mp1 == "mp1"
    assert raw_mp1 == "mp1float"

    # mp2 and float alias
    can_mp2, raw_mp2 = FFmpegService.validate_and_normalize_codec("mp2float")
    assert can_mp2 == "mp2"
    assert raw_mp2 == "mp2float"

    # aac alias
    can_aac, raw_aac = FFmpegService.validate_and_normalize_codec("aac_latm")
    assert can_aac == "aac"
    assert raw_aac == "aac_latm"


def test_14_unsupported_codec_rejection_no_bypass():
    """Test 14: Unsupported codecs are strictly rejected with UNSUPPORTED_CODEC without bypassing validation."""
    for bogus in ("experimental_codec_bogus", "unsupported_xyz_format", "video_codec_only"):
        assert FFmpegService.is_decoder_available(bogus) is False
        with pytest.raises(FFmpegInspectionError) as exc_info:
            FFmpegService.validate_and_normalize_codec(bogus)
        assert exc_info.value.error_code == "UNSUPPORTED_CODEC"

    # Test via inspect_container mock
    dummy_data = make_mp3_audio(duration=0.5)
    with patch("backend.services.ffmpeg_service.av.open") as mock_open:
        mock_container = MagicMock()
        mock_astream = MagicMock()
        mock_astream.codec_context.name = "unknown_audio_codec_q123"
        mock_container.streams.audio = [mock_astream]
        mock_container.streams.video = []
        mock_open.return_value.__enter__.return_value = mock_container

        with pytest.raises(FFmpegInspectionError) as exc_info:
            FFmpegService.inspect_container(dummy_data, "bad.mpeg")
        assert exc_info.value.error_code == "UNSUPPORTED_CODEC"


def test_15_end_to_end_mp3_analyze_endpoint(client, auth_headers):
    """Test 15: End-to-end POST /api/v1/audio/analyze with MP3 audio in MPEG and MP3 containers."""
    mp3_data = make_mp3_audio(duration=1.5, sr=16000, freq=520.0)

    # Submit as .mpeg
    res_mpeg = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("wiretap.mpeg", mp3_data, "audio/mpeg")},
        headers=auth_headers,
    )
    assert res_mpeg.status_code == 200
    report_mpeg = res_mpeg.json()
    assert report_mpeg["success"] is True
    assert report_mpeg["status"] in ("completed", "AI_MODEL_NOT_CONFIGURED")
    assert report_mpeg["model"]["name"] == "AASIST"
    assert report_mpeg["audio_information"]["sample_rate"] == 16000
    assert report_mpeg["segments_analyzed"] >= 1

    # Submit as .mp3
    res_mp3 = client.post(
        "/api/v1/audio/analyze",
        files={"file": ("wiretap.mp3", mp3_data, "audio/mp3")},
        headers=auth_headers,
    )
    assert res_mp3.status_code == 200
    report_mp3 = res_mp3.json()
    assert report_mp3["success"] is True
    assert report_mp3["model"]["name"] == "AASIST"
    assert report_mp3["audio_information"]["sample_rate"] == 16000
    assert report_mp3["segments_analyzed"] >= 1


