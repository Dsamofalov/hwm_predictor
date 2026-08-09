$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/6] C++ Debug"
cmake --preset debug
cmake --build --preset debug
ctest --preset debug --output-on-failure

Write-Host "[2/6] C++ Release"
cmake --preset release
cmake --build --preset release
ctest --preset release --output-on-failure

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }
$env:PYTHONPATH = Join-Path $root "python"

Write-Host "[3/6] Python"
& $python -m pytest -q

Write-Host "[4/6] Corpus manifest"
& $python -m hwm_solver.cli manifest data\input\battle_urls.txt data\manifests\battles.jsonl

Write-Host "[5/6] Extension"
Push-Location extension
npx tsc --noEmit
npm run build
Pop-Location

Write-Host "[6/6] Planner benchmark"
& .\build\release\planner-demo.exe 5000
Write-Host "ALL CHECKS PASSED"
