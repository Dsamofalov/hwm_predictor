from __future__ import annotations

import hashlib
import json
import os
import warnings
from pathlib import Path

from hwm_solver.ability.hexingattack_evidence import analyze_corpus
from hwm_solver.ability.hexingattack_wire_evidence import analyze_wire_collisions
from hwm_solver.protocol.replay import (
    RawEntity,
    _apply_command,
    _decision_semantic_unresolved_flags,
    parse_commands,
)


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "hwm_battles"

EXPECTED_TOOLTIP = (
    "С некоторой вероятностью жертва атаки этого существа будет поражена одним из следующих заклинаний: "
    "«Проклятие», «Замедление», «Слабость» или «Разрушающий луч». Эти заклинания накладываются "
    "на искусном уровне."
)


def _export_wire_evidence(report: dict) -> None:
    evidence_dir = os.environ.get("ABILITY_EVIDENCE_DIR", "").strip()
    if not evidence_dir:
        return
    out_dir = Path(evidence_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "hexingattack-wire.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ray_entity(
    uid: int,
    owner: int,
    *,
    mana: int = 0,
    magic_blob: str = "",
    abilities: list[str] | None = None,
) -> RawEntity:
    return RawEntity(
        uid=uid,
        owner=owner,
        creature_id=0,
        max_hp=1,
        top_hp=1,
        min_damage=0,
        max_damage=0,
        mana=mana,
        max_mana=mana,
        speed=1,
        atb=0,
        initiative=1,
        max_count=1,
        count=1,
        x=uid,
        y=1,
        attack_range=1,
        shots=0,
        attack=0,
        defense=0,
        morale_raw=0,
        luck_raw=0,
        retaliation_raw=0,
        real_health=1,
        experience_level_code=0,
        abilities=list(abilities or []),
        magic_blob=magic_blob,
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
    assert report["other_special_codes"].get("ray") == 3

    warnings.warn(
        "HEXINGATTACK_EVIDENCE "
        + json.dumps(report, ensure_ascii=False, sort_keys=True)
    )


def test_hexingattack_wire_collision_audit():
    wire = analyze_wire_collisions(CORPUS)
    _export_wire_evidence(wire)

    assert wire["parse_errors"] == []
    assert wire["corpus_battle_dirs"] == 866
    assert wire["candidate_codes"] == ["crs", "slw", "sff", "ray"]
    assert wire["total_raw_count"] == 3895
    assert wire["records"] == {"slw": 1412, "ray": 1179, "sff": 824, "crs": 480}
    assert wire["raw_record_width_shapes"] == {
        "crs": {"19": 480},
        "ray": {"19": 1179},
        "sff": {"19": 824},
        "slw": {"19": 1412},
    }
    assert wire["payload_width_shapes"] == {
        "crs": {"15": 480},
        "ray": {"15": 1179},
        "sff": {"15": 824},
        "slw": {"15": 1412},
    }
    assert wire["field2_shapes"] == {
        "crs": {"00": 305, "04": 92, "08": 81, "06": 2},
        "ray": {"00": 574, "05": 374, "10": 227, "07": 3, "01": 1},
        "sff": {"00": 723, "06": 55, "10": 22, "05": 16, "07": 6, "03": 2},
        "slw": {"00": 585, "04": 554, "08": 257, "03": 10, "06": 6},
    }
    assert _json_sha256(wire["field2_shapes"]) == "76a3b76b71c8e2d838bf51b6d651b1ec69c6776607ca806af5565bc436ec0169"
    assert _json_sha256(wire["field4_shapes"]) == "a75be56a94da873c7769e9f9684100a8545434622e554dacbfe790ea9e70ccef"
    assert _json_sha256(wire["field3_shapes"]) == "a4cd53da1d782ca34d4b2d4c88447bec2de817bf8ed51703e592360e945678bf"
    assert wire["source_present"] == wire["records"]
    assert wire["target_present"] == wire["records"]
    assert wire["other_owner"] == wire["records"]
    assert wire["same_owner"] == {}
    assert wire["source_hexing"] == {"ray": 330, "slw": 52, "sff": 7, "crs": 6}
    assert wire["decision_actor_match"] == {"slw": 1379, "ray": 1178, "sff": 647, "crs": 422}
    assert wire["decision_target_match"] == {"sff": 507, "crs": 68, "slw": 27, "ray": 4}
    assert wire["action_types"] == {
        "crs": {"HERO_ACTION": 275, "MELEE_ATTACK": 108, "CAST_OR_ABILITY": 79, "RANGED_ATTACK": 18},
        "ray": {"HERO_ACTION": 768, "CAST_OR_ABILITY": 406, "MELEE_ATTACK": 5},
        "sff": {"MELEE_ATTACK": 658, "CAST_OR_ABILITY": 77, "HERO_ACTION": 63, "RANGED_ATTACK": 26},
        "slw": {"HERO_ACTION": 920, "CAST_OR_ABILITY": 430, "MELEE_ATTACK": 37, "RANGED_ATTACK": 23, "ABILITY": 2},
    }
    assert _json_sha256(wire["action_types"]) == "4ae946ef015663fc9b4b341c9f8abf6d30a0b92649861c7c8e66b0caab9ee3f7"
    assert wire["attack_bound"] == {"sff": 507, "crs": 68, "slw": 27, "ray": 4}
    assert wire["hexing_attack_bound"] == {"sff": 5, "crs": 4, "slw": 3, "ray": 3}
    assert wire["nonhexing_attack_bound"] == {"sff": 502, "crs": 64, "slw": 24, "ray": 1}
    assert wire["zero_field2"] == {"sff": 723, "slw": 585, "ray": 574, "crs": 305}
    assert wire["positive_field2"] == {"slw": 827, "ray": 605, "crs": 175, "sff": 101}

    # Large collision inventories are pinned by canonical JSON digest so every source
    # ability-set, creature, spellbook entry and representative row remains exact without
    # turning the test into a duplicated 30kB data snapshot.
    assert _json_sha256(wire["source_ability_sets"]) == "54a76e80047833293fe5b49106306f6f1e6c2a5c37c5085cacfc696abe0c71fa"
    assert _json_sha256(wire["source_creatures"]) == "901f26aef691ff72b983d0a3a1ffe3abb4403f65c6cecb381c8b1e278c84528e"
    assert _json_sha256(wire["source_spellbook_names"]) == "2cf711e32fe88a60e6f55074fc91f13facdcf39101026421f37ed3212e3c3472"
    assert _json_sha256(wire["positive_exact_cost_spellbook_names"]) == "1ceb000790faad36521d51604fdadba17cedaa6f58b7669c6bbeb7235dcc2a47"
    assert _json_sha256(wire["positive_compatible_cost_spellbook_names"]) == "368e465f17abe114843c24f331b9e0f4e0ce79a43fef9f9d2ef3e786a829800e"
    assert _json_sha256(wire["positive_spellbook_entry_shapes"]) == "c8579e7efb46ba96827afb6dfab9a46c4aa05014df33878eb643821002f2db91"
    assert _json_sha256(wire["examples"]) == "b5433be3e7bcde8d9f65c478406d940daa834775ab57614596416f045936283a"
    assert _json_sha256(wire["positive_examples"]) == "61882e442d7723e81b94c1d2a8eb618eefea8528e396dafd00bf58ceda84e9fc"

    # Independent server-spellbook controls are visible but cost alone is deliberately
    # not treated as identity: several spells can share a cost in the same source book.
    exact = wire["positive_exact_cost_spellbook_names"]
    assert exact["ray"]["dray"] == 376
    assert exact["ray"]["mdray"] == 277
    assert exact["sff"]["suffering"] == 71
    assert exact["sff"]["msuffering"] == 35
    assert exact["crs"]["curse"] == 94
    assert exact["crs"]["mcurse"] == 118
    assert exact["slw"]["slow"] == 559
    assert exact["slw"]["mslow"] == 346

    # Normal selectable casts now provide an independent identity discriminator. Cost is
    # still not universal identity: the complete ambiguous same-cost sets are digest-pinned
    # below, while unique same-source exact-cost rows resolve only the expected families.
    assert wire["cast_or_ability_records"] == {"crs": 79, "slw": 430, "sff": 77, "ray": 406}
    assert wire["cast_or_ability_field2_shapes"] == {
        "crs": {"00": 15, "04": 59, "08": 5},
        "ray": {"00": 263, "01": 1, "05": 76, "07": 3, "10": 63},
        "sff": {"03": 2, "05": 14, "06": 55, "07": 6},
        "slw": {"04": 430},
    }
    assert wire["cast_or_ability_positive_field2"] == {"crs": 64, "slw": 430, "sff": 77, "ray": 143}
    assert wire["cast_or_ability_unique_exact_cost_names"] == {
        "crs": {"curse": 52, "mcurse": 5},
        "slw": {"slow": 261},
        "sff": {"suffering": 51},
        "ray": {"dray": 65, "mdray": 63},
    }
    assert _json_sha256(wire["cast_or_ability_records"]) == "a74f2d7d722d45ac456cda865b907a9cefb7a2c69bb194839e90c874feb26d19"
    assert _json_sha256(wire["cast_or_ability_field2_shapes"]) == "45b9500c95015078672ec0cff543aadaa935769a6447d46f70c00f79ad48734e"
    assert _json_sha256(wire["cast_or_ability_positive_field2"]) == "2e33caa01434dd5c933acf2b104c46fb307673144bcb6712a9b3efa87ed4b68c"
    assert _json_sha256(wire["cast_or_ability_exact_cost_name_sets"]) == "20d7b988ab42e34161f83c84c356f49a5ec8969666f79c9b2bb84352f52b68f6"
    assert _json_sha256(wire["cast_or_ability_unique_exact_cost_names"]) == "7ec8b8d3fd5670f9e37ab5143aa729f3582d611f84548870a644aff202061357"

    # The complete Hexing-bound population is a distinct zero-cost attack subset. Lock it
    # exactly without treating 15/115 as a probability and without declaring zero-cost
    # records semantically exact in replay merely because the source carries Hexing Attack.
    assert len(wire["hexing_attack_records"]) == 15
    assert wire["hexing_attack_field2_shapes"] == {
        "crs": {"00": 4},
        "slw": {"00": 3},
        "sff": {"00": 5},
        "ray": {"00": 3},
    }
    assert wire["hexing_attack_field3_shapes"] == {
        "crs": {"096": 1, "100": 3},
        "slw": {"040": 3},
        "sff": {"012": 5},
        "ray": {"006": 3},
    }
    assert wire["hexing_attack_field4_shapes"] == {
        "crs": {"1100": 1, "3400": 1, "5000": 2},
        "slw": {"0500": 1, "2600": 1, "5000": 1},
        "sff": {"2000": 1, "3600": 1, "4100": 2, "5000": 1},
        "ray": {"0000": 3},
    }
    assert _json_sha256(wire["hexing_attack_field2_shapes"]) == "6be9950008b044f8c4c24100b6c4cc3cf4247aab1f4acb260e711cb0f8d8a4b7"
    assert _json_sha256(wire["hexing_attack_field4_shapes"]) == "d156f9ae3d34779ed77ad3c81ae47e97a1d0d0ae725a3cd5e1c9e3cbe2432794"
    assert _json_sha256(wire["hexing_attack_field3_shapes"]) == "7027b9f0253a68114acf6d13c77838103cc42b51567610cc1151c74edcaba85b"
    assert _json_sha256(wire["hexing_attack_records"]) == "46541623c51538c75939a68e8b19cfeec8e63512194192e55d5a534193812579"

    for code in wire["candidate_codes"]:
        count = wire["records"][code]
        assert sum(wire["field2_shapes"][code].values()) == count
        assert sum(wire["field4_shapes"][code].values()) == count
        assert sum(wire["field3_shapes"][code].values()) == count
        assert sum(wire["action_types"][code].values()) == count
        assert wire["zero_field2"].get(code, 0) + wire["positive_field2"].get(code, 0) == count
        assert wire["hexing_attack_bound"].get(code, 0) + wire["nonhexing_attack_bound"].get(code, 0) == wire["attack_bound"].get(code, 0)

    warnings.warn(
        "HEXINGATTACK_WIRE_COLLISION_EVIDENCE "
        + json.dumps(wire, ensure_ascii=False, sort_keys=True)
    )


def test_shared_ray_status_decode_preserves_zero_cost_uncertainty():
    # Unique positive-cost normal-cast controls independently identify the shared `ray`
    # wire as the dray/mdray family. This regression deliberately does not use Hexing
    # tooltip wording or the 15/115 Hexing attack frequency as a semantic discriminator.
    for spell_name, cost in (("dray", 5), ("mdray", 10)):
        actor = _ray_entity(
            1,
            1,
            mana=20,
            abilities=["hero", "caster"],
            magic_blob=f"{spell_name}-{cost}-0-1-0-0-0",
        )
        target = _ray_entity(2, 2)
        entities = {1: actor, 2: target}
        raw = f"Sray001002{cost:02d}0600006"
        commands = parse_commands(raw)

        assert len(commands) == 1
        command = commands[0]
        assert command.opcode == "SPECIAL"
        assert command.code == "ray"
        assert command.actor_uid == 1
        assert command.target_uid == 2
        assert command.value == float(cost)
        assert command.duration == 6
        assert command.amount == 6
        assert _decision_semantic_unresolved_flags(commands, entities, 1) == [False]

        _apply_command(entities, command)
        assert target.effects == {"ray": raw}
        assert actor.effects == {}
        assert actor.mana == 20 - cost

    # Hexing attack-bound ray rows are standalone zero-cost records. Structural target
    # decode is useful observed state, but decision semantics must stay unresolved and no
    # mana can be consumed merely because the wire family is known.
    actor = _ray_entity(
        1,
        1,
        mana=20,
        abilities=["caster", "hexingattack"],
        magic_blob="dray-5-0-1-0-0-0",
    )
    target = _ray_entity(2, 2)
    entities = {1: actor, 2: target}
    raw = "Sray001002000600006"
    commands = parse_commands(raw)
    assert len(commands) == 1
    command = commands[0]
    assert command.target_uid == 2
    assert command.value == 0.0
    assert command.duration == 6
    assert command.amount == 6
    assert _decision_semantic_unresolved_flags(commands, entities, 1) == [True]

    _apply_command(entities, command)
    assert target.effects == {"ray": raw}
    assert actor.effects == {}
    assert actor.mana == 20

    # A same-cost but non-dray source spellbook must not make a positive ray record exact
    # or spend mana. Structural decoding remains separate from spell identity.
    actor = _ray_entity(
        1,
        1,
        mana=20,
        abilities=["hero", "caster"],
        magic_blob="magicfist-5-0-1-0-0-0",
    )
    target = _ray_entity(2, 2)
    entities = {1: actor, 2: target}
    raw = "Sray001002050600006"
    commands = parse_commands(raw)
    command = commands[0]
    assert command.target_uid == 2
    assert _decision_semantic_unresolved_flags(commands, entities, 1) == [True]
    _apply_command(entities, command)
    assert target.effects == {"ray": raw}
    assert actor.mana == 20
