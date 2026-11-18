"""VOICEGUARD AI — Services Package"""

from backend.services.audio_validator import (
    AudioValidator,
    AudioValidationError,
    ValidationResult,
)
from backend.services.audio_preprocessor import (
    AudioPreprocessor,
    AudioQualityMetrics,
    AudioPreprocessingError,
)
from backend.services.audio_segmenter import (
    AudioSegmenter,
    AudioSegment,
)
from backend.services.model_manager import (
    ModelManager,
    ModelNotFoundError,
    ModelInferenceError,
)
from backend.services.inference_pipeline import (
    DetectionPipeline,
)
from backend.services.audio_service import (
    VoiceDetectionService,
)
from backend.services.risk_engine import (
    FraudRiskEngine,
)
from backend.services.ffmpeg_service import (
    FFmpegService,
    FFmpegInspectionError,
    SUPPORTED_MPEG_CODECS,
    CANONICAL_MPEG_CODECS,
    CODEC_CANONICAL_MAP,
)
from backend.services.feature_extractor import (
    AudioFeatureExtractor,
    AudioFeatures,
)
from backend.services.prediction_engine import (
    VoicePredictionEngine,
    PredictionResult,
    stable_softmax,
)
from backend.services.rawnet2_service import (
    RawNet2Service,
    RawNet2ModelError,
    RawNet2InferenceError,
    RawNet2InferenceResult,
)
from backend.services.ecapa_service import (
    ECAPAService,
    ECAPAModelError,
    ECAPAInferenceError,
    SpeakerVerificationResult,
)

__all__ = [
    "AudioValidator",
    "AudioValidationError",
    "ValidationResult",
    "AudioPreprocessor",
    "AudioQualityMetrics",
    "AudioPreprocessingError",
    "AudioSegmenter",
    "AudioSegment",
    "ModelManager",
    "ModelNotFoundError",
    "ModelInferenceError",
    "DetectionPipeline",
    "VoiceDetectionService",
    "FraudRiskEngine",
    "FFmpegService",
    "FFmpegInspectionError",
    "SUPPORTED_MPEG_CODECS",
    "CANONICAL_MPEG_CODECS",
    "CODEC_CANONICAL_MAP",
    "AudioFeatureExtractor",
    "AudioFeatures",
    "VoicePredictionEngine",
    "PredictionResult",
    "stable_softmax",
    "RawNet2Service",
    "RawNet2ModelError",
    "RawNet2InferenceError",
    "RawNet2InferenceResult",
    "ECAPAService",
    "ECAPAModelError",
    "ECAPAInferenceError",
    "SpeakerVerificationResult",
]


