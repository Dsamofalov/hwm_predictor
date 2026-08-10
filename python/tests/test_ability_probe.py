from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ability_probe", ROOT / "scripts" / "ability_probe.py")
assert SPEC and SPEC.loader
ability_probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ability_probe)


def test_ability_probe_exposes_target_state_deltas():
    before = [
        {
            "uid": 1,
            "owner": 1,
            "creature_id": 10,
            "alive": True,
            "count": 4,
            "max_hp": 20,
            "top_hp": 20,
            "mana": 0,
            "speed": 6,
            "initiative": 10,
            "atb": 100,
            "x": 1,
            "y": 1,
            "abilities": ["samplecontrol"],
            "effects": [],
        },
        {
            "uid": 2,
            "owner": 2,
            "creature_id": 20,
            "alive": True,
            "count": 3,
            "max_hp": 30,
            "top_hp": 25,
            "mana": 0,
            "speed": 8,
            "initiative": 12,
            "atb": 500,
            "x": 4,
            "y": 4,
            "abilities": [],
            "effects": [{"id": "old"}],
        },
    ]
    after = [
        dict(before[0]),
        {
            **before[1],
            "count": 2,
            "top_hp": 15,
            "speed": 4,
            "initiative": 8.4,
            "atb": 250,
            "x": 5,
            "effects": [{"id": "new"}],
        },
    ]
    decision = {
        "battle_id": "1",
        "decision_index": 2,
        "server_turn": 3,
        "actor_uid": 1,
        "action_type": "MELEE_ATTACK",
        "target_uid": 2,
        "special_codes": ["wnd"],
        "raw_opcodes": ["MOVE", "DAMAGE", "SPECIAL", "STATE"],
        "semantic_unresolved_opcodes": [],
        "raw": "synthetic",
        "state_before": before,
        "state_after": after,
    }

    report = ability_probe.analyze_decisions([decision], "samplecontrol", row_limit=10)
    assert report["matched_decisions"] == 1
    assert report["candidate_decisions"] == 1
    assert report["special_codes"] == {"wnd": 1}
    assert report["target_deltas"]["count"] == {"-1": 1}
    assert report["target_deltas"]["total_hp"] == {"-40": 1}
    assert report["target_deltas"]["speed"] == {"-4.0": 1}
    assert report["target_deltas"]["initiative"] == {"-3.5999999999999996": 1}
    assert report["target_deltas"]["atb"] == {"-250.0": 1}
    assert report["target_deltas"]["position"] == {"1,0": 1}
    assert report["target_deltas"]["effects_added"] == {"new": 1}
    assert report["target_deltas"]["effects_removed"] == {"old": 1}
    row = report["rows"][0]
    assert row["target_delta"]["count"] == -1
    assert row["target_delta"]["total_hp"] == -40
    assert row["target_delta"]["position_before"] == [4, 4]
    assert row["target_delta"]["position_after"] == [5, 4]
