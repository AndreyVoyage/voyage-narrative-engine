# KIRA Companion MVP RC1 -- Windows release build.
#
# Produces a bounded distribution under  dist\character-companion\  containing
# only what the current application mode needs:
#   web\        the built React SPA (vite build output)
#   backend\    the Companion backend python package + server + accepted KIRA
#   RELEASE_MANIFEST.json   (no secrets)
#   START.ps1   thin launcher for the distributed copy
#
# Uses ONLY already-installed tooling. No npm install, no packaging framework,
# no model download, no network. If a true single-EXE is wanted later that is a
# separate slice (SELF_CONTAINED_EXE_DEFERRED).

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
$reactDir  = Join-Path $repoRoot "apps\character_companion_react"
$outDir    = Join-Path $repoRoot "dist\character-companion"

# --- 1. build the React SPA with installed tooling -------------------------
$viteLocal   = Join-Path $reactDir "node_modules\.bin\vite.cmd"
$viteSibling = Join-Path $repoRoot "apps\character_lab_react\node_modules\.bin\vite.cmd"
$vite = if (Test-Path $viteLocal) { $viteLocal } elseif (Test-Path $viteSibling) { $viteSibling } else { $null }
if (-not $vite) {
    Write-Error "vite not found. Run 'npm ci' in $reactDir (or apps\character_lab_react) first."
    exit 1
}
Push-Location $reactDir
try { & $vite build } finally { Pop-Location }

$spa = Join-Path $reactDir "dist"
if (-not (Test-Path (Join-Path $spa "index.html"))) { Write-Error "vite build produced no dist/index.html"; exit 1 }

# --- 2. assemble the distribution ----------------------------------------
if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir, (Join-Path $outDir "web"), `
    (Join-Path $outDir "backend\services"), (Join-Path $outDir "backend\tools"), `
    (Join-Path $outDir "backend\accepted") | Out-Null

Copy-Item (Join-Path $spa "*") (Join-Path $outDir "web") -Recurse -Force
Copy-Item (Join-Path $repoRoot "services\character_companion") (Join-Path $outDir "backend\services\character_companion") -Recurse -Force
Copy-Item (Join-Path $repoRoot "services\character_core")      (Join-Path $outDir "backend\services\character_core") -Recurse -Force
Copy-Item (Join-Path $repoRoot "services\character_runtime")   (Join-Path $outDir "backend\services\character_runtime") -Recurse -Force
Copy-Item (Join-Path $repoRoot "services\character_lab")       (Join-Path $outDir "backend\services\character_lab") -Recurse -Force
Copy-Item (Join-Path $repoRoot "services\crp_authoring")       (Join-Path $outDir "backend\services\crp_authoring") -Recurse -Force
Copy-Item (Join-Path $repoRoot "tools\character_companion_server.py") (Join-Path $outDir "backend\tools\character_companion_server.py") -Force
Copy-Item (Join-Path $repoRoot "accepted\kira") (Join-Path $outDir "backend\accepted\kira") -Recurse -Force
Get-ChildItem $outDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# --- 3. release manifest (no secrets) ----------------------------------
$env:PYTHONPATH = $repoRoot
$buildId = (Get-ChildItem (Join-Path $spa "assets") -Filter "index-*.js" -ErrorAction SilentlyContinue |
            Select-Object -First 1).BaseName
py -c "import json,sys; from services.character_companion import build_release_manifest; m=build_release_manifest(acceptance_root=r'$repoRoot\accepted', frontend_build_id='$buildId'); open(r'$outDir\RELEASE_MANIFEST.json','w',encoding='utf-8').write(json.dumps(m,ensure_ascii=False,indent=2))"

@"
`$ErrorActionPreference='Stop'
`$here = Split-Path -Parent `$MyInvocation.MyCommand.Path
`$data = Join-Path `$env:LOCALAPPDATA 'KiraCompanion\data'
New-Item -ItemType Directory -Force -Path `$data | Out-Null
`$env:PYTHONPATH = Join-Path `$here 'backend'
`$pf = Join-Path `$env:TEMP ('kc_' + [Guid]::NewGuid().ToString('N') + '.txt')
`$p = Start-Process py -PassThru -WindowStyle Hidden -ArgumentList @((Join-Path `$here 'backend\tools\character_companion_server.py'), '--mode','release','--port','0','--port-file',`$pf,'--data-root',`$data,'--web-root',(Join-Path `$here 'web'))
for (`$i=0; `$i -lt 100 -and -not (Test-Path `$pf); `$i++) { Start-Sleep -Milliseconds 100 }
`$port = (Get-Content `$pf -Raw).Trim(); Start-Process "http://127.0.0.1:`$port/"
Write-Host "KIRA Companion RC1 -> http://127.0.0.1:`$port/  (data: `$data)"
while (-not `$p.HasExited) { Start-Sleep -Seconds 1 }
"@ | Set-Content -Path (Join-Path $outDir "START.ps1") -Encoding UTF8

Write-Host "Built: $outDir"
Get-ChildItem $outDir | Select-Object Name, Mode
