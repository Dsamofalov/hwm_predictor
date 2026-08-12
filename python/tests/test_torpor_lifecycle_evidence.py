from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.torpor_lifecycle_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_torpor_lifecycle_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["carrier_melee_attacks"] > 0
    assert report["observed_proc_attacks"] > 0
    warnings.warn(
        "TORPOR_LIFECYCLE_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
