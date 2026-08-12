from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.powerstrike_discriminator import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_powerstrike_discriminator_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["analysis_errors"] == []
    assert report["corpus_battles_seen"] >= 800

    isolated = report["isolated_powerstrike"]
    assert isolated["attacks"] > isolated["proc_attacks"] > 0
    assert isolated["no_proc_attacks"] > 0

    discriminator = report["discriminator"]
    assert discriminator["same_wire_without_powerstrike"] > 0
    assert discriminator["pawstrike_tagged_controls"] == discriminator["same_wire_without_powerstrike"]
    assert discriminator["unexplained_controls"] == 0
    assert discriminator["powerstrike_pawstrike_co_carrier"]["attacks"] == 0
    assert discriminator["powerstrike_pawstrike_co_carrier"]["proc_attacks"] == 0

    consequence = report["observed_consequence"]
    proc_attacks = isolated["proc_attacks"]
    assert consequence["zero_state_after_i"]["true"] == proc_attacks
    assert consequence["zero_state_after_i"]["false"] == 0
    assert consequence["retaliation_present"]["true"] == 0
    assert consequence["retaliation_present"]["false"] == proc_attacks
    assert consequence["owner_relation"].get("enemy", 0) == proc_attacks
    assert consequence["forced_coordinate"]["changed"] > 0
    assert consequence["forced_coordinate"]["same"] > 0

    holdout = report["temporal_holdout"]
    assert holdout["train_rows"] > 0
    assert holdout["holdout_rows"] > 0
    assert "train_frequency" in holdout["models"]

    warnings.warn(
        "POWERSTRIKE_DISCRIMINATOR "
        + json.dumps(
            {
                "isolated_powerstrike": isolated,
                "discriminator": discriminator,
                "observed_consequence": consequence,
                "temporal_holdout": holdout,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
