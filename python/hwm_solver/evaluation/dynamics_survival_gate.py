from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from hwm_solver.evaluation.dynamics_multistep import (
    DEFAULT_HORIZONS,
    ResidualProfile,
    _collect,
    _hp_map,
    _rows,
    _state_with_hp,
    _window_error,
    fit_battle_jackknife_ensemble,
)
from hwm_solver.models.train_damage_model import (
    ATTACK_TYPES,
    _effect_magnitude,
    _expected_damage,
    _observed_damage,
)

# Midpoint-stratified starts for Uniform[0, 1] damage rolls.  Each subsequent
# action rotates this grid by an irrational shift so different turns do not share
# an artificial all-low/all-high damage correlation while the run stays deterministic.
DEFAULT_ROLLS = (1.0 / 6.0, 0.5, 5.0 / 6.0)
ROLL_SHIFT = 0.6180339887498949


def _roll_at_step(base_roll: float, step: int) -> float:
    return (float(base_roll) + int(step) * ROLL_SHIFT) % 1.0


def _sampled_expected_damage(row: dict, actor: dict, target: dict, roll: float) -> float:
    """Evaluate the existing exact-core algebra at a fixed base-damage quantile.

    C++ rollouts draw the per-creature physical base uniformly between effective min/max
    damage (unless Accuracy forces max). The Python training baseline already contains
    the recovered deterministic attack/defence/passive algebra. To avoid duplicating
    that algebra here, collapse min/max to one sampled per-unit value and call the same
    `_expected_damage` implementation.

    Multi-hit C++ rollouts spread hit rolls by +/-0.08 around the sampled action roll;
    this diagnostic intentionally uses one shared action quantile for all hits. The report
    exposes that approximation and this gate remains evidence-only.
    """
    r = min(1.0, max(0.0, float(roll)))
    abilities = set(actor.get("abilities", []) or [])
    effect_values = actor.get("effect_values", {}) or {}
    tob = float(effect_values.get("tob", 0) or 0)
    mn = float(actor.get("min_damage", 0)) + tob
    mx = max(mn, float(actor.get("max_damage", 0)))
    bless_curse = (_effect_magnitude(actor, "bls") - _effect_magnitude(actor, "crs")) / 100.0
    if bless_curse > 0:
        mn = min(mx, mn + (mx - mn) * bless_curse)
    elif bless_curse < 0:
        mx = max(mn, mx - (mx - mn) * (-bless_curse))
    sampled = mx if "accuracy" in abilities else mn + (mx - mn) * r

    patched_actor = dict(actor)
    patched_actor["min_damage"] = sampled - tob
    patched_actor["max_damage"] = sampled
    return _expected_damage(row, patched_actor, target)


def _prediction_at_roll(
    row: dict,
    predicted_hp: dict[int, float],
    profile: ResidualProfile | None,
    roll: float,
) -> tuple[int, int, float | None] | None:
    if row.get("action_type") not in ATTACK_TYPES or row.get("target_uid") is None:
        return None
    observed = _observed_damage(row)
    if observed <= 0:
        return None
    actor_uid = int(row["actor_uid"])
    target_uid = int(row["target_uid"])
    state = _state_with_hp(row["state_before"], predicted_hp)
    by_uid = {int(e["uid"]): e for e in state}
    actor = by_uid.get(actor_uid)
    target = by_uid.get(target_uid)
    if not actor or not target or not actor.get("alive", True) or not target.get("alive", True):
        return observed, target_uid, None
    expected = _sampled_expected_damage(row, actor, target, roll)
    if not math.isfinite(expected) or expected <= 0:
        return observed, target_uid, None
    multiplier = 1.0 if profile is None else profile.multiplier(
        str(row["action_type"]), int(actor.get("creature_id", 0))
    )
    return observed, target_uid, max(1e-6, expected * multiplier)


def _advance_at_roll(
    row: dict,
    predicted_hp: dict[int, float],
    profile: ResidualProfile | None,
    roll: float,
) -> tuple[bool, bool]:
    replacement = _prediction_at_roll(row, predicted_hp, profile, roll)
    before = _hp_map(row["state_before"])
    after = _hp_map(row["state_after"])
    for uid in set(before) | set(after) | set(predicted_hp):
        base = predicted_hp.get(uid, before.get(uid, 0.0))
        predicted_hp[uid] = max(0.0, base + after.get(uid, 0.0) - before.get(uid, 0.0))
    if replacement is None:
        return False, False
    observed, target_uid, predicted = replacement
    predicted_hp[target_uid] = max(0.0, predicted_hp.get(target_uid, 0.0) + float(observed))
    if predicted is None:
        return True, True
    predicted_hp[target_uid] = max(0.0, predicted_hp.get(target_uid, 0.0) - predicted)
    return True, False


def _trajectory_mean(trajectories: list[dict[int, float]]) -> dict[int, float]:
    uids: set[int] = set()
    for hp in trajectories:
        uids.update(hp)
    return {uid: float(np.mean([hp.get(uid, 0.0) for hp in trajectories])) for uid in uids}


def evaluate_survival(
    heldout_battles: list[Path],
    ensemble: list[ResidualProfile],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    rolls: tuple[float, ...] = DEFAULT_ROLLS,
) -> dict:
    if not ensemble:
        raise ValueError("ensemble must contain at least one profile")
    if not rolls:
        raise ValueError("at least one damage-roll quantile is required")
    max_h = max(horizons)
    acc = {
        h: {
            "generic_l1": [],
            "learned_l1": [],
            "generic_valid_action_coverage": [],
            "learned_valid_action_coverage": [],
            "generic_full_survival": [],
            "learned_full_survival": [],
            "modeled": [],
        }
        for h in horizons
    }

    for battle in heldout_battles:
        decisions = list(_rows(battle))
        for start in range(len(decisions)):
            available = min(max_h, len(decisions) - start)
            if available < min(horizons):
                continue
            initial_hp = _hp_map(decisions[start]["state_before"])
            initial_total = sum(initial_hp.values())
            generic = [dict(initial_hp) for _ in rolls]
            learned = [dict(initial_hp) for _profile in ensemble for _roll in rolls]
            generic_invalid = [0 for _ in generic]
            learned_invalid = [0 for _ in learned]
            modeled = 0

            for offset in range(available):
                row = decisions[start + offset]
                generic_modeled = False
                for i, (hp, base_roll) in enumerate(zip(generic, rolls)):
                    action_roll = _roll_at_step(base_roll, offset)
                    is_modeled, is_invalid = _advance_at_roll(row, hp, None, action_roll)
                    generic_modeled = generic_modeled or is_modeled
                    generic_invalid[i] += int(is_invalid)
                li = 0
                for profile in ensemble:
                    for base_roll in rolls:
                        action_roll = _roll_at_step(base_roll, offset)
                        is_modeled, is_invalid = _advance_at_roll(row, learned[li], profile, action_roll)
                        learned_invalid[li] += int(is_invalid)
                        li += 1
                modeled += int(generic_modeled)
                horizon = offset + 1
                if horizon not in acc or modeled == 0:
                    continue

                observed = row["state_after"]
                generic_mean = _trajectory_mean(generic)
                learned_mean = _trajectory_mean(learned)
                generic_l1, _gb, _gm, _gn = _window_error(generic_mean, observed, initial_total)
                learned_l1, _lb, _lm, _ln = _window_error(learned_mean, observed, initial_total)
                g_total = max(1, modeled * len(generic))
                l_total = max(1, modeled * len(learned))
                bucket = acc[horizon]
                bucket["generic_l1"].append(generic_l1)
                bucket["learned_l1"].append(learned_l1)
                bucket["generic_valid_action_coverage"].append(1.0 - sum(generic_invalid) / g_total)
                bucket["learned_valid_action_coverage"].append(1.0 - sum(learned_invalid) / l_total)
                bucket["generic_full_survival"].append(
                    float(np.mean(np.asarray(generic_invalid, dtype=np.int64) == 0))
                )
                bucket["learned_full_survival"].append(
                    float(np.mean(np.asarray(learned_invalid, dtype=np.int64) == 0))
                )
                bucket["modeled"].append(modeled)

    out: dict[str, dict] = {}
    for h in horizons:
        m = acc[h]
        if not m["learned_l1"]:
            out[str(h)] = {"windows": 0}
            continue
        out[str(h)] = {
            "windows": len(m["learned_l1"]),
            "mean_modeled_primary_attacks": float(np.mean(m["modeled"])),
            "generic_mean_force_l1": float(np.mean(m["generic_l1"])),
            "learned_mean_force_l1": float(np.mean(m["learned_l1"])),
            "generic_mean_valid_observed_action_coverage": float(np.mean(m["generic_valid_action_coverage"])),
            "learned_mean_valid_observed_action_coverage": float(np.mean(m["learned_valid_action_coverage"])),
            "generic_mean_full_window_survival_probability": float(np.mean(m["generic_full_survival"])),
            "learned_mean_full_window_survival_probability": float(np.mean(m["learned_full_survival"])),
        }
    return out


def run_gate(
    corpus: Path,
    *,
    members: int = 5,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    shrinkage: float = 20.0,
    rolls: tuple[float, ...] = DEFAULT_ROLLS,
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
    cut = int(len(battles) * 0.8)
    train, heldout = battles[:cut], battles[cut:]
    samples = _collect(train)
    ensemble = fit_battle_jackknife_ensemble(samples, members=members, shrinkage=shrinkage)
    metrics = evaluate_survival(heldout, ensemble, horizons=horizons, rolls=rolls)
    comparable = [x for x in metrics.values() if x.get("windows", 0)]
    return {
        "schema_version": 1,
        "scope": "distributional survival gate for the primary physical-damage residual ensemble; non-primary deltas are replay teacher-forced",
        "source": "raw corpus chronological 80/20 battle split",
        "train_battles": len(train),
        "heldout_battles": len(heldout),
        "ensemble_members": members,
        "damage_roll_quantile_starts": list(rolls),
        "damage_roll_sequence": "midpoint-stratified starts rotated by golden-ratio fractional shift per subsequent action",
        "trajectory_count_generic": len(rolls),
        "trajectory_count_learned": len(rolls) * members,
        "sampling_approximation": "one sampled quantile per action shared across that action's multi-hit components; C++ runtime adds +/-0.08 per-hit spread",
        "metrics": metrics,
        "diagnostic_gate": {
            "learned_beats_generic_mean_l1_at_all_horizons": bool(comparable)
            and all(x["learned_mean_force_l1"] <= x["generic_mean_force_l1"] for x in comparable),
            "learned_action_coverage_not_below_generic_at_all_horizons": bool(comparable)
            and all(
                x["learned_mean_valid_observed_action_coverage"]
                >= x["generic_mean_valid_observed_action_coverage"]
                for x in comparable
            ),
            "production_enablement": False,
            "reason": "Evidence-only distributional gate for one transition submodel; full M11 structured dynamics remains incomplete.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--members", type=int, default=5)
    ap.add_argument("--horizons", default="2,4,8,16")
    ap.add_argument("--shrinkage", type=float, default=20.0)
    ap.add_argument("--rolls", default=",".join(str(x) for x in DEFAULT_ROLLS))
    args = ap.parse_args()
    horizons = tuple(sorted({int(x) for x in args.horizons.split(",") if x.strip()}))
    rolls = tuple(float(x) for x in args.rolls.split(",") if x.strip())
    report = run_gate(args.corpus, members=args.members, horizons=horizons, shrinkage=args.shrinkage, rolls=rolls)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
