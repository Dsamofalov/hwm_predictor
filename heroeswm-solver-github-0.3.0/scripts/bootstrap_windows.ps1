$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Require-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found. $Hint"
    }
}

Require-Command "cmake" "Install CMake 3.25+."
Require-Command "ninja" "Install Ninja and add it to PATH."
Require-Command "node" "Install Node.js 22 LTS."
Require-Command "npm" "Install npm together with Node.js."
if (-not (Get-Command "cl.exe" -ErrorAction SilentlyContinue) -and -not (Get-Command "clang++.exe" -ErrorAction SilentlyContinue) -and -not (Get-Command "g++.exe" -ErrorAction SilentlyContinue)) {
    throw "No C++ compiler found. Recommended: open x64 Native Tools/Developer PowerShell for VS 2022, then run 'code .' from it."
}

$pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
if ($pyLauncher) {
    $created = $false
    foreach ($ver in @("3.12", "3.13")) {
        & py "-$ver" -c "import sys; raise SystemExit(0 if (3,12) <= sys.version_info[:2] < (3,14) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            & py "-$ver" -m venv .venv
            $created = $true
            break
        }
    }
    if (-not $created) { throw "Python 3.12 or 3.13 not found via py launcher." }
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    & python -c "import sys; raise SystemExit(0 if (3,12) <= sys.version_info[:2] < (3,14) else 1)"
    if ($LASTEXITCODE -ne 0) { throw "python must be Python 3.12 or 3.13." }
    & python -m venv .venv
} else {
    throw "Python 3.12/3.13 not found."
}

$python = Join-Path $root ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -e ".[dev]"

cmake --preset debug
cmake --build --preset debug
ctest --preset debug --output-on-failure

Push-Location extension
npm install
npm run typecheck
npm run build
Pop-Location

$env:PYTHONPATH = Join-Path $root "python"
& $python -m hwm_solver.cli manifest data\input\battle_urls.txt data\manifests\battles.jsonl
Write-Host "Bootstrap complete. Use VS Code task 'Validate all' or .\scripts\start_daemon_windows.ps1"
