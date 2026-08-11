from __future__ import annotations

from pathlib import Path

from hwm_solver.evaluation.legal_coverage import supports_observed
from hwm_solver.protocol.replay import iter_battle_decisions


ROOT = Path(__file__).resolve().parents[2]


def _cells(entity: dict) -> set[tuple[int, int]]:
    if not entity.get("alive", True) or entity.get("is_hero") or entity.get("is_hidden", False):
        return set()
    size = 2 if "big" in set(entity.get("abilities", [])) else 1
    x, y = int(entity["x"]), int(entity["y"])
    return {(x + dx, y + dy) for dx in range(size) for dy in range(size)}


def test_unique_one_cell_melee_hint_is_canonicalized_consistently():
    battle = ROOT / "hwm_battles" / "battles" / "1631502382"
    rows = list(iter_battle_decisions(battle))
    row = rows[116]

    assert row["actor_uid"] == 20
    assert row["action_type"] == "MELEE_ATTACK"
    assert row["special_codes"] == []
    assert (row["destination_x"], row["destination_y"]) == (12, 20)

    by_uid = {int(entity["uid"]): entity for entity in row["state_after"]}
    assert (by_uid[20]["x"], by_uid[20]["y"]) == (12, 20)
    assert not (_cells(by_uid[20]) & _cells(by_uid[18]))


def test_far_special_free_melee_hint_is_not_reinterpreted_generically():
    battle = ROOT / "hwm_battles" / "battles" / "1635145851"
    rows = list(iter_battle_decisions(battle))
    row = rows[6]

    assert row["actor_uid"] == 3
    assert row["action_type"] == "MELEE_ATTACK"
    assert row["special_codes"] == []
    # The only ordinary-geometry landing is three cells away from this raw hint.  It is
    # deliberately left untouched because this creature has movement mechanics whose
    # semantics belong outside the generic decoder.
    assert (row["destination_x"], row["destination_y"]) == (11, 5)


def test_shooter_collision_marker_keeps_stationary_melee_anchor():
    battle = ROOT / "hwm_battles" / "battles" / "1626319743"
    row = list(iter_battle_decisions(battle))[110]
    assert row["actor_uid"] == 24
    assert row["action_type"] == "MELEE_ATTACK"
    assert row["special_codes"] == []
    assert (row["destination_x"], row["destination_y"]) == (1, 2)
    by_uid = {int(entity["uid"]): entity for entity in row["state_after"]}
    assert (by_uid[24]["x"], by_uid[24]["y"]) == (1, 2)
    assert not (_cells(by_uid[24]) & _cells(by_uid[23]))


def test_impossible_shooter_move_marker_can_recover_ranged_attack():
    battle = ROOT / "hwm_battles" / "battles" / "1632012084"
    row = list(iter_battle_decisions(battle))[77]
    assert row["actor_uid"] == 16
    assert row["action_type"] == "RANGED_ATTACK"
    assert row["special_codes"] == []
    assert row["destination_x"] is None and row["destination_y"] is None
    by_uid = {int(entity["uid"]): entity for entity in row["state_after"]}
    assert (by_uid[16]["x"], by_uid[16]["y"]) == (1, 1)


def test_stationary_shooter_marker_closes_heldout_melee_false_negative():
    battle = ROOT / "hwm_battles" / "battles" / "1632715976"
    row = list(iter_battle_decisions(battle))[102]
    assert row["actor_uid"] == 13
    assert row["action_type"] == "MELEE_ATTACK"
    assert row["special_codes"] == []
    assert (row["destination_x"], row["destination_y"]) == (11, 4)
    by_uid = {int(entity["uid"]): entity for entity in row["state_after"]}
    assert (by_uid[13]["x"], by_uid[13]["y"]) == (11, 4)
    assert not (_cells(by_uid[13]) & _cells(by_uid[21]))


def test_unique_near_raw_landing_recovers_observed_melee_actions():
    cases = [
        ("1632715976", 92, 13, (10, 3)),
        ("1633140429", 27, 14, (7, 3)),
        ("1633877663", 55, 11, (11, 10)),
        ("1633879731", 29, 18, (10, 9)),
        ("1633884421", 60, 22, (3, 19)),
        ("1633884421", 71, 22, (1, 20)),
    ]
    for battle_id, index, actor_uid, destination in cases:
        battle = ROOT / "hwm_battles" / "battles" / battle_id
        row = list(iter_battle_decisions(battle))[index]
        assert row["actor_uid"] == actor_uid
        assert row["action_type"] == "MELEE_ATTACK"
        assert row["special_codes"] == []
        assert (row["destination_x"], row["destination_y"]) == destination
        ok, reason = supports_observed(row)
        assert ok, (battle_id, index, reason)
