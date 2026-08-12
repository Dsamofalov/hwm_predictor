from __future__ import annotations

import numpy as np

from hwm_solver.evaluation import dynamics_selector as ds


def _examples() -> list[dict]:
    rows: list[dict] = []
    for i in range(31):
        x = i / 30.0
        rows.append(
            {
                "features": np.asarray(
                    [x, x * x, 1.0 - x, x / 3.0, 0.25 + x / 7.0, float(i % 2)],
                    dtype=np.float64,
                ),
                "generic_error": 0.12 + 0.2 * (1.0 - x),
                "ensemble_error": 0.12 + 0.2 * x,
                "learned_worse": float(x > 0.5),
            }
        )
    return rows


def test_fitted_selector_weights_use_canonical_evidence_precision():
    _mean, _scale, weights = ds.fit_logistic_selector(
        _examples(), l2=0.25, steps=200, learning_rate=0.05
    )
    assert weights.tolist() == [
        round(float(value), ds.SELECTOR_CANONICAL_DECIMALS) for value in weights
    ]


def test_selector_probability_uses_same_canonical_precision_boundary():
    mean, scale, weights = ds.fit_logistic_selector(
        _examples(), l2=0.25, steps=200, learning_rate=0.05
    )
    model = ds.SelectorModel(mean, scale, weights, threshold=0.5)
    probability = model.probability_learned_worse(_examples()[11]["features"])
    assert probability == round(probability, ds.SELECTOR_CANONICAL_DECIMALS)


def test_canonicalization_absorbs_binary64_tail_noise():
    base = 0.3141592653589793
    perturbed = np.nextafter(base, np.inf)
    assert base != perturbed
    assert ds._canonical_selector_float(base) == ds._canonical_selector_float(perturbed)
