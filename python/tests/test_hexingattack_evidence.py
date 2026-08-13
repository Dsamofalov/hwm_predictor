from __future__ import annotations

import json
import warnings
from pathlib import Path

from hwm_solver.ability.hexingattack_evidence import analyze_corpus
from hwm_solver.ability.hexingattack_wire_evidence import analyze_wire_collisions


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"

EXPECTED_TOOLTIP = (
    "С некоторой вероятностью жертва атаки этого существа будет поражена одним из следующих заклинаний: "
    "«Проклятие», «Замедление», «Слабость» или «Разрушающий луч». Эти заклинания накладываются "
    "на искусном уровне."
)


def test_hexingattack_whole_corpus_evidence():
    report = analyze_corpus(CORPUS)
    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] == 866
    assert report["carrier_battles"] == 32
    assert report["carrier_entities"] == 88
    assert report["carrier_creatures"] == {"333": 41, "269": 27, "268": 20}
    assert report["carrier_ability_sets"] == {
        "caster,hexingattack,undead": 47,
        "alive,caster,hexingattack,ragingblood,sacrificegoblin,swiftattack": 41,
    }
    assert report["tooltip_battles"] == 32
    assert report["tooltip_names"] == {"Колдовской удар.": 32}
    assert report["tooltip_descriptions"] == {EXPECTED_TOOLTIP: 32}
    assert report["tooltip_claim_shapes"] == [
        {
            "count": 32,
            "claims": {
                "integers": [],
                "mentions_attack": True,
                "mentions_expert": True,
                "mentions_probability": True,
                "named_effects": {
                    "curse": True,
                    "disrupting_ray": True,
                    "slow": True,
                    "weakness": True,
                },
                "percentages": [],
            },
        }
    ]
    assert report["carrier_attacks"] == 115
    assert report["attack_action_types"] == {"MELEE_ATTACK": 115}
    assert report["attack_creatures"] == {"333": 94, "269": 16, "268": 5}
    assert report["attacks_with_same_target_special"] == 12
    assert report["same_target_special_records"] == 12
    assert report["same_target_codes"] == {"sff": 5, "crs": 4, "slw": 3}
    assert report["code_added_effects"] == {
        "crs": {"crs": 4},
        "sff": {"sff": 5},
        "slw": {"slw": 3},
    }
    assert report["code_value_shapes"] == {
        "crs": {"0.0": 4},
        "sff": {"0.0": 5},
        "slw": {"0.0": 3},
    }
    assert report["code_amount_shapes"] == {
        "crs": {"100": 3, "96": 1},
        "sff": {"12": 5},
        "slw": {"40": 3},
    }
    # The current generic parser does not decode the target-shaped fields of raw Sray.
    # Keep the observed three carrier-attack occurrences visible until the independent
    # whole-corpus collision auditor establishes whether ray has one stable identity.
    assert report["other_special_codes"].get("ray") == 3

    wire = analyze_wire_collisions(CORPUS)
    assert wire["parse_errors"] == []
    assert wire["corpus_battle_dirs"] == 866
    assert wire["candidate_codes"] == ["crs", "slw", "sff", "ray"]
    assert all(wire["records"].get(code, 0) > 0 for code in wire["candidate_codes"])
    assert wire["records"].get("ray", 0) >= 3

    warnings.warn(
        "HEXINGATTACK_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )
    warnings.warn(
        "HEXINGATTACK_WIRE_COLLISION_EVIDENCE "
        + json.dumps(wire, ensure_ascii=False, sort_keys=True)
    )
