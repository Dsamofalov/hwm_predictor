from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.cripplingwound_probability_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_cripplingwound_rolling_probability_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["analysis_errors"] == []
    assert report["replay_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["primary_hits"] > report["primary_proc_hits"] > 0
    assert report["counter_hits"] > report["counter_proc_hits"] > 0
    primary = report["primary_rolling"]
    assert len(primary["folds"]) >= 3
    assert "train_frequency" in primary["aggregate"]
    assert "fixed_0_25" in primary["aggregate"]
    assert "fixed_0_30" in primary["aggregate"]
    warnings.warn(
        "CRIPPLINGWOUND_PROBABILITY_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
