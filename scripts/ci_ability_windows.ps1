param(
    [ValidateSet('CppBuild', 'CppInventory', 'CppCase', 'PythonInventory', 'PythonCase')]
    [string]$Mode = 'CppBuild',
    [string]$CaseName = '',
    [string]$TestNode = ''
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
    if ($help -match 'Visual Studio 18 2026') { return 'Visual Studio 18 2026' }
    if ($help -match 'Visual Studio 17 2022') { return 'Visual Studio 17 2022' }
    throw 'No supported Visual Studio CMake generator found.'
}

function Bootstrap-PythonEnvironment {
    Write-Host '==> Bootstrap ability Python environment'
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

function Assert-WholeCorpus {
    foreach ($candidate in @('hwm_battles\battles', 'hwm_battles')) {
        if (-not (Test-Path $candidate -PathType Container)) { continue }
        $battleCount = @(Get-ChildItem $candidate -Directory -ErrorAction Stop).Count
        if ($battleCount -ge 800) {
            Write-Host "Whole-corpus battle directories: $battleCount ($candidate)"
            return
        }
    }
    throw 'Whole-corpus directory is incomplete: expected >=800 battle directories.'
}

function Write-GitHubJsonOutput([string]$Name, [object[]]$Values) {
    $items = @($Values)
    if ($items.Count -eq 0) { throw "$Name inventory is empty." }
    $unique = @($items | Sort-Object -Unique)
    if ($unique.Count -ne $items.Count) { throw "$Name inventory contains duplicates." }
    $json = ConvertTo-Json -InputObject $items -Compress
    Write-Host "$Name inventory count: $($items.Count)"
    if (-not $env:GITHUB_OUTPUT) {
        Write-Host $json
        return
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($env:GITHUB_OUTPUT, "$Name=$json`n", $utf8NoBom)
}

function Get-AbilityPythonTestFiles {
    $manifest = 'python/tests/ABILITY_TESTS.txt'
    if (-not (Test-Path $manifest -PathType Leaf)) { throw "Ability test manifest not found: $manifest" }
    $tests = @(
        Get-Content $manifest -Encoding UTF8 |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith('#') }
    )
    if ($tests.Count -eq 0) { throw 'Ability Python test manifest is empty.' }
    if (@($tests | Sort-Object -Unique).Count -ne $tests.Count) {
        throw 'Ability Python test manifest contains duplicate paths.'
    }
    foreach ($test in $tests) {
        if (-not (Test-Path $test -PathType Leaf)) { throw "Ability Python test is missing: $test" }
    }
    return $tests
}

$caseExe = 'build/ability-artifact/hwm-ability-case-tests.exe'

switch ($Mode) {
    'CppBuild' {
        $generator = Resolve-CMakeGenerator
        $build = 'build/ability-ci'
        Write-Host "==> Configure ability C++ Debug ($generator / x64)"
        cmake.exe -S . -B $build -G $generator -A x64 -DHWM_BUILD_TESTS=ON
        Assert-NativeSuccess 'Ability CMake configure'
        cmake.exe --build $build --config Debug --target hwm-ability-case-tests --parallel 2
        Assert-NativeSuccess 'Ability case runner build'
        $exe = Join-Path $build 'Debug\hwm-ability-case-tests.exe'
        if (-not (Test-Path $exe -PathType Leaf)) { throw "Ability case runner not found: $exe" }
        $out = 'build/ability-artifact'
        New-Item -ItemType Directory -Force $out | Out-Null
        Copy-Item $exe (Join-Path $out 'hwm-ability-case-tests.exe') -Force
        Write-Host 'HWM ABILITY WINDOWS C++ BUILD: PASS'
    }
    'CppInventory' {
        if (-not (Test-Path $caseExe -PathType Leaf)) { throw "Ability case runner not found: $caseExe" }
        $json = (& $caseExe --list-json | Out-String).Trim()
        Assert-NativeSuccess 'Ability C++ inventory'
        try { $cases = @($json | ConvertFrom-Json) } catch { throw "Invalid C++ case inventory JSON: $json" }
        Write-GitHubJsonOutput -Name 'cases' -Values $cases
    }
    'CppCase' {
        if (-not $CaseName) { throw 'CaseName is required for CppCase.' }
        if (-not (Test-Path $caseExe -PathType Leaf)) { throw "Downloaded ability case runner not found: $caseExe" }
        & $caseExe --case $CaseName
        Assert-NativeSuccess "Ability C++ case $CaseName"
        Write-Host "HWM ABILITY WINDOWS C++ CASE ${CaseName}: PASS"
    }
    'PythonInventory' {
        Bootstrap-PythonEnvironment
        Assert-WholeCorpus
        $tests = Get-AbilityPythonTestFiles
        Write-Host "==> Collect exact pytest node inventory from $($tests.Count) ability test files"
        $collected = @(& $script:Python -m pytest --collect-only -q @tests 2>&1)
        Assert-NativeSuccess 'Ability pytest collection'
        $nodes = @(
            $collected |
                ForEach-Object { "$_".Trim() } |
                Where-Object { $_ -match '^python[\\/]tests[\\/].+::.+$' } |
                Sort-Object -Unique
        )
        if ($nodes.Count -eq 0) {
            Write-Host ($collected -join [Environment]::NewLine)
            throw 'Pytest collection produced no ability test node IDs.'
        }
        Write-GitHubJsonOutput -Name 'cases' -Values $nodes
    }
    'PythonCase' {
        if (-not $TestNode) { throw 'TestNode is required for PythonCase.' }
        Bootstrap-PythonEnvironment
        Assert-WholeCorpus
        & $script:Python -m pytest -q --durations=5 $TestNode
        Assert-NativeSuccess "Ability Python case $TestNode"
        Write-Host "HWM ABILITY WINDOWS PYTHON CASE ${TestNode}: PASS"
    }
}
