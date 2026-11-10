<#
.SYNOPSIS
Starts the Wokwi virtual smart-home hub (broker + telemetry reader + serial bridge) on the port Edge Watch's IDS captures.
Optional; run after start-edgewatch.ps1.

.EXAMPLE
.\scripts\start-edgewatch.ps1 -Mode dashboard     # IDS + API on MQTT port 18840
.\scripts\start-wokwi-home.ps1                    # this script; then start the simulator in VS Code (printed below)
.\scripts\stop-wokwi-home.ps1

Default (free): the ESP32 prints structured serial lines; Wokwi for VS Code serves its serial port over RFC2217 on
localhost:4000 (wokwi.toml), and lab.home's serial bridge publishes them over MQTT. The ESP32 itself does not speak MQTT then.
-Gateway: the ESP32 connects over Wokwi WiFi to host.wokwi.internal instead (needs the paid Private IoT Gateway, firmware env
esp32dev-wifi). The broker accepts loopback connections only. Nothing here starts or controls the Wokwi simulator itself.
#>
param([int]$MqttPort = 18840, [switch]$SkipBuild, [switch]$Gateway, [int]$SerialPort = 4000)
$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $PSScriptRoot
$Data = if ($env:EDGEWATCH_DATA) { $env:EDGEWATCH_DATA } else { Join-Path $HOME "edgewatch-data" }
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
$HomeDir = Join-Path $Data "home"
$State = Join-Path $HomeDir "wokwi-home-pid.json"
$Firmware = Join-Path $Repo "simulators\wokwi-smart-home"
$Pio = Join-Path $HOME ".platformio\penv\Scripts\pio.exe"
$FwEnv = if ($Gateway) { "esp32dev-wifi" } else { "esp32dev" }
$env:PYTHONPATH = "$Repo\src;$Repo"
$env:EDGEWATCH_DATA = $Data

function Fail($message) { Write-Host "FAILED: $message" -ForegroundColor Red; exit 1 }
function Ok($message) { Write-Host "OK      $message" -ForegroundColor Green }
function Warn($message) { Write-Host "NOTE    $message" -ForegroundColor Yellow }

if (-not (Test-Path $Python)) { Fail "no .venv. See docs\SETUP.md." }
if (-not $Gateway) {
    & $Python -c "import serial.rfc2217" 2>$null
    if ($LASTEXITCODE -ne 0) { Fail "the serial bridge needs pyserial: .venv\Scripts\python.exe -m pip install pyserial" }
}

# One instance only: a live lab.home process recorded here blocks a second start.
if (Test-Path $State) {
    $old = Get-Content $State -Raw | ConvertFrom-Json
    $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($old.pid)" -ErrorAction SilentlyContinue
    if ($live -and $live.CommandLine -like "*lab.home*") { Fail "the smart-home hub is already running (PID $($old.pid)). Run .\scripts\stop-wokwi-home.ps1 first." }
}

# Edge Watch should already be capturing this port, or the device's traffic is not analysed.
$runDir = $null
$pids = Join-Path $Data "run\edgewatch-pids.json"
if (Test-Path $pids) {
    $ew = Get-Content $pids -Raw | ConvertFrom-Json
    $ids = $ew.processes | Where-Object { $_.name -eq "ids" }
    $idsProc = if ($ids) { Get-CimInstance Win32_Process -Filter "ProcessId=$($ids.pid)" -ErrorAction SilentlyContinue }
    if ($idsProc -and $idsProc.CommandLine -like "*ids.service*") {
        if ($idsProc.CommandLine -notlike "*--port $MqttPort*") { Fail "Edge Watch's IDS is not capturing port $MqttPort. Use the -MqttPort it was started with." }
        $runDir = $ew.run_dir
        Ok "Edge Watch IDS is capturing port $MqttPort"
    }
    $lab = $ew.processes | Where-Object { $_.name -eq "lab" }
    $labProc = if ($lab) { Get-CimInstance Win32_Process -Filter "ProcessId=$($lab.pid)" -ErrorAction SilentlyContinue }
    if ($labProc -and $labProc.CommandLine -like "*lab.run*") { Fail "the startup demo lab is still running its own broker on this port. Wait for it to finish, or start Edge Watch with -Mode dashboard." }
}
if (-not $runDir) { Warn "Edge Watch is not running. Start it first with .\scripts\start-edgewatch.ps1 -Mode dashboard, or the device's traffic will not be analysed." }

$busy = Get-NetTCPConnection -LocalPort $MqttPort -State Listen -ErrorAction SilentlyContinue
if ($busy) { Fail "port $MqttPort is in use by PID $($busy[0].OwningProcess) (a lab run's broker?). Wait for it to finish." }

# Accounts, broker config and the firmware's secrets.h (idempotent), then a firmware build when it is missing or older.
& $Python -m lab.home init --port $MqttPort
if ($LASTEXITCODE -ne 0) { Fail "lab.home init failed" }
$bin = Join-Path $Firmware ".pio\build\$FwEnv\firmware.bin"
$secrets = Join-Path $Firmware "include\secrets.h"
$stale = -not (Test-Path $bin) -or ($Gateway -and (Get-Item $secrets).LastWriteTime -gt (Get-Item $bin).LastWriteTime)
if ($stale -and -not $SkipBuild) {
    if (-not (Test-Path $Pio)) { Fail "firmware needs building and PlatformIO was not found at $Pio. Install the PlatformIO VS Code extension." }
    Write-Host "Building the ESP32 firmware ($FwEnv; the first build downloads the Arduino-ESP32 framework)..."
    Push-Location $Firmware
    try { & $Pio run -e $FwEnv | Out-Host; $code = $LASTEXITCODE } finally { Pop-Location }
    if ($code -ne 0) { Fail "firmware build failed; see the output above" }
}
if (-not (Test-Path $bin)) { Fail "no firmware at $bin" }
Ok "firmware $bin"

$arguments = @("-m", "lab.home", "serve", "--port", "$MqttPort")
if (-not $Gateway) { $arguments += @("--serial", "rfc2217://localhost:$SerialPort") }
if ($runDir) { $arguments += @("--devices", "`"$(Join-Path $runDir 'devices.json')`"") }
$process = Start-Process -FilePath $Python -ArgumentList ($arguments -join " ") -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $HomeDir "serve.out.log") -RedirectStandardError (Join-Path $HomeDir "serve.err.log")
@{ pid = $process.Id; port = $MqttPort } | ConvertTo-Json | Set-Content -Encoding UTF8 $State
$ready = $false
foreach ($i in 1..30) {
    if ($process.HasExited) { Get-Content (Join-Path $HomeDir "serve.err.log") -Tail 10; Fail "the hub exited with code $($process.ExitCode)" }
    if (Get-NetTCPConnection -LocalPort $MqttPort -State Listen -ErrorAction SilentlyContinue) { $ready = $true; break }
    Start-Sleep -Milliseconds 300
}
if (-not $ready) { & taskkill.exe /T /F /PID $process.Id | Out-Null; Fail "the hub did not open port $MqttPort" }
Ok "smart-home hub on 127.0.0.1:$MqttPort and [::1]:$MqttPort (PID $($process.Id))"
if (-not $Gateway) { Ok "serial bridge waiting for Wokwi at rfc2217://localhost:$SerialPort" }

$hasWokwi = (& code --list-extensions 2>$null) -contains "wokwi.wokwi-vscode"
if (-not $hasWokwi) { Warn "the Wokwi for VS Code extension was not found (wokwi.wokwi-vscode)." }
Write-Host ""
Write-Host "Manual step in VS Code (the simulator cannot be started from a script):" -ForegroundColor Cyan
Write-Host "  1. File > Open Folder... > $Firmware   (wokwi.toml must be at the root of the opened folder)"
Write-Host "  2. F1 > 'Wokwi: Request a new License' the first time, if VS Code asks for one."
if ($Gateway) {
    Write-Host "  3. Point wokwi.toml at .pio/build/esp32dev-wifi/ and F1 > 'Enable Private Wokwi IoT Gateway' (Wokwi paid plans)."
    Write-Host "  4. F1 > 'Wokwi: Start Simulator'. Serial: 'MQTT: connecting to host.wokwi.internal:$MqttPort ... connected'."
} else {
    Write-Host "  3. F1 > 'Wokwi: Start Simulator'. No gateway is needed: the bridge connects to rfc2217://localhost:$SerialPort by itself."
    Write-Host "  4. Evidence: $HomeDir\serve.out.log shows 'serial bridge: connected to rfc2217://localhost:$SerialPort'."
}
Write-Host "  5. Dashboard > Overview > Virtual Smart Home shows the readings. Click the PIR sensor or DHT22 in Wokwi to change them."
Write-Host "Stop with .\scripts\stop-wokwi-home.ps1 (Edge Watch keeps running)."
