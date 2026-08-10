$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '==> HWM Windows Core suite'
& .\scripts\ci_entrypoint_windows.ps1 -Suite Core

Write-Host '==> HWM Windows Full suite'
& .\scripts\ci_entrypoint_windows.ps1 -Suite Full

Write-Host 'HWM WINDOWS LOCAL VALIDATION: PASS'
