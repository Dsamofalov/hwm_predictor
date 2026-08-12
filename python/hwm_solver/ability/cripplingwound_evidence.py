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
HOLDOUT_FRACTION = 0.20
ATTACK_TYPES = frozenset({"MELEE_ATTACK", "RANGED_ATTACK"})


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _total_hp(entity: dict | None) -> int:
    if not entity or not bool(entity.get("alive", True)):
        return 0
    count = max(0, int(entity.get("count", 0)))
    if count <= 0:
        return 0
    max_hp = max(1, int(entity.get("max_hp", 1)))
    top_hp = max(0, int(entity.get("top_hp", max_hp)))
    return (count - 1) * max_hp + top_hp


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _ability_set(entity: dict | None) -> str:
    values = sorted(_abilities(entity))
    return ",".join(values) if values else "<none>"


def _wire_records(decision: dict) -> list[dict]:
    before = list(decision.get("state_before") or [])
    commands = parse_commands(str(decision.get("raw", "")))
    actor_uid = int(decision.get("actor_uid", -1))
    primary_target_raw = decision.get("target_uid")
    primary_target_uid = int(primary_target_raw) if primary_target_raw is not None else None

    primary_damage_index = next(
        (
            i
            for i, c in enumerate(commands)
            if c.opcode == "DAMAGE"
            and c.actor_uid == actor_uid
            and primary_target_uid is not None
            and c.target_uid == primary_target_uid
        ),
        None,
    )
    retaliation_indices = [
        i
        for i, c in enumerate(commands)
        if c.opcode == "DAMAGE"
        and primary_target_uid is not None
        and c.actor_uid == primary_target_uid
        and c.target_uid == actor_uid
    ]

    out: list[dict] = []
    for i, c in enumerate(commands):
        if c.opcode != "SPECIAL" or c.code != WIRE_CODE:
            continue
        source = _by_uid(before, c.actor_uid)
        target = _by_uid(before, c.target_uid)
        source_uid = int(c.actor_uid) if c.actor_uid is not None else None
        target_uid = int(c.target_uid) if c.target_uid is not None else None
        if source_uid == actor_uid and target_uid == primary_target_uid:
            relation = "primary_actor_to_primary_target"
        elif (
            primary_target_uid is not None
            and source_uid == primary_target_uid
            and target_uid == actor_uid
        ):
            relation = "counter_source_to_actor"
        else:
            relation = "other"

        preceding_damage = next(
            (
                j
                for j in range(i - 1, -1, -1)
                if commands[j].opcode == "DAMAGE"
                and commands[j].actor_uid == source_uid
                and commands[j].target_uid == target_uid
            ),
            None,
        )
        out.append(
            {
                "index": i,
                "raw": c.raw,
                "trailer": c.raw[10:] if len(c.raw) >= 10 else "",
                "source_uid": source_uid,
                "target_uid": target_uid,
                "source_exists": source is not None,
                "target_exists": target is not None,
                "source_owner": int(source.get("owner", -1)) if source else None,
                "target_owner": int(target.get("owner", -1)) if target else None,
                "enemy": bool(
                    source
                    and target
                    and int(source.get("owner", -1)) != int(target.get("owner", -1))
                ),
                "source_creature_id": int(source.get("creature_id", 0)) if source else None,
                "target_creature_id": int(target.get("creature_id", 0)) if target else None,
                "source_abilities": sorted(_abilities(source)),
                "source_has_ability": ABILITY in _abilities(source),
                "relation": relation,
                "preceding_same_pair_damage_index": preceding_damage,
                "after_same_pair_damage": preceding_damage is not None,
                "after_primary_damage": (
                    primary_damage_index is not None and i > primary_damage_index
                ),
                "after_retaliation_damage": any(j < i for j in retaliation_indices),
                "window_from_damage": (
                    [commands[j].opcode for j in range(preceding_damage, i + 1)]
                    if preceding_damage is not None
                    else []
                ),
                "post_opcodes": [x.opcode for x in commands[i + 1 :]],
            }
        )
    return out


def _attack_row(decision: dict) -> dict | None:
    action_type = str(decision.get("action_type", ""))
    if action_type not in ATTACK_TYPES:
        return None
    before = list(decision.get("state_before") or [])
    after = list(decision.get("state_after") or [])
    actor_uid = int(decision.get("actor_uid", -1))
    target_raw = decision.get("target_uid")
    if target_raw is None:
        return None
    target_uid = int(target_raw)
    actor = _by_uid(before, actor_uid)
    target = _by_uid(before, target_uid)
    if actor is None or target is None:
        return None

    commands = parse_commands(str(decision.get("raw", "")))
    damage = next(
        (
            int(c.amount)
            for c in commands
            if c.opcode == "DAMAGE"
            and c.actor_uid == actor_uid
            and c.target_uid == target_uid
            and c.amount is not None
        ),
        0,
    )
    wires = _wire_records(decision)
    primary_wires = [w for w in wires if w["relation"] == "primary_actor_to_primary_target"]
    target_after = _by_uid(after, target_uid)
    target_abilities = _abilities(target)
    actor_abilities = _abilities(actor)
    target_hp = _total_hp(target)

    return {
        "battle_id": str(decision.get("battle_id", "")),
        "decision_index": int(decision.get("decision_index", -1)),
        "server_turn": int(decision.get("server_turn", -1)),
        "action_type": action_type,
        "actor_uid": actor_uid,
        "target_uid": target_uid,
        "actor_owner": int(actor.get("owner", -1)),
        "target_owner": int(target.get("owner", -1)),
        "actor_creature_id": int(actor.get("creature_id", 0)),
        "target_creature_id": int(target.get("creature_id", 0)),
        "actor_abilities": sorted(actor_abilities),
        "target_abilities": sorted(target_abilities),
        "actor_count": int(actor.get("count", 0)),
        "target_count": int(target.get("count", 0)),
        "actor_total_hp": _total_hp(actor),
        "target_total_hp": target_hp,
        "target_big": "big" in target_abilities,
        "target_mechanical": "mechanical" in target_abilities,
        "target_undead": "undead" in target_abilities,
        "damage": damage,
        "lethal_primary_damage": damage >= target_hp > 0,
        "proc": bool(primary_wires),
        "primary_wire_count": len(primary_wires),
        "all_wires": wires,
        "target_effect_before": "proc_cripple" in set(target.get("effects") or []),
        "target_effect_after": bool(
            target_after and "proc_cripple" in set(target_after.get("effects") or [])
        ),
        "target_effect_turns_after": (
            int((target_after.get("effect_turns") or {}).get("proc_cripple", -1))
            if target_after
            else None
        ),
        "raw": str(decision.get("raw", "")),
    }


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
        (float(p) - float(bool(r["proc"]))) ** 2
        for r, p in zip(rows, probabilities)
    ) / len(rows)


def _auc(rows: list[dict], probabilities: list[float]) -> float | None:
    pairs = [(float(p), int(bool(r["proc"]))) for r, p in zip(rows, probabilities)]
    positives = sum(y for _p, y in pairs)
    negatives = len(pairs) - positives
    if positives == 0 or negatives == 0:
        return None
    wins = 0.0
    for pp, yp in pairs:
        if not yp:
            continue
        for pn, yn in pairs:
            if yn:
                continue
            if pp > pn:
                wins += 1.0
            elif pp == pn:
                wins += 0.5
    return wins / (positives * negatives)


def _calibration(rows: list[dict], probabilities: list[float], bins: int = 5) -> list[dict]:
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for row, p in zip(rows, probabilities):
        idx = min(bins - 1, max(0, int(float(p) * bins)))
        buckets[idx].append((float(p), int(bool(row["proc"]))))
    out: list[dict] = []
    for i, bucket in enumerate(buckets):
        if bucket:
            out.append(
                {
                    "bin": i,
                    "n": len(bucket),
                    "mean_p": sum(p for p, _y in bucket) / len(bucket),
                    "observed": sum(y for _p, y in bucket) / len(bucket),
                }
            )
    return out


def _smoothed_group_probability(
    train: list[dict], holdout: list[dict], key: str, *, prior_strength: float = 8.0
) -> list[float]:
    global_p = _frequency(train)
    groups: dict[object, list[int]] = defaultdict(list)
    for row in train:
        groups[row[key]].append(int(bool(row["proc"])))
    out: list[float] = []
    for row in holdout:
        ys = groups.get(row[key], [])
        out.append((sum(ys) + prior_strength * global_p) / (len(ys) + prior_strength))
    return out


def _model_metrics(rows: list[dict]) -> dict:
    train, holdout = _chronological_split(rows)
    base = {
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "train_battles": len({r["battle_id"] for r in train}),
        "holdout_battles": len({r["battle_id"] for r in holdout}),
    }
    if not train or not holdout:
        return {**base, "models": {}}

    train_p = _frequency(train)
    candidates = {
        "train_frequency": [train_p] * len(holdout),
        "action_type_smoothed": _smoothed_group_probability(train, holdout, "action_type"),
        "actor_creature_smoothed": _smoothed_group_probability(train, holdout, "actor_creature_id"),
        "target_creature_smoothed": _smoothed_group_probability(train, holdout, "target_creature_id"),
        "target_big_smoothed": _smoothed_group_probability(train, holdout, "target_big"),
        "target_mechanical_smoothed": _smoothed_group_probability(train, holdout, "target_mechanical"),
        "target_undead_smoothed": _smoothed_group_probability(train, holdout, "target_undead"),
    }
    models: dict[str, dict] = {}
    for name, probabilities in candidates.items():
        models[name] = {
            "brier": _brier(holdout, probabilities),
            "auc": _auc(holdout, probabilities),
            "mean_p": sum(probabilities) / len(probabilities),
            "calibration": _calibration(holdout, probabilities),
        }
    baseline = models["train_frequency"]["brier"]
    for item in models.values():
        item["brier_improvement_vs_baseline"] = baseline - item["brier"]
    best = min(models, key=lambda name: models[name]["brier"])
    return {
        **base,
        "train_proc_rate": train_p,
        "holdout_proc_rate": _frequency(holdout),
        "best_model": best,
        "models": models,
    }


def _compact_row(row: dict) -> dict:
    return {
        "battle_id": row["battle_id"],
        "decision_index": row["decision_index"],
        "server_turn": row["server_turn"],
        "action_type": row["action_type"],
        "actor_uid": row["actor_uid"],
        "target_uid": row["target_uid"],
        "actor_creature_id": row["actor_creature_id"],
        "target_creature_id": row["target_creature_id"],
        "actor_abilities": row["actor_abilities"],
        "target_abilities": row["target_abilities"],
        "damage": row["damage"],
        "lethal_primary_damage": row["lethal_primary_damage"],
        "target_effect_before": row["target_effect_before"],
        "target_effect_after": row["target_effect_after"],
        "target_effect_turns_after": row["target_effect_turns_after"],
        "wires": row["all_wires"],
        "raw": row["raw"],
    }


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    battle_ids: set[str] = set()
    errors: list[str] = []
    attack_rows: list[dict] = []
    all_wires: list[dict] = []

    for decision in decisions:
        battle_id = str(decision.get("battle_id", ""))
        battle_ids.add(battle_id)
        try:
            wires = _wire_records(decision)
            for wire in wires:
                all_wires.append(
                    {
                        **wire,
                        "battle_id": battle_id,
                        "decision_index": int(decision.get("decision_index", -1)),
                        "server_turn": int(decision.get("server_turn", -1)),
                        "decision_actor_uid": int(decision.get("actor_uid", -1)),
                        "decision_target_uid": (
                            int(decision["target_uid"])
                            if decision.get("target_uid") is not None
                            else None
                        ),
                        "action_type": str(decision.get("action_type", "")),
                        "raw_decision": str(decision.get("raw", "")),
                    }
                )
            row = _attack_row(decision)
            if row is not None:
                attack_rows.append(row)
        except Exception as exc:
            errors.append(
                f"{battle_id}:{decision.get('decision_index')}:"
                f"{type(exc).__name__}:{exc}"
            )

    carrier_attacks = [r for r in attack_rows if ABILITY in set(r["actor_abilities"])]
    carrier_proc = [r for r in carrier_attacks if r["proc"]]
    carrier_no_proc = [r for r in carrier_attacks if not r["proc"]]
    source_carrier_wires = [w for w in all_wires if w["source_has_ability"]]
    noncarrier_wires = [w for w in all_wires if not w["source_has_ability"]]
    primary_wires = [w for w in source_carrier_wires if w["relation"] == "primary_actor_to_primary_target"]
    counter_wires = [w for w in source_carrier_wires if w["relation"] == "counter_source_to_actor"]
    other_wires = [w for w in source_carrier_wires if w["relation"] == "other"]

    wire_action_types = Counter(w["action_type"] for w in source_carrier_wires)
    source_ability_sets = Counter(
        ",".join(w["source_abilities"]) or "<none>" for w in source_carrier_wires
    )
    trailer = Counter(w["trailer"] for w in source_carrier_wires)
    windows = Counter("->".join(w["window_from_damage"]) or "<no-pair-damage>" for w in source_carrier_wires)
    post = Counter("->".join(w["post_opcodes"]) or "<end>" for w in source_carrier_wires)

    return {
        "ability": ABILITY,
        "runtime_status": "evidence_only",
        "evidence_scope": "full_raw_corpus_read_only",
        "corpus_battles_seen": len(battle_ids),
        "attack_decisions": len(attack_rows),
        "analysis_errors": errors,
        "wire": {
            "records_total": len(all_wires),
            "source_carrier_records": len(source_carrier_wires),
            "noncarrier_source_records": len(noncarrier_wires),
            "primary_actor_target_records": len(primary_wires),
            "counter_source_records": len(counter_wires),
            "other_relation_records": len(other_wires),
            "enemy_records": sum(bool(w["enemy"]) for w in source_carrier_wires),
            "after_same_pair_damage": sum(bool(w["after_same_pair_damage"]) for w in source_carrier_wires),
            "action_types": _counter(wire_action_types),
            "source_ability_sets": _counter(source_ability_sets),
            "trailer_telemetry": _counter(trailer),
            "damage_to_wire_windows": _counter(windows),
            "post_wire_opcodes": _counter(post),
        },
        "carrier_attacks": {
            "total": len(carrier_attacks),
            "proc": len(carrier_proc),
            "no_proc": len(carrier_no_proc),
            "observed_rate": _frequency(carrier_attacks),
            "action_types": _counter(Counter(r["action_type"] for r in carrier_attacks)),
            "proc_action_types": _counter(Counter(r["action_type"] for r in carrier_proc)),
            "ability_sets": _counter(Counter(",".join(r["actor_abilities"]) for r in carrier_attacks)),
            "creatures": _counter(Counter(r["actor_creature_id"] for r in carrier_attacks)),
            "battles": len({r["battle_id"] for r in carrier_attacks}),
        },
        "observed_consequence": {
            "canonical_proc_effect_after": {
                "true": sum(bool(r["target_effect_after"]) for r in carrier_proc),
                "false": sum(not bool(r["target_effect_after"]) for r in carrier_proc),
            },
            "canonical_effect_turns_after": _counter(
                Counter(r["target_effect_turns_after"] for r in carrier_proc)
            ),
            "proc_on_lethal_primary_damage": sum(bool(r["lethal_primary_damage"]) for r in carrier_proc),
            "proc_target_already_marked_before": sum(bool(r["target_effect_before"]) for r in carrier_proc),
        },
        "temporal_holdout": _model_metrics(carrier_attacks),
        "noncarrier_wire_examples": noncarrier_wires[:20],
        "other_relation_examples": other_wires[:20],
        "proc_examples": [_compact_row(r) for r in carrier_proc[:30]],
        "no_proc_examples": [_compact_row(r) for r in carrier_no_proc[:12]],
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    parse_errors: list[str] = []

    def stream():
        if not root.is_dir():
            raise FileNotFoundError(root)
        battle_dirs = [p for p in root.iterdir() if p.is_dir()]
        battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))
        for battle_dir in battle_dirs:
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
    parser = argparse.ArgumentParser(description="Read-only Crippling Wound corpus evidence audit.")
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
