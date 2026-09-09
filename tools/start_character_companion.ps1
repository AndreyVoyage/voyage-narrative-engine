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

$ErrorActionPreference = "Stop"

# Anchor everything on THIS script's directory, not the current shell CWD.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
$backend   = Join-Path $scriptDir "character_companion_server.py"
$webRoot   = Join-Path $repoRoot  "apps\character_companion_react\dist"
$dataRoot  = Join-Path $env:LOCALAPPDATA "KiraCompanion\data"

$python = (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python -ErrorAction SilentlyContinue) }
if (-not $python) { Write-Error "Python 3.11+ not found on PATH (`py` / `python`)."; exit 1 }

if (-not (Test-Path (Join-Path $webRoot "index.html"))) {
    Write-Error "Frontend build not found at:`n  $webRoot`nRun tools\build_character_companion_release.ps1 first."
    exit 1
}
New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null

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

try {
    $port = $null
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path $portFile) { $port = (Get-Content $portFile -Raw).Trim(); if ($port) { break } }
        Start-Sleep -Milliseconds 100
    }
    if (-not $port) { Write-Error "Companion backend did not start."; exit 1 }

    $url = "http://127.0.0.1:$port/"
    Write-Host "KIRA Companion RC1 running at $url"
    Write-Host "Data: $dataRoot"
    Start-Process $url
    Write-Host "Press Ctrl+C in this window to stop."
    while (-not $proc.HasExited) { Start-Sleep -Seconds 1 }
}
finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    Remove-Item $portFile -ErrorAction SilentlyContinue
}
