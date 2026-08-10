param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Core', 'Full')]
    [string]$Suite
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Assert-NativeSuccess([string]$Label) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

function Ensure-Path([string]$Directory) {
    if ((Test-Path $Directory) -and (($env:Path -split ';') -notcontains $Directory)) {
        $env:Path = "$Directory;$env:Path"
    }
}

function Bootstrap-CIEnvironment {
    Write-Host '==> Bootstrap Windows CI environment'

    $toolRoot = if ($env:RUNNER_TOOL_CACHE) {
        $env:RUNNER_TOOL_CACHE
    } else {
        Join-Path $env:LOCALAPPDATA 'hwm-runner-tools'
    }

    $uvVersion = '0.12.2'
    $uvDir = Join-Path $toolRoot "uv\$uvVersion"
    $uvExe = Join-Path $uvDir 'uv.exe'
    $pythonDir = Join-Path $toolRoot 'uv-python'
    $uvCache = Join-Path $toolRoot 'uv-cache'

    New-Item -ItemType Directory -Force $uvDir, $pythonDir, $uvCache | Out-Null

    if (-not (Test-Path $uvExe)) {
        Write-Host "Installing uv $uvVersion into service-owned tool cache..."
        $env:UV_UNMANAGED_INSTALL = $uvDir
        $installer = Invoke-RestMethod "https://astral.sh/uv/$uvVersion/install.ps1"
        Invoke-Expression $installer
    }
    if (-not (Test-Path $uvExe)) {
        throw "uv.exe not found after installation: $uvExe"
    }

    $env:UV_PYTHON_INSTALL_DIR = $pythonDir
    $env:UV_CACHE_DIR = $uvCache
    $env:UV_MANAGED_PYTHON = '1'

    & $uvExe --version
    Assert-NativeSuccess 'uv version check'

    & $uvExe python install 3.13 --install-dir $pythonDir
    Assert-NativeSuccess 'uv Python 3.13 install'

    if (Test-Path '.venv') {
        Remove-Item -Recurse -Force '.venv'
    }
    & $uvExe venv --python 3.13 --managed-python .venv
    Assert-NativeSuccess 'uv venv'

    $venvScripts = (Resolve-Path '.venv\Scripts').Path
    $env:VIRTUAL_ENV = (Resolve-Path '.venv').Path
    Ensure-Path $venvScripts
    Ensure-Path $uvDir
    Ensure-Path 'C:\Program Files\nodejs'
    Ensure-Path 'C:\Program Files\CMake\bin'

    $script:Python = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
    if (-not (Test-Path $script:Python)) {
        throw "venv Python not found: $script:Python"
    }
    $script:Npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $script:Npm) {
        throw 'npm.cmd not found.'
    }

    & $script:Python --version
    Assert-NativeSuccess 'Python version check'

    & $uvExe pip install --python $script:Python -e '.[dev]'
    Assert-NativeSuccess 'Python dependency install'

    if (-not (Get-Command cmake.exe -ErrorAction SilentlyContinue)) {
        throw 'cmake.exe not found. Install CMake system-wide.'
    }
    if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
        throw 'node.exe not found. Install Node.js 22+ system-wide.'
    }

    $nodeVersion = (& node.exe --version).Trim()
    if ($nodeVersion -notmatch '^v(\d+)\.') {
        throw "Cannot parse Node version: $nodeVersion"
    }
    if ([int]$Matches[1] -lt 22) {
        throw "Node 22+ required; found $nodeVersion"
    }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $vswhere)) {
        throw 'vswhere.exe not found. Install Visual Studio 2022 Build Tools.'
    }
    $script:VsInstall = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
    if (-not $script:VsInstall) {
        throw 'Visual Studio C++ x64 toolchain not found.'
    }

    Write-Host "Python: $(& $script:Python --version)"
    Write-Host "Node:   $nodeVersion"
    Write-Host "npm:    $(& $script:Npm --version)"
    Write-Host "CMake:  $((& cmake.exe --version | Select-Object -First 1))"
    Write-Host "MSVC:   $script:VsInstall"
}

function Build-Msvc([string]$Config, [string]$BuildDir) {
    Write-Host "==> Configure C++ $Config"
    cmake.exe -S . -B $BuildDir -G 'Visual Studio 17 2022' -A x64 -DHWM_BUILD_TESTS=ON
    Assert-NativeSuccess "CMake $Config configure"

    Write-Host "==> Build C++ $Config"
    cmake.exe --build $BuildDir --config $Config --parallel 2
    Assert-NativeSuccess "C++ $Config build"
}

function Run-CoreSuite {
    $build = 'build/ci-debug'
    Build-Msvc 'Debug' $build

    Write-Host '==> C++ main-front Debug tests'
    ctest.exe --test-dir $build -C Debug --output-on-failure -E '^hwm-tests$'
    Assert-NativeSuccess 'C++ main-front Debug tests'

    $plannerEval = Join-Path $build 'Debug\planner-eval.exe'
    $daemon = Join-Path $build 'Debug\solver-daemon.exe'

    Write-Host '==> Held-out 120-state planner validity'
    & $script:Python scripts/test_planner_replay_gate.py $plannerEval hwm_battles 120 1 120
    Assert-NativeSuccess 'planner replay gate'

    Write-Host '==> Pairing/auth integration'
    & $script:Python scripts/test_local_api_auth.py $daemon
    Assert-NativeSuccess 'pairing/auth integration'

    Write-Host '==> Stale cancellation integration'
    & $script:Python scripts/test_stale_cancellation.py $daemon
    Assert-NativeSuccess 'stale cancellation integration'

    Write-Host '==> Live recommendation binding contract'
    & $script:Python scripts/test_live_binding.py $daemon
    Assert-NativeSuccess 'live binding integration'

    Write-Host '==> WebSocket revision streaming'
    & $script:Python scripts/test_websocket_stream.py $daemon
    Assert-NativeSuccess 'WebSocket integration'

    Write-Host '==> Python tests'
    & $script:Python -m pytest python/tests -q
    Assert-NativeSuccess 'Python tests'

    Write-Host '==> Extension install/typecheck/build'
    Push-Location extension
    try {
        & $script:Npm install --no-audit --no-fund
        Assert-NativeSuccess 'extension npm install'
        & $script:Npm run typecheck
        Assert-NativeSuccess 'extension typecheck'
        & $script:Npm run build
        Assert-NativeSuccess 'extension build'
    }
    finally {
        Pop-Location
    }
}

function Run-FullSuite {
    $build = 'build/ci-release'
    Build-Msvc 'Release' $build

    Write-Host '==> C++ main-front Release tests'
    ctest.exe --test-dir $build -C Release --output-on-failure -E '^hwm-tests$'
    Assert-NativeSuccess 'C++ main-front Release tests'

    Write-Host '==> Release planner benchmark'
    & (Join-Path $build 'Release\planner-demo.exe') 5000
    Assert-NativeSuccess 'planner-demo 5000'

    New-Item -ItemType Directory -Force 'build/validation' | Out-Null

    Write-Host '==> M11 full-corpus multistep residual gate'
    & $script:Python -m hwm_solver.evaluation.dynamics_multistep hwm_battles --out build/validation/dynamics-multistep-damage.json
    Assert-NativeSuccess 'M11 multistep gate'

    Write-Host '==> M11 full-corpus uncertainty calibration'
    & $script:Python -m hwm_solver.evaluation.dynamics_uncertainty hwm_battles --out build/validation/dynamics-uncertainty-calibration.json
    Assert-NativeSuccess 'M11 uncertainty calibration'

    Write-Host '==> M11 full-corpus selector gate'
    & $script:Python -m hwm_solver.evaluation.dynamics_selector hwm_battles --out build/validation/dynamics-selector-gate.json
    Assert-NativeSuccess 'M11 selector gate'

    Write-Host '==> M11 stochastic survival-distribution gate'
    & $script:Python -m hwm_solver.evaluation.dynamics_survival_gate hwm_battles --out build/validation/m11_dynamics_survival_gate.json
    Assert-NativeSuccess 'M11 survival gate'

    Write-Host '==> Verify committed M11 evidence'
    & $script:Python scripts/verify_m11_evidence.py
    Assert-NativeSuccess 'M11 evidence verification'

    Write-Host '==> M11 positive-residual temperature calibration'
    & $script:Python -m hwm_solver.evaluation.dynamics_temperature_gate hwm_battles --out build/validation/m11_dynamics_temperature_gate.json
    Assert-NativeSuccess 'M11 temperature gate'
}

Bootstrap-CIEnvironment

switch ($Suite) {
    'Core' { Run-CoreSuite }
    'Full' { Run-FullSuite }
}

Write-Host "HWM WINDOWS CI ${Suite}: PASS"
