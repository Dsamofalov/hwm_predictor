[CmdletBinding()]
param(
    [switch]$InstallDevDependencies,
    [switch]$RequireNode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Add-HwmPath([string]$Directory) {
    if (-not (Test-Path $Directory)) { return }
    if (($env:Path -split ';') -notcontains $Directory) {
        $env:Path = "$Directory;$env:Path"
    }
    if ($env:GITHUB_PATH) {
        [IO.File]::AppendAllText(
            $env:GITHUB_PATH,
            "$Directory`n",
            [Text.UTF8Encoding]::new($false)
        )
    }
}

function Export-HwmEnv([string]$Name, [string]$Value) {
    Set-Item -Path "Env:$Name" -Value $Value
    if ($env:GITHUB_ENV) {
        [IO.File]::AppendAllText(
            $env:GITHUB_ENV,
            "$Name=$Value`n",
            [Text.UTF8Encoding]::new($false)
        )
    }
}

function Require-HwmCommand([string]$Name, [string]$Hint) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) { throw "$Name not found. $Hint" }
    return $command
}

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'HWM CI requires 64-bit Windows.'
}

$cmakeDir = 'C:\Program Files\CMake\bin'
if (Test-Path $cmakeDir) { Add-HwmPath $cmakeDir }
$cmake = Require-HwmCommand 'cmake.exe' 'Install CMake x64.'
Write-Host "CMake: $((& $cmake.Source --version | Select-Object -First 1))"

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path $vswhere)) {
    throw 'vswhere.exe not found. Install Visual Studio 2022 Build Tools with Desktop development with C++.'
}
$vsInstall = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
if (-not $vsInstall) {
    throw 'Visual Studio 2022 C++ x64 toolchain not found.'
}
Export-HwmEnv 'HWM_VS_INSTALL' $vsInstall.Trim()
Write-Host "Visual Studio: $($vsInstall.Trim())"

if ($RequireNode) {
    $nodeDir = 'C:\Program Files\nodejs'
    if (Test-Path $nodeDir) { Add-HwmPath $nodeDir }
    $node = Require-HwmCommand 'node.exe' 'Install Node.js 22 or newer.'
    $npm = Require-HwmCommand 'npm.cmd' 'Install npm with Node.js.'
    $nodeVersion = (& $node.Source --version).Trim()
    if ($nodeVersion -notmatch '^v(\d+)\.') {
        throw "Cannot parse Node version: $nodeVersion"
    }
    if ([int]$Matches[1] -lt 22) {
        throw "Node.js 22+ required; found $nodeVersion"
    }
    Write-Host "Node: $nodeVersion"
    Write-Host "npm: $((& $npm.Source --version).Trim())"
}

$uvVersion = if ($env:HWM_UV_VERSION) { $env:HWM_UV_VERSION } else { '0.12.2' }
$toolRoot = if ($env:RUNNER_TOOL_CACHE) {
    $env:RUNNER_TOOL_CACHE
} else {
    Join-Path $root '.tools'
}
$uvDir = Join-Path $toolRoot "uv\$uvVersion"
$uvExe = Join-Path $uvDir 'uv.exe'
$pythonDir = Join-Path $toolRoot 'uv-python'
$uvCache = Join-Path $toolRoot 'uv-cache'

New-Item -ItemType Directory -Force $uvDir, $pythonDir, $uvCache | Out-Null

if (-not (Test-Path $uvExe)) {
    Write-Host "Installing portable uv $uvVersion into $uvDir"
    $env:UV_UNMANAGED_INSTALL = $uvDir
    $installer = Invoke-RestMethod "https://astral.sh/uv/$uvVersion/install.ps1"
    Invoke-Expression $installer
}
if (-not (Test-Path $uvExe)) {
    throw "uv.exe not found after installation: $uvExe"
}

Add-HwmPath $uvDir
Export-HwmEnv 'UV_PYTHON_INSTALL_DIR' $pythonDir
Export-HwmEnv 'UV_CACHE_DIR' $uvCache
Export-HwmEnv 'UV_MANAGED_PYTHON' '1'

& $uvExe --version
& $uvExe python install 3.13 --install-dir $pythonDir
if ($LASTEXITCODE -ne 0) { throw 'uv python install 3.13 failed.' }

$venvPath = Join-Path $root '.venv'
if ($env:GITHUB_ACTIONS -eq 'true' -and (Test-Path $venvPath)) {
    Remove-Item -Recurse -Force $venvPath
}

& $uvExe venv --python 3.13 --managed-python $venvPath
if ($LASTEXITCODE -ne 0) { throw 'uv venv failed.' }

$venvScripts = Join-Path $venvPath 'Scripts'
$venvPython = Join-Path $venvScripts 'python.exe'
if (-not (Test-Path $venvPython)) {
    throw "venv Python not found: $venvPython"
}
Add-HwmPath $venvScripts
Export-HwmEnv 'VIRTUAL_ENV' $venvPath

& $venvPython --version

if ($InstallDevDependencies) {
    & $uvExe pip install --python $venvPython -e '.[dev]'
    if ($LASTEXITCODE -ne 0) { throw 'Python dev dependency installation failed.' }
}

Write-Host 'Windows CI bootstrap: OK'
