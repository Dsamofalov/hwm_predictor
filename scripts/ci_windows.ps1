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

function Invoke-NativeGate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][object[]]$Arguments,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[string]]$Failures
    )

    Write-Host "==> $Name"
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Name exited with code $LASTEXITCODE."
        }
        Write-Host "[PASS] $Name"
    }
    catch {
        $message = $_.Exception.Message
        [void]$Failures.Add("$Name :: $message")
        Write-Warning "[FAIL] $Name :: $message"
    }
}

function Assert-GatesPassed {
    param(
        [Parameter(Mandatory = $true)][string]$SuiteName,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.Generic.List[string]]$Failures
    )

    if ($Failures.Count -eq 0) {
        return
    }

    Write-Host "=== $SuiteName FAILURE SUMMARY ==="
    foreach ($failure in $Failures) {
        Write-Host " - $failure"
    }
    throw "$SuiteName failed $($Failures.Count) independent gate(s)."
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

    $failures = New-Object 'System.Collections.Generic.List[string]'
    $plannerEval = Join-Path $build 'Debug\planner-eval.exe'
    $daemon = Join-Path $build 'Debug\solver-daemon.exe'

    Invoke-NativeGate -Name 'C++ main-front Debug tests' -Command 'ctest.exe' -Arguments @(
        '--test-dir', $build, '-C', 'Debug', '--output-on-failure', '-E', '^hwm-tests$'
    ) -Failures $failures

    Invoke-NativeGate -Name 'Held-out 120-state planner validity' -Command $script:Python -Arguments @(
        'scripts/test_planner_replay_gate.py', $plannerEval, 'hwm_battles', '120', '1', '120'
    ) -Failures $failures

    Invoke-NativeGate -Name 'Pairing/auth integration' -Command $script:Python -Arguments @(
        'scripts/test_local_api_auth.py', $daemon
    ) -Failures $failures

    Invoke-NativeGate -Name 'Stale cancellation integration' -Command $script:Python -Arguments @(
        'scripts/test_stale_cancellation.py', $daemon
    ) -Failures $failures

    Invoke-NativeGate -Name 'Live recommendation binding contract' -Command $script:Python -Arguments @(
        'scripts/test_live_binding.py', $daemon
    ) -Failures $failures

    Invoke-NativeGate -Name 'WebSocket revision streaming' -Command $script:Python -Arguments @(
        'scripts/test_websocket_stream.py', $daemon
    ) -Failures $failures

    Invoke-NativeGate -Name 'Python tests' -Command $script:Python -Arguments @(
        '-m', 'pytest', 'python/tests', '-q'
    ) -Failures $failures

    Push-Location extension
    try {
        Invoke-NativeGate -Name 'Extension dependency install' -Command $script:Npm -Arguments @(
            'install', '--no-audit', '--no-fund'
        ) -Failures $failures
        Invoke-NativeGate -Name 'TypeScript typecheck' -Command $script:Npm -Arguments @(
            'run', 'typecheck'
        ) -Failures $failures
        Invoke-NativeGate -Name 'Extension build' -Command $script:Npm -Arguments @(
            'run', 'build'
        ) -Failures $failures
    }
    finally {
        Pop-Location
    }

    Assert-GatesPassed -SuiteName 'Core' -Failures $failures
}

function Run-FullSuite {
    $build = 'build/ci-release'
    Build-Msvc 'Release' $build

    $failures = New-Object 'System.Collections.Generic.List[string]'
    New-Item -ItemType Directory -Force 'build/validation' | Out-Null

    Invoke-NativeGate -Name 'C++ main-front Release tests' -Command 'ctest.exe' -Arguments @(
        '--test-dir', $build, '-C', 'Release', '--output-on-failure', '-E', '^hwm-tests$'
    ) -Failures $failures

    Invoke-NativeGate -Name 'Full-corpus structural-invalid budget' -Command $script:Python -Arguments @(
        'scripts/test_corpus_structural_budget.py', (Join-Path $build 'Release\corpus-check.exe'), 'hwm_battles', '18'
    ) -Failures $failures

    Invoke-NativeGate -Name 'Release planner benchmark' -Command (Join-Path $build 'Release\planner-demo.exe') -Arguments @(
        '5000'
    ) -Failures $failures

    Invoke-NativeGate -Name 'M11 full-corpus multistep residual gate' -Command $script:Python -Arguments @(
        '-m', 'hwm_solver.evaluation.dynamics_multistep', 'hwm_battles', '--out', 'build/validation/dynamics-multistep-damage.json'
    ) -Failures $failures

    Invoke-NativeGate -Name 'M11 full-corpus uncertainty calibration' -Command $script:Python -Arguments @(
        '-m', 'hwm_solver.evaluation.dynamics_uncertainty', 'hwm_battles', '--out', 'build/validation/dynamics-uncertainty-calibration.json'
    ) -Failures $failures

    Invoke-NativeGate -Name 'M11 full-corpus selector gate' -Command $script:Python -Arguments @(
        '-m', 'hwm_solver.evaluation.dynamics_selector', 'hwm_battles', '--out', 'build/validation/dynamics-selector-gate.json'
    ) -Failures $failures

    Invoke-NativeGate -Name 'M11 stochastic survival-distribution gate' -Command $script:Python -Arguments @(
        '-m', 'hwm_solver.evaluation.dynamics_survival_gate', 'hwm_battles', '--out', 'build/validation/m11_dynamics_survival_gate.json'
    ) -Failures $failures

    Invoke-NativeGate -Name 'Verify committed M11 evidence' -Command $script:Python -Arguments @(
        'scripts/verify_m11_evidence.py'
    ) -Failures $failures

    Invoke-NativeGate -Name 'M11 positive-residual temperature calibration' -Command $script:Python -Arguments @(
        '-m', 'hwm_solver.evaluation.dynamics_temperature_gate', 'hwm_battles', '--out', 'build/validation/m11_dynamics_temperature_gate.json'
    ) -Failures $failures

    Assert-GatesPassed -SuiteName 'Full' -Failures $failures
}

Bootstrap-CIEnvironment

switch ($Suite) {
    'Core' { Run-CoreSuite }
    'Full' { Run-FullSuite }
}

Write-Host "HWM WINDOWS CI ${Suite}: PASS"
