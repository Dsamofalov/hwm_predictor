from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.gribbomb_selfdestruct_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_gribbomb_selfdestruct_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["carrier_battles"] > 0
    assert report["active_actor_deaths"] >= report["selfdestruct_candidates"]
    assert report["candidate_damage_hits"] >= report["selfdestruct_candidates"]
    warnings.warn(
        "GRIBBOMB_SELFDESTRUCT "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
