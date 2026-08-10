from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
CI_SCRIPT = ROOT / "scripts" / "ci_windows.ps1"


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

    assert "ubuntu-latest" not in lowered
    assert "windows-latest" not in lowered
    assert "actions/setup-python" not in lowered
    assert "actions/setup-node" not in lowered
    assert text.count("runs-on: [self-hosted, windows, x64, hwm-windows]") == 2
    assert ".\\scripts\\ci_windows.ps1 -Suite Core" in text
    assert ".\\scripts\\ci_windows.ps1 -Suite Full" in text


def test_windows_ci_has_exactly_two_permanent_parallel_suites():
    with CI.open("r", encoding="utf-8") as fh:
        parsed = yaml.safe_load(fh)

    jobs = parsed["jobs"]
    assert set(jobs) == {"core", "full"}
    assert jobs["core"]["runs-on"] == ["self-hosted", "windows", "x64", "hwm-windows"]
    assert jobs["full"]["runs-on"] == ["self-hosted", "windows", "x64", "hwm-windows"]


def test_windows_ci_script_owns_core_and_full_test_inventory():
    text = CI_SCRIPT.read_text(encoding="utf-8")

    assert "[ValidateSet('Core', 'Full')]" in text
    assert "Scripts\\python.exe" in text
    assert "npm.cmd" in text

    core_markers = (
        "test_planner_replay_gate.py",
        "test_local_api_auth.py",
        "test_stale_cancellation.py",
        "test_live_binding.py",
        "test_websocket_stream.py",
        "& $script:Python -m pytest python/tests -q",
        "& $script:Npm run typecheck",
        "& $script:Npm run build",
    )
    for marker in core_markers:
        assert marker in text

    full_markers = (
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
    assert text.count("-E '^hwm-tests$'") == 2
