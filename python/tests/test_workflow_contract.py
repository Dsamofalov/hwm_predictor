from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
ENTRYPOINT = ROOT / "scripts" / "ci_entrypoint_windows.ps1"
CI_SCRIPT = ROOT / "scripts" / "ci_windows.ps1"
MAIN_CI_SCRIPT = ROOT / "scripts" / "ci_main_windows.ps1"
LOCAL_VALIDATE = ROOT / "scripts" / "validate_windows.ps1"


def test_all_workflow_yaml_parses():
    paths = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert paths, "no GitHub Actions workflows found"
    for path in paths:
        with path.open("r", encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh)
        assert isinstance(parsed, dict), f"workflow root must be a mapping: {path}"


def test_main_ci_keeps_windows_bootstrap_out_of_yaml():
    text = CI.read_text(encoding="utf-8")
    lowered = text.lower()
    with CI.open("r", encoding="utf-8") as fh:
        jobs = yaml.safe_load(fh)["jobs"]

    assert "ubuntu-latest" not in lowered
    assert "windows-latest" not in lowered
    assert "self-hosted" not in lowered
    assert "hwm-windows" not in lowered
    assert "actions/setup-python" not in lowered
    assert "actions/setup-node" not in lowered
    assert jobs, "main CI must expose validation jobs"
    assert all(job.get("runs-on") == "windows-2022" for job in jobs.values())
    assert ".\\scripts\\ci_main_windows.ps1" in text


def test_windows_ci_has_two_strict_aggregates_over_atomic_jobs():
    with CI.open("r", encoding="utf-8") as fh:
        parsed = yaml.safe_load(fh)

    jobs = parsed["jobs"]
    assert {"core", "full"} <= set(jobs)
    assert len(jobs) > 2, "Core/Full must aggregate independently scheduled atomic jobs"

    expected_needs = {
        "core": {
            "core_pending",
            "core_cpp_build",
            "core_cpp_case",
            "core_python_inventory",
            "core_python_case",
            "core_planner",
            "core_runtime",
            "core_extension",
        },
        "full": {
            "full_pending",
            "full_cpp_build",
            "full_cpp_case",
            "full_structural_budget",
            "full_planner_benchmark",
            "m11_verify",
            "m11_temperature",
        },
    }
    for aggregate, required in expected_needs.items():
        job = jobs[aggregate]
        assert job["runs-on"] == "windows-2022"
        assert "always()" in job["if"]
        assert required <= set(job["needs"])

    # Dynamic matrices are execution representations of frozen inventories,
    # not hard-coded correctness shard counts (TESTS_CANON.md).
    assert "fromJSON(needs.core_cpp_build.outputs.cases)" in jobs["core_cpp_case"]["strategy"]["matrix"]["case"]
    assert "fromJSON(needs.core_python_inventory.outputs.cases)" in jobs["core_python_case"]["strategy"]["matrix"]["case"]
    assert "fromJSON(needs.full_cpp_build.outputs.cases)" in jobs["full_cpp_case"]["strategy"]["matrix"]["case"]


def test_main_windows_ci_script_exposes_atomic_inventory_and_reducer_modes():
    text = MAIN_CI_SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "CppBuildInventory",
        "CppCase",
        "PythonInventory",
        "PythonCase",
        "CoreRuntimeCase",
        "FullStructuralBudget",
        "M11Evaluate",
        "M11Verify",
    ):
        assert marker in text


def test_windows_ci_entrypoint_preflights_powershell_syntax():
    text = ENTRYPOINT.read_text(encoding="utf-8")
    local_text = LOCAL_VALIDATE.read_text(encoding="utf-8")

    assert "[System.Management.Automation.Language.Parser]::ParseFile" in text
    assert "PowerShell syntax preflight: PASS" in text
    assert "ci_windows.ps1" in text
    assert "ci_entrypoint_windows.ps1 -Suite Core" in local_text
    assert "ci_entrypoint_windows.ps1 -Suite Full" in local_text


def test_windows_ci_script_owns_core_and_full_test_inventory():
    text = CI_SCRIPT.read_text(encoding="utf-8")

    assert "[ValidateSet('Core', 'Full')]" in text
    assert "Scripts\\python.exe" in text
    assert "npm.cmd" in text
    assert "function Invoke-NativeGate" in text
    assert "function Assert-GatesPassed" in text
    assert "FAILURE SUMMARY" in text
    assert text.count("[AllowEmptyCollection()]") == 2

    core_markers = (
        "test_planner_replay_gate.py",
        "test_local_api_auth.py",
        "test_stale_cancellation.py",
        "test_live_binding.py",
        "test_websocket_stream.py",
        "'pytest', 'python/tests', '-q'",
        "'run', 'typecheck'",
        "'run', 'build'",
    )
    for marker in core_markers:
        assert marker in text

    full_markers = (
        "test_corpus_structural_budget.py",
        "planner-demo.exe",
        "dynamics_multistep",
        "dynamics_uncertainty",
        "dynamics_selector",
        "dynamics_survival_gate",
        "verify_m11_evidence.py",
        "dynamics_temperature_gate",
    )
    for marker in full_markers:
        assert marker in text

    # Ability-owned monolithic CTest remains deliberately outside main-front CI.
    assert text.count("'^hwm-tests$'") == 2
    assert "'hwm_battles', '14'" in text
