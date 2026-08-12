from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


ABILITY = "cripplingwound"
WIRE_CODE = "wnd"
ATTACK_TYPES = frozenset({"MELEE_ATTACK", "RANGED_ATTACK"})
HOLDOUT_FRACTION = 0.20


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _paired_wnd(commands: list, damage_index: int, source_uid: int, target_uid: int) -> list:
    """Return same-pair Swnd records attributable to one DAMAGE hit.

    Stop at the next DAMAGE from the same source to the same target. This makes
    repeated/double attacks separate Bernoulli observations instead of collapsing an
    entire decision into one proc label.
    """
    out = []
    for command in commands[damage_index + 1 :]:
        if (
            command.opcode == "DAMAGE"
            and command.actor_uid == source_uid
            and command.target_uid == target_uid
        ):
            break
        if (
            command.opcode == "SPECIAL"
            and command.code == WIRE_CODE
            and command.actor_uid == source_uid
            and command.target_uid == target_uid
        ):
            out.append(command)
    return out


def _damage_rows(decision: dict) -> list[dict]:
    action_type = str(decision.get("action_type", ""))
    if action_type not in ATTACK_TYPES:
        return []
    before = list(decision.get("state_before") or [])
    actor_uid = int(decision.get("actor_uid", -1))
    primary_raw = decision.get("target_uid")
    primary_uid = int(primary_raw) if primary_raw is not None else None
    commands = parse_commands(str(decision.get("raw", "")))

    pair_ordinals: Counter[tuple[int, int]] = Counter()
    rows: list[dict] = []
    for index, command in enumerate(commands):
        if (
            command.opcode != "DAMAGE"
            or command.actor_uid is None
            or command.target_uid is None
        ):
            continue
        source_uid = int(command.actor_uid)
        target_uid = int(command.target_uid)
        source = _by_uid(before, source_uid)
        target = _by_uid(before, target_uid)
        source_abilities = _abilities(source)
        if ABILITY not in source_abilities:
            continue

        if source_uid == actor_uid and target_uid == primary_uid:
            relation = "primary"
        elif primary_uid is not None and source_uid == primary_uid and target_uid == actor_uid:
            relation = "counter"
        else:
            relation = "other"

        pair = (source_uid, target_uid)
        pair_ordinals[pair] += 1
        wound = _paired_wnd(commands, index, source_uid, target_uid)
        target_abilities = _abilities(target)
        source_owner = int(source.get("owner", -1)) if source else None
        target_owner = int(target.get("owner", -1)) if target else None
        rows.append(
            {
                "battle_id": str(decision.get("battle_id", "")),
                "decision_index": int(decision.get("decision_index", -1)),
                "server_turn": int(decision.get("server_turn", -1)),
                "action_type": action_type,
                "relation": relation,
                "source_uid": source_uid,
                "target_uid": target_uid,
                "source_owner": source_owner,
                "target_owner": target_owner,
                "enemy_by_prestate": bool(
                    source_owner is not None
                    and target_owner is not None
                    and source_owner != target_owner
                ),
                "source_creature_id": int(source.get("creature_id", 0)) if source else None,
                "target_creature_id": int(target.get("creature_id", 0)) if target else None,
                "source_abilities": sorted(source_abilities),
                "target_abilities": sorted(target_abilities),
                "target_big": "big" in target_abilities,
                "target_mechanical": "mechanical" in target_abilities,
                "target_undead": "undead" in target_abilities,
                "hit_ordinal_same_pair": int(pair_ordinals[pair]),
                "damage_index": index,
                "damage": int(command.amount) if command.amount is not None else None,
                "proc": bool(wound),
                "proc_records": [c.raw for c in wound],
                "proc_record_count": len(wound),
                "raw": str(decision.get("raw", "")),
            }
        )
    return rows


def _chronological_split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    battle_ids = sorted(
        {r["battle_id"] for r in rows},
        key=lambda x: (0, int(x)) if str(x).isdigit() else (1, str(x)),
    )
    if len(battle_ids) < 2:
        return rows[:], []
    n_holdout = max(1, math.ceil(len(battle_ids) * HOLDOUT_FRACTION))
    holdout_ids = set(battle_ids[-n_holdout:])
    return (
        [r for r in rows if r["battle_id"] not in holdout_ids],
        [r for r in rows if r["battle_id"] in holdout_ids],
    )


def _frequency(rows: list[dict]) -> float:
    return sum(bool(r["proc"]) for r in rows) / len(rows) if rows else 0.0


def _brier(rows: list[dict], probabilities: list[float]) -> float:
    if not rows:
        return float("nan")
    return sum(
        (float(p) - float(bool(row["proc"]))) ** 2
        for row, p in zip(rows, probabilities)
    ) / len(rows)


def _auc(rows: list[dict], probabilities: list[float]) -> float | None:
    positives = [(p, r) for p, r in zip(probabilities, rows) if r["proc"]]
    negatives = [(p, r) for p, r in zip(probabilities, rows) if not r["proc"]]
    if not positives or not negatives:
        return None
    wins = 0.0
    for pp, _ in positives:
        for pn, _ in negatives:
            if pp > pn:
                wins += 1.0
            elif pp == pn:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _smoothed(train: list[dict], holdout: list[dict], key: str, prior: float = 8.0) -> list[float]:
    base = _frequency(train)
    groups: dict[object, list[int]] = defaultdict(list)
    for row in train:
        groups[row[key]].append(int(bool(row["proc"])))
    result = []
    for row in holdout:
        ys = groups.get(row[key], [])
        result.append((sum(ys) + prior * base) / (len(ys) + prior))
    return result


def _model_metrics(rows: list[dict]) -> dict:
    train, holdout = _chronological_split(rows)
    out = {
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "train_battles": len({r["battle_id"] for r in train}),
        "holdout_battles": len({r["battle_id"] for r in holdout}),
    }
    if not train or not holdout:
        return {**out, "models": {}}
    base_p = _frequency(train)
    probabilities = {
        "train_frequency": [base_p] * len(holdout),
        "action_type_smoothed": _smoothed(train, holdout, "action_type"),
        "source_creature_smoothed": _smoothed(train, holdout, "source_creature_id"),
        "target_creature_smoothed": _smoothed(train, holdout, "target_creature_id"),
        "target_big_smoothed": _smoothed(train, holdout, "target_big"),
        "target_mechanical_smoothed": _smoothed(train, holdout, "target_mechanical"),
        "target_undead_smoothed": _smoothed(train, holdout, "target_undead"),
        "hit_ordinal_smoothed": _smoothed(train, holdout, "hit_ordinal_same_pair"),
    }
    models = {
        name: {
            "brier": _brier(holdout, probs),
            "auc": _auc(holdout, probs),
            "mean_p": sum(probs) / len(probs),
        }
        for name, probs in probabilities.items()
    }
    baseline = models["train_frequency"]["brier"]
    for item in models.values():
        item["brier_improvement_vs_baseline"] = baseline - item["brier"]
    best = min(models, key=lambda name: models[name]["brier"])
    return {
        **out,
        "train_proc_rate": base_p,
        "holdout_proc_rate": _frequency(holdout),
        "best_model": best,
        "models": models,
    }


def _summary(rows: list[dict]) -> dict:
    return {
        "hits": len(rows),
        "proc_hits": sum(bool(r["proc"]) for r in rows),
        "no_proc_hits": sum(not bool(r["proc"]) for r in rows),
        "proc_rate": _frequency(rows),
        "battles": len({r["battle_id"] for r in rows}),
        "action_types": _counter(Counter(r["action_type"] for r in rows)),
        "proc_action_types": _counter(Counter(r["action_type"] for r in rows if r["proc"])),
        "hit_ordinals": _counter(Counter(r["hit_ordinal_same_pair"] for r in rows)),
        "proc_hit_ordinals": _counter(Counter(r["hit_ordinal_same_pair"] for r in rows if r["proc"])),
        "source_creatures": _counter(Counter(r["source_creature_id"] for r in rows)),
    }


def _compact(row: dict) -> dict:
    return {
        key: row[key]
        for key in (
            "battle_id",
            "decision_index",
            "server_turn",
            "action_type",
            "relation",
            "source_uid",
            "target_uid",
            "source_owner",
            "target_owner",
            "source_creature_id",
            "target_creature_id",
            "source_abilities",
            "target_abilities",
            "hit_ordinal_same_pair",
            "damage",
            "proc",
            "proc_records",
            "raw",
        )
    }


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    rows: list[dict] = []
    battle_ids: set[str] = set()
    errors: list[str] = []
    for decision in decisions:
        battle_ids.add(str(decision.get("battle_id", "")))
        try:
            rows.extend(_damage_rows(decision))
        except Exception as exc:
            errors.append(
                f"{decision.get('battle_id')}:{decision.get('decision_index')}:"
                f"{type(exc).__name__}:{exc}"
            )

    primary = [r for r in rows if r["relation"] == "primary"]
    counter = [r for r in rows if r["relation"] == "counter"]
    other = [r for r in rows if r["relation"] == "other"]
    proc_rows = [r for r in rows if r["proc"]]
    multi_marker_hits = [r for r in proc_rows if r["proc_record_count"] != 1]
    non_enemy_proc = [r for r in proc_rows if not r["enemy_by_prestate"]]

    return {
        "ability": ABILITY,
        "evidence_scope": "hit_level_raw_damage_to_swnd",
        "corpus_battles_seen": len(battle_ids),
        "analysis_errors": errors,
        "all_carrier_damage_hits": _summary(rows),
        "primary_attack_hits": _summary(primary),
        "counter_hits": _summary(counter),
        "other_damage_hits": _summary(other),
        "primary_temporal_holdout": _model_metrics(primary),
        "counter_temporal_holdout": _model_metrics(counter),
        "proc_marker_invariants": {
            "proc_hits": len(proc_rows),
            "exactly_one_marker_per_proc_hit": len(proc_rows) - len(multi_marker_hits),
            "multi_marker_hits": len(multi_marker_hits),
            "non_enemy_by_prestate_proc_hits": len(non_enemy_proc),
        },
        "multi_marker_examples": [_compact(r) for r in multi_marker_hits[:20]],
        "non_enemy_proc_examples": [_compact(r) for r in non_enemy_proc[:20]],
        "other_proc_examples": [_compact(r) for r in other if r["proc"]][:20],
        "primary_proc_examples": [_compact(r) for r in primary if r["proc"]][:15],
        "counter_proc_examples": [_compact(r) for r in counter if r["proc"]][:15],
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    parse_errors: list[str] = []

    def stream():
        if not root.is_dir():
            raise FileNotFoundError(root)
        dirs = [p for p in root.iterdir() if p.is_dir()]
        dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))
        for battle_dir in dirs:
            if not (battle_dir / "init.txt").exists() or not (battle_dir / "turns0.txt").exists():
                continue
            try:
                yield from iter_battle_decisions(battle_dir)
            except Exception as exc:
                parse_errors.append(f"{battle_dir.name}:{type(exc).__name__}:{exc}")

    report = analyze_decisions(stream())
    report["corpus"] = str(corpus)
    report["parse_errors"] = parse_errors
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Crippling Wound hit-level raw evidence audit.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] or report["analysis_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
