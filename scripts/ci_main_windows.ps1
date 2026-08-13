param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        'CppBuildInventory',
        'CppCase',
        'PythonInventory',
        'PythonCase',
        'CorePlanner',
        'CoreRuntimeCase',
        'CoreExtension',
        'FullStructuralBudget',
        'FullPlannerBenchmark',
        'M11Evaluate',
        'M11Verify',
        'M11Temperature'
    )]
    [string]$Mode,
    [ValidateSet('Debug', 'Release')]
    [string]$Config = 'Debug',
    [string]$CaseName = '',
    [string]$CaseExe = '',
    [string]$TestNode = '',
    [string]$GateName = ''
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

function Resolve-CMakeGenerator {
    Ensure-Path 'C:\Program Files\CMake\bin'
    if (-not (Get-Command cmake.exe -ErrorAction SilentlyContinue)) {
        throw 'cmake.exe not found on the hosted Windows runner.'
    }
    $help = (& cmake.exe --help | Out-String)
    if ($help -match 'Visual Studio 17 2022') { return 'Visual Studio 17 2022' }
    throw 'Visual Studio 17 2022 CMake generator not found.'
}

function Bootstrap-PythonEnvironment {
    Write-Host '==> Bootstrap main-front Python environment'
    $toolRoot = if ($env:RUNNER_TOOL_CACHE) { $env:RUNNER_TOOL_CACHE } else { Join-Path $env:LOCALAPPDATA 'hwm-runner-tools' }
    $uvVersion = '0.12.2'
    $uvDir = Join-Path $toolRoot "uv\$uvVersion"
    $uvExe = Join-Path $uvDir 'uv.exe'
    $pythonDir = Join-Path $toolRoot 'uv-python'
    $uvCache = Join-Path $toolRoot 'uv-cache'
    New-Item -ItemType Directory -Force $uvDir, $pythonDir, $uvCache | Out-Null

    if (-not (Test-Path $uvExe)) {
        $env:UV_UNMANAGED_INSTALL = $uvDir
        $installer = Invoke-RestMethod "https://astral.sh/uv/$uvVersion/install.ps1"
        Invoke-Expression $installer
    }
    if (-not (Test-Path $uvExe)) { throw "uv.exe not found after installation: $uvExe" }

    $env:UV_PYTHON_INSTALL_DIR = $pythonDir
    $env:UV_CACHE_DIR = $uvCache
    $env:UV_MANAGED_PYTHON = '1'
    & $uvExe python install 3.13 --install-dir $pythonDir
    Assert-NativeSuccess 'uv Python 3.13 install'

    if (Test-Path '.venv') { Remove-Item -Recurse -Force '.venv' }
    & $uvExe venv --python 3.13 --managed-python .venv
    Assert-NativeSuccess 'uv venv'
    $env:VIRTUAL_ENV = (Resolve-Path '.venv').Path
    $venvScripts = Join-Path $env:VIRTUAL_ENV 'Scripts'
    Ensure-Path $venvScripts
    Ensure-Path $uvDir
    $script:Python = Join-Path $venvScripts 'python.exe'
    if (-not (Test-Path $script:Python)) { throw "venv Python not found: $script:Python" }

    & $uvExe pip install --python $script:Python -e '.[dev]'
    Assert-NativeSuccess 'Python dependency install'
}

function Write-GitHubJsonOutput([string]$Name, [object[]]$Values) {
    $items = @($Values)
    if ($items.Count -eq 0) { throw "$Name inventory is empty." }
    $canonical = @($items | ForEach-Object {
        if ($_ -is [string]) { $_ } else { ConvertTo-Json $_ -Compress -Depth 8 }
    })
    if (@($canonical | Sort-Object -Unique).Count -ne $canonical.Count) {
        throw "$Name inventory contains duplicates."
    }
    $json = ConvertTo-Json -InputObject $items -Compress -Depth 8
    Write-Host "$Name inventory count: $($items.Count)"
    if (-not $env:GITHUB_OUTPUT) {
        Write-Host $json
        return
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($env:GITHUB_OUTPUT, "$Name=$json`n", $utf8NoBom)
}

function Get-BuildDirectory([string]$BuildConfig) {
    if ($BuildConfig -eq 'Debug') { return 'build/main-ci-debug' }
    return 'build/main-ci-release'
}

function Build-CppAndFreezeInventory([string]$BuildConfig) {
    $generator = Resolve-CMakeGenerator
    $build = Get-BuildDirectory $BuildConfig
    Write-Host "==> Configure main-front C++ $BuildConfig ($generator / x64)"
    cmake.exe -S . -B $build -G $generator -A x64 -DHWM_BUILD_TESTS=ON
    Assert-NativeSuccess "CMake $BuildConfig configure"

    Write-Host "==> Build main-front C++ $BuildConfig"
    cmake.exe --build $build --config $BuildConfig --parallel 2
    Assert-NativeSuccess "C++ $BuildConfig build"

    $ctestJsonText = (& ctest.exe --test-dir $build -C $BuildConfig -N --show-only=json-v1 | Out-String).Trim()
    Assert-NativeSuccess "CTest $BuildConfig inventory"
    if (-not $ctestJsonText) { throw "CTest $BuildConfig inventory emitted no JSON." }
    $ctestJson = ConvertFrom-Json -InputObject $ctestJsonText

    $cases = New-Object 'System.Collections.Generic.List[object]'
    foreach ($test in @($ctestJson.tests)) {
        $name = [string]$test.name
        if ($name -eq 'hwm-tests') { continue }
        if (-not $name) { throw 'CTest inventory contains an unnamed test.' }
        $command = @($test.command)
        if ($command.Count -lt 1) { throw "CTest test has no command: $name" }
        if ($command.Count -ne 1) {
            throw "CTest test has unsupported command arguments; atomic runner must preserve them explicitly: $name"
        }
        $exe = [System.IO.Path]::GetFileName([string]$command[0])
        if (-not $exe.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "CTest test is not backed by an executable: $name -> $exe"
        }
        [void]$cases.Add([pscustomobject]@{ name = $name; exe = $exe })
    }
    $sorted = @($cases | Sort-Object name)
    Write-GitHubJsonOutput -Name 'cases' -Values $sorted

    $sourceDir = Join-Path $build $BuildConfig
    if (-not (Test-Path $sourceDir -PathType Container)) {
        throw "C++ output directory not found: $sourceDir"
    }
    $executables = @(Get-ChildItem $sourceDir -Filter '*.exe' -File)
    if ($executables.Count -eq 0) { throw "No $BuildConfig executables were built." }
    foreach ($case in $sorted) {
        if (-not (Test-Path (Join-Path $sourceDir $case.exe) -PathType Leaf)) {
            throw "Frozen CTest case executable missing from build output: $($case.name) -> $($case.exe)"
        }
    }
}

function Resolve-BuildExe([string]$BuildConfig, [string]$ExeName) {
    if (-not $ExeName) { throw 'Executable name is required.' }
    if ([System.IO.Path]::GetFileName($ExeName) -ne $ExeName) {
        throw "Executable name must be a basename: $ExeName"
    }
    $build = Get-BuildDirectory $BuildConfig
    $exe = Join-Path (Join-Path $build $BuildConfig) $ExeName
    if (-not (Test-Path $exe -PathType Leaf)) {
        throw "Downloaded $BuildConfig executable not found: $exe"
    }
    return (Resolve-Path $exe).Path
}

function Invoke-CppCase([string]$BuildConfig, [string]$Name, [string]$ExeName) {
    if (-not $Name) { throw 'CaseName is required for CppCase.' }
    $exe = Resolve-BuildExe $BuildConfig $ExeName
    $build = Get-BuildDirectory $BuildConfig
    Write-Host "==> C++ $BuildConfig case: $Name ($ExeName)"
    Push-Location $build
    try {
        & $exe
        Assert-NativeSuccess "C++ $BuildConfig case $Name"
    }
    finally {
        Pop-Location
    }
}

function Freeze-PythonInventory {
    Bootstrap-PythonEnvironment
    Write-Host '==> Freeze exact main-front pytest node inventory'
    $collected = @(& $script:Python -m pytest --collect-only -q python/tests 2>&1)
    Assert-NativeSuccess 'Main-front pytest collection'
    $nodes = @(
        $collected |
            ForEach-Object { "$_".Trim() } |
            Where-Object { $_ -match '^python[\\/]tests[\\/].+::.+$' } |
            Sort-Object -Unique
    )
    if ($nodes.Count -eq 0) {
        Write-Host ($collected -join [Environment]::NewLine)
        throw 'Pytest collection produced no main-front test node IDs.'
    }
    Write-GitHubJsonOutput -Name 'cases' -Values $nodes
}

function Invoke-PythonCase([string]$Node) {
    if (-not $Node) { throw 'TestNode is required for PythonCase.' }
    Bootstrap-PythonEnvironment
    & $script:Python -m pytest -q --durations=5 $Node
    Assert-NativeSuccess "Main-front Python case $Node"
}

function Invoke-CorePlanner {
    Bootstrap-PythonEnvironment
    $planner = Resolve-BuildExe 'Debug' 'planner-eval.exe'
    & $script:Python scripts/test_planner_replay_gate.py $planner hwm_battles 120 1 120
    Assert-NativeSuccess 'Held-out 120-state planner validity'
}

function Invoke-CoreRuntimeCase([string]$Name) {
    Bootstrap-PythonEnvironment
    $daemon = Resolve-BuildExe 'Debug' 'solver-daemon.exe'
    $scripts = @{
        'pairing-auth' = 'scripts/test_local_api_auth.py'
        'stale-cancellation' = 'scripts/test_stale_cancellation.py'
        'live-binding' = 'scripts/test_live_binding.py'
        'websocket-stream' = 'scripts/test_websocket_stream.py'
    }
    if (-not $scripts.ContainsKey($Name)) {
        throw "Unknown Core runtime case: $Name"
    }
    & $script:Python $scripts[$Name] $daemon
    Assert-NativeSuccess "Core runtime case $Name"
}

function Invoke-CoreExtension {
    Ensure-Path 'C:\Program Files\nodejs'
    $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
    if (-not $npm) { throw 'npm.cmd not found.' }
    Push-Location extension
    try {
        & $npm install --no-audit --no-fund
        Assert-NativeSuccess 'Extension dependency install'
        & $npm run typecheck
        Assert-NativeSuccess 'TypeScript typecheck'
        & $npm run build
        Assert-NativeSuccess 'Extension build'
    }
    finally {
        Pop-Location
    }
}

function Invoke-FullStructuralBudget {
    Bootstrap-PythonEnvironment
    $corpusCheck = Resolve-BuildExe 'Release' 'corpus-check.exe'
    & $script:Python scripts/test_corpus_structural_budget.py $corpusCheck hwm_battles 14
    Assert-NativeSuccess 'Full-corpus structural-invalid budget'
}

function Invoke-FullPlannerBenchmark {
    $planner = Resolve-BuildExe 'Release' 'planner-demo.exe'
    & $planner 5000
    Assert-NativeSuccess 'Release planner benchmark'
}

function Invoke-M11Evaluate([string]$Name) {
    Bootstrap-PythonEnvironment
    New-Item -ItemType Directory -Force 'build/validation' | Out-Null
    $gates = @{
        'multistep' = @('hwm_solver.evaluation.dynamics_multistep', 'build/validation/dynamics-multistep-damage.json')
        'uncertainty' = @('hwm_solver.evaluation.dynamics_uncertainty', 'build/validation/dynamics-uncertainty-calibration.json')
        'selector' = @('hwm_solver.evaluation.dynamics_selector', 'build/validation/dynamics-selector-gate.json')
        'survival' = @('hwm_solver.evaluation.dynamics_survival_gate', 'build/validation/m11_dynamics_survival_gate.json')
    }
    if (-not $gates.ContainsKey($Name)) { throw "Unknown M11 evaluator: $Name" }
    $module = $gates[$Name][0]
    $out = $gates[$Name][1]
    & $script:Python -m $module hwm_battles --out $out
    Assert-NativeSuccess "M11 evaluator $Name"
    if (-not (Test-Path $out -PathType Leaf)) { throw "M11 evaluator output missing: $out" }
}

function Invoke-M11Verify {
    Bootstrap-PythonEnvironment
    foreach ($required in @(
        'build/validation/dynamics-multistep-damage.json',
        'build/validation/dynamics-uncertainty-calibration.json',
        'build/validation/dynamics-selector-gate.json',
        'build/validation/m11_dynamics_survival_gate.json'
    )) {
        if (-not (Test-Path $required -PathType Leaf)) {
            throw "Required generated M11 evidence missing: $required"
        }
    }
    & $script:Python scripts/verify_m11_evidence.py
    Assert-NativeSuccess 'Verify committed M11 evidence'
}

function Invoke-M11Temperature {
    Bootstrap-PythonEnvironment
    New-Item -ItemType Directory -Force 'build/validation' | Out-Null
    & $script:Python -m hwm_solver.evaluation.dynamics_temperature_gate hwm_battles --out build/validation/m11_dynamics_temperature_gate.json
    Assert-NativeSuccess 'M11 positive-residual temperature calibration'
}

switch ($Mode) {
    'CppBuildInventory' { Build-CppAndFreezeInventory $Config }
    'CppCase' { Invoke-CppCase $Config $CaseName $CaseExe }
    'PythonInventory' { Freeze-PythonInventory }
    'PythonCase' { Invoke-PythonCase $TestNode }
    'CorePlanner' { Invoke-CorePlanner }
    'CoreRuntimeCase' { Invoke-CoreRuntimeCase $CaseName }
    'CoreExtension' { Invoke-CoreExtension }
    'FullStructuralBudget' { Invoke-FullStructuralBudget }
    'FullPlannerBenchmark' { Invoke-FullPlannerBenchmark }
    'M11Evaluate' { Invoke-M11Evaluate $GateName }
    'M11Verify' { Invoke-M11Verify }
    'M11Temperature' { Invoke-M11Temperature }
}

Write-Host "HWM MAIN WINDOWS ATOMIC ${Mode}: PASS"
