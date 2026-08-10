from __future__ import annotations

import math
from pathlib import Path

import pytest

from hwm_solver.evaluation import dynamics_multistep as dm


def _entity(uid: int, total_hp: int, *, max_hp: int = 10, creature_id: int = 1) -> dict:
    count = 0 if total_hp <= 0 else math.ceil(total_hp / max_hp)
    top = 0 if total_hp <= 0 else total_hp - (count - 1) * max_hp
    return {
        "uid": uid,
        "creature_id": creature_id,
        "owner": 1 if uid == 1 else 2,
        "count": count,
        "max_count": 10,
        "top_hp": top,
        "max_hp": max_hp,
        "alive": total_hp > 0,
        "attack": 10,
        "defense": 10,
        "min_damage": 1,
        "max_damage": 1,
        "speed": 5,
        "initiative": 10,
        "x": uid,
        "y": 1,
        "shots": 0,
        "abilities": [],
        "effects": [],
    }


def test_patch_entity_hp_roundtrip():
    e = _entity(2, 10)
    patched = dm._patch_entity_hp(e, 25.0)
    assert patched["count"] == 3
    assert patched["top_hp"] == pytest.approx(5.0)
    assert dm.hp_equivalent(patched) == pytest.approx(25.0)


def test_fit_battle_jackknife_ensemble():
    samples = []
    for battle_id in range(1, 11):
        samples.append(
            {
                "battle_id": battle_id,
                "action_type": "MELEE_ATTACK",
                "creature_id": 7,
                "log_ratio": math.log(1.0 + battle_id / 100.0),
            }
        )
    ensemble = dm.fit_battle_jackknife_ensemble(samples, members=5, shrinkage=2.0)
    assert len(ensemble) == 5
    multipliers = [m.multiplier("MELEE_ATTACK", 7) for m in ensemble]
    assert all(math.isfinite(x) and x > 0 for x in multipliers)
    assert len({round(x, 8) for x in multipliers}) > 1


def test_advance_damage_chain_replaces_observed_primary_damage(monkeypatch):
    before = [_entity(1, 20), _entity(2, 20)]
    after = [_entity(1, 20), _entity(2, 15)]
    row = {"state_before": before, "state_after": after}
    predicted = dm._hp_map(before)
    monkeypatch.setattr(
        dm,
        "_primary_damage_prediction",
        lambda _r, _p, _m: dm.DamagePrediction(5, 2, 7.0),
    )
    result = dm.advance_damage_chain(row, predicted, None)
    assert result.modeled
    assert not result.predicted_invalid_action
    assert predicted[1] == pytest.approx(20.0)
    assert predicted[2] == pytest.approx(13.0)


def test_invalid_predicted_action_does_not_teacher_force_primary_damage(monkeypatch):
    before = [_entity(1, 20), _entity(2, 20)]
    after = [_entity(1, 20), _entity(2, 15)]
    row = {"state_before": before, "state_after": after}
    predicted = dm._hp_map(before)
    monkeypatch.setattr(
        dm,
        "_primary_damage_prediction",
        lambda _r, _p, _m: dm.DamagePrediction(5, 2, None),
    )
    result = dm.advance_damage_chain(row, predicted, None)
    assert result.modeled
    assert result.predicted_invalid_action
    assert predicted[2] == pytest.approx(20.0)


def test_evaluate_battles_emits_requested_horizons(monkeypatch):
    decisions = []
    hp = 20
    for _ in range(4):
        before = [_entity(1, 20), _entity(2, hp)]
        hp -= 1
        after = [_entity(1, 20), _entity(2, hp)]
        decisions.append({"state_before": before, "state_after": after})

    monkeypatch.setattr(dm, "_rows", lambda _battle: list(decisions))

    def fake_advance(row, predicted, profile):
        before = dm._hp_map(row["state_before"])
        after = dm._hp_map(row["state_after"])
        for uid in set(before) | set(after):
            predicted[uid] = (
                predicted.get(uid, before.get(uid, 0.0))
                + after.get(uid, 0.0)
                - before.get(uid, 0.0)
            )
        return dm.AdvanceResult(True, False)

    monkeypatch.setattr(dm, "advance_damage_chain", fake_advance)
    profile = dm.ResidualProfile({}, {})
    report = dm.evaluate_battles([Path("dummy")], [profile, profile, profile], horizons=(2, 4))
    assert report["2"]["windows"] == 3
    assert report["4"]["windows"] == 1
    assert report["2"]["ensemble_mean_force_l1"] == pytest.approx(0.0)
    assert report["4"]["alive_mismatch_rate"] == pytest.approx(0.0)
    assert report["4"]["ensemble_mean_invalid_action_fraction"] == pytest.approx(0.0)
