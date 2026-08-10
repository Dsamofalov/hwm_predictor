param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Core', 'Full')]
    [string]$Suite
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$target = Join-Path $PSScriptRoot 'ci_windows.ps1'
if (-not (Test-Path $target)) {
    throw "Windows CI script not found: $target"
}

$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $target,
    [ref]$tokens,
    [ref]$parseErrors
) | Out-Null

if ($parseErrors.Count -gt 0) {
    Write-Host '=== POWERSHELL SYNTAX ERRORS ==='
    foreach ($parseError in $parseErrors) {
        $line = $parseError.Extent.StartLineNumber
        $column = $parseError.Extent.StartColumnNumber
        Write-Host " - ${line}:${column} $($parseError.Message)"
    }
    throw "PowerShell syntax preflight failed with $($parseErrors.Count) error(s)."
}

Write-Host "PowerShell syntax preflight: PASS ($target)"
& $target -Suite $Suite
