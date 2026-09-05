# React Character Lab -- Desktop Integration v1 launcher
#
# Convenience launcher ONLY. Starts:
#   1. The local loopback backend (tools/character_lab_react_server.py) --
#      127.0.0.1 only, FAKE provider only, a fixed conventional port.
#   2. The React/Vite dev server in "local" client mode (vite --mode
#      local-core), which proxies /api/... to that backend (see
#      apps/character_lab_react/vite.config.ts) -- no CORS configuration
#      needed.
# Opens a browser window at the Vite dev URL, then shuts BOTH processes down
# cleanly when that window is closed.
#
# This does not touch, replace, or start the existing vanilla Character Lab
# (tools/character_lab_server.py / tools/start_character_lab.ps1) -- run them
# independently; they are unrelated servers on unrelated ports.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$backendScript = Join-Path $repoRoot "tools\character_lab_react_server.py"
$reactDir = Join-Path $repoRoot "apps\character_lab_react"
$python = "py"
$frontendPort = 5183

function Find-BrowserExe {
    $candidates = @(
        "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "$env:LocalAppData\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
        "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    foreach ($cmd in @("msedge", "chrome")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    return $null
}

$portFile = Join-Path $env:TEMP ("character_lab_react_port_" + [System.Guid]::NewGuid().ToString("N") + ".txt")
Remove-Item $portFile -ErrorAction SilentlyContinue

$backendProc = $null
$frontendProc = $null
$backendPort = $null

try {
    # ---- 1. backend (loopback, fake provider only) ----
    $backendProc = Start-Process -FilePath $python `
        -ArgumentList @($backendScript, "--port-file", $portFile) `
        -PassThru -WindowStyle Hidden

    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path $portFile) {
            $backendPort = (Get-Content $portFile -Raw).Trim()
            if ($backendPort) { break }
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $backendPort) {
        throw "React Character Lab backend did not report a port."
    }

    $backendHealthy = $false
    for ($i = 0; $i -lt 100; $i++) {
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health" -TimeoutSec 1 | Out-Null
            $backendHealthy = $true
            break
        } catch {
            Start-Sleep -Milliseconds 100
        }
    }
    if (-not $backendHealthy) {
        throw "React Character Lab backend did not become healthy."
    }
    Write-Host "React Character Lab backend ready: http://127.0.0.1:$backendPort"

    # ---- 2. frontend (Vite dev server, local client mode) ----
    # vite.config.ts's dev proxy targets 127.0.0.1:8787 (the backend's fixed
    # DEFAULT_PORT) -- fail fast here rather than silently proxying nowhere.
    if ($backendPort -ne "8787") {
        throw "Backend bound to port $backendPort, but vite.config.ts's dev proxy expects 8787. " +
              "Re-run without forcing a different backend port."
    }

    $frontendArgs = "run dev:local -- --port $frontendPort --strictPort"
    $frontendProc = Start-Process -FilePath "cmd.exe" `
        -ArgumentList @("/c", "npm $frontendArgs") `
        -WorkingDirectory $reactDir -PassThru -WindowStyle Hidden

    $frontendUrl = "http://127.0.0.1:$frontendPort/"
    $frontendHealthy = $false
    for ($i = 0; $i -lt 150; $i++) {
        try {
            Invoke-WebRequest -Uri $frontendUrl -TimeoutSec 1 -UseBasicParsing | Out-Null
            $frontendHealthy = $true
            break
        } catch {
            Start-Sleep -Milliseconds 200
        }
    }
    if (-not $frontendHealthy) {
        throw "React Character Lab dev server did not become ready on $frontendUrl."
    }
    Write-Host "React Character Lab dev server ready: $frontendUrl"

    # ---- 3. open + wait for the window to close ----
    $browser = Find-BrowserExe
    if (-not $browser) {
        throw "No supported browser (Edge/Chrome) found."
    }

    $browserProc = Start-Process -FilePath $browser -ArgumentList @("--app=$frontendUrl") -PassThru
    $browserProc.WaitForExit()
}
finally {
    if ($backendPort) {
        try { Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$backendPort/shutdown" -TimeoutSec 2 | Out-Null } catch { }
    }
    if ($backendProc -and -not $backendProc.HasExited) {
        $null = $backendProc.WaitForExit(5000)
        if (-not $backendProc.HasExited) {
            Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
        }
    }
    if ($frontendProc -and -not $frontendProc.HasExited) {
        # The frontend process is `cmd.exe /c npm ...`, which itself spawns
        # npm.cmd -> node (vite) as child processes -- Stop-Process alone
        # would leave those running, so kill the whole tree.
        & taskkill /PID $frontendProc.Id /T /F 2>$null | Out-Null
    }
    Remove-Item $portFile -ErrorAction SilentlyContinue
}
