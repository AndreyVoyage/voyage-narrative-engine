# Character Lab V1 launcher
#
# Starts the local backend on 127.0.0.1, waits for /health, opens Edge (or
# Chrome) in App Mode as a dedicated application window, then shuts the backend
# down cleanly when the app window closes.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$serverScript = Join-Path $repoRoot "tools\character_lab_server.py"
$python = "py"

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

$portFile = Join-Path $env:TEMP ("character_lab_port_" + [System.Guid]::NewGuid().ToString("N") + ".txt")
Remove-Item $portFile -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath $python -ArgumentList @($serverScript, "--port-file", $portFile) -PassThru -WindowStyle Hidden

try {
    $port = $null
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path $portFile) {
            $port = (Get-Content $portFile -Raw).Trim()
            if ($port) { break }
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $port) {
        throw "Backend did not report a port."
    }

    $healthOk = $false
    for ($i = 0; $i -lt 100; $i++) {
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1 | Out-Null
            $healthOk = $true
            break
        } catch {
            Start-Sleep -Milliseconds 100
        }
    }
    if (-not $healthOk) {
        throw "Backend did not become healthy."
    }

    $browser = Find-BrowserExe
    if (-not $browser) {
        throw "No supported browser (Edge/Chrome) found."
    }

    $appUrl = "http://127.0.0.1:$port"
    $browserProc = Start-Process -FilePath $browser -ArgumentList @("--app=$appUrl") -PassThru
    $browserProc.WaitForExit()
}
finally {
    if ($port) {
        try { Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$port/shutdown" -TimeoutSec 2 | Out-Null } catch { }
    }
    if (-not $proc.HasExited) {
        $null = $proc.WaitForExit(5000)
        if (-not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force
        }
    }
    Remove-Item $portFile -ErrorAction SilentlyContinue
}
