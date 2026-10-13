# Builds desktop/build/agent: a self-contained Python runtime plus the backend,
# shipped inside the installer as resources/agent so users need no Python.
#   python/   relocatable CPython (python-build-standalone, installed with uv)
#   backend/  the backend source (local_agent.py is the entry point)
# Requires uv on PATH (https://docs.astral.sh/uv/). Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File desktop/scripts/bundle-agent.ps1
$ErrorActionPreference = "Stop"

$desktop = Split-Path -Parent $PSScriptRoot
$backend = Join-Path (Split-Path -Parent $desktop) "backend"
$out = Join-Path $desktop "build\agent"
$pythonVersion = "3.12"

if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null

# 1. Relocatable CPython.
$staging = Join-Path $out "_python"
uv python install $pythonVersion --install-dir $staging
if ($LASTEXITCODE -ne 0) { throw "uv python install failed" }
$exe = Get-ChildItem $staging -Recurse -Filter python.exe | Select-Object -First 1
if (-not $exe) { throw "python.exe not found after uv python install" }
Move-Item $exe.Directory.FullName (Join-Path $out "python")
Remove-Item -Recurse -Force $staging
$python = Join-Path $out "python\python.exe"
Remove-Item (Join-Path $out "python\Lib\EXTERNALLY-MANAGED") -ErrorAction SilentlyContinue

# 2. Dependencies (core + Windows desktop control; no torch/OmniParser).
& $python -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw "ensurepip failed" }
& $python -m pip install --no-warn-script-location --disable-pip-version-check -r (Join-Path $backend "requirements-local.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# pywin32's core DLLs (pywintypes3XX.dll, pythoncom3XX.dll) must be loadable
# or xlwings silently drops its Excel engine. Put them beside python.exe so
# they load even if the pywin32.pth bootstrap is skipped.
$pywin32Dlls = Join-Path $out "python\Lib\site-packages\pywin32_system32"
if (-not (Test-Path $pywin32Dlls)) { throw "pywin32_system32 not found; pywin32 did not install" }
Copy-Item (Join-Path $pywin32Dlls "*.dll") (Join-Path $out "python") -Force

# 3. Backend source, without tests, runtime data or local secrets.
robocopy $backend (Join-Path $out "backend") /E /NFL /NDL /NJH /NJS `
    /XD __pycache__ tests scripts storage store .venv .venv-linux venv .pytest_cache (Join-Path $backend "knowledge\data") `
    /XF .env *.log *.pyc
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with $LASTEXITCODE" }
$global:LASTEXITCODE = 0

# 3b. Cua Driver (accessibility-based desktop control). Pinned and checked
#     against the SHA256SUMS published with that release.
$cuaVersion = "0.34.0"
$cuaZip = "cua-driver-rs-$cuaVersion-windows-x86_64-binary.zip"
$cuaSha256 = "bcc520e50861c7092cf775846fec76ae386d7dcd6b5b408608b0ea4423a8b888"
$cuaUrl = "https://github.com/trycua/cua/releases/download/cua-driver-rs-v$cuaVersion/$cuaZip"
$cuaTemp = Join-Path ([System.IO.Path]::GetTempPath()) "xelora-cua-$cuaVersion"
if (Test-Path $cuaTemp) { Remove-Item -Recurse -Force $cuaTemp }
New-Item -ItemType Directory -Force $cuaTemp | Out-Null
$cuaArchive = Join-Path $cuaTemp $cuaZip
Invoke-WebRequest -Uri $cuaUrl -OutFile $cuaArchive -UseBasicParsing
$actual = (Get-FileHash $cuaArchive -Algorithm SHA256).Hash.ToLower()
if ($actual -ne $cuaSha256) { throw "Cua Driver checksum mismatch: expected $cuaSha256, got $actual" }
Expand-Archive $cuaArchive -DestinationPath (Join-Path $cuaTemp "x") -Force
$cuaExe = Get-ChildItem (Join-Path $cuaTemp "x") -Recurse -Filter "cua-driver*.exe" | Select-Object -First 1
if (-not $cuaExe) { throw "cua-driver executable not found in $cuaZip" }
$cuaOut = Join-Path $out "cua"
New-Item -ItemType Directory -Force $cuaOut | Out-Null
Copy-Item (Join-Path $cuaExe.Directory.FullName "*") $cuaOut -Recurse -Force
if ($cuaExe.Name -ne "cua-driver.exe") {
    Move-Item (Join-Path $cuaOut $cuaExe.Name) (Join-Path $cuaOut "cua-driver.exe") -Force
}
$cuaVersionOutput = & (Join-Path $cuaOut "cua-driver.exe") --version
if ($LASTEXITCODE -ne 0) { throw "bundled cua-driver --version failed" }
Write-Host "Bundled Cua Driver: $cuaVersionOutput"
Remove-Item -Recurse -Force $cuaTemp

# 4. Smoke test, run the way Xelora Desktop runs it (python -I): the agent
#    imports cleanly, xlwings has its Excel engine (pywin32 loads), and
#    importing the backend writes nothing into the install directory, which
#    is read-only under Program Files.
$smoke = @"
import os, sys
sys.path.insert(0, r'$out\backend')
import local_agent
local_agent.configure_environment('https://example.invalid', 'smoke-test')
status = local_agent.excel_engine_status()
assert status == 'Excel automation ready', status
assert local_agent.bundled_cua_driver(), 'the Cua Driver is missing from the bundle'
assert os.environ.get('ENABLE_CUA_DRIVER') == 'true', 'the bundled Cua Driver was not enabled'
import pywintypes, pythoncom, win32api, win32com.client
import agent.core, knowledge.rag, memory._store, reporting.pdf_generator
from skills import loader
from skills.base import SKILL_REGISTRY
folders = {n for n in os.listdir(loader.LIBRARY_DIR) if os.path.isdir(os.path.join(loader.LIBRARY_DIR, n)) and not n.startswith(('_', '.'))}
assert folders <= set(SKILL_REGISTRY), 'skills failed to load: ' + ', '.join(sorted(folders - set(SKILL_REGISTRY)))
backend = os.path.normcase(os.path.abspath(r'$out\backend'))
for name, path in [('knowledge', knowledge.rag.DATA_DIR), ('reports', str(reporting.pdf_generator.REPORTS_DIR))]:
    assert not os.path.normcase(os.path.abspath(path)).startswith(backend), name + ' data would be written into the install directory: ' + path
assert not os.path.exists(os.path.join(backend, 'knowledge', 'data')), 'importing the agent created knowledge/data'
print('local agent bundle OK')
"@
& $python -I -c $smoke
if ($LASTEXITCODE -ne 0) { throw "bundled agent smoke test failed" }
