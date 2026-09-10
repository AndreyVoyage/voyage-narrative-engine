# KIRA Companion MVP RC1 -- Windows launcher (single canonical user entry point).
#
# Starts ONE local process: the Companion backend, which also serves the built
# React SPA (no separate dev server, no CORS). Loopback only. Fake provider is
# NOT used to answer as KIRA in release mode -- if no real DIALOGUE provider is
# configured, the UI shows a "configure a provider" state.
#
# Prerequisites:
#   - Python 3.11+ on PATH (`py`)
#   - A built frontend: run  tools\build_character_companion_release.ps1  first
#
# User data (chats, memory, state, settings, encrypted key) lives in
#   %LOCALAPPDATA%\KiraCompanion\data
# and is NEVER touched by rebuilding the frontend.
#
# SINGLE-INSTANCE / DEVELOPMENT CONTRACT
#   There is exactly ONE launcher-owned backend per real data root. Its identity
#   (pid + port + data root) is recorded next to the data root in
#   backend.owned.json. Double-clicking the shortcut again:
#     - if that owned backend is healthy  -> just opens it, spawns nothing;
#     - if it is stale / wedged           -> replaces ONLY that one pid.
#   Unrelated Python/PowerShell processes are never touched, and processes are
#   never matched by executable name.
#
#   A running backend keeps the code it was started with. Editing repo code does
#   NOT affect it. To load new backend code, restart it for acceptance:
#     tools\start_character_companion.ps1 -Restart
#   (or close this launcher window, which stops the backend, then relaunch).

[CmdletBinding()]
param(
    # Stop the current launcher-owned backend (if any) and start a fresh one on
    # the current code. This is the explicit "restart for acceptance" switch.
    [switch]$Restart
)

$ErrorActionPreference = "Stop"

# Anchor everything on THIS script's directory, not the current shell CWD.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
$backend   = Join-Path $scriptDir "character_companion_server.py"
$webRoot   = Join-Path $repoRoot  "apps\character_companion_react\dist"
$dataRoot  = Join-Path $env:LOCALAPPDATA "KiraCompanion\data"
# Runtime ownership marker for the ONE launcher-owned backend bound to this data
# root. It is a SIBLING of the data root (never written inside it) so it can
# never touch the owner's chats / memory / settings.
$ownerFile = Join-Path $env:LOCALAPPDATA "KiraCompanion\backend.owned.json"

$python = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python -ErrorAction SilentlyContinue) }
if (-not $python) { Write-Error "Python 3.11+ not found on PATH (`py` / `python`)."; exit 1 }

if (-not (Test-Path (Join-Path $webRoot "index.html"))) {
    Write-Error "Frontend build not found at:`n  $webRoot`nRun tools\build_character_companion_release.ps1 first."
    exit 1
}
New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null

# --- identify a launcher-owned backend already bound to THIS data root -------
function Get-OwnedCompanionBackend {
    if (-not (Test-Path $ownerFile)) { return $null }
    try { $m = Get-Content $ownerFile -Raw -ErrorAction Stop | ConvertFrom-Json } catch { return $null }
    if (-not $m.pid -or -not $m.port -or ($m.dataRoot -ne $dataRoot)) { return $null }
    if (-not (Get-Process -Id $m.pid -ErrorAction SilentlyContinue)) { return $null }
    # Deterministic identity: this exact pid must be a Companion backend started
    # for THIS data root -- verified by command line, never by process name.
    $ci = Get-CimInstance Win32_Process -Filter "ProcessId = $($m.pid)" -ErrorAction SilentlyContinue
    if (-not $ci) { return $null }
    if ($ci.CommandLine -notlike "*character_companion_server.py*") { return $null }
    if ($ci.CommandLine -notlike "*$dataRoot*") { return $null }
    return $m
}

function Test-CompanionHealthy([int]$port) {
    try {
        $r = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/health" -f $port) -TimeoutSec 3 -ErrorAction Stop
        return ($r.status -eq "ready" -and $r.client -eq "companion")
    } catch { return $false }
}

function Stop-OwnedBackend($m) {
    # Stop ONLY this one verified pid (and its child interpreter, if `py` spawned
    # one). Never a name-based or wildcard kill.
    Get-CimInstance Win32_Process -Filter "ParentProcessId = $($m.pid)" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*character_companion_server.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $m.pid -Force -ErrorAction SilentlyContinue
    Remove-Item $ownerFile -ErrorAction SilentlyContinue
}

$owned = Get-OwnedCompanionBackend

if ($owned -and -not $Restart) {
    if (Test-CompanionHealthy $owned.port) {
        $url = "http://127.0.0.1:$($owned.port)/"
        Write-Host "KIRA Companion is already running (owned pid $($owned.pid)) at $url"
        Write-Host "Data: $dataRoot"
        Write-Host "Opening the existing instance. Use  -Restart  to load new backend code."
        Start-Process $url
        return
    }
    Write-Host "Owned backend pid $($owned.pid) is not responding; replacing that instance."
    Stop-OwnedBackend $owned
}
elseif ($owned -and $Restart) {
    Write-Host "-Restart: stopping owned backend pid $($owned.pid) to load current code."
    Stop-OwnedBackend $owned
}
elseif (Test-Path $ownerFile) {
    # Stale marker: dead pid, not our backend, or a different data root.
    Remove-Item $ownerFile -ErrorAction SilentlyContinue
}

$portFile = Join-Path $env:TEMP ("kira_companion_port_" + [Guid]::NewGuid().ToString("N") + ".txt")
Remove-Item $portFile -ErrorAction SilentlyContinue

$env:PYTHONPATH = $repoRoot
$proc = Start-Process -FilePath $python.Source -PassThru -WindowStyle Hidden -ArgumentList @(
    $backend,
    "--mode", "release",
    "--port", "0",
    "--port-file", $portFile,
    "--data-root", $dataRoot,
    "--web-root", $webRoot
)

# The actual server pid: `py` (the launcher) spawns a child interpreter; use it
# when present so health checks, the ownership marker and shutdown all target
# the real backend, not the wrapper.
$serverPid = $proc.Id

try {
    $port = $null
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path $portFile) { $port = (Get-Content $portFile -Raw).Trim(); if ($port) { break } }
        Start-Sleep -Milliseconds 100
    }
    if (-not $port) { Write-Error "Companion backend did not start."; exit 1 }

    $child = Get-CimInstance Win32_Process -Filter "ParentProcessId = $($proc.Id)" -ErrorAction SilentlyContinue |
             Where-Object { $_.CommandLine -like "*character_companion_server.py*" } | Select-Object -First 1
    if ($child) { $serverPid = [int]$child.ProcessId }

    # Record ownership of exactly this backend + data root.
    [pscustomobject]@{
        pid        = $serverPid
        port       = [int]$port
        dataRoot   = $dataRoot
        startedUtc = (Get-Date).ToUniversalTime().ToString("o")
    } | ConvertTo-Json | Set-Content -Path $ownerFile -Encoding UTF8

    $url = "http://127.0.0.1:$port/"
    Write-Host "KIRA Companion RC1 running at $url"
    Write-Host "Data: $dataRoot"
    Start-Process $url
    Write-Host "Press Ctrl+C in this window to stop.  (repo code edits need a restart: -Restart, or close + relaunch)"
    while (-not $proc.HasExited) { Start-Sleep -Seconds 1 }
}
finally {
    # Stop the real server first, then the `py` wrapper -- by explicit pid only.
    if ($serverPid -ne $proc.Id) { Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue }
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $portFile -ErrorAction SilentlyContinue
    # Clear the ownership marker only if it still points at THIS backend.
    if (Test-Path $ownerFile) {
        try { $m = Get-Content $ownerFile -Raw -ErrorAction Stop | ConvertFrom-Json } catch { $m = $null }
        if ($m -and ($m.pid -eq $serverPid)) { Remove-Item $ownerFile -ErrorAction SilentlyContinue }
    }
}
