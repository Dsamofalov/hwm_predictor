from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

from hwm_solver.evaluation.dynamics_multistep import _collect, fit_battle_jackknife_ensemble
from hwm_solver.evaluation.dynamics_survival_gate import DEFAULT_ROLLS, evaluate_survival

DEFAULT_SCALES = (0.0, 0.25, 0.5, 0.75, 1.0)
DEFAULT_HORIZONS = (2, 4, 8, 16)


@dataclass(frozen=True)
class PositiveTemperedProfile:
    """Shrink only positive learned log-residuals toward the generic core."""

    base: object
    positive_scale: float

    def multiplier(self, action_type: str, creature_id: int) -> float:
        m = max(1e-9, float(self.base.multiplier(action_type, creature_id)))
        log_m = math.log(m)
        if log_m > 0.0:
            log_m *= self.positive_scale
        return math.exp(log_m)


@dataclass(frozen=True)
class GeometricMeanProfile:
    """Deterministic calibration proxy for a fitted residual ensemble.

    Residuals are multiplicative, so their natural ensemble centre is the
    geometric mean (the arithmetic mean in log-residual space). Calibration
    evaluates five temperature candidates against this one profile and the
    stochastic damage-roll grid. The chosen temperature is then opened once
    on the untouched final split using every ensemble member.
    """

    members: tuple[object, ...]

    def multiplier(self, action_type: str, creature_id: int) -> float:
        if not self.members:
            return 1.0
        logs = [
            math.log(max(1e-9, float(member.multiplier(action_type, creature_id))))
            for member in self.members
        ]
        return math.exp(math.fsum(logs) / len(logs))


def battle_split(corpus: Path) -> tuple[list[Path], list[Path], list[Path]]:
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
    return battles[:fit_cut], battles[fit_cut:calibration_cut], battles[calibration_cut:]


def summarize(metrics: dict[str, dict]) -> dict:
    comparable = [
        metrics[key]
        for key in sorted(metrics, key=int)
        if metrics[key].get("windows", 0)
    ]
    if not comparable:
        return {
            "mean_l1_ratio_learned_over_generic": float("inf"),
            "min_valid_action_coverage_delta_learned_minus_generic": float("-inf"),
            "coverage_not_below_generic_at_all_horizons": False,
            "l1_better_than_generic_at_all_horizons": False,
        }
    l1_ratio = math.fsum(
        row["learned_mean_force_l1"] / max(1e-12, row["generic_mean_force_l1"])
        for row in comparable
    ) / len(comparable)
    min_coverage_delta = min(
        row["learned_mean_valid_observed_action_coverage"]
        - row["generic_mean_valid_observed_action_coverage"]
        for row in comparable
    )
    return {
        "mean_l1_ratio_learned_over_generic": l1_ratio,
        "min_valid_action_coverage_delta_learned_minus_generic": min_coverage_delta,
        "coverage_not_below_generic_at_all_horizons": min_coverage_delta >= 0.0,
        "l1_better_than_generic_at_all_horizons": all(
            row["learned_mean_force_l1"] < row["generic_mean_force_l1"]
            for row in comparable
        ),
    }


def choose_scale(calibration: dict[str, dict]) -> tuple[float, str]:
    """Choose on calibration only; final-test metrics never influence selection."""
    rows = []
    for key, report in calibration.items():
        scale = float(key)
        summary = report["summary"]
        feasible = bool(
            summary["coverage_not_below_generic_at_all_horizons"]
            and summary["l1_better_than_generic_at_all_horizons"]
        )
        rows.append((scale, summary, feasible))
    feasible_rows = [row for row in rows if row[2]]
    if feasible_rows:
        chosen = min(
            feasible_rows,
            key=lambda row: (
                row[1]["mean_l1_ratio_learned_over_generic"],
                -row[0],
            ),
        )
        return chosen[0], "calibration_feasible"

    chosen = max(
        rows,
        key=lambda row: (
            row[1]["min_valid_action_coverage_delta_learned_minus_generic"],
            -row[1]["mean_l1_ratio_learned_over_generic"],
            row[0],
        ),
    )
    return chosen[0], "no_calibration_candidate_passed_hard_gate"


def run_gate(
    corpus: Path,
    *,
    members: int = 5,
    scales: tuple[float, ...] = DEFAULT_SCALES,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    shrinkage: float = 20.0,
    rolls: tuple[float, ...] = DEFAULT_ROLLS,
) -> dict:
    fit, calibration_battles, test_battles = battle_split(corpus)
    samples = _collect(fit)
    base_ensemble = fit_battle_jackknife_ensemble(
        samples, members=members, shrinkage=shrinkage
    )
    calibration_centre = GeometricMeanProfile(tuple(base_ensemble))

    calibration: dict[str, dict] = {}
    for scale in scales:
        tempered_centre = [PositiveTemperedProfile(calibration_centre, scale)]
        metrics = evaluate_survival(
            calibration_battles,
            tempered_centre,
            horizons=horizons,
            rolls=rolls,
        )
        calibration[str(scale)] = {
            "metrics": metrics,
            "summary": summarize(metrics),
        }

    chosen_scale, selection_reason = choose_scale(calibration)
    chosen_ensemble = [
        PositiveTemperedProfile(profile, chosen_scale) for profile in base_ensemble
    ]
    final_metrics = evaluate_survival(
        test_battles,
        chosen_ensemble,
        horizons=horizons,
        rolls=rolls,
    )
    final_summary = summarize(final_metrics)
    final_pass = bool(
        selection_reason == "calibration_feasible"
        and final_summary["coverage_not_below_generic_at_all_horizons"]
        and final_summary["l1_better_than_generic_at_all_horizons"]
    )

    return {
        "schema_version": 2,
        "scope": "leakage-safe positive-log residual temperature calibration for the M11 stochastic physical-damage survival gate",
        "split": {
            "fit_battles": len(fit),
            "calibration_battles": len(calibration_battles),
            "final_test_battles": len(test_battles),
        },
        "ensemble_members": members,
        "candidate_positive_scales": list(scales),
        "damage_roll_quantile_starts": list(rolls),
        "calibration_profile": "geometric mean of fitted ensemble members; one residual profile across the stochastic roll grid",
        "final_test_profile": "full fitted ensemble across the stochastic roll grid",
        "calibration": calibration,
        "selection": {
            "chosen_positive_scale": chosen_scale,
            "reason": selection_reason,
        },
        "final_test": {
            "metrics": final_metrics,
            "summary": final_summary,
        },
        "diagnostic_gate": {
            "final_test_pass": final_pass,
            "production_enablement": False,
            "reason": (
                "Positive residual temperature passes this isolated physical-damage submodel gate; full M11 structured dynamics remains incomplete."
                if final_pass
                else "No production change: calibration/final-test validity and accuracy gates were not both cleared."
            ),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--members", type=int, default=5)
    ap.add_argument("--scales", default=",".join(str(x) for x in DEFAULT_SCALES))
    ap.add_argument("--horizons", default=",".join(str(x) for x in DEFAULT_HORIZONS))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    scales = tuple(float(x) for x in args.scales.split(",") if x.strip())
    horizons = tuple(sorted({int(x) for x in args.horizons.split(",") if x.strip()}))
    report = run_gate(
        args.corpus,
        members=args.members,
        scales=scales,
        horizons=horizons,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
