from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"


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
