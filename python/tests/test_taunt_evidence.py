from __future__ import annotations

from pathlib import Path

from hwm_solver.ability.taunt_evidence import analyze_corpus


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"
TOOLTIP = "Это существо имеет шанс отвлечь на себя атаку противника, направленную против дружественного отряда, находящегося по соседству."


def test_taunt_whole_corpus_targeting_evidence():
    report = analyze_corpus(CORPUS)

    assert report["parse_errors"] == []
    assert report["corpus_battle_dirs"] == 866
    assert report["carrier_battles"] == 24
    assert report["carrier_entities"] == 25
    assert report["carrier_creatures"] == {"330": 15, "730": 10}
    assert report["carrier_owners"] == {"1": 13, "2": 11, "4": 1}
    assert report["carrier_ability_sets"] == {
        "alive,enraged,fierceretaliation,ragingblood,taunt": 15,
        "alive,big,taunt": 10,
    }

    assert report["tooltip_battles"] == 24
    assert report["tooltip_names"] == {"Задира.": 24}
    assert report["tooltip_descriptions"] == {TOOLTIP: 24}
    assert report["tooltip_claim_shapes"] == [
        {
            "count": 24,
            "claims": {
                "integers": [],
                "mentions_adjacent": True,
                "mentions_attack": True,
                "mentions_chance": True,
                "mentions_friendly": True,
                "mentions_redirect": True,
                "percentages": [],
            },
        }
    ]

    assert report["attacks_seen_in_carrier_battles"] == 712
    assert report["carrier_ally_opportunities"] == 169
    assert report["attacks_targeting_carrier"] == 78
    assert report["attacks_targeting_carrier_with_adjacent_ally"] == 31
    assert report["attacks_targeting_adjacent_ally"] == 37
    assert report["target_action_types"] == {"MELEE_ATTACK": 44, "RANGED_ATTACK": 34}
    assert report["adjacent_ally_count_when_carrier_targeted"] == {"1": 24, "2": 5, "3": 2}


def test_taunt_has_no_raw_redirect_proc_label():
    report = analyze_corpus(CORPUS)

    assert report["parse_errors"] == []
    assert report["carrier_involved_special_codes"] == {
        "ra2": 10,
        "ral": 5,
        "enr": 3,
        "rag": 3,
        "wnd": 1,
    }

    # ra2/ral are emitted by the final attacked target in both the direct-carrier
    # and adjacent-ally control contexts. They therefore describe a generic target
    # reaction, not a Taunt redirect event or the attacker's original intent.
    target_source = report["target_source_special_code_contexts"]
    assert target_source["ra2"] == {
        "adjacent_ally_target": 19,
        "carrier_target_with_adjacent_ally": 10,
    }
    assert target_source["ral"] == {
        "adjacent_ally_target": 13,
        "carrier_target_with_adjacent_ally": 5,
    }

    # The server tooltip states only that redirect has a chance to occur. It gives
    # neither a numeric probability nor a raw per-attack proc label, so final target
    # observations cannot be turned into supervised redirect outcomes.
    claims = report["tooltip_claim_shapes"][0]["claims"]
    assert claims["mentions_chance"] is True
    assert claims["mentions_redirect"] is True
    assert claims["percentages"] == []
    assert claims["integers"] == []
