$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:HWM_CAPTURE_DIR = Join-Path $root "data\captured-live"
$env:HWM_SEARCH_MS = if ($env:HWM_SEARCH_MS) { $env:HWM_SEARCH_MS } else { "5000" }
$env:HWM_SEARCH_SIMS = if ($env:HWM_SEARCH_SIMS) { $env:HWM_SEARCH_SIMS } else { "100000" }
New-Item -ItemType Directory -Force -Path $env:HWM_CAPTURE_DIR | Out-Null
$release = Join-Path $root "build\release\solver-daemon.exe"
$debug = Join-Path $root "build\debug\solver-daemon.exe"
$exe = if (Test-Path $release) { $release } elseif (Test-Path $debug) { $debug } else { $null }
if (-not $exe) { throw "solver-daemon.exe not found. Run .\scripts\bootstrap_windows.ps1 first." }
Write-Host "Daemon: $exe"
Write-Host "Raw battle bodies: $env:HWM_CAPTURE_DIR"
Write-Host "Planner budget: $env:HWM_SEARCH_MS ms / max $env:HWM_SEARCH_SIMS simulations"
& $exe
