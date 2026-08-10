from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Iterable

import numpy as np

from hwm_solver.models.train_damage_model import (
    ATTACK_TYPES,
    _collect,
    _expected_damage,
    _observed_damage,
    _rows,
)

DEFAULT_HORIZONS = (2, 4, 8, 16)


def hp_equivalent(entity: dict) -> float:
    if not bool(entity.get("alive", True)) or int(entity.get("count", 0) or 0) <= 0:
        return 0.0
    count = max(0, int(entity.get("count", 0) or 0))
    max_hp = max(1.0, float(entity.get("max_hp", entity.get("max_hp_per_unit", 1)) or 1))
    top_hp = max(0.0, float(entity.get("top_hp", entity.get("hp", max_hp)) or 0))
    return max(0.0, (count - 1) * max_hp + top_hp)


def _hp_map(state: list[dict]) -> dict[int, float]:
    return {int(e["uid"]): hp_equivalent(e) for e in state}


def _patch_entity_hp(entity: dict, total_hp: float) -> dict:
    out = dict(entity)
    max_hp = max(1.0, float(out.get("max_hp", out.get("max_hp_per_unit", 1)) or 1))
    total_hp = max(0.0, float(total_hp))
    if total_hp <= 0.0:
        out["count"] = 0
        out["top_hp"] = 0
        out["hp"] = 0
        out["alive"] = False
        return out
    count = int(math.ceil(total_hp / max_hp - 1e-12))
    max_count = int(out.get("max_count", 0) or 0)
    if max_count > 0:
        count = min(count, max_count)
        total_hp = min(total_hp, max_count * max_hp)
    top_hp = total_hp - (count - 1) * max_hp
    top_hp = min(max_hp, max(1e-9, top_hp))
    out["count"] = count
    out["top_hp"] = top_hp
    out["hp"] = top_hp
    out["alive"] = True
    return out


def _state_with_hp(state: list[dict], predicted_hp: dict[int, float]) -> list[dict]:
    return [_patch_entity_hp(e, predicted_hp.get(int(e["uid"]), hp_equivalent(e))) for e in state]


@dataclass(frozen=True)
class ResidualProfile:
    global_log: dict[str, float]
    creature_log: dict[tuple[str, int], float]

    def multiplier(self, action_type: str, creature_id: int) -> float:
        log_m = self.creature_log.get(
            (action_type, creature_id), self.global_log.get(action_type, 0.0)
        )
        return math.exp(log_m)


@dataclass(frozen=True)
class DamagePrediction:
    observed_damage: int
    target_uid: int
    predicted_damage: float | None


@dataclass(frozen=True)
class AdvanceResult:
    modeled: bool
    predicted_invalid_action: bool


def fit_profile(samples: Iterable[dict], *, shrinkage: float = 20.0) -> ResidualProfile:
    global_logs: dict[str, list[float]] = defaultdict(list)
    creature_logs: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in samples:
        global_logs[row["action_type"]].append(float(row["log_ratio"]))
        creature_logs[(row["action_type"], int(row["creature_id"]))].append(
            float(row["log_ratio"])
        )
    global_median = {k: float(median(v)) for k, v in global_logs.items() if v}
    creature: dict[tuple[str, int], float] = {}
    for key, values in creature_logs.items():
        n = len(values)
        local = float(median(values))
        prior = global_median.get(key[0], 0.0)
        weight = n / (n + shrinkage)
        creature[key] = weight * local + (1.0 - weight) * prior
    return ResidualProfile(global_median, creature)


def fit_battle_jackknife_ensemble(
    train_samples: list[dict], *, members: int = 5, shrinkage: float = 20.0
) -> list[ResidualProfile]:
    if members < 3:
        raise ValueError("dynamics ensemble requires at least three members")
    battle_ids = sorted({int(r["battle_id"]) for r in train_samples})
    fold_for = {bid: i % members for i, bid in enumerate(battle_ids)}
    ensemble = []
    for held_fold in range(members):
        subset = [r for r in train_samples if fold_for[int(r["battle_id"])] != held_fold]
        ensemble.append(fit_profile(subset, shrinkage=shrinkage))
    return ensemble


def _primary_damage_prediction(
    row: dict, predicted_hp: dict[int, float], profile: ResidualProfile | None
) -> DamagePrediction | None:
    if row.get("action_type") not in ATTACK_TYPES or row.get("target_uid") is None:
        return None
    observed = _observed_damage(row)
    if observed <= 0:
        return None
    target_uid = int(row["target_uid"])
    state = _state_with_hp(row["state_before"], predicted_hp)
    by_uid = {int(e["uid"]): e for e in state}
    actor_uid = int(row["actor_uid"])
    actor = by_uid.get(actor_uid)
    target = by_uid.get(target_uid)
    if not actor or not target or not actor.get("alive", True) or not target.get("alive", True):
        return DamagePrediction(observed, target_uid, None)
    patched = dict(row)
    patched["state_before"] = state
    expected = _expected_damage(patched, actor, target)
    if not math.isfinite(expected) or expected <= 0:
        return DamagePrediction(observed, target_uid, None)
    multiplier = 1.0 if profile is None else profile.multiplier(
        row["action_type"], int(actor.get("creature_id", 0))
    )
    return DamagePrediction(observed, target_uid, max(1e-6, expected * multiplier))


def advance_damage_chain(
    row: dict, predicted_hp: dict[int, float], profile: ResidualProfile | None
) -> AdvanceResult:
    # Predict from the autoregressive pre-step state.  Only after that do we teacher-force
    # the observed non-primary delta and replace the observed primary physical damage with
    # the model prediction.
    replacement = _primary_damage_prediction(row, predicted_hp, profile)
    before = _hp_map(row["state_before"])
    after = _hp_map(row["state_after"])
    all_uids = set(before) | set(after) | set(predicted_hp)
    for uid in all_uids:
        base = predicted_hp.get(uid, before.get(uid, 0.0))
        observed_delta = after.get(uid, 0.0) - before.get(uid, 0.0)
        predicted_hp[uid] = max(0.0, base + observed_delta)

    if replacement is None:
        return AdvanceResult(False, False)

    # Remove the observed primary damage from the teacher-forced target delta first.
    # If the predicted chain already made the real action impossible, do not resurrect the
    # observed damage effect; preserve the invalid-action divergence as a gate failure.
    target_uid = replacement.target_uid
    predicted_hp[target_uid] = max(
        0.0,
        predicted_hp.get(target_uid, 0.0) + float(replacement.observed_damage),
    )
    if replacement.predicted_damage is None:
        return AdvanceResult(True, True)
    predicted_hp[target_uid] = max(
        0.0,
        predicted_hp.get(target_uid, 0.0) - replacement.predicted_damage,
    )
    return AdvanceResult(True, False)


def _window_error(
    predicted: dict[int, float], observed_state: list[dict], initial_total_hp: float
) -> tuple[float, float, int, int]:
    observed = _hp_map(observed_state)
    uids = set(predicted) | set(observed)
    abs_error = sum(abs(predicted.get(uid, 0.0) - observed.get(uid, 0.0)) for uid in uids)
    bias = sum(predicted.get(uid, 0.0) - observed.get(uid, 0.0) for uid in uids)
    alive_mismatch = sum(
        (predicted.get(uid, 0.0) > 0.5) != (observed.get(uid, 0.0) > 0.5) for uid in uids
    )
    return (
        abs_error / max(1.0, initial_total_hp),
        bias / max(1.0, initial_total_hp),
        alive_mismatch,
        len(uids),
    )


def evaluate_battles(
    heldout_battles: list[Path],
    ensemble: list[ResidualProfile],
    *,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict:
    if not ensemble:
        raise ValueError("ensemble must contain at least one profile")
    max_h = max(horizons)
    metrics = {
        h: {
            "generic_l1": [],
            "ensemble_l1": [],
            "ensemble_bias": [],
            "ensemble_disagreement": [],
            "generic_invalid": [],
            "ensemble_invalid_fraction": [],
            "alive_mismatch": 0,
            "alive_entities": 0,
            "modeled_steps": [],
        }
        for h in horizons
    }

    for battle in heldout_battles:
        decisions = list(_rows(battle))
        for start in range(len(decisions)):
            available = min(max_h, len(decisions) - start)
            if available < min(horizons):
                continue
            initial_state = decisions[start]["state_before"]
            initial_hp = _hp_map(initial_state)
            initial_total = sum(initial_hp.values())
            generic_hp = dict(initial_hp)
            member_hp = [dict(initial_hp) for _ in ensemble]
            modeled = 0
            generic_invalid = 0
            member_invalid = [0 for _ in ensemble]

            for offset in range(available):
                row = decisions[start + offset]
                generic_result = advance_damage_chain(row, generic_hp, None)
                modeled += int(generic_result.modeled)
                generic_invalid += int(generic_result.predicted_invalid_action)
                for i, (profile, hp) in enumerate(zip(ensemble, member_hp)):
                    result = advance_damage_chain(row, hp, profile)
                    member_invalid[i] += int(result.predicted_invalid_action)
                horizon = offset + 1
                if horizon not in metrics or modeled == 0:
                    continue

                observed_state = row["state_after"]
                generic_l1, _generic_bias, _gm, _gn = _window_error(
                    generic_hp, observed_state, initial_total
                )
                uids = set().union(*(set(x) for x in member_hp))
                ensemble_mean = {
                    uid: float(np.mean([hp.get(uid, 0.0) for hp in member_hp])) for uid in uids
                }
                ensemble_l1, ensemble_bias, mismatches, entity_count = _window_error(
                    ensemble_mean, observed_state, initial_total
                )
                disagreement = sum(
                    float(np.std([hp.get(uid, 0.0) for hp in member_hp])) for uid in uids
                ) / max(1.0, initial_total)

                m = metrics[horizon]
                m["generic_l1"].append(generic_l1)
                m["ensemble_l1"].append(ensemble_l1)
                m["ensemble_bias"].append(ensemble_bias)
                m["ensemble_disagreement"].append(disagreement)
                m["generic_invalid"].append(generic_invalid / max(1, modeled))
                m["ensemble_invalid_fraction"].append(
                    float(np.mean(member_invalid)) / max(1, modeled)
                )
                m["alive_mismatch"] += mismatches
                m["alive_entities"] += entity_count
                m["modeled_steps"].append(modeled)

    out: dict[str, dict] = {}
    for h in horizons:
        m = metrics[h]
        if not m["ensemble_l1"]:
            out[str(h)] = {"windows": 0}
            continue
        generic = np.asarray(m["generic_l1"], dtype=np.float64)
        learned = np.asarray(m["ensemble_l1"], dtype=np.float64)
        bias = np.asarray(m["ensemble_bias"], dtype=np.float64)
        disagreement = np.asarray(m["ensemble_disagreement"], dtype=np.float64)
        out[str(h)] = {
            "windows": int(len(learned)),
            "mean_modeled_primary_attacks": float(np.mean(m["modeled_steps"])),
            "generic_mean_force_l1": float(np.mean(generic)),
            "generic_median_force_l1": float(np.median(generic)),
            "ensemble_mean_force_l1": float(np.mean(learned)),
            "ensemble_median_force_l1": float(np.median(learned)),
            "ensemble_mean_force_bias": float(np.mean(bias)),
            "ensemble_mean_disagreement": float(np.mean(disagreement)),
            "generic_mean_invalid_action_fraction": float(np.mean(m["generic_invalid"])),
            "ensemble_mean_invalid_action_fraction": float(
                np.mean(m["ensemble_invalid_fraction"])
            ),
            "alive_mismatch_rate": m["alive_mismatch"] / max(1, m["alive_entities"]),
            "ensemble_better_than_generic_rate": float(np.mean(learned < generic)),
        }
    return out


def run_gate(
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
    cut = int(len(battles) * 0.8)
    train_battles, heldout_battles = battles[:cut], battles[cut:]
    train_samples = _collect(train_battles)
    ensemble = fit_battle_jackknife_ensemble(
        train_samples, members=members, shrinkage=shrinkage
    )
    horizon_metrics = evaluate_battles(heldout_battles, ensemble, horizons=horizons)
    comparable = [v for v in horizon_metrics.values() if v.get("windows", 0)]
    return {
        "schema_version": 1,
        "scope": "primary physical-damage residual only; all non-primary state deltas are teacher-forced from replay",
        "source": "raw corpus chronological 80/20 battle split",
        "train_battles": len(train_battles),
        "heldout_battles": len(heldout_battles),
        "train_attack_samples": len(train_samples),
        "ensemble": {
            "members": members,
            "construction": "battle-jackknife; each member excludes a distinct 1/members fold of training battles",
            "shrinkage": shrinkage,
        },
        "horizons_halfturns": list(horizons),
        "metrics": horizon_metrics,
        "diagnostic_gate": {
            "beats_generic_mean_l1_at_all_horizons": bool(comparable)
            and all(
                x["ensemble_mean_force_l1"] <= x["generic_mean_force_l1"] for x in comparable
            ),
            "production_enablement": False,
            "reason": "This is the first M11 submodel multi-step gate, not a full structured world-model ensemble.",
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
    report = run_gate(
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
