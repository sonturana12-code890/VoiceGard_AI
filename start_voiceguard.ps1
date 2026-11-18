# ============================================================================
# VOICEGUARD AI — Automated Production Startup Script (PowerShell)
# Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "       VOICEGUARD AI — CYBER ACOUSTIC DEFENSE PLATFORM STARTUP                  " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# 1. Detect Python Virtual Environment
$WorkspaceRoot = $PSScriptRoot
Set-Location $WorkspaceRoot

$PythonExe = $null
$CandidatePythons = @(
    (Join-Path $WorkspaceRoot "backend\.venv\Scripts\python.exe"),
    (Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"),
    "python.exe"
)

foreach ($candidate in $CandidatePythons) {
    if (Test-Path $candidate) {
        $PythonExe = $candidate
        break
    }
}

if (-not $PythonExe) {
    Write-Host "[ERROR] Python virtual environment (.venv) was not found!" -ForegroundColor Red
    Write-Host "Please create a virtual environment first: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Detected Python Environment: $PythonExe" -ForegroundColor Green

# 2. Check Required Python Dependencies
Write-Host "[INFO] Verifying core dependencies (FastAPI, PyAV, ONNX Runtime, NumPy, SpeechBrain, Torch)..." -ForegroundColor Gray
$CheckScript = "import sys, importlib.util; missing = [p for p in ['fastapi', 'uvicorn', 'av', 'numpy', 'onnxruntime', 'bcrypt', 'jwt', 'pydantic', 'torch', 'speechbrain', 'torchaudio'] if not importlib.util.find_spec(p)]; sys.exit(1 if missing else 0)"

& $PythonExe -c $CheckScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Installing missing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $PythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FATAL] Failed to install dependencies. Check network and compiler tools." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[OK] All core dependencies verified." -ForegroundColor Green
}

# 3. Detect FFmpeg & FFprobe Executables
Write-Host "[INFO] Detecting FFmpeg & FFprobe engines..." -ForegroundColor Gray
$FFmpegCandidates = @(
    "C:\Users\LC\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe",
    (Join-Path $env:USERPROFILE "Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe"),
    "C:\ffmpeg\bin\ffmpeg.exe",
    "C:\Program Files\ffmpeg\bin\ffmpeg.exe"
)

$FFprobeCandidates = @(
    "C:\Users\LC\Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin\ffprobe.exe",
    (Join-Path $env:USERPROFILE "Downloads\ffmpeg-9.0.2-essentials_build\ffmpeg-9.0.2-essentials_build\bin\ffprobe.exe"),
    "C:\ffmpeg\bin\ffprobe.exe",
    "C:\Program Files\ffmpeg\bin\ffprobe.exe"
)

$FoundFFmpeg = $null
foreach ($path in $FFmpegCandidates) {
    if (Test-Path $path) {
        $FoundFFmpeg = $path
        break
    }
}

$FoundFFprobe = $null
foreach ($path in $FFprobeCandidates) {
    if (Test-Path $path) {
        $FoundFFprobe = $path
        break
    }
}

if ($FoundFFmpeg) {
    $env:FFMPEG_PATH = $FoundFFmpeg
    Write-Host "[OK] Discovered FFmpeg Binary: $FoundFFmpeg" -ForegroundColor Green
} else {
    Write-Host "[WARN] Standalone FFmpeg CLI binary not found. Falling back to embedded PyAV (libav) C-engine." -ForegroundColor Yellow
}

if ($FoundFFprobe) {
    $env:FFPROBE_PATH = $FoundFFprobe
    Write-Host "[OK] Discovered FFprobe Binary: $FoundFFprobe" -ForegroundColor Green
} else {
    Write-Host "[WARN] Standalone FFprobe CLI binary not found. Falling back to embedded PyAV (libav) C-engine." -ForegroundColor Yellow
}

# 4. Check If Port 8000 Is In Use
$Port = 8000
$ExistingProc = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($ExistingProc) {
    Write-Host "[WARN] Port $Port is currently occupied by PID $($ExistingProc[0].OwningProcess)." -ForegroundColor Yellow
    Write-Host "Terminating previous process to ensure fresh startup..." -ForegroundColor Yellow
    Stop-Process -Id $ExistingProc[0].OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

# 5. Launch FastAPI Backend via Uvicorn
Write-Host "[INFO] Starting VOICEGUARD AI server on http://127.0.0.1:$Port..." -ForegroundColor Cyan

Start-Process -FilePath (Resolve-Path $PythonExe).Path -ArgumentList "-m uvicorn backend.main:app --host 127.0.0.1 --port $Port --reload" -WorkingDirectory $WorkspaceRoot

# 6. Verify Health Endpoint
Write-Host "[INFO] Waiting for server initialization..." -ForegroundColor Gray
$HealthUrl = "http://127.0.0.1:$Port/health"
$IsHealthy = $false

for ($i = 1; $i -le 25; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($res.status -eq "healthy") {
            $IsHealthy = $true
            break
        }
    } catch {
        Write-Host "." -NoNewline
    }
}

Write-Host ""
if ($IsHealthy) {
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "  VOICEGUARD AI APPLICATION IS ONLINE AND FULLY OPERATIONAL!                   " -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Landing Page:        http://127.0.0.1:$Port/" -ForegroundColor Cyan
    Write-Host "  Security Dashboard:  http://127.0.0.1:$Port/app" -ForegroundColor Cyan
    Write-Host "  API Documentation:   http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
    Write-Host "  Health Status:       http://127.0.0.1:$Port/api/health" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Opening default browser to http://127.0.0.1:$Port/ ..." -ForegroundColor Green
    Start-Process "http://127.0.0.1:$Port/"
    Write-Host "  To stop the server, run: .\stop_voiceguard.bat (or .\stop_voiceguard.ps1)" -ForegroundColor Yellow
} else {
    Write-Host "[ERROR] The server did not respond to health checks within 15 seconds." -ForegroundColor Red
    Write-Host "Check terminal window or uvicorn logs for errors." -ForegroundColor Yellow
}

