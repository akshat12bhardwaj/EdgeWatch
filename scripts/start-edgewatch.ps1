<#
.SYNOPSIS
Starts Edge Watch: API (with dashboard), then IDS, then the lab (which runs its own broker and clients).

.EXAMPLE
.\scripts\start-edgewatch.ps1                         # benign traffic, then 5 scheduled attack families, about 6 minutes
.\scripts\start-edgewatch.ps1 -Mode benign -Seconds 1800
.\scripts\start-edgewatch.ps1 -Mode dashboard         # API and IDS only; start demos from the Security Demo page

Never deletes data. Each run writes to a new folder under edgewatch-data\run. Stop with .\scripts\stop-edgewatch.ps1.
#>
param(
    [ValidateSet("demo", "benign", "dashboard")][string]$Mode = "demo",
    [int]$Seconds = 1800,
    [int]$MqttPort = 18840,
    [int]$ApiPort = 8000,
    [string]$Model = "ew-dt12-lab-v6"
)
$ErrorActionPreference = "Stop"

$Repo = Split-Path -Parent $PSScriptRoot
$Data = if ($env:EDGEWATCH_DATA) { $env:EDGEWATCH_DATA } else { Join-Path $HOME "edgewatch-data" }
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
$Bundle = Join-Path $Data "models\$Model"
$Db = Join-Path $Data "run\events.sqlite"
$State = Join-Path $Data "run\edgewatch-pids.json"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RunDir = Join-Path $Data "run\$Stamp"

function Fail($message) { Write-Host "FAILED: $message" -ForegroundColor Red; exit 1 }
function Ok($message) { Write-Host "OK      $message" -ForegroundColor Green }

# Prerequisites. Each failure names its fix.
if (-not (Test-Path $Python)) { Fail "no .venv. See docs\implementation\WINDOWS_QUICK_START.md section A." }
if (-not (Test-Path (Join-Path $Repo "dashboard\web\dist\index.html"))) { Fail "dashboard not built. Run: cd dashboard\web; npm ci; npm run build" }
if (-not (Test-Path (Join-Path $Data "tools\mosquitto\Library\sbin\mosquitto.exe")) -and -not (Get-Command mosquitto -ErrorAction SilentlyContinue)) { Fail "Mosquitto not found under $Data\tools\mosquitto" }
if (-not (Test-Path "C:\Program Files\Wireshark\dumpcap.exe") -and -not (Get-Command dumpcap -ErrorAction SilentlyContinue)) { Fail "dumpcap not found. Install Wireshark with Npcap." }
& $Python -c "import sys; from ids.detector import Detector; Detector(sys.argv[1])" $Bundle
if ($LASTEXITCODE -ne 0) { Fail "model $Model did not load. See the error above; a version mismatch means reinstalling with constraints-model.txt." }
Ok "prerequisites, and model $Model loads"

# Refuse to start twice, or on a busy port.
if (Test-Path $State) {
    $old = Get-Content $State -Raw | ConvertFrom-Json
    $expected = @{ lab = "lab.run"; ids = "ids.service"; api = "dashboard.api" }
    foreach ($p in $old.processes) {
        # By command line, because Windows reuses PIDs: a stale file must not block a start.
        $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.pid)" -ErrorAction SilentlyContinue
        if ($live -and $live.CommandLine -like "*$($expected[$p.name])*") { Fail "Edge Watch looks already running ($($p.name), PID $($p.pid)). Run .\scripts\stop-edgewatch.ps1 first." }
    }
}
foreach ($port in @($ApiPort, $MqttPort)) {
    $busy = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($busy) { Fail "port $port is in use by PID $($busy[0].OwningProcess). Stop it first." }
}

New-Item -ItemType Directory -Force $RunDir | Out-Null
$truth = Join-Path $RunDir "ground_truth.json"
$env:EDGEWATCH_DB = $Db
$env:EDGEWATCH_MODEL = $Bundle
$env:EDGEWATCH_DATA = $Data
# The dashboard's Security Demo page starts bounded lab runs on the IDS's port and writes ground truth where the IDS reads it.
$env:EDGEWATCH_MQTT_PORT = "$MqttPort"
$env:EDGEWATCH_SCHEDULE = $truth
$env:PYTHONUNBUFFERED = "1"
$started = New-Object System.Collections.ArrayList

function Save-State {
    @{ run_dir = $RunDir; processes = @($started) } | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 $State
}

function Start-Part($name, [string[]]$arguments) {
    $quoted = ($arguments | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -join " "
    $process = Start-Process -FilePath $Python -ArgumentList $quoted -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $RunDir "$name.out.log") -RedirectStandardError (Join-Path $RunDir "$name.err.log")
    [void]$started.Add(@{ name = $name; pid = $process.Id })
    Save-State
    return $process
}

function Stop-Started {
    foreach ($p in $started) { & taskkill.exe /T /F /PID $p.pid 2>$null | Out-Null }
}

function Fail-Started($name, $message) {
    Write-Host "FAILED: $message" -ForegroundColor Red
    $log = Join-Path $RunDir "$name.err.log"
    if (Test-Path $log) { Write-Host "--- last lines of $log"; Get-Content $log -Tail 15 }
    Stop-Started
    exit 1
}

# 1. API first, so the dashboard can show the IDS arriving.
$api = Start-Part "api" @("-m", "dashboard.api", "--port", "$ApiPort")
$health = $null
foreach ($i in 1..40) {
    if ($api.HasExited) { Fail-Started "api" "API exited with code $($api.ExitCode)." }
    try { $health = Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 2; break } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $health) { Fail-Started "api" "API did not answer on port $ApiPort." }
Ok "API on http://127.0.0.1:$ApiPort (PID $($api.Id))"

# 2. IDS before traffic, so early packets are seen. Its capture only reads this port.
$scenario = if ($Mode -eq "demo") { "demo-benign-then-attacks" } elseif ($Mode -eq "benign") { "benign-base" } else { "dashboard-controlled" }
$ids = Start-Part "ids" @("-m", "ids.service", "--db", $Db, "--model", $Bundle, "--port", "$MqttPort", "--schedule", $truth, "--scenario", $scenario)
$capture = $null
foreach ($i in 1..60) {
    if ($ids.HasExited) { Fail-Started "ids" "IDS exited with code $($ids.ExitCode)." }
    # By command line, not parent: the venv python.exe is a launcher, so dumpcap is a grandchild.
    $capture = Get-CimInstance Win32_Process -Filter "Name='dumpcap.exe'" | Where-Object { $_.CommandLine -like "*tcp port $MqttPort*" -and $_.CommandLine -like "* -w - *" }
    if ($capture) { break }
    Start-Sleep -Milliseconds 500
}
if (-not $capture) { Fail-Started "ids" "IDS started no capture. Is it paused? See the Pause IDS button, or section D of the guide." }
Start-Sleep -Seconds 3   # dumpcap has no ready signal
Ok "IDS capturing port $MqttPort with model $Model (PID $($ids.Id))"

# 3. Lab last. It starts its own Mosquitto and clients, so no other broker is needed.
if ($Mode -ne "dashboard") {
    $out = Join-Path $Data "lab\live\$Stamp"
    $common = @("-m", "lab.run", "--out", $out, "--port", "$MqttPort", "--ground-truth", $truth)
    $lab = if ($Mode -eq "demo") {
        Start-Part "lab" ($common + @("--plan", "episodes", "--episodes", "1", "--scenario", "base", "--seed", ([int](Get-Date -UFormat %s) % 100000).ToString()))
    } else {
        Start-Part "lab" ($common + @("--plan", "benign", "--scenario", "base", "--seconds", "$Seconds"))
    }
    $reachable = $false
    foreach ($i in 1..40) {
        if ($lab.HasExited) { Fail-Started "lab" "lab runner exited with code $($lab.ExitCode)." }
        if (Get-NetTCPConnection -LocalPort $MqttPort -State Listen -ErrorAction SilentlyContinue) { $reachable = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $reachable) { Fail-Started "lab" "broker did not open port $MqttPort." }
    Ok "lab and its broker on port $MqttPort (PID $($lab.Id)); output in $out"
}

Save-State
Write-Host ""
Write-Host "Dashboard: http://127.0.0.1:$ApiPort/" -ForegroundColor Cyan
Write-Host "Logs:      $RunDir"
Write-Host "Stop:      .\scripts\stop-edgewatch.ps1"
if ($Mode -eq "demo") { Write-Host "The demo runs about 6 minutes: 20 s benign, then 5 attack families. The API and IDS then stay up, and the broker stops with the lab." }
