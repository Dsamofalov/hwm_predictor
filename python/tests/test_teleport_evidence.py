from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.teleport_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_teleport_whole_corpus_evidence():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["carrier_battles"] > 0
    assert report["carrier_entities"] > 0
    assert report["carrier_creatures"]
    assert report["carrier_ability_sets"]
    assert report["carrier_decisions"] > 0
    warnings.warn(
        "TELEPORT_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
