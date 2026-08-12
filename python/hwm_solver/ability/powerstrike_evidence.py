from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


ABILITY = "powerstrike"
HOLDOUT_FRACTION = 0.20


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
    max_hp = max(1, int(entity.get("max_hp", entity.get("max_hp_per_unit", 1))))
    top_hp = max(0, int(entity.get("top_hp", entity.get("top_unit_hp", max_hp))))
    return (count - 1) * max_hp + top_hp


def _chebyshev(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


def _powerstrike_wire(decision: dict) -> dict:
    """Extract the candidate Power Strike raw signature without mutating replay state.

    The candidate is intentionally strict: primary actor DAMAGE -> target forced-position
    -> I<target><actor>. I-record semantics are not assumed here; the following target
    `i...0000` state marker is counted separately as corroborating wire evidence.
    """
    actor_uid = int(decision.get("actor_uid", -1))
    target_raw = decision.get("target_uid")
    target_uid = int(target_raw) if target_raw is not None else None
    commands = parse_commands(str(decision.get("raw", "")))

    damage_idx = next(
        (
            i
            for i, c in enumerate(commands)
            if c.opcode == "DAMAGE"
            and c.actor_uid == actor_uid
            and target_uid is not None
            and c.target_uid == target_uid
        ),
        None,
    )
    forced = [
        (i, c)
        for i, c in enumerate(commands)
        if c.opcode == "FORCED_POSITION"
        and target_uid is not None
        and c.actor_uid == target_uid
    ]
    i_records = [
        (i, c)
        for i, c in enumerate(commands)
        if c.opcode == "I_RECORD"
        and target_uid is not None
        and c.actor_uid == target_uid
        and c.target_uid == actor_uid
    ]

    pair: tuple[int, object, int, object] | None = None
    if damage_idx is not None:
        for fi, fc in forced:
            if fi <= damage_idx:
                continue
            match = next(((ii, ic) for ii, ic in i_records if ii > fi), None)
            if match:
                pair = (fi, fc, match[0], match[1])
                break

    zero_state_after_i = False
    forced_xy: list[int] | None = None
    if pair:
        _fi, fc, ii, _ic = pair
        forced_xy = [int(fc.x), int(fc.y)] if fc.x is not None and fc.y is not None else None
        zero_state_after_i = any(
            c.opcode == "STATE"
            and c.actor_uid == target_uid
            and c.code == "0000"
            for c in commands[ii + 1 :]
        )

    retaliation = False
    retaliation_after_i = False
    if damage_idx is not None and target_uid is not None:
        retaliation_indices = [
            i
            for i, c in enumerate(commands)
            if i > damage_idx
            and c.opcode == "DAMAGE"
            and c.actor_uid == target_uid
            and c.target_uid == actor_uid
        ]
        retaliation = bool(retaliation_indices)
        if pair and retaliation_indices:
            retaliation_after_i = any(i > pair[2] for i in retaliation_indices)

    return {
        "proc": pair is not None,
        "forced_xy": forced_xy,
        "zero_state_after_i": zero_state_after_i,
        "retaliation": retaliation,
        "retaliation_after_i": retaliation_after_i,
        "opcodes": [c.opcode for c in commands],
        "raw_i_records": [c.raw for _i, c in i_records],
    }


def _attack_row(decision: dict) -> dict | None:
    if str(decision.get("action_type")) != "MELEE_ATTACK":
        return None
    before = list(decision.get("state_before") or [])
    actor_uid = int(decision.get("actor_uid", -1))
    target_raw = decision.get("target_uid")
    if target_raw is None:
        return None
    target_uid = int(target_raw)
    actor = _by_uid(before, actor_uid)
    target = _by_uid(before, target_uid)
    if actor is None or target is None:
        return None

    wire = _powerstrike_wire(decision)
    commands = parse_commands(str(decision.get("raw", "")))
    primary_damage = next(
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
    attack_move = None
    for c in commands:
        if c.opcode == "MOVE" and c.actor_uid == actor_uid:
            attack_move = c
        if c.opcode == "DAMAGE" and c.actor_uid == actor_uid and c.target_uid == target_uid:
            break
    ax = int(attack_move.x) if attack_move and attack_move.x is not None else int(actor.get("x", 0))
    ay = int(attack_move.y) if attack_move and attack_move.y is not None else int(actor.get("y", 0))
    tx, ty = int(target.get("x", 0)), int(target.get("y", 0))
    before_actor_x, before_actor_y = int(actor.get("x", 0)), int(actor.get("y", 0))

    forced_changed = False
    if wire["forced_xy"] is not None:
        forced_changed = tuple(wire["forced_xy"]) != (tx, ty)

    target_abilities = _abilities(target)
    actor_abilities = _abilities(actor)
    return {
        "battle_id": str(decision.get("battle_id", "")),
        "decision_index": int(decision.get("decision_index", -1)),
        "server_turn": int(decision.get("server_turn", -1)),
        "actor_uid": actor_uid,
        "target_uid": target_uid,
        "actor_creature_id": int(actor.get("creature_id", 0)),
        "target_creature_id": int(target.get("creature_id", 0)),
        "actor_abilities": sorted(actor_abilities),
        "target_abilities": sorted(target_abilities),
        "actor_count": int(actor.get("count", 0)),
        "target_count": int(target.get("count", 0)),
        "actor_total_hp": _total_hp(actor),
        "target_total_hp": _total_hp(target),
        "primary_damage": primary_damage,
        "target_total_hp_after_primary": max(0, _total_hp(target) - primary_damage),
        "actor_atb": float(actor.get("atb", 0.0)),
        "target_atb": float(target.get("atb", 0.0)),
        "actor_x": before_actor_x,
        "actor_y": before_actor_y,
        "attack_x": ax,
        "attack_y": ay,
        "target_x": tx,
        "target_y": ty,
        "travelled_cells": _chebyshev(before_actor_x, before_actor_y, ax, ay),
        "target_big": "big" in target_abilities,
        "target_nonshiftable": "nonshiftable" in target_abilities,
        "target_mechanical": "mechanical" in target_abilities,
        "target_alive_before": bool(target.get("alive", True)),
        "proc": bool(wire["proc"]),
        "forced_changed": forced_changed,
        "zero_state_after_i": bool(wire["zero_state_after_i"]),
        "retaliation": bool(wire["retaliation"]),
        "retaliation_after_i": bool(wire["retaliation_after_i"]),
        "raw_i_records": wire["raw_i_records"],
        "raw": str(decision.get("raw", "")),
    }


def _brier(rows: list[dict], probabilities: list[float]) -> float:
    if not rows:
        return float("nan")
    return sum((float(p) - float(bool(r["proc"]))) ** 2 for r, p in zip(rows, probabilities)) / len(rows)


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
    for r, p in zip(rows, probabilities):
        idx = min(bins - 1, max(0, int(float(p) * bins)))
        buckets[idx].append((float(p), int(bool(r["proc"]))))
    out = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        out.append(
            {
                "bin": i,
                "n": len(bucket),
                "mean_p": sum(p for p, _y in bucket) / len(bucket),
                "observed": sum(y for _p, y in bucket) / len(bucket),
            }
        )
    return out


def _chronological_split(rows: list[dict], fraction: float = HOLDOUT_FRACTION) -> tuple[list[dict], list[dict]]:
    battle_ids = sorted({r["battle_id"] for r in rows}, key=lambda x: int(x) if str(x).isdigit() else str(x))
    if len(battle_ids) < 2:
        return rows[:], []
    holdout_battles = max(1, math.ceil(len(battle_ids) * fraction))
    cutoff = set(battle_ids[-holdout_battles:])
    train = [r for r in rows if r["battle_id"] not in cutoff]
    holdout = [r for r in rows if r["battle_id"] in cutoff]
    return train, holdout


def _frequency(rows: list[dict]) -> float:
    return sum(bool(r["proc"]) for r in rows) / len(rows) if rows else 0.0


def _smoothed_group_probability(
    train: list[dict], holdout: list[dict], key: str, *, prior_strength: float = 8.0
) -> list[float]:
    global_p = _frequency(train)
    groups: dict[object, list[int]] = defaultdict(list)
    for r in train:
        groups[r[key]].append(int(bool(r["proc"])))
    result: list[float] = []
    for r in holdout:
        ys = groups.get(r[key], [])
        result.append((sum(ys) + prior_strength * global_p) / (len(ys) + prior_strength))
    return result


def _eligibility_probability(train: list[dict], holdout: list[dict]) -> list[float]:
    eligible = [r for r in train if not r["target_nonshiftable"]]
    p = _frequency(eligible) if eligible else _frequency(train)
    return [0.0 if r["target_nonshiftable"] else p for r in holdout]


def _reference_probability(attacker_hp: float, target_hp_after: float) -> float:
    """Current published post-hit formula, clipped to [5%, 75%]."""
    if attacker_hp <= 0 or target_hp_after <= 0:
        return 0.75 if attacker_hp > target_hp_after else 0.05
    if attacker_hp > target_hp_after:
        p = 0.25 + 0.03 * (attacker_hp / target_hp_after)
    else:
        p = 0.25 - 0.03 * (target_hp_after / attacker_hp)
    return max(0.05, min(0.75, p))


def _reference_probability_pre_hit(attacker_hp: float, target_hp: float) -> float:
    """Historical/pre-hit variant retained only as a falsification baseline."""
    if attacker_hp <= 0 or target_hp <= 0:
        return 0.75 if attacker_hp > target_hp else 0.05
    if attacker_hp > target_hp:
        p = 0.25 + 0.03 * (attacker_hp / target_hp)
    else:
        p = 0.25 - 0.03 * (target_hp / attacker_hp)
    return max(0.05, min(0.75, p))


def _model_metrics(rows: list[dict]) -> dict:
    train, holdout = _chronological_split(rows)
    if not train or not holdout:
        return {
            "train_rows": len(train),
            "holdout_rows": len(holdout),
            "train_battles": len({r["battle_id"] for r in train}),
            "holdout_battles": len({r["battle_id"] for r in holdout}),
            "models": {},
        }
    base_p = _frequency(train)
    candidates: dict[str, list[float]] = {
        "train_frequency": [base_p] * len(holdout),
        "nonshiftable_gate": _eligibility_probability(train, holdout),
        "actor_creature_smoothed": _smoothed_group_probability(train, holdout, "actor_creature_id"),
        "target_big_smoothed": _smoothed_group_probability(train, holdout, "target_big"),
        "travelled_cells_smoothed": _smoothed_group_probability(train, holdout, "travelled_cells"),
        "reference_post_hit_hp": [
            _reference_probability(r["actor_total_hp"], r["target_total_hp_after_primary"])
            for r in holdout
        ],
        "reference_pre_hit_hp": [
            _reference_probability_pre_hit(r["actor_total_hp"], r["target_total_hp"])
            for r in holdout
        ],
    }
    metrics = {}
    for name, probs in candidates.items():
        metrics[name] = {
            "brier": _brier(holdout, probs),
            "auc": _auc(holdout, probs),
            "calibration": _calibration(holdout, probs),
            "mean_p": sum(probs) / len(probs),
        }
    baseline = metrics["train_frequency"]["brier"]
    for name, item in metrics.items():
        item["brier_improvement_vs_baseline"] = baseline - item["brier"]
    best = min(metrics, key=lambda name: metrics[name]["brier"])
    return {
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "train_battles": len({r["battle_id"] for r in train}),
        "holdout_battles": len({r["battle_id"] for r in holdout}),
        "train_first_battle": min((r["battle_id"] for r in train), key=int),
        "train_last_battle": max((r["battle_id"] for r in train), key=int),
        "holdout_first_battle": min((r["battle_id"] for r in holdout), key=int),
        "holdout_last_battle": max((r["battle_id"] for r in holdout), key=int),
        "train_proc_rate": base_p,
        "holdout_proc_rate": _frequency(holdout),
        "best_model": best,
        "best_beats_baseline": best != "train_frequency" and metrics[best]["brier"] < baseline,
        "models": metrics,
    }


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    carrier_rows: list[dict] = []
    all_melee_rows: list[dict] = []
    battle_ids: set[str] = set()
    carrier_battle_ids: set[str] = set()
    errors: list[str] = []

    for decision in decisions:
        battle_ids.add(str(decision.get("battle_id", "")))
        try:
            row = _attack_row(decision)
        except Exception as exc:
            errors.append(
                f"{decision.get('battle_id')}:{decision.get('decision_index')}:{type(exc).__name__}:{exc}"
            )
            continue
        if row is None:
            continue
        all_melee_rows.append(row)
        if ABILITY in set(row["actor_abilities"]):
            carrier_rows.append(row)
            carrier_battle_ids.add(row["battle_id"])

    proc_rows = [r for r in carrier_rows if r["proc"]]
    no_proc_rows = [r for r in carrier_rows if not r["proc"]]
    control_proc_rows = [r for r in all_melee_rows if r["proc"] and ABILITY not in set(r["actor_abilities"])]

    source_ability_sets = Counter(
        ",".join(r["actor_abilities"]) or "<none>" for r in control_proc_rows
    )
    carrier_creatures = Counter(r["actor_creature_id"] for r in carrier_rows)
    proc_by_creature: dict[str, dict] = {}
    for creature_id in sorted(carrier_creatures):
        subset = [r for r in carrier_rows if r["actor_creature_id"] == creature_id]
        proc_by_creature[str(creature_id)] = {
            "attacks": len(subset),
            "procs": sum(r["proc"] for r in subset),
            "rate": _frequency(subset),
        }

    def count_flag(flag: str, rows: list[dict]) -> dict:
        return {
            "true": sum(bool(r[flag]) for r in rows),
            "false": sum(not bool(r[flag]) for r in rows),
        }

    evidence_examples = [
        {
            "battle_id": r["battle_id"],
            "decision_index": r["decision_index"],
            "actor_uid": r["actor_uid"],
            "target_uid": r["target_uid"],
            "actor_creature_id": r["actor_creature_id"],
            "target_creature_id": r["target_creature_id"],
            "forced_changed": r["forced_changed"],
            "zero_state_after_i": r["zero_state_after_i"],
            "retaliation": r["retaliation"],
            "raw_i_records": r["raw_i_records"],
            "raw": r["raw"],
        }
        for r in proc_rows[:20]
    ]
    no_proc_examples = [
        {
            "battle_id": r["battle_id"],
            "decision_index": r["decision_index"],
            "actor_uid": r["actor_uid"],
            "target_uid": r["target_uid"],
            "actor_creature_id": r["actor_creature_id"],
            "target_creature_id": r["target_creature_id"],
            "target_nonshiftable": r["target_nonshiftable"],
            "target_big": r["target_big"],
            "travelled_cells": r["travelled_cells"],
            "raw": r["raw"],
        }
        for r in no_proc_rows[:10]
    ]

    return {
        "ability": ABILITY,
        "runtime_status": "learned_damage",
        "runtime_status_reason": (
            "Read-only evidence phase: candidate wire/consequence may be promoted only after "
            "signature isolation and chronological probability gate."
        ),
        "corpus_battles_seen": len(battle_ids),
        "carrier_battles": len(carrier_battle_ids),
        "all_melee_attacks": len(all_melee_rows),
        "carrier_melee_attacks": len(carrier_rows),
        "proc_attacks": len(proc_rows),
        "no_proc_attacks": len(no_proc_rows),
        "observed_proc_rate": _frequency(carrier_rows),
        "carrier_creatures": dict(carrier_creatures.most_common()),
        "proc_by_creature": proc_by_creature,
        "signature": {
            "definition": "primary DAMAGE -> target FORCED_POSITION -> I<target><actor>",
            "zero_state_after_i": count_flag("zero_state_after_i", proc_rows),
            "forced_coordinate_changed": count_flag("forced_changed", proc_rows),
            "retaliation_present": count_flag("retaliation", proc_rows),
            "retaliation_after_i": count_flag("retaliation_after_i", proc_rows),
        },
        "negative_control": {
            "same_signature_non_powerstrike_melee": len(control_proc_rows),
            "source_ability_sets": dict(source_ability_sets.most_common(20)),
        },
        "target_ineligibility": {
            "nonshiftable": {
                "attacks": sum(r["target_nonshiftable"] for r in carrier_rows),
                "procs": sum(r["target_nonshiftable"] and r["proc"] for r in carrier_rows),
            },
            "big": {
                "attacks": sum(r["target_big"] for r in carrier_rows),
                "procs": sum(r["target_big"] and r["proc"] for r in carrier_rows),
            },
            "mechanical": {
                "attacks": sum(r["target_mechanical"] for r in carrier_rows),
                "procs": sum(r["target_mechanical"] and r["proc"] for r in carrier_rows),
            },
        },
        "temporal_holdout": _model_metrics(carrier_rows),
        "analysis_errors": errors,
        "proc_examples": evidence_examples,
        "no_proc_examples": no_proc_examples,
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
    ap = argparse.ArgumentParser(description="Read-only whole-corpus Power Strike evidence analysis.")
    ap.add_argument("corpus", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] or report["analysis_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
