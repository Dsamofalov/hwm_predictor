from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from hwm_solver.ability.cripplingwound_hit_evidence import _damage_rows
from hwm_solver.protocol.replay import iter_battle_decisions


ABILITY = "cripplingwound"
ROLLING_FOLDS = 4
MIN_TRAIN_FRACTION = 0.55


def _frequency(rows: list[dict]) -> float:
    return sum(bool(row["proc"]) for row in rows) / len(rows) if rows else 0.0


def _brier(rows: list[dict], probabilities: list[float]) -> float:
    return sum(
        (float(p) - float(bool(row["proc"]))) ** 2
        for row, p in zip(rows, probabilities)
    ) / len(rows) if rows else float("nan")


def _smoothed(train: list[dict], test: list[dict], key: str, prior: float = 8.0) -> list[float]:
    base = _frequency(train)
    groups: dict[object, list[int]] = defaultdict(list)
    for row in train:
        groups[row[key]].append(int(bool(row["proc"])))
    return [
        (sum(groups.get(row[key], [])) + prior * base)
        / (len(groups.get(row[key], [])) + prior)
        for row in test
    ]


def _candidate_probabilities(train: list[dict], test: list[dict]) -> dict[str, list[float]]:
    base = _frequency(train)
    return {
        "train_frequency": [base] * len(test),
        "fixed_0_25": [0.25] * len(test),
        "fixed_0_30": [0.30] * len(test),
        "action_type_smoothed": _smoothed(train, test, "action_type"),
        "source_creature_smoothed": _smoothed(train, test, "source_creature_id"),
        "target_creature_smoothed": _smoothed(train, test, "target_creature_id"),
        "target_big_smoothed": _smoothed(train, test, "target_big"),
        "target_mechanical_smoothed": _smoothed(train, test, "target_mechanical"),
        "target_undead_smoothed": _smoothed(train, test, "target_undead"),
        "hit_ordinal_smoothed": _smoothed(train, test, "hit_ordinal_same_pair"),
    }


def _rolling_folds(rows: list[dict]) -> list[tuple[list[dict], list[dict]]]:
    battle_ids = sorted(
        {row["battle_id"] for row in rows},
        key=lambda value: (0, int(value)) if str(value).isdigit() else (1, str(value)),
    )
    if len(battle_ids) < 3:
        return []
    train_n = max(1, int(math.floor(len(battle_ids) * MIN_TRAIN_FRACTION)))
    remaining = battle_ids[train_n:]
    if not remaining:
        return []
    fold_size = max(1, math.ceil(len(remaining) / ROLLING_FOLDS))
    folds: list[tuple[list[dict], list[dict]]] = []
    for start in range(0, len(remaining), fold_size):
        test_ids = set(remaining[start : start + fold_size])
        if not test_ids:
            continue
        first_test = min(
            test_ids,
            key=lambda value: (0, int(value)) if str(value).isdigit() else (1, str(value)),
        )
        def before(value: str) -> bool:
            if str(value).isdigit() and str(first_test).isdigit():
                return int(value) < int(first_test)
            return str(value) < str(first_test)
        train = [row for row in rows if before(row["battle_id"])]
        test = [row for row in rows if row["battle_id"] in test_ids]
        if train and test:
            folds.append((train, test))
    return folds


def _rolling_metrics(rows: list[dict]) -> dict:
    folds = _rolling_folds(rows)
    fold_reports: list[dict] = []
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {"sse": 0.0, "rows": 0.0, "wins": 0.0})
    for fold_index, (train, test) in enumerate(folds):
        candidates = _candidate_probabilities(train, test)
        baseline_brier = _brier(test, candidates["train_frequency"])
        metrics = {}
        for name, probabilities in candidates.items():
            brier = _brier(test, probabilities)
            improvement = baseline_brier - brier
            metrics[name] = {
                "brier": brier,
                "brier_improvement_vs_train_frequency": improvement,
                "mean_p": sum(probabilities) / len(probabilities),
            }
            totals[name]["sse"] += brier * len(test)
            totals[name]["rows"] += len(test)
            totals[name]["wins"] += float(improvement > 0)
        fold_reports.append(
            {
                "fold": fold_index + 1,
                "train_rows": len(train),
                "test_rows": len(test),
                "train_battles": len({r["battle_id"] for r in train}),
                "test_battles": len({r["battle_id"] for r in test}),
                "train_last_battle": max(
                    {r["battle_id"] for r in train},
                    key=lambda value: (0, int(value)) if str(value).isdigit() else (1, str(value)),
                ),
                "test_first_battle": min(
                    {r["battle_id"] for r in test},
                    key=lambda value: (0, int(value)) if str(value).isdigit() else (1, str(value)),
                ),
                "test_last_battle": max(
                    {r["battle_id"] for r in test},
                    key=lambda value: (0, int(value)) if str(value).isdigit() else (1, str(value)),
                ),
                "train_proc_rate": _frequency(train),
                "test_proc_rate": _frequency(test),
                "models": metrics,
            }
        )

    aggregate = {}
    baseline = None
    for name, total in totals.items():
        brier = total["sse"] / total["rows"] if total["rows"] else float("nan")
        aggregate[name] = {
            "brier": brier,
            "fold_wins_vs_train_frequency": int(total["wins"]),
            "folds": len(folds),
            "test_rows": int(total["rows"]),
        }
        if name == "train_frequency":
            baseline = brier
    if baseline is not None:
        for item in aggregate.values():
            item["brier_improvement_vs_train_frequency"] = baseline - item["brier"]
    best = min(aggregate, key=lambda name: aggregate[name]["brier"]) if aggregate else None
    return {"folds": fold_reports, "aggregate": aggregate, "best_model": best}


def _trait_summary(rows: list[dict], key: str) -> dict[str, dict]:
    groups: dict[object, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return {
        str(value): {
            "hits": len(group),
            "proc_hits": sum(bool(row["proc"]) for row in group),
            "proc_rate": _frequency(group),
            "battles": len({row["battle_id"] for row in group}),
        }
        for value, group in groups.items()
    }


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    rows: list[dict] = []
    errors: list[str] = []
    battle_ids: set[str] = set()
    for decision in decisions:
        battle_ids.add(str(decision.get("battle_id", "")))
        try:
            rows.extend(_damage_rows(decision))
        except Exception as exc:
            errors.append(
                f"{decision.get('battle_id')}:{decision.get('decision_index')}:"
                f"{type(exc).__name__}:{exc}"
            )
    primary = [row for row in rows if row["relation"] == "primary"]
    counter = [row for row in rows if row["relation"] == "counter"]
    return {
        "ability": ABILITY,
        "evidence_scope": "chronological_rolling_hit_probability",
        "corpus_battles_seen": len(battle_ids),
        "analysis_errors": errors,
        "primary_hits": len(primary),
        "primary_proc_hits": sum(bool(row["proc"]) for row in primary),
        "primary_proc_rate": _frequency(primary),
        "counter_hits": len(counter),
        "counter_proc_hits": sum(bool(row["proc"]) for row in counter),
        "counter_proc_rate": _frequency(counter),
        "primary_traits": {
            "target_big": _trait_summary(primary, "target_big"),
            "target_mechanical": _trait_summary(primary, "target_mechanical"),
            "target_undead": _trait_summary(primary, "target_undead"),
            "hit_ordinal": _trait_summary(primary, "hit_ordinal_same_pair"),
            "action_type": _trait_summary(primary, "action_type"),
            "source_creature": _trait_summary(primary, "source_creature_id"),
        },
        "primary_rolling": _rolling_metrics(primary),
        "counter_rolling": _rolling_metrics(counter),
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))
    replay_errors: list[str] = []

    def stream():
        for battle_dir in battle_dirs:
            if not (battle_dir / "init.txt").exists() or not (battle_dir / "turns0.txt").exists():
                continue
            try:
                yield from iter_battle_decisions(battle_dir)
            except Exception as exc:
                replay_errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")

    report = analyze_decisions(stream())
    report["corpus_battle_dirs"] = len(battle_dirs)
    report["replay_errors"] = replay_errors
    report["corpus"] = str(corpus)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Crippling Wound chronological probability audit.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["analysis_errors"] or report["replay_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
