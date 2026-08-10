from __future__ import annotations

import math

import pytest

from hwm_solver.evaluation import dynamics_temperature_gate as tg


class _Profile:
    def __init__(self, multiplier: float):
        self.value = multiplier

    def multiplier(self, _action_type: str, _creature_id: int) -> float:
        return self.value


def test_positive_temperature_zero_removes_only_positive_correction():
    assert tg.PositiveTemperedProfile(_Profile(2.0), 0.0).multiplier("MELEE_ATTACK", 1) == pytest.approx(1.0)
    assert tg.PositiveTemperedProfile(_Profile(0.5), 0.0).multiplier("MELEE_ATTACK", 1) == pytest.approx(0.5)


def test_positive_temperature_one_preserves_profile():
    assert tg.PositiveTemperedProfile(_Profile(2.0), 1.0).multiplier("MELEE_ATTACK", 1) == pytest.approx(2.0)
    assert tg.PositiveTemperedProfile(_Profile(0.5), 1.0).multiplier("MELEE_ATTACK", 1) == pytest.approx(0.5)


def test_positive_temperature_half_scales_in_log_space():
    got = tg.PositiveTemperedProfile(_Profile(4.0), 0.5).multiplier("MELEE_ATTACK", 1)
    assert got == pytest.approx(2.0)
    assert math.isfinite(got)


def _report(*, l1_ratio: float, coverage_delta: float, l1_ok: bool = True) -> dict:
    return {
        "summary": {
            "mean_l1_ratio_learned_over_generic": l1_ratio,
            "min_valid_action_coverage_delta_learned_minus_generic": coverage_delta,
            "coverage_not_below_generic_at_all_horizons": coverage_delta >= 0.0,
            "l1_better_than_generic_at_all_horizons": l1_ok,
        }
    }


def test_choose_scale_prefers_best_feasible_l1():
    calibration = {
        "0.0": _report(l1_ratio=0.80, coverage_delta=0.002),
        "0.5": _report(l1_ratio=0.70, coverage_delta=0.001),
        "1.0": _report(l1_ratio=0.65, coverage_delta=-0.001),
    }
    scale, reason = tg.choose_scale(calibration)
    assert scale == pytest.approx(0.5)
    assert reason == "calibration_feasible"


def test_choose_scale_without_feasible_candidate_preserves_coverage_first():
    calibration = {
        "0.0": _report(l1_ratio=0.90, coverage_delta=-0.001),
        "0.5": _report(l1_ratio=0.70, coverage_delta=-0.003),
        "1.0": _report(l1_ratio=0.60, coverage_delta=-0.010),
    }
    scale, reason = tg.choose_scale(calibration)
    assert scale == pytest.approx(0.0)
    assert reason == "no_calibration_candidate_passed_hard_gate"
