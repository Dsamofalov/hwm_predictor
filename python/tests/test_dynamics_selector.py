from __future__ import annotations

import math

import numpy as np
import pytest

from hwm_solver.evaluation import dynamics_selector as ds


def _examples() -> list[dict]:
    rows = []
    for i in range(40):
        x = i / 39.0
        learned_worse = float(x > 0.5)
        rows.append(
            {
                "features": np.asarray([x, 0.0, 0.0, 0.0, 0.0, 0.0]),
                "generic_error": 0.1 if learned_worse else 0.4,
                "ensemble_error": 0.4 if learned_worse else 0.1,
                "learned_worse": learned_worse,
            }
        )
    return rows


def test_fit_logistic_selector_learns_separable_risk():
    rows = _examples()
    mean, scale, weights = ds.fit_logistic_selector(
        rows, l2=0.0, steps=1200, learning_rate=0.1
    )
    model = ds.SelectorModel(mean, scale, weights, 0.5)
    low = model.probability_learned_worse(rows[2]["features"])
    high = model.probability_learned_worse(rows[-3]["features"])
    assert low < 0.2
    assert high > 0.8


def test_choose_threshold_improves_synthetic_selection():
    rows = _examples()
    mean, scale, weights = ds.fit_logistic_selector(
        rows, l2=0.0, steps=1200, learning_rate=0.1
    )
    threshold, calibration = ds.choose_threshold(rows, mean, scale, weights)
    model = ds.SelectorModel(mean, scale, weights, threshold)
    metrics = ds.one_step_metrics(rows, model)
    assert calibration["mean_abs_log_error"] < 0.15
    assert metrics["selector_mean_abs_log_error"] < metrics["generic_mean_abs_log_error"]
    assert metrics["selector_mean_abs_log_error"] < metrics["ensemble_mean_abs_log_error"]
    assert 0.0 < metrics["selector_generic_usage_rate"] < 1.0


def test_support_counts_group_by_action_and_creature():
    rows = [
        {"action_type": "MELEE_ATTACK", "creature_id": 7},
        {"action_type": "MELEE_ATTACK", "creature_id": 7},
        {"action_type": "RANGED_ATTACK", "creature_id": 7},
    ]
    counts = ds._support_counts(rows)
    assert counts[("MELEE_ATTACK", 7)] == 2
    assert counts[("RANGED_ATTACK", 7)] == 1


def test_safe_abs_log_error_is_zero_on_exact_match():
    assert ds._safe_abs_log_error(12.0, 12.0) == pytest.approx(0.0)
    assert math.isfinite(ds._safe_abs_log_error(0.0, 12.0))
