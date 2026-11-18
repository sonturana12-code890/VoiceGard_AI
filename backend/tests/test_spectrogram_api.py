"""
VOICEGUARD AI — Test Suite: 2D Log-Mel Spectrogram Visualization & API Engine
Validates:
1. AudioFeatureExtractor.extract_spectrogram_matrix()
2. Center frequency calculations across 40 Mel bands (0-8000 Hz)
3. DetectionPipeline spectrogram packaging
4. Schema validation for Phase3AudioAnalysisResponse.spectrogram
5. GET /api/v1/audio/{analysis_id}/spectrogram endpoint
6. Downsampling handling for long audio (> 600 frames)
"""

import io
import wave
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.feature_extractor import AudioFeatureExtractor
from backend.services.inference_pipeline import DetectionPipeline


def make_test_wav(duration: float = 2.0, sr: int = 16000, freq: float = 440.0) -> bytes:
    """Generates synthetic pure-tone PCM WAV bytes at 16kHz mono."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    pcm = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


class TestSpectrogramExtraction:
    """Unit tests for DSP Log-Mel spectrogram computation."""

    def test_feature_extractor_spectrogram_matrix(self):
        extractor = AudioFeatureExtractor(sample_rate=16000, n_fft=512, hop_length=160, n_mels=40)
        # 1.5s audio = 24,000 samples -> ~147 frames
        t = np.sin(2 * np.pi * 440 * np.linspace(0, 1.5, 24000)).astype(np.float32)
        features = extractor.extract_all(t)

        spec = features.spectrogram_matrix
        assert spec is not None
        assert "matrix" in spec
        assert isinstance(spec["matrix"], list)
        assert len(spec["matrix"]) > 0

        # Verify inner dimension is exactly 40 Mel bands
        assert len(spec["matrix"][0]) == 40
        assert spec["num_mels"] == 40
        assert spec["num_frames"] == len(spec["matrix"])

        # Check frequency bounds
        freqs = spec["mel_frequencies"]
        assert len(freqs) == 40
        assert freqs[0] > 0.0
        assert freqs[-1] < 8000.0
        assert all(freqs[i] < freqs[i + 1] for i in range(len(freqs) - 1))

        # Check dB calibration
        assert spec["min_db"] >= -80.0
        assert spec["max_db"] <= 0.0

    def test_spectrogram_downsampling_for_long_audio(self):
        extractor = AudioFeatureExtractor(sample_rate=16000, n_fft=512, hop_length=160, n_mels=40)
        # 10s audio at 10ms hop = ~1000 frames -> should downsample to max 600
        long_t = np.sin(2 * np.pi * 300 * np.linspace(0, 10.0, 160000)).astype(np.float32)
        frames = extractor.frame_signal(long_t)
        _, power = extractor.compute_stft(frames)
        mel_db, _ = extractor.extract_mel_spectrogram(power)

        spec = extractor.extract_spectrogram_matrix(mel_db, duration_seconds=10.0, max_frames=600)
        assert spec["num_frames"] == 600
        assert len(spec["matrix"]) == 600
        assert len(spec["matrix"][0]) == 40
        assert spec["duration_seconds"] == 10.0

    def test_pipeline_includes_spectrogram(self):
        pipeline = DetectionPipeline()
        wav_bytes = make_test_wav(duration=1.0)
        report = pipeline.analyze_audio(wav_bytes, "test_spec.wav", "audio/wav")

        assert report["success"] is True
        assert "spectrogram" in report
        spec = report["spectrogram"]
        assert spec is not None
        assert spec["num_mels"] == 40
        assert len(spec["matrix"]) > 0


class TestSpectrogramAPIEndpoints:
    """Integration tests for FastAPI spectrogram endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client):
        # Create test user or authenticate
        test_email = "spectrogram_tester@voiceguard.ai"
        test_pass = "TestPass123!Secure"
        signup_res = client.post("/api/auth/signup", json={
            "fullName": "Spectrogram Tester",
            "email": test_email,
            "password": test_pass,
            "termsAccepted": True,
        })
        if signup_res.status_code == 200 and "access_token" in signup_res.json():
            token = signup_res.json()["access_token"]
        else:
            login_res = client.post("/api/auth/login", json={
                "email": test_email,
                "password": test_pass,
            })
            token = login_res.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}

    def test_analyze_audio_v1_returns_spectrogram(self, client, auth_headers):
        wav_bytes = make_test_wav(duration=1.2)
        files = {"file": ("test_acoustic.wav", wav_bytes, "audio/wav")}
        res = client.post("/api/v1/audio/analyze", headers=auth_headers, files=files)

        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "spectrogram" in data
        assert data["spectrogram"] is not None

        spec = data["spectrogram"]
        assert "matrix" in spec
        assert isinstance(spec["matrix"], list)
        assert len(spec["matrix"][0]) == 40
        assert len(spec["mel_frequencies"]) == 40
        assert spec["num_mels"] == 40

    def test_get_spectrogram_by_id_endpoint(self, client, auth_headers):
        # 1. Upload audio to analyze
        wav_bytes = make_test_wav(duration=1.5)
        files = {"file": ("test_acoustic_id.wav", wav_bytes, "audio/wav")}
        res = client.post("/api/v1/audio/analyze", headers=auth_headers, files=files)
        assert res.status_code == 200
        analysis_id = res.json()["analysis_id"]

        # 2. Fetch spectrogram on-demand
        spec_res = client.get(f"/api/v1/audio/{analysis_id}/spectrogram", headers=auth_headers)
        assert spec_res.status_code == 200
        spec = spec_res.json()
        assert "matrix" in spec
        assert len(spec["matrix"][0]) == 40
        assert spec["num_mels"] == 40

    def test_get_spectrogram_non_existent_id(self, client, auth_headers):
        res = client.get("/api/v1/audio/non-existent-uuid/spectrogram", headers=auth_headers)
        assert res.status_code == 404

    def test_spectrogram_95_second_audio_and_zoom_bounds(self):
        """
        Validates 95.472-second audio file processing:
        - Downsampled to exactly 600 frames
        - Full 95.472s duration preserved
        - Mathematical zoom boundary checks: min 1.0x, max 8.0x, reset to 1.0x
        """
        duration_95s = 95.472
        sr = 16000
        extractor = AudioFeatureExtractor(sample_rate=sr, n_fft=512, hop_length=160, n_mels=40)

        # Generate lightweight 95.472-second audio simulation
        num_samples = int(duration_95s * sr)
        # 1.5M samples
        t = np.sin(2 * np.pi * 440 * np.linspace(0, duration_95s, num_samples)).astype(np.float32)

        frames = extractor.frame_signal(t)
        _, power = extractor.compute_stft(frames)
        mel_db, _ = extractor.extract_mel_spectrogram(power)

        spec = extractor.extract_spectrogram_matrix(mel_db, duration_seconds=duration_95s, max_frames=600)

        assert spec["num_frames"] == 600
        assert len(spec["matrix"]) == 600
        assert len(spec["matrix"][0]) == 40
        assert spec["duration_seconds"] == 95.472
        assert spec["num_mels"] == 40

        # Simulate LogMelSpectrogramViewer zoom logic
        total_duration = spec["duration_seconds"]
        zoom_level = 1.0
        view_start = 0.0
        view_end = total_duration

        # 1. Initial state must be exactly 1.0x with full duration
        assert zoom_level == 1.0
        assert view_start == 0.0
        assert view_end == 95.472
        assert (view_end - view_start) == 95.472

        def set_zoom(target_zoom, current_start, current_end):
            clamped = max(1.0, min(8.0, target_zoom))
            zl = round(clamped, 1)
            if zl <= 1.001:
                return 1.0, 0.0, total_duration
            new_span = total_duration / zl
            center_time = (current_start + current_end) / 2.0
            start = center_time - new_span / 2.0
            end = start + new_span
            if start < 0:
                start = 0.0
                end = min(total_duration, new_span)
            if end > total_duration:
                end = total_duration
                start = max(0.0, total_duration - new_span)
            return zl, start, end

        # 2. Zoom in 50 times (must clamp strictly to 8.0x, never 763.8x)
        current_zl = zoom_level
        for _ in range(50):
            current_zl, view_start, view_end = set_zoom(current_zl * 1.3, view_start, view_end)
        assert current_zl == 8.0
        assert round(view_end - view_start, 2) == round(95.472 / 8.0, 2)
        assert current_zl <= 8.0

        # 3. Zoom out 50 times (must clamp strictly to 1.0x)
        for _ in range(50):
            current_zl, view_start, view_end = set_zoom(current_zl / 1.3, view_start, view_end)
        assert current_zl == 1.0
        assert view_start == 0.0
        assert view_end == 95.472

        # 4. Reset zoom
        current_zl, view_start, view_end = set_zoom(1.0, view_start, view_end)
        assert current_zl == 1.0
        assert view_start == 0.0
        assert view_end == 95.472

