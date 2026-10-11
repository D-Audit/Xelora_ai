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

# 3. Backend source, without tests, runtime data or local secrets.
robocopy $backend (Join-Path $out "backend") /E /NFL /NDL /NJH /NJS `
    /XD __pycache__ tests scripts storage store .venv .venv-linux venv .pytest_cache `
    /XF .env *.log *.pyc
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with $LASTEXITCODE" }
$global:LASTEXITCODE = 0

# 4. Smoke test: the agent imports cleanly with the bundled runtime.
& $python -I -c "import sys; sys.path.insert(0, r'$out\backend'); import local_agent, agent.core; print('local agent bundle OK')"
if ($LASTEXITCODE -ne 0) { throw "bundled agent failed to import" }
