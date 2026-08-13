from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
SCRIPT = ROOT / "scripts" / "ci_main_windows.ps1"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_main_ci_uses_atomic_windows_topology_not_monolithic_suite_entrypoint() -> None:
    workflow = _workflow_text()
    assert "runs-on: windows-2022" in workflow
    assert "ci_entrypoint_windows.ps1 -Suite" not in workflow
    assert "core_cpp_build:" in workflow
    assert "core_cpp_case:" in workflow
    assert "core_python_inventory:" in workflow
    assert "core_python_case:" in workflow
    assert "core_runtime:" in workflow
    assert "full_cpp_build:" in workflow
    assert "full_cpp_case:" in workflow
    assert "m11_verify:" in workflow


def test_main_ci_freezes_exact_cpp_and_pytest_inventories_before_fanout() -> None:
    workflow = _workflow_text()
    script = _script_text()
    assert "outputs:\n      cases: ${{ steps.inventory.outputs.cases }}" in workflow
    assert "fromJSON(needs.core_cpp_build.outputs.cases)" in workflow
    assert "fromJSON(needs.full_cpp_build.outputs.cases)" in workflow
    assert "fromJSON(needs.core_python_inventory.outputs.cases)" in workflow
    assert "ctest.exe --test-dir $build -C $BuildConfig -N --show-only=json-v1" in script
    assert "-m pytest --collect-only -q python/tests" in script
    assert "inventory contains duplicates" in script


def test_main_ci_builds_each_cpp_configuration_once_and_fans_out_immutable_artifacts() -> None:
    workflow = _workflow_text()
    assert workflow.count("-Mode CppBuildInventory -Config Debug") == 1
    assert workflow.count("-Mode CppBuildInventory -Config Release") == 1
    assert "name: main-cpp-debug" in workflow
    assert "name: main-cpp-release" in workflow
    assert "needs: core_cpp_build" in workflow
    assert "needs: full_cpp_build" in workflow


def test_main_ci_keeps_m11_generation_parallel_then_verifies_exact_combined_evidence() -> None:
    workflow = _workflow_text()
    script = _script_text()
    assert "needs: [m11_multistep, m11_uncertainty, m11_selector, m11_survival]" in workflow
    for artifact in (
        "dynamics-multistep-damage.json",
        "dynamics-uncertainty-calibration.json",
        "dynamics-selector-gate.json",
        "m11_dynamics_survival_gate.json",
    ):
        assert artifact in workflow
        assert artifact in script
    assert "scripts/verify_m11_evidence.py" in script


def test_main_ci_aggregates_every_mandatory_atomic_surface_without_magic_parallelism_contract() -> None:
    workflow = _workflow_text()
    assert "max-parallel:" not in workflow
    for dependency in (
        "core_cpp_case",
        "core_python_case",
        "core_planner",
        "core_runtime",
        "core_extension",
        "full_cpp_case",
        "full_structural_budget",
        "full_planner_benchmark",
        "m11_verify",
        "m11_temperature",
    ):
        assert f"- {dependency}" in workflow
    assert "Strict Core aggregate" in workflow
    assert "Strict Full aggregate" in workflow
    assert "if (-not $ok)" in workflow
