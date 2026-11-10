<#
Attach the four independent Wokwi serial bridges to the existing local home hub.
This script never starts/stops the hub, IDS, API or VS Code. Ctrl+C stops only
these bridge sessions. Start each simulator in its own visible VS Code window.
Use -Build to compile the four projects with the existing local PlatformIO install.
#>
param([switch]$Build)
$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { throw "Create the project's .venv first (see README.md)." }
Push-Location $Repo
try {
    if ($Build) {
        $Pio = Join-Path $HOME ".platformio\penv\Scripts\pio.exe"
        if (-not (Test-Path -LiteralPath $Pio)) { throw "PlatformIO is missing. Use the existing project setup guide." }
        foreach ($Role in @("environment", "access", "lighting", "safety")) {
            & $Pio run -d "simulators/wokwi-$Role" -e esp32dev
            if ($LASTEXITCODE -ne 0) { throw "Firmware build failed for $Role; bridges were not started." }
        }
    }
    & $Python -m lab.controllers --config simulators/controllers.example.json
    if ($LASTEXITCODE -ne 0) { throw "Controller bridges exited with an error." }
} finally {
    Pop-Location
}
