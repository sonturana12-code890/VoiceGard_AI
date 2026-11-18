# ============================================================================
# VOICEGUARD AI — Automated Shutdown Script (PowerShell)
# Problem Statement: SIH26104 — AI Voice Anti-Spoofing & Cyber Acoustic Defense
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"

Write-Host "================================================================================" -ForegroundColor Yellow
Write-Host "       STOPPING VOICEGUARD AI SERVER PROCESSES                                  " -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Yellow

$Port = 8000
$Connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue

$StoppedAny = $false

if ($Connections) {
    foreach ($conn in $Connections) {
        $pidToKill = $conn.OwningProcess
        if ($pidToKill -and $pidToKill -ne 0) {
            $proc = Get-Process -Id $pidToKill -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "[INFO] Terminating process $($proc.ProcessName) (PID: $pidToKill) on port $Port..." -ForegroundColor Cyan
                Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
                $StoppedAny = $true
            }
        }
    }
}

# Also find any remaining python processes running uvicorn backend.main:app
$UvicornProcs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*uvicorn*backend.main:app*" }
foreach ($p in $UvicornProcs) {
    Write-Host "[INFO] Terminating orphan uvicorn process (PID: $($p.ProcessId))..." -ForegroundColor Cyan
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    $StoppedAny = $true
}

Start-Sleep -Seconds 1

# Verify port is free
$Remaining = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if (-not $Remaining) {
    Write-Host "[OK] Port $Port is free. VOICEGUARD AI server stopped successfully." -ForegroundColor Green
} else {
    Write-Host "[WARN] Port $Port is still in use by PID $($Remaining[0].OwningProcess)." -ForegroundColor Red
}

