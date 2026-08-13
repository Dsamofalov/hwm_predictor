from __future__ import annotations

import csv
import json
import warnings
from pathlib import Path

from hwm_solver.evaluation.ability_risk_report import report as ability_risk_report
from hwm_solver.knowledge.build_ability_registry import build


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def _enabled_collateral_codes() -> set[str]:
    with (ROOT / "models/collateral_model.csv").open(encoding="utf-8") as f:
        return {
            str(row["ability_code"])
            for row in csv.DictReader(f)
            if int(row.get("enabled", 0) or 0) == 1
        }


def test_gribbomb_partial_exact_registry_and_risk(tmp_path: Path):
    registry_path = tmp_path / "ability_registry.json"
    build_result = build(
        ROOT / "data/catalog/generated_v4.json",
        registry_path,
        ROOT / "models/ability_damage_model.csv",
        ROOT / "models/collateral_model.csv",
        ROOT / "models/proc_model.csv",
        ROOT / "models/kill_trigger_model.csv",
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    rows = {row["code"]: row for row in payload["abilities"]}
    gribbomb = rows["gribbomb"]

    # Exact observed carrier self-removal plus exact observed target-set evidence justify
    # partial_exact only. Predictive Earth-damage magnitude remains deliberately unresolved.
    assert gribbomb["support"] == "partial_exact"
    assert gribbomb["risk_weight"] == 0.25
    assert "gribbomb" not in _enabled_collateral_codes()

    # Reconstruct the pre-promotion registry from the same candidate payload so the risk
    # comparison changes only Gribbomb's support/risk classification. Global support-count
    # cardinalities are deliberately compared relatively: unrelated registry growth must not
    # turn this ability regression into a magic-number scheduling/catalog contract.
    baseline_path = tmp_path / "ability_registry_baseline.json"
    baseline_payload = json.loads(json.dumps(payload))
    baseline_gribbomb = next(
        row for row in baseline_payload["abilities"] if row["code"] == "gribbomb"
    )
    baseline_gribbomb["support"] = "unresolved"
    baseline_gribbomb["risk_weight"] = 0.62
    baseline_payload["support_counts"]["partial_exact"] -= 1
    baseline_payload["support_counts"]["unresolved"] += 1
    assert (
        build_result["support_counts"]["partial_exact"]
        == baseline_payload["support_counts"]["partial_exact"] + 1
    )
    assert (
        build_result["support_counts"]["unresolved"]
        == baseline_payload["support_counts"]["unresolved"] - 1
    )
    baseline_path.write_text(
        json.dumps(baseline_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    baseline_risk = ability_risk_report(CORPUS, baseline_path)
    candidate_risk = ability_risk_report(CORPUS, registry_path)
    assert candidate_risk["heldout_battles"] == baseline_risk["heldout_battles"]
    assert candidate_risk["sampled_player_states"] == baseline_risk["sampled_player_states"]
    assert candidate_risk["risk_mean"] < baseline_risk["risk_mean"]
    assert candidate_risk["risk_p90"] <= baseline_risk["risk_p90"]

    gribbomb_top = next(
        (row for row in candidate_risk["top_contributors"] if row["code"] == "gribbomb"),
        None,
    )
    if gribbomb_top is not None:
        assert gribbomb_top["support"] == "partial_exact"
        assert gribbomb_top["risk_weight"] == 0.25

    warnings.warn(
        "GRIBBOMB_REGISTRY_RISK "
        + json.dumps(
            {
                "support_counts": build_result["support_counts"],
                "gribbomb": gribbomb,
                "baseline_risk_mean": baseline_risk["risk_mean"],
                "candidate_risk_mean": candidate_risk["risk_mean"],
                "baseline_risk_p90": baseline_risk["risk_p90"],
                "candidate_risk_p90": candidate_risk["risk_p90"],
                "heldout_battles": candidate_risk["heldout_battles"],
                "sampled_player_states": candidate_risk["sampled_player_states"],
                "top_contributors": candidate_risk["top_contributors"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
