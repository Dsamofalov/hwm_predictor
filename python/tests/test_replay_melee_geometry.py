from __future__ import annotations

from pathlib import Path

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
