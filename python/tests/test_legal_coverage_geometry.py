from __future__ import annotations

from hwm_solver.evaluation.legal_coverage import (
    _bounds,
    _can_place,
    _canonical_observed_destination,
    _reachable,
)


def _actor(*, big: bool = False) -> dict:
    abilities = ["big"] if big else []
    return {
        "uid": 1,
        "owner": 1,
        "creature_id": 1,
        "x": 6,
        "y": 10,
        "speed": 5,
        "alive": True,
        "is_hero": False,
        "is_hidden": False,
        "abilities": abilities,
        "rune_speed_active": False,
    }


def _blocker(uid: int, x: int, y: int) -> dict:
    return {
        "uid": uid,
        "owner": 2,
        "creature_id": uid,
        "x": x,
        "y": y,
        "speed": 0,
        "alive": True,
        "is_hero": False,
        "is_hidden": False,
        "abilities": [],
        "rune_speed_active": False,
    }


def test_protocol_board_bounds_are_fixed_12_by_20():
    actor = _actor()
    assert _bounds([actor]) == (1, 1, 12, 20)


def test_reachability_does_not_shrink_to_current_occupancy():
    actor = _actor()
    reachable = _reachable([actor], actor)
    assert (6, 15) in reachable


def test_big_stack_may_anchor_at_bottom_right_footprint_boundary():
    actor = _actor(big=True)
    bounds = _bounds([actor])
    assert _can_place([actor], actor, (11, 19), bounds)
    assert not _can_place([actor], actor, (12, 20), bounds)


def test_big_stack_raw_cell_is_reinterpreted_only_when_direct_anchor_is_blocked():
    actor = _actor(big=True)
    actor["x"], actor["y"] = 5, 5
    blocker = _blocker(2, 8, 7)
    state = [actor, blocker]

    assert _canonical_observed_destination(state, actor, (7, 7)) == (6, 6)
    assert _canonical_observed_destination(state, actor, (4, 4)) == (4, 4)
