<# Starts/reuses the local IDS, home broker, correctly configured API and four controller bridges.
No attack starts automatically. Existing services are never restarted.
Stop only this launcher's processes with: .venv\Scripts\python.exe -m lab.startup stop
#>
param([int]$ApiPort = 8020, [int]$MqttPort = 18840)
$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
Push-Location $Repo
try {
    & .venv\Scripts\python.exe -m lab.startup start --api-port $ApiPort --mqtt-port $MqttPort
    if ($LASTEXITCODE -ne 0) { throw "Smart Home startup failed. Existing services were left intact; inspect the startup logs." }
} finally { Pop-Location }
