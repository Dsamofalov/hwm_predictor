from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from hwm_solver.evaluation.dynamics_multistep import (
    DEFAULT_HORIZONS,
    _collect,
    _hp_map,
    _rows,
    _window_error,
    advance_damage_chain,
    fit_battle_jackknife_ensemble,
)


def _rankdata(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        rank = 0.5 * ((i + 1) + j)
        ranks[order[i:j]] = rank
        i = j
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if len(x) < 2 or len(y) != len(x):
        return 0.0
    rx, ry = _rankdata(x), _rankdata(y)
    sx, sy = float(np.std(rx)), float(np.std(ry))
    if sx <= 0.0 or sy <= 0.0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int8)
    pos = labels == 1
    n_pos = int(np.sum(pos))
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    ranks = _rankdata(scores)
    rank_sum = float(np.sum(ranks[pos]))
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def calibration_bins(samples: list[dict], bins: int = 10) -> list[dict]:
    if not samples:
        return []
    ordered = sorted(samples, key=lambda x: x["disagreement"])
    out = []
    for idx, chunk in enumerate(np.array_split(np.asarray(ordered, dtype=object), min(bins, len(ordered)))):
        rows = list(chunk)
        if not rows:
            continue
        out.append(
            {
                "bin": idx,
                "count": len(rows),
                "disagreement_min": float(rows[0]["disagreement"]),
                "disagreement_max": float(rows[-1]["disagreement"]),
                "mean_disagreement": float(np.mean([r["disagreement"] for r in rows])),
                "mean_ensemble_force_l1": float(np.mean([r["ensemble_l1"] for r in rows])),
                "mean_generic_force_l1": float(np.mean([r["generic_l1"] for r in rows])),
                "mean_excess_force_l1": float(
                    np.mean([r["ensemble_l1"] - r["generic_l1"] for r in rows])
                ),
                "ensemble_better_than_generic_rate": float(
                    np.mean([r["ensemble_l1"] < r["generic_l1"] for r in rows])
                ),
                "mean_ensemble_invalid_action_fraction": float(
                    np.mean([r["ensemble_invalid_fraction"] for r in rows])
                ),
                "mean_generic_invalid_action_fraction": float(
                    np.mean([r["generic_invalid_fraction"] for r in rows])
                ),
            }
        )
    return out


def collect_window_samples(
    heldout_battles: list[Path], ensemble: list, horizons: tuple[int, ...]
) -> dict[int, list[dict]]:
    max_h = max(horizons)
    samples: dict[int, list[dict]] = {h: [] for h in horizons}
    for battle in heldout_battles:
        decisions = list(_rows(battle))
        for start in range(len(decisions)):
            available = min(max_h, len(decisions) - start)
            if available < min(horizons):
                continue
            initial_hp = _hp_map(decisions[start]["state_before"])
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
                if horizon not in samples or modeled == 0:
                    continue
                observed = row["state_after"]
                generic_l1, _gb, _gm, _gn = _window_error(generic_hp, observed, initial_total)
                uids = set().union(*(set(hp) for hp in member_hp))
                ensemble_mean = {
                    uid: float(np.mean([hp.get(uid, 0.0) for hp in member_hp])) for uid in uids
                }
                ensemble_l1, _eb, _em, _en = _window_error(
                    ensemble_mean, observed, initial_total
                )
                disagreement = sum(
                    float(np.std([hp.get(uid, 0.0) for hp in member_hp])) for uid in uids
                ) / max(1.0, initial_total)
                samples[horizon].append(
                    {
                        "battle_id": int(battle.name),
                        "start": start,
                        "modeled_steps": modeled,
                        "disagreement": disagreement,
                        "ensemble_l1": ensemble_l1,
                        "generic_l1": generic_l1,
                        "ensemble_invalid_fraction": float(np.mean(member_invalid)) / max(1, modeled),
                        "generic_invalid_fraction": generic_invalid / max(1, modeled),
                    }
                )
    return samples


def summarize(samples: list[dict], bins: int) -> dict:
    if not samples:
        return {"windows": 0}
    disagreement = np.asarray([x["disagreement"] for x in samples], dtype=np.float64)
    ensemble_l1 = np.asarray([x["ensemble_l1"] for x in samples], dtype=np.float64)
    generic_l1 = np.asarray([x["generic_l1"] for x in samples], dtype=np.float64)
    excess = ensemble_l1 - generic_l1
    invalid = np.asarray([x["ensemble_invalid_fraction"] for x in samples], dtype=np.float64)
    learned_worse = (excess > 0).astype(np.int8)
    binned = calibration_bins(samples, bins=bins)
    low = binned[0] if binned else {}
    high = binned[-1] if binned else {}
    return {
        "windows": len(samples),
        "spearman_disagreement_vs_ensemble_l1": spearman(disagreement, ensemble_l1),
        "spearman_disagreement_vs_excess_l1": spearman(disagreement, excess),
        "spearman_disagreement_vs_invalid_action_fraction": spearman(disagreement, invalid),
        "auc_disagreement_flags_learned_worse_than_generic": roc_auc(disagreement, learned_worse),
        "learned_worse_than_generic_rate": float(np.mean(learned_worse)),
        "low_to_high_bin_error_ratio": (
            float(high.get("mean_ensemble_force_l1", 0.0))
            / max(1e-12, float(low.get("mean_ensemble_force_l1", 0.0)))
            if low and high
            else 0.0
        ),
        "low_to_high_bin_invalid_ratio": (
            float(high.get("mean_ensemble_invalid_action_fraction", 0.0))
            / max(1e-12, float(low.get("mean_ensemble_invalid_action_fraction", 0.0)))
            if low and high
            else 0.0
        ),
        "bins": binned,
    }


def run_calibration(
    corpus: Path,
    *,
    members: int = 5,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    shrinkage: float = 20.0,
    bins: int = 10,
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
    windows = collect_window_samples(heldout_battles, ensemble, horizons)
    summaries = {str(h): summarize(windows[h], bins) for h in horizons}
    comparable = [x for x in summaries.values() if x.get("windows", 0)]
    return {
        "schema_version": 1,
        "scope": "uncertainty calibration for the M11 primary physical-damage residual ensemble",
        "source": "raw corpus chronological 80/20 battle split; ensemble fit on train battles only",
        "train_battles": len(train_battles),
        "heldout_battles": len(heldout_battles),
        "ensemble_members": members,
        "horizons_halfturns": list(horizons),
        "metrics": summaries,
        "diagnostic_gate": {
            "disagreement_tracks_absolute_error_at_all_horizons": bool(comparable)
            and all(x["spearman_disagreement_vs_ensemble_l1"] > 0.0 for x in comparable),
            "disagreement_flags_learned_underperformance_at_all_horizons": bool(comparable)
            and all(x["auc_disagreement_flags_learned_worse_than_generic"] > 0.5 for x in comparable),
            "production_uncertainty_gate_enabled": False,
            "reason": "Calibration evidence is diagnostic; a runtime threshold requires a separate train/calibration/test selection gate.",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--members", type=int, default=5)
    ap.add_argument("--horizons", default="2,4,8,16")
    ap.add_argument("--bins", type=int, default=10)
    ap.add_argument("--shrinkage", type=float, default=20.0)
    args = ap.parse_args()
    horizons = tuple(sorted({int(x) for x in args.horizons.split(",") if x.strip()}))
    report = run_calibration(
        args.corpus,
        members=args.members,
        horizons=horizons,
        shrinkage=args.shrinkage,
        bins=args.bins,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
