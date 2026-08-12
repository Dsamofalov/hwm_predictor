from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.powerstrike_retaliation_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_powerstrike_retaliation_evidence_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["analysis_errors"] == []
    assert report["corpus_battles_seen"] >= 800

    # The corpus must expose real carrier counterattacks so this is not a vacuous check.
    assert report["carrier_retaliation_hits"] > 0

    # Every observed Power Strike proc on a primary hit suppresses a later target retaliation.
    assert report["primary_proc_hits"] > 0
    assert report["primary_proc_with_retaliation_after_i"] == 0

    # If retaliation procs are present, the I consequence must carry the same zero-state marker.
    if report["carrier_retaliation_proc_hits"]:
        assert report["carrier_retaliation_proc_zero_state_after_i"] == report["carrier_retaliation_proc_hits"]

    warnings.warn(
        "POWERSTRIKE_RETALIATION "
        + json.dumps(
            {
                "carrier_retaliation_hits": report["carrier_retaliation_hits"],
                "carrier_retaliation_battles": report["carrier_retaliation_battles"],
                "carrier_retaliation_proc_hits": report["carrier_retaliation_proc_hits"],
                "carrier_retaliation_proc_battles": report["carrier_retaliation_proc_battles"],
                "carrier_retaliation_proc_zero_state_after_i": report["carrier_retaliation_proc_zero_state_after_i"],
                "primary_proc_hits": report["primary_proc_hits"],
                "primary_proc_with_retaliation_after_i": report["primary_proc_with_retaliation_after_i"],
                "retaliation_proc_examples": report["retaliation_proc_examples"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
