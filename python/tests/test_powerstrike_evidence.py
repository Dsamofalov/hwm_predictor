from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.powerstrike_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_powerstrike_whole_corpus_evidence():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["analysis_errors"] == []
    assert report["corpus_battles_seen"] >= 800
    assert report["carrier_melee_attacks"] > report["proc_attacks"] > 0
    assert report["no_proc_attacks"] > 0
    holdout = report["temporal_holdout"]
    assert holdout["train_rows"] > 0
    assert holdout["holdout_rows"] > 0
    warnings.warn(
        "POWERSTRIKE_EVIDENCE "
        + json.dumps(
            {
                "carrier_attacks": report["carrier_melee_attacks"],
                "proc_attacks": report["proc_attacks"],
                "no_proc_attacks": report["no_proc_attacks"],
                "observed_rate": report["observed_proc_rate"],
                "signature": report["signature"],
                "negative_control": report["negative_control"],
                "target_ineligibility": report["target_ineligibility"],
                "temporal_holdout": holdout,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
