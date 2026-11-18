"""
VOICEGUARD AI — Backend Entrypoint
FastAPI Application, Middleware, Route Registration, and Static Asset Serving.
Problem Statement: SIH26104 – AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure both workspace root and backend directory are in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
for _p in [str(ROOT_DIR), str(BACKEND_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

try:
    from backend.auth import get_current_user
    from backend.database import get_db, init_db
except ImportError:
    from auth import get_current_user
    from database import get_db, init_db

from backend.routes.audio_routes import router as audio_router
from backend.routes.auth_routes import router as auth_router
from backend.routes.dashboard_routes import router as dashboard_router
from backend.routes.live_stream_routes import router as live_stream_router
from backend.routes.report_routes import router as report_router
from backend.routes.speaker_routes import router as speaker_router
from backend.routes.threat_routes import router as threat_router

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
PUBLIC_ASSET_SUFFIXES = {
    ".css", ".glb", ".gltf", ".html", ".ico", ".jpeg", ".jpg", ".js",
    ".json", ".mp3", ".ogg", ".otf", ".png", ".svg", ".ttf", ".wav",
    ".webp", ".woff", ".woff2",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event to initialize SQLite tables on application startup."""
    init_db()
    yield


app = FastAPI(
    title="VOICEGUARD AI — Cyber Acoustic Defense & Voice Biometrics API",
    description=(
        "Production-grade FastAPI backend for SIH26104: AI-Powered Real-Time Detection "
        "and Prevention of Voice Cloning Impersonation Attacks. "
        "Features JWT authentication, secure audio ingestion, modular preprocessing, "
        "forensic reporting, and interfaces prepared for AASIST & ECAPA-TDNN model integration."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============================================================================
# CORS MIDDLEWARE
# ============================================================================
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "null",
]
env_cors_raw = os.environ.get("CORS_ORIGINS", "")
allowed_origins = list(DEFAULT_CORS_ORIGINS)
if env_cors_raw:
    for o in env_cors_raw.split(","):
        cleaned = o.strip()
        if cleaned and cleaned not in allowed_origins:
            allowed_origins.append(cleaned)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://((localhost|127\.0\.0\.1)(:\d+)?|([a-zA-Z0-9-]+\.)*vercel\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)

logger = logging.getLogger("voiceguard.api")

@app.middleware("http")
async def log_and_pna_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    origin = request.headers.get("origin", "direct")
    pna_requested = request.headers.get("access-control-request-private-network") == "true"
    logger.info(f"Incoming: {request.method} {request.url.path} [Client: {client_ip}, Origin: {origin}]")
    try:
        response = await call_next(request)
        if pna_requested:
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        if origin == "null" or origin in allowed_origins:
            if "Access-Control-Allow-Origin" not in response.headers:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
        if response.status_code >= 400:
            logger.warning(f"Response: {request.method} {request.url.path} -> Status {response.status_code}")
        else:
            logger.info(f"Response: {request.method} {request.url.path} -> Status {response.status_code}")
        return response
    except Exception as exc:
        logger.error(f"Error handling {request.method} {request.url.path}: {exc}")
        raise


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Provides dual key compatibility ('detail' and 'error') for frontend clients."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": exc.detail},
        headers=getattr(exc, "headers", None) or {},
    )


# ============================================================================
# ROUTER REGISTRATION
# ============================================================================
app.include_router(auth_router)
app.include_router(audio_router)
app.include_router(speaker_router)
app.include_router(threat_router)
app.include_router(dashboard_router)
app.include_router(live_stream_router)
app.include_router(report_router)


# ============================================================================
# HEALTH & TELEMETRY ENDPOINTS
# ============================================================================
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """System health check, model checkpoint status, and device provider telemetry."""
    from backend.services.model_manager import ModelManager
    from backend.services.ffmpeg_service import FFmpegService

    model_mgr = ModelManager()
    model_report = model_mgr.get_status_report()
    aasist_active = model_report["models"]["aasist"]["installed"]
    rawnet_active = model_report["models"]["rawnet2"]["installed"]

    return {
        "status": "healthy",
        "message": "VoiceGuard AI Backend Running",
        "service": "VOICEGUARD AI Backend",
        "version": "3.0.0",
        "inference": {
            "synthetic_detection": "AASIST_ACTIVE" if aasist_active else "AI_MODEL_NOT_CONFIGURED",
            "speaker_verification": "RAWNET2_ACTIVE" if rawnet_active else "AI_MODEL_NOT_CONFIGURED",
            "pipeline_readiness": "AASIST / RawNet2 / ECAPA-TDNN ready",
            "device": model_mgr.device,
            "models_status": model_report,
        },
        "ffmpeg": FFmpegService.get_diagnostics(),
        "database": "SQLite / SQLAlchemy connected",
    }


# ============================================================================
# STATIC FRONTEND SERVING & WEB ROUTES
# ============================================================================
@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
@app.get("/signup", include_in_schema=False)
async def serve_landing():
    root_index = ROOT_DIR / "index.html"
    if root_index.is_file():
        return FileResponse(root_index, media_type="text/html")
    return JSONResponse({"message": "VOICEGUARD AI Backend is running. Access Swagger at /docs."})


@app.get("/app", include_in_schema=False)
@app.get("/app.html", include_in_schema=False)
async def serve_dashboard(request: Request, db: Session = Depends(get_db)):
    try:
        await get_current_user(request, None, db)
    except HTTPException as exc:
        if exc.status_code == 401:
            return RedirectResponse(url="/login?auth=login", status_code=303)
        raise

    app_html = ROOT_DIR / "app.html"
    if app_html.is_file():
        return FileResponse(
            app_html,
            media_type="text/html",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )
    root_index = ROOT_DIR / "index.html"
    if root_index.is_file():
        return FileResponse(root_index, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard interface not found.")


@app.get("/{filename:path}", include_in_schema=False)
async def serve_static_file(filename: str):
    file_path = (ROOT_DIR / filename).resolve()
    try:
        relative_path = file_path.relative_to(ROOT_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    private_directories = {"backend", "_backup_voiceguard"}
    if (
        not relative_path.parts
        or relative_path.parts[0].lower() in private_directories
        or any(part.startswith(".") for part in relative_path.parts)
        or file_path.suffix.lower() not in PUBLIC_ASSET_SUFFIXES
    ):
        raise HTTPException(status_code=404, detail=f"File {filename} not found.")

    if file_path.is_file():
        mime = None
        if filename.endswith(".js"):
            mime = "application/javascript"
        elif filename.endswith(".css"):
            mime = "text/css"
        elif filename.endswith(".html"):
            mime = "text/html"
        elif filename.endswith(".svg"):
            mime = "image/svg+xml"
        elif filename.endswith(".json"):
            mime = "application/json"
        elif filename.endswith(".png"):
            mime = "image/png"
        elif filename.endswith(".wav"):
            mime = "audio/wav"
        return FileResponse(file_path, media_type=mime)
    raise HTTPException(status_code=404, detail=f"File {filename} not found.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
