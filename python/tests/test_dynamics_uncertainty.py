from __future__ import annotations

import numpy as np
import pytest

from hwm_solver.evaluation.dynamics_uncertainty import (
    _rankdata,
    _stable_mean,
    _stable_std,
    calibration_bins,
    roc_auc,
    spearman,
    summarize,
)


def test_rankdata_averages_ties():
    ranks = _rankdata(np.asarray([10.0, 20.0, 20.0, 40.0]))
    assert ranks.tolist() == pytest.approx([1.0, 2.5, 2.5, 4.0])


def test_spearman_tracks_monotonic_order():
    x = np.asarray([1.0, 2.0, 3.0, 4.0])
    assert spearman(x, x) == pytest.approx(1.0)
    assert spearman(x, x[::-1]) == pytest.approx(-1.0)


def test_roc_auc_perfect_separation():
    scores = np.asarray([0.1, 0.2, 0.9, 1.0])
    labels = np.asarray([0, 0, 1, 1])
    assert roc_auc(scores, labels) == pytest.approx(1.0)


def test_calibration_bins_preserve_rows_and_order():
    rows = [
        {
            "disagreement": float(i),
            "ensemble_l1": float(i + 1),
            "generic_l1": 2.0,
            "ensemble_invalid_fraction": float(i) / 10.0,
            "generic_invalid_fraction": 0.1,
        }
        for i in range(10)
    ]
    bins = calibration_bins(rows, bins=5)
    assert sum(x["count"] for x in bins) == len(rows)
    assert bins[0]["disagreement_max"] < bins[-1]["disagreement_min"]
    assert bins[-1]["mean_ensemble_force_l1"] > bins[0]["mean_ensemble_force_l1"]


def test_summarize_reports_predictive_uncertainty():
    rows = []
    for i in range(20):
        disagreement = i / 20.0
        rows.append(
            {
                "disagreement": disagreement,
                "ensemble_l1": disagreement + 0.01,
                "generic_l1": 0.4,
                "ensemble_invalid_fraction": disagreement,
                "generic_invalid_fraction": 0.1,
            }
        )
    out = summarize(rows, bins=4)
    assert out["spearman_disagreement_vs_ensemble_l1"] > 0.99
    assert out["spearman_disagreement_vs_invalid_action_fraction"] > 0.99
    assert out["low_to_high_bin_error_ratio"] > 1.0
    assert out["low_to_high_bin_invalid_ratio"] > 1.0


def test_stable_moments_do_not_invent_disagreement_for_identical_members():
    value = 0.123456789012345
    members = [value] * 5
    assert _stable_mean(members) == value
    assert _stable_std(members) == 0.0


def test_summarize_treats_sub_epsilon_error_as_numerical_tie():
    rows = [
        {
            "disagreement": float(i),
            "ensemble_l1": 0.25 + 5e-13,
            "generic_l1": 0.25,
            "ensemble_invalid_fraction": 0.0,
            "generic_invalid_fraction": 0.0,
        }
        for i in range(20)
    ]
    out = summarize(rows, bins=4)
    assert out["learned_worse_than_generic_rate"] == 0.0
    assert out["auc_disagreement_flags_learned_worse_than_generic"] == 0.5
    assert all(x["ensemble_better_than_generic_rate"] == 0.0 for x in out["bins"])
