# ==============================================================================
# VOICEGUARD AI — Production Dockerfile for Render Web Service
# SIH26104 Cyber Acoustic Defense & Real-Time Anti-Spoofing Detection
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    ENVIRONMENT=production

WORKDIR /app

# Install system dependencies (FFmpeg CLI, libsndfile for audio DSP, build-essential)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install lightweight CPU-only PyTorch & TorchAudio wheel (keeps image small & fast)
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy all application code, models, and assets
COPY . /app

# Validate presence of production ONNX models
RUN python -c "from pathlib import Path; assert (Path('/app/backend/models_weights/rawnet2.onnx')).is_file(), 'Missing rawnet2.onnx'" \
    && python -c "from pathlib import Path; assert (Path('/app/backend/models_weights/aasist.onnx')).is_file(), 'Missing aasist.onnx'"

EXPOSE 8000

# Health check probing the FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Production startup command
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
