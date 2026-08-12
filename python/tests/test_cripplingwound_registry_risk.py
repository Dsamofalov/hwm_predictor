from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.evaluation.ability_risk_report import report as ability_risk_report
from hwm_solver.knowledge.build_ability_registry import build


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_cripplingwound_partial_exact_registry_and_risk(tmp_path: Path):
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
    cripple = rows["cripplingwound"]
    assert cripple["support"] == "partial_exact"
    assert cripple["risk_weight"] == 0.25
    assert build_result["support_counts"]["partial_exact"] >= 1

    risk = ability_risk_report(CORPUS, registry_path)
    cripple_top = next(
        (row for row in risk["top_contributors"] if row["code"] == "cripplingwound"),
        None,
    )
    if cripple_top is not None:
        assert cripple_top["support"] == "partial_exact"
        assert cripple_top["risk_weight"] == 0.25

    warnings.warn(
        "CRIPPLINGWOUND_REGISTRY_RISK "
        + json.dumps(
            {
                "support_counts": build_result["support_counts"],
                "cripplingwound": cripple,
                "heldout_battles": risk["heldout_battles"],
                "sampled_player_states": risk["sampled_player_states"],
                "risk_mean": risk["risk_mean"],
                "risk_p50": risk["risk_p50"],
                "risk_p90": risk["risk_p90"],
                "risk_p99": risk["risk_p99"],
                "top_contributors": risk["top_contributors"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
