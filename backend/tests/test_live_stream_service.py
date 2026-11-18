import numpy as np
import pytest

from backend.services.live_stream_service import (
    MAX_WINDOW_BYTES,
    LiveAudioSession,
)


def test_live_session_calculates_pcm_metrics_and_bounds_sliding_window():
    session = LiveAudioSession()
    chunk = np.full(3200, 16384, dtype="<i2").tobytes()

    metrics = session.ingest(chunk)

    assert metrics["sample_rate"] == 16000
    assert metrics["channels"] == 1
    assert metrics["sample_count"] == 3200
    assert metrics["input_level_percent"] == pytest.approx(50.0, abs=0.1)
    assert metrics["rms_dbfs"] == pytest.approx(-6.02, abs=0.1)
    assert metrics["duration_seconds"] == pytest.approx(0.2)
    assert metrics["signal_quality"] == "usable"

    for _ in range(30):
        session.ingest(chunk)
    assert len(session.window_pcm) == MAX_WINDOW_BYTES
    assert session.samples_processed == 31 * 3200


def test_live_session_rejects_malformed_pcm():
    with pytest.raises(ValueError, match="16-bit PCM"):
        LiveAudioSession().ingest(b"\x01")
