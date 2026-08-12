from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.auraoffirevul_spellwire_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"


def test_auraoffirevul_fire_spell_wire_whole_corpus():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] >= 800
    assert report["aura_battles"] > 0
    assert report["fire_spellbook_actors"] > 0
    assert report["special_codes"].get("fbl", 0) > 0
    assert report["fbl"]["records"] == report["special_codes"]["fbl"]
    assert report["fbl"]["examples_captured"] == report["fbl"]["records"]
    assert report["fbl"]["fire_spell_names"].get("fireball", 0) > 0
    warnings.warn(
        "AURAOFFIREVUL_SPELLWIRE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
