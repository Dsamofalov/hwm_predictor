from __future__ import annotations

import json
from pathlib import Path


PAIRS = [
    (
        Path("build/validation/dynamics-multistep-damage.json"),
        Path("data/reports/dynamics-multistep-damage.json"),
    ),
    (
        Path("build/validation/dynamics-uncertainty-calibration.json"),
        Path("data/reports/dynamics-uncertainty-calibration.json"),
    ),
    (
        Path("build/validation/dynamics-selector-gate.json"),
        Path("data/reports/dynamics-selector-gate.json"),
    ),
    (
        Path("build/validation/m11_dynamics_survival_gate.json"),
        Path("data/reports/m11_dynamics_survival_gate.json"),
    ),
]

# These fields are presentation/validation metadata in the committed compact reports,
# not part of the model evidence that the evaluator regenerates.
SKIP_KEYS = {"validation", "report_kind", "reason"}


def _prepare_generated(committed_path: Path, value: dict) -> dict:
    value = dict(value)
    if committed_path.name == "dynamics-selector-gate.json":
        selector = dict(value["selector"])
        calibration = selector.get("calibration_selection", {})
        selector["calibration_generic_usage_rate"] = calibration.get("generic_usage_rate")
        selector["calibration_mean_abs_log_error"] = calibration.get("mean_abs_log_error")
        value["selector"] = selector
    return value


def _project_like(actual, template, context: str = "root"):
    if isinstance(template, dict):
        if not isinstance(actual, dict):
            raise AssertionError(f"evidence type mismatch at {context}")
        out = {}
        for key, expected in template.items():
            if key in SKIP_KEYS:
                continue
            if key not in actual:
                raise AssertionError(f"missing evidence field {context}.{key}")
            out[key] = _project_like(actual[key], expected, f"{context}.{key}")
        return out
    if isinstance(template, list):
        if not isinstance(actual, list):
            raise AssertionError(f"evidence type mismatch at {context}")
        return actual
    return actual


def verify_pair(generated_path: Path, committed_path: Path) -> None:
    generated = json.loads(generated_path.read_text(encoding="utf-8"))
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    generated = _prepare_generated(committed_path, generated)
    actual = _project_like(generated, committed)
    expected = _project_like(committed, committed)
    if actual != expected:
        raise AssertionError(f"reproducibility mismatch: {committed_path}")


def main() -> None:
    for generated_path, committed_path in PAIRS:
        verify_pair(generated_path, committed_path)
        print(f"MATCH: {committed_path}")


if __name__ == "__main__":
    main()
