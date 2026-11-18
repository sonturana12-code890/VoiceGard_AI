@echo off
title Stop VOICEGUARD AI
cd /d "%~dp0"

echo =======================================================================
echo          STOPPING VOICEGUARD AI SERVER PROCESSES
echo =======================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_voiceguard.ps1"

echo.
pause
