$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$exe = Join-Path $root "build\release\solver-daemon.exe"
if (-not (Test-Path $exe)) { $exe = Join-Path $root "build\debug\solver-daemon.exe" }
if (-not (Test-Path $exe)) { throw "Build solver-daemon first." }
$oldDebug=$env:HWM_ENABLE_DEBUG; $oldMs=$env:HWM_SEARCH_MS; $oldSims=$env:HWM_SEARCH_SIMS
$env:HWM_ENABLE_DEBUG="1"; $env:HWM_SEARCH_MS="1000"; $env:HWM_SEARCH_SIMS="5000"
$p = Start-Process -FilePath $exe -WorkingDirectory $root -PassThru -NoNewWindow
try {
    Start-Sleep -Milliseconds 500
    Write-Host "HEALTH"
    Invoke-RestMethod http://127.0.0.1:38471/health | ConvertTo-Json -Depth 10
    Write-Host "LOAD SYNTHETIC CANONICAL STATE"
    Invoke-RestMethod -Method Post http://127.0.0.1:38471/debug/demo-state | ConvertTo-Json -Depth 10
    Write-Host "RECOMMEND"
    Invoke-RestMethod -Method Post http://127.0.0.1:38471/recommend | ConvertTo-Json -Depth 10
} finally {
    if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
    $env:HWM_ENABLE_DEBUG=$oldDebug; $env:HWM_SEARCH_MS=$oldMs; $env:HWM_SEARCH_SIMS=$oldSims
}
