from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.cripplingwound_tooltip_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_cripplingwound_server_tooltip_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_failures"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["battles_with_ability_tooltip"] > 0
    assert report["exact_consequence_descriptions"] == report["battles_with_ability_tooltip"]
    assert (
        report["chance_without_numeric_probability_descriptions"]
        == report["battles_with_ability_tooltip"]
    )
    assert report["derived_exact_consequence"] == {
        "speed_multiplier": 0.5,
        "initiative_multiplier": 0.7,
        "duration_turns": 2,
    }
    assert report["probability"]["numeric_probability_from_tooltip"] is None
    assert report["probability"]["status"] == "unknown"
    warnings.warn(
        "CRIPPLINGWOUND_TOOLTIP_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
