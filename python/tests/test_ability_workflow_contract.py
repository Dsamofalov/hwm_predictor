from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ability.yml"
SCRIPT = ROOT / "scripts" / "ci_ability_windows.ps1"
CMAKE = ROOT / "CMakeLists.txt"
MONOLITH = ROOT / "cpp" / "tests" / "test_main.cpp"
CASE_RUNNER = ROOT / "cpp" / "tests" / "test_ability_cases.cpp"
PYTHON_MANIFEST = ROOT / "python" / "tests" / "ABILITY_TESTS.txt"


def _workflow() -> tuple[str, dict]:
    text = WORKFLOW.read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, dict)
    return text, parsed


def _manifest_paths() -> list[str]:
    paths = [
        line.strip()
        for line in PYTHON_MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return paths


def test_ability_workflow_is_windows_only_and_fork_safe():
    text, parsed = _workflow()
    lowered = text.lower()
    jobs = parsed["jobs"]
    required = {
        "ability_cpp_build",
        "ability_cpp_case",
        "ability_python_inventory",
        "ability_python_case",
        "publish_status",
    }
    assert required <= set(jobs)
    assert "pull_request:" in text
    assert "workflow_dispatch:" in text
    assert "pull_request_target" not in text
    assert "ubuntu-latest" not in lowered
    assert "self-hosted" not in lowered
    assert "contents: write" not in lowered
    assert "${{ secrets." not in text
    assert parsed.get("permissions") == {"contents": "read"}
    for name in required:
        assert str(jobs[name]["runs-on"]).startswith("windows")


def test_cpp_matrix_is_derived_from_the_exact_executable_inventory():
    workflow_text, parsed = _workflow()
    script = SCRIPT.read_text(encoding="utf-8")
    cmake = CMAKE.read_text(encoding="utf-8")
    runner = CASE_RUNNER.read_text(encoding="utf-8")
    monolith = MONOLITH.read_text(encoding="utf-8")

    build = parsed["jobs"]["ability_cpp_build"]
    case_job = parsed["jobs"]["ability_cpp_case"]
    assert "steps.inventory.outputs.cases" in str(build["outputs"]["cases"])
    assert "fromJSON(needs.ability_cpp_build.outputs.cases)" in str(
        case_job["strategy"]["matrix"]["case"]
    )
    assert case_job["strategy"]["fail-fast"] is False
    assert case_job["needs"] == "ability_cpp_build"
    assert "actions/upload-artifact@v4" in workflow_text
    assert "actions/download-artifact@v4" in workflow_text

    assert "hwm-ability-case-tests" in cmake
    assert "test_ability_cases.cpp" in cmake
    assert "--list-json" in runner
    assert "--case" in runner
    assert "CppInventory" in script
    assert "CppCase" in script

    monolithic_cases = re.findall(
        r"if\s*\(\s*!\s*(test_[A-Za-z0-9_]+)\(\)\s*\)\s*return\s+EXIT_FAILURE",
        monolith,
    )
    runner_pairs = re.findall(
        r'\{"(test_[A-Za-z0-9_]+)",\s*&\s*(test_[A-Za-z0-9_]+)\}',
        runner,
    )
    assert monolithic_cases, "failed to discover hwm-tests monolithic case inventory"
    assert runner_pairs, "failed to discover ability C++ case-runner inventory"
    assert all(name == fn for name, fn in runner_pairs)
    runner_cases = [name for name, _ in runner_pairs]
    assert len(runner_cases) == len(set(runner_cases))
    assert runner_cases == monolithic_cases


def test_python_matrix_is_derived_from_unique_collected_pytest_nodes():
    _, parsed = _workflow()
    script = SCRIPT.read_text(encoding="utf-8")
    paths = _manifest_paths()

    assert paths
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))
    for relpath in paths:
        assert relpath.startswith("python/tests/")
        assert (ROOT / relpath).is_file(), relpath

    inventory = parsed["jobs"]["ability_python_inventory"]
    case_job = parsed["jobs"]["ability_python_case"]
    assert "steps.inventory.outputs.cases" in str(inventory["outputs"]["cases"])
    assert "fromJSON(needs.ability_python_inventory.outputs.cases)" in str(
        case_job["strategy"]["matrix"]["case"]
    )
    assert case_job["strategy"]["fail-fast"] is False
    assert case_job["needs"] == "ability_python_inventory"

    assert "ABILITY_TESTS.txt" in script
    assert "--collect-only" in script
    assert "Sort-Object -Unique" in script
    assert "inventory contains duplicates" in script
    assert "PythonInventory" in script
    assert "PythonCase" in script
    assert "GITHUB_OUTPUT" in script


def test_registry_risk_manifest_tests_trigger_ability_ci():
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    registry_risk_tests = [
        relpath for relpath in _manifest_paths() if relpath.endswith("_registry_risk.py")
    ]

    assert registry_risk_tests
    # One generic path filter in push and one in pull_request keeps future registry-risk
    # nodes trigger-covered without hard-coding individual ability names.
    assert workflow_text.count("'python/tests/test_*_registry_risk.py'") == 2


def test_parallelism_is_an_implementation_detail_not_a_numeric_contract():
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")

    # The canonical workflow exposes one independent case per matrix entry.  It does
    # not encode a required worker/shard count; GitHub runner availability may vary.
    assert "ShardCount" not in workflow_text
    assert "ShardIndex" not in workflow_text
    assert "ShardCount" not in script
    assert "ShardIndex" not in script
    assert "matrix.shard" not in workflow_text


def test_ability_status_requires_every_validation_surface():
    _, parsed = _workflow()
    publisher = parsed["jobs"]["publish_status"]
    assert publisher["needs"] == [
        "ability_cpp_build",
        "ability_cpp_case",
        "ability_python_inventory",
        "ability_python_case",
    ]
    assert publisher["permissions"] == {"statuses": "write"}
    assert "github.event_name == 'push'" in str(publisher["if"])
    text = yaml.safe_dump(publisher, sort_keys=True).lower()
    assert "actions/checkout" not in text
    assert "github.token" in text
