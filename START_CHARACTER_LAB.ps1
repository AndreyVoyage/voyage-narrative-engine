# START_CHARACTER_LAB.ps1
# ============================================================================
#  Character Lab Test App V1 - official tracked launcher (PowerShell 7.6.3).
#
#  Runs the local Character Lab desktop app using the base/system Python (which
#  contains PySide6) plus the PINNED Voyage Character Platform (VCP) runtime from
#  build/output/lab_vcp_env. It never injects the live sibling VCP source tree
#  and never installs packages or makes network calls.
#
#  Bootstrap (run separately, once, when the pinned environment is absent):
#      py build/scripts/bootstrap_lab_vcp_env.py
# ============================================================================

# 1. Resolve the repository root independently of the caller's current directory.
$RepoRoot = $PSScriptRoot

# 2. Locate the pinned VCP runtime site-packages directory.
$VcpSitePackages = Join-Path $RepoRoot 'build\output\lab_vcp_env\Lib\site-packages'
$VcpPackage = Join-Path $VcpSitePackages 'voyage_character_platform'

if (-not (Test-Path -LiteralPath $VcpPackage)) {
    Write-Host ''
    Write-Host '[ERROR] Pinned Voyage Character Platform runtime not found:' -ForegroundColor Red
    Write-Host "        $VcpSitePackages"
    Write-Host ''
    Write-Host '        Bootstrap the pinned environment first (offline, no network):'
    Write-Host '            py build/scripts/bootstrap_lab_vcp_env.py'
    Write-Host ''
    exit 1
}

# 3. Require the Python launcher (which carries PySide6 in this environment).
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host ''
    Write-Host '[ERROR] Python launcher "py" not found. Install Python 3 (with PySide6).' -ForegroundColor Red
    Write-Host ''
    exit 1
}

# 3b. Verify PySide6 is importable in the base Python (offline check, no install).
& py -c "import PySide6" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] PySide6 is not importable in the base Python interpreter.' -ForegroundColor Red
    Write-Host '        Install PySide6 into the base Python once, then retry.' -ForegroundColor Yellow
    Write-Host ''
    exit 1
}

# 4. Inject ONLY the pinned VCP site-packages into PYTHONPATH. Never the live
#    sibling source tree, never an ambient install.
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$VcpSitePackages;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $VcpSitePackages
}

# 5. Launch the real entry point with the repository root as the working
#    directory, so ``py -m ui.character_lab`` resolves the Lab package root
#    regardless of the caller's current directory. Environment variables,
#    including DEEPSEEK_*, are inherited unchanged. No credentials are stored
#    in this launcher.
Push-Location $RepoRoot
try {
    & py -m ui.character_lab
    $ExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($ExitCode -ne 0) {
    Write-Host ''
    Write-Host "Character Lab exited with code $ExitCode." -ForegroundColor Yellow
    Write-Host ''
}

exit $ExitCode
