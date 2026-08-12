from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.stonegarden_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_stonegarden_whole_corpus_evidence():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["carrier_battles"] > 0
    assert report["carrier_entities"] > 0
    assert report["carrier_melee_attacks"] > 0
    assert report["temporal_holdout"]["train_rows"] > 0
    assert report["temporal_holdout"]["holdout_rows"] > 0
    warnings.warn(
        "STONEGARDEN_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
