from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hwm_solver.evaluation.dynamics_multistep import (
    DEFAULT_HORIZONS,
    DamagePrediction,
    _collect,
    _hp_map,
    _primary_damage_prediction,
    _rows,
    _window_error,
    fit_battle_jackknife_ensemble,
)

FEATURE_NAMES = (
    "log1p_creature_action_support",
    "relative_ensemble_disagreement",
    "absolute_log_residual_correction",
    "signed_log_residual_correction",
    "generic_lethality_ratio",
    "is_ranged_attack",
)


@dataclass(frozen=True)
class SelectorModel:
    mean: np.ndarray
    scale: np.ndarray
    weights: np.ndarray
    threshold: float

    def probability_learned_worse(self, features: np.ndarray) -> float:
        z = (np.asarray(features, dtype=np.float64) - self.mean) / self.scale
        logit = float(self.weights[0] + np.dot(self.weights[1:], z))
        logit = max(-40.0, min(40.0, logit))
        return 1.0 / (1.0 + math.exp(-logit))

    def choose_generic(self, features: np.ndarray) -> bool:
        return self.probability_learned_worse(features) >= self.threshold


@dataclass(frozen=True)
class CandidatePrediction:
    observed_damage: int
    target_uid: int
    generic_damage: float | None
    ensemble_damage: float | None
    features: np.ndarray | None


def _support_counts(samples: list[dict]) -> Counter[tuple[str, int]]:
    return Counter((str(r["action_type"]), int(r["creature_id"])) for r in samples)


def _safe_abs_log_error(predicted: float, observed: float) -> float:
    return abs(math.log(max(1e-6, predicted) / max(1e-6, observed)))


def _feature_vector(
    row: dict,
    predicted_hp: dict[int, float],
    generic_damage: float,
    member_damage: list[float],
    support: Counter[tuple[str, int]],
) -> np.ndarray:
    state = row["state_before"]
    by_uid = {int(e["uid"]): e for e in state}
    actor = by_uid[int(row["actor_uid"])]
    target_uid = int(row["target_uid"])
    creature_id = int(actor.get("creature_id", 0))
    n = support[(str(row["action_type"]), creature_id)]
    ensemble_mean = float(np.mean(member_damage))
    ensemble_std = float(np.std(member_damage))
    relative_disagreement = ensemble_std / max(1e-6, ensemble_mean)
    signed_correction = math.log(max(1e-6, ensemble_mean) / max(1e-6, generic_damage))
    target_hp = max(1e-6, predicted_hp.get(target_uid, _hp_map(state).get(target_uid, 0.0)))
    return np.asarray(
        [
            math.log1p(n),
            relative_disagreement,
            abs(signed_correction),
            signed_correction,
            generic_damage / target_hp,
            1.0 if row["action_type"] == "RANGED_ATTACK" else 0.0,
        ],
        dtype=np.float64,
    )


def candidate_prediction(
    row: dict,
    predicted_hp: dict[int, float],
    ensemble: list,
    support: Counter[tuple[str, int]],
) -> CandidatePrediction | None:
    generic = _primary_damage_prediction(row, predicted_hp, None)
    if generic is None:
        return None
    if generic.predicted_damage is None:
        return CandidatePrediction(
            generic.observed_damage,
            generic.target_uid,
            None,
            None,
            None,
        )
    member_damage: list[float] = []
    for profile in ensemble:
        p = _primary_damage_prediction(row, predicted_hp, profile)
        if p is None or p.predicted_damage is None:
            return CandidatePrediction(
                generic.observed_damage,
                generic.target_uid,
                generic.predicted_damage,
                None,
                None,
            )
        member_damage.append(float(p.predicted_damage))
    ensemble_damage = float(np.mean(member_damage))
    features = _feature_vector(
        row,
        predicted_hp,
        float(generic.predicted_damage),
        member_damage,
        support,
    )
    return CandidatePrediction(
        generic.observed_damage,
        generic.target_uid,
        float(generic.predicted_damage),
        ensemble_damage,
        features,
    )


def one_step_examples(
    battles: list[Path], ensemble: list, support: Counter[tuple[str, int]]
) -> list[dict]:
    out: list[dict] = []
    for battle in battles:
        for row in _rows(battle):
            predicted_hp = _hp_map(row["state_before"])
            cand = candidate_prediction(row, predicted_hp, ensemble, support)
            if (
                cand is None
                or cand.generic_damage is None
                or cand.ensemble_damage is None
                or cand.features is None
                or cand.observed_damage <= 0
            ):
                continue
            generic_error = _safe_abs_log_error(cand.generic_damage, cand.observed_damage)
            ensemble_error = _safe_abs_log_error(cand.ensemble_damage, cand.observed_damage)
            out.append(
                {
                    "battle_id": int(battle.name),
                    "features": cand.features,
                    "generic_error": generic_error,
                    "ensemble_error": ensemble_error,
                    "learned_worse": float(ensemble_error > generic_error),
                }
            )
    return out


def fit_logistic_selector(
    examples: list[dict], *, l2: float = 0.5, steps: int = 800, learning_rate: float = 0.05
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if not examples:
        raise ValueError("selector calibration examples are empty")
    x = np.vstack([r["features"] for r in examples]).astype(np.float64)
    y = np.asarray([r["learned_worse"] for r in examples], dtype=np.float64)
    mean = np.mean(x, axis=0)
    scale = np.std(x, axis=0)
    scale = np.where(scale > 1e-9, scale, 1.0)
    z = (x - mean) / scale
    design = np.column_stack([np.ones(len(z)), z])
    weights = np.zeros(design.shape[1], dtype=np.float64)
    for _ in range(steps):
        logits = np.clip(design @ weights, -40.0, 40.0)
        probs = 1.0 / (1.0 + np.exp(-logits))
        grad = design.T @ (probs - y) / len(y)
        grad[1:] += l2 * weights[1:] / len(y)
        weights -= learning_rate * grad
    return mean, scale, weights


def choose_threshold(
    examples: list[dict], mean: np.ndarray, scale: np.ndarray, weights: np.ndarray
) -> tuple[float, dict]:
    provisional = SelectorModel(mean, scale, weights, 0.5)
    probs = np.asarray(
        [provisional.probability_learned_worse(r["features"]) for r in examples],
        dtype=np.float64,
    )
    generic_error = np.asarray([r["generic_error"] for r in examples], dtype=np.float64)
    ensemble_error = np.asarray([r["ensemble_error"] for r in examples], dtype=np.float64)
    candidates = sorted(
        set([0.0, 1.0] + [float(x) for x in np.quantile(probs, np.linspace(0.0, 1.0, 101))])
    )
    best: tuple[float, float, float] | None = None
    best_threshold = 1.0
    for threshold in candidates:
        use_generic = probs >= threshold
        selected = np.where(use_generic, generic_error, ensemble_error)
        mean_error = float(np.mean(selected))
        generic_rate = float(np.mean(use_generic))
        key = (mean_error, generic_rate, threshold)
        if best is None or key < best:
            best = key
            best_threshold = threshold
    assert best is not None
    return best_threshold, {
        "mean_abs_log_error": best[0],
        "generic_usage_rate": best[1],
        "threshold": best_threshold,
    }


def fit_selector(examples: list[dict]) -> tuple[SelectorModel, dict]:
    mean, scale, weights = fit_logistic_selector(examples)
    threshold, calibration = choose_threshold(examples, mean, scale, weights)
    return SelectorModel(mean, scale, weights, threshold), calibration


def one_step_metrics(examples: list[dict], selector: SelectorModel) -> dict:
    if not examples:
        return {"samples": 0}
    generic = np.asarray([r["generic_error"] for r in examples], dtype=np.float64)
    ensemble = np.asarray([r["ensemble_error"] for r in examples], dtype=np.float64)
    use_generic = np.asarray(
        [selector.choose_generic(r["features"]) for r in examples], dtype=bool
    )
    selected = np.where(use_generic, generic, ensemble)
    y = np.asarray([r["learned_worse"] for r in examples], dtype=np.int8)
    p = np.asarray(
        [selector.probability_learned_worse(r["features"]) for r in examples],
        dtype=np.float64,
    )
    from hwm_solver.evaluation.dynamics_uncertainty import roc_auc

    return {
        "samples": len(examples),
        "generic_mean_abs_log_error": float(np.mean(generic)),
        "ensemble_mean_abs_log_error": float(np.mean(ensemble)),
        "selector_mean_abs_log_error": float(np.mean(selected)),
        "selector_generic_usage_rate": float(np.mean(use_generic)),
        "selector_auc_learned_worse": float(roc_auc(p, y)),
    }


def _teacher_force_non_primary(
    row: dict,
    predicted_hp: dict[int, float],
    observed_damage: int | None,
    target_uid: int | None,
) -> None:
    before = _hp_map(row["state_before"])
    after = _hp_map(row["state_after"])
    for uid in set(before) | set(after) | set(predicted_hp):
        base = predicted_hp.get(uid, before.get(uid, 0.0))
        delta = after.get(uid, 0.0) - before.get(uid, 0.0)
        predicted_hp[uid] = max(0.0, base + delta)
    if observed_damage is not None and target_uid is not None:
        predicted_hp[target_uid] = max(
            0.0, predicted_hp.get(target_uid, 0.0) + float(observed_damage)
        )


def advance_policy_chain(
    row: dict,
    predicted_hp: dict[int, float],
    ensemble: list,
    support: Counter[tuple[str, int]],
    policy: str | SelectorModel,
) -> tuple[bool, bool, bool]:
    cand = candidate_prediction(row, predicted_hp, ensemble, support)
    if cand is None:
        _teacher_force_non_primary(row, predicted_hp, None, None)
        return False, False, False
    _teacher_force_non_primary(
        row, predicted_hp, cand.observed_damage, cand.target_uid
    )
    if cand.generic_damage is None or cand.ensemble_damage is None or cand.features is None:
        return True, True, False
    use_generic = policy == "generic"
    if isinstance(policy, SelectorModel):
        use_generic = policy.choose_generic(cand.features)
    damage = cand.generic_damage if use_generic else cand.ensemble_damage
    predicted_hp[cand.target_uid] = max(
        0.0, predicted_hp.get(cand.target_uid, 0.0) - float(damage)
    )
    return True, False, use_generic


def evaluate_multistep_policies(
    battles: list[Path],
    ensemble: list,
    support: Counter[tuple[str, int]],
    selector: SelectorModel,
    horizons: tuple[int, ...],
) -> dict:
    max_h = max(horizons)
    policies: dict[str, str | SelectorModel] = {
        "generic": "generic",
        "ensemble_mean": "ensemble",
        "selector": selector,
    }
    acc = {
        h: {
            name: {"l1": [], "invalid": [], "generic_usage": [], "modeled": []}
            for name in policies
        }
        for h in horizons
    }
    for battle in battles:
        decisions = list(_rows(battle))
        for start in range(len(decisions)):
            available = min(max_h, len(decisions) - start)
            if available < min(horizons):
                continue
            initial_hp = _hp_map(decisions[start]["state_before"])
            initial_total = sum(initial_hp.values())
            hp = {name: dict(initial_hp) for name in policies}
            modeled = {name: 0 for name in policies}
            invalid = {name: 0 for name in policies}
            generic_uses = {name: 0 for name in policies}
            for offset in range(available):
                row = decisions[start + offset]
                for name, policy in policies.items():
                    is_modeled, is_invalid, used_generic = advance_policy_chain(
                        row, hp[name], ensemble, support, policy
                    )
                    modeled[name] += int(is_modeled)
                    invalid[name] += int(is_invalid)
                    generic_uses[name] += int(is_modeled and used_generic)
                horizon = offset + 1
                if horizon not in acc or modeled["generic"] == 0:
                    continue
                observed = row["state_after"]
                for name in policies:
                    l1, _bias, _am, _an = _window_error(
                        hp[name], observed, initial_total
                    )
                    acc[horizon][name]["l1"].append(l1)
                    acc[horizon][name]["invalid"].append(
                        invalid[name] / max(1, modeled[name])
                    )
                    acc[horizon][name]["generic_usage"].append(
                        generic_uses[name] / max(1, modeled[name])
                    )
                    acc[horizon][name]["modeled"].append(modeled[name])
    out: dict[str, dict] = {}
    for h in horizons:
        out[str(h)] = {}
        for name in policies:
            x = acc[h][name]
            if not x["l1"]:
                out[str(h)][name] = {"windows": 0}
                continue
            out[str(h)][name] = {
                "windows": len(x["l1"]),
                "mean_force_l1": float(np.mean(x["l1"])),
                "median_force_l1": float(np.median(x["l1"])),
                "mean_invalid_action_fraction": float(np.mean(x["invalid"])),
                "mean_generic_usage_rate": float(np.mean(x["generic_usage"])),
                "mean_modeled_primary_attacks": float(np.mean(x["modeled"])),
            }
    return out


def run_selector_gate(
    corpus: Path,
    *,
    members: int = 5,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    shrinkage: float = 20.0,
) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted(
        (
            d
            for d in root.iterdir()
            if d.is_dir() and (d / "init.txt").exists() and (d / "turns0.txt").exists()
        ),
        key=lambda p: int(p.name),
    )
    fit_cut = int(len(battles) * 0.64)
    calibration_cut = int(len(battles) * 0.80)
    fit_battles = battles[:fit_cut]
    calibration_battles = battles[fit_cut:calibration_cut]
    test_battles = battles[calibration_cut:]
    fit_samples = _collect(fit_battles)
    support = _support_counts(fit_samples)
    ensemble = fit_battle_jackknife_ensemble(
        fit_samples, members=members, shrinkage=shrinkage
    )
    calibration_examples = one_step_examples(calibration_battles, ensemble, support)
    test_examples = one_step_examples(test_battles, ensemble, support)
    selector, calibration_selection = fit_selector(calibration_examples)
    one_step = {
        "calibration": one_step_metrics(calibration_examples, selector),
        "test": one_step_metrics(test_examples, selector),
    }
    multi = evaluate_multistep_policies(
        test_battles, ensemble, support, selector, horizons
    )
    horizons_ok = []
    for h in horizons:
        m = multi[str(h)]
        if not m["selector"].get("windows", 0):
            continue
        horizons_ok.append(
            m["selector"]["mean_force_l1"] <= m["generic"]["mean_force_l1"]
            and m["selector"]["mean_force_l1"] <= m["ensemble_mean"]["mean_force_l1"]
            and m["selector"]["mean_invalid_action_fraction"]
            <= m["generic"]["mean_invalid_action_fraction"]
        )
    return {
        "schema_version": 1,
        "scope": "calibrated fallback selector for the M11 primary physical-damage residual ensemble",
        "split": {
            "fit_battles": len(fit_battles),
            "calibration_battles": len(calibration_battles),
            "test_battles": len(test_battles),
        },
        "ensemble_members": members,
        "feature_names": list(FEATURE_NAMES),
        "selector": {
            "threshold": selector.threshold,
            "weights": selector.weights.tolist(),
            "feature_mean": selector.mean.tolist(),
            "feature_scale": selector.scale.tolist(),
            "calibration_selection": calibration_selection,
        },
        "one_step": one_step,
        "multistep": multi,
        "diagnostic_gate": {
            "selector_beats_both_models_and_matches_generic_invalid_rate_at_all_horizons": bool(horizons_ok)
            and all(horizons_ok),
            "production_selector_enabled": False,
            "reason": "The selector remains evidence-only until the final test split passes all accuracy and invalid-action gates.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--members", type=int, default=5)
    ap.add_argument("--horizons", default="2,4,8,16")
    ap.add_argument("--shrinkage", type=float, default=20.0)
    args = ap.parse_args()
    horizons = tuple(sorted({int(x) for x in args.horizons.split(",") if x.strip()}))
    report = run_selector_gate(
        args.corpus,
        members=args.members,
        horizons=horizons,
        shrinkage=args.shrinkage,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
