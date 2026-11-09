<#
.SYNOPSIS
Stops what start-edgewatch.ps1 started, and nothing else: lab and broker first, then IDS, then API. Never deletes data.

It checks each PID's command line first, because Windows reuses PIDs.
#>
$ErrorActionPreference = "Stop"
$Data = if ($env:EDGEWATCH_DATA) { $env:EDGEWATCH_DATA } else { Join-Path $HOME "edgewatch-data" }
$State = Join-Path $Data "run\edgewatch-pids.json"
$Expected = @{ lab = "lab.run"; ids = "ids.service"; api = "dashboard.api" }

if (-not (Test-Path $State)) { Write-Host "Nothing recorded as started (no $State)."; exit 0 }
$saved = Get-Content $State -Raw | ConvertFrom-Json
$failed = $false
foreach ($name in @("lab", "ids", "api")) {
    $entry = $saved.processes | Where-Object { $_.name -eq $name }
    if (-not $entry) { continue }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.pid)"
    if (-not $process) { Write-Host "$name (PID $($entry.pid)) had already stopped."; continue }
    if ($process.CommandLine -notlike "*$($Expected[$name])*") { Write-Host "PID $($entry.pid) is no longer $name, so it was left alone."; continue }
    # /T also stops the child processes: the lab's Mosquitto and capture, and the IDS's capture.
    & taskkill.exe /T /F /PID $entry.pid | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "FAILED to stop $name (PID $($entry.pid))." -ForegroundColor Red; $failed = $true }
    else { Write-Host "Stopped $name (PID $($entry.pid))." -ForegroundColor Green }
}
if ($failed) { exit 1 }
Remove-Item $State    # only the list of PIDs; no run data lives here
Write-Host "Data kept in $Data."
