from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.shootbash_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_shootbash_whole_corpus_evidence():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["carrier_battles"] > 0
    assert report["carrier_entities"] > 0
    assert report["carrier_creatures"]
    assert report["carrier_ability_sets"]
    assert 0 <= report["tooltip_battles"] <= report["carrier_battles"]
    assert report["ranged_attacks"] > 0
    warnings.warn(
        "SHOOTBASH_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
