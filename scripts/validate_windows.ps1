$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '==> HWM Windows Core suite'
& .\scripts\ci_windows.ps1 -Suite Core
if ($LASTEXITCODE -ne 0) { throw "Core validation failed with exit code $LASTEXITCODE." }

Write-Host '==> HWM Windows Full suite'
& .\scripts\ci_windows.ps1 -Suite Full
if ($LASTEXITCODE -ne 0) { throw "Full validation failed with exit code $LASTEXITCODE." }

Write-Host 'HWM WINDOWS LOCAL VALIDATION: PASS'
