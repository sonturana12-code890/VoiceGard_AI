@echo off
title VOICEGUARD AI - Cyber Acoustic Defense Platform
cd /d "%~dp0"

echo =======================================================================
echo          VOICEGUARD AI - CYBER ACOUSTIC DEFENSE PLATFORM
echo =======================================================================
echo.

:: 1. Clear any zombie or leftover processes on Port 8000
echo [INFO] Checking Port 8000 availability...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: 2. Detect the virtual environment Python interpreter
set "PY_EXE="
if exist "backend\.venv\Scripts\python.exe" set "PY_EXE=backend\.venv\Scripts\python.exe"
if not defined PY_EXE if exist ".venv\Scripts\python.exe" set "PY_EXE=.venv\Scripts\python.exe"
if not defined PY_EXE set "PY_EXE=python"

echo [OK] Using Python Environment: %PY_EXE%

:: 3. Launch background watcher that opens browser once backend is healthy
echo [INFO] Background browser launcher scheduled (waits for server health)...
start "" powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 30; $i++) { Start-Sleep -Milliseconds 600; try { if ((Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { Start-Process 'http://127.0.0.1:8000/'; break } } catch {} }"

echo [INFO] Starting VoiceGuard AI Backend on http://127.0.0.1:8000...
echo [INFO] Press Ctrl+C in this window at any time to stop the server.
echo.

"%PY_EXE%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

echo.
echo [INFO] VoiceGuard AI Server has stopped.
pause
