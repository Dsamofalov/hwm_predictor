from __future__ import annotations

import pytest

from hwm_solver.evaluation import dynamics_survival_gate as sg


def _entity(uid: int, *, accuracy: bool = False) -> dict:
    return {
        "uid": uid,
        "creature_id": uid,
        "owner": 1 if uid == 1 else 2,
        "count": 2,
        "max_count": 2,
        "top_hp": 10,
        "max_hp": 10,
        "hp": 10,
        "alive": True,
        "x": uid,
        "y": 1,
        "attack": 10,
        "defense": 10,
        "min_damage": 2,
        "max_damage": 6,
        "shots": 0,
        "abilities": ["accuracy"] if accuracy else [],
        "effects": [],
        "effect_values": {},
    }


def _row(actor: dict | None = None, target: dict | None = None) -> dict:
    actor = actor or _entity(1)
    target = target or _entity(2)
    return {
        "action_type": "MELEE_ATTACK",
        "actor_uid": 1,
        "target_uid": 2,
        "destination_x": actor["x"],
        "destination_y": actor["y"],
        "state_before": [actor, target],
        "state_after": [actor, target],
        "raw": "",
    }


def test_sampled_expected_damage_orders_uniform_quantiles():
    actor, target = _entity(1), _entity(2)
    row = _row(actor, target)
    low = sg._sampled_expected_damage(row, actor, target, 0.0)
    mid = sg._sampled_expected_damage(row, actor, target, 0.5)
    high = sg._sampled_expected_damage(row, actor, target, 1.0)
    assert low < mid < high


def test_midpoint_sample_matches_training_expected_damage():
    actor, target = _entity(1), _entity(2)
    row = _row(actor, target)
    from hwm_solver.models.train_damage_model import _expected_damage

    assert sg._sampled_expected_damage(row, actor, target, 0.5) == pytest.approx(
        _expected_damage(row, actor, target)
    )


def test_accuracy_forces_max_damage_independent_of_quantile():
    actor, target = _entity(1, accuracy=True), _entity(2)
    row = _row(actor, target)
    assert sg._sampled_expected_damage(row, actor, target, 0.0) == pytest.approx(
        sg._sampled_expected_damage(row, actor, target, 1.0)
    )


def test_trajectory_mean_averages_hp_maps():
    assert sg._trajectory_mean([{1: 10.0, 2: 0.0}, {1: 6.0, 2: 4.0}]) == {
        1: pytest.approx(8.0),
        2: pytest.approx(2.0),
    }
