<#
.SYNOPSIS
Stops the smart-home hub that start-wokwi-home.ps1 started (broker and telemetry bridge), and nothing else. Keeps all data.
#>
$ErrorActionPreference = "Stop"
$Data = if ($env:EDGEWATCH_DATA) { $env:EDGEWATCH_DATA } else { Join-Path $HOME "edgewatch-data" }
$State = Join-Path $Data "home\wokwi-home-pid.json"
if (-not (Test-Path $State)) { Write-Host "Nothing recorded as started (no $State)."; exit 0 }
$saved = Get-Content $State -Raw | ConvertFrom-Json
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($saved.pid)" -ErrorAction SilentlyContinue
if (-not $process) { Write-Host "The hub (PID $($saved.pid)) had already stopped." }
elseif ($process.CommandLine -notlike "*lab.home*") { Write-Host "PID $($saved.pid) is no longer the hub, so it was left alone." }
else {
    # /T also stops its Mosquitto child.
    & taskkill.exe /T /F /PID $saved.pid | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED to stop the hub (PID $($saved.pid))." -ForegroundColor Red; exit 1 }
    Write-Host "Stopped the smart-home hub (PID $($saved.pid))." -ForegroundColor Green
}
Remove-Item $State
