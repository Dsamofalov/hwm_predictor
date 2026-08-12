from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from hwm_solver.ability.powerstrike_evidence import ABILITY, _attack_row, _model_metrics
from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


PAWSTRIKE = "pawstrike"


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


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _footprint(entity: dict, *, x: int | None = None, y: int | None = None) -> set[tuple[int, int]]:
    ax = int(entity.get("x", 0) if x is None else x)
    ay = int(entity.get("y", 0) if y is None else y)
    size = 2 if "big" in _abilities(entity) else 1
    return {(ax + dx, ay + dy) for dx in range(size) for dy in range(size)}


def _wire_details(decision: dict) -> dict:
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
    if damage_idx is None or target_uid is None:
        return {
            "matched": False,
            "window_opcodes": [],
            "post_i_opcodes": [],
            "forced_xy": None,
            "raw_i": None,
        }

    forced_pair = next(
        (
            (i, c)
            for i, c in enumerate(commands)
            if i > damage_idx and c.opcode == "FORCED_POSITION" and c.actor_uid == target_uid
        ),
        None,
    )
    if forced_pair is None:
        return {
            "matched": False,
            "window_opcodes": [],
            "post_i_opcodes": [],
            "forced_xy": None,
            "raw_i": None,
        }
    forced_idx, forced = forced_pair

    i_pair = next(
        (
            (i, c)
            for i, c in enumerate(commands)
            if i > forced_idx
            and c.opcode == "I_RECORD"
            and c.actor_uid == target_uid
            and c.target_uid == actor_uid
        ),
        None,
    )
    if i_pair is None:
        return {
            "matched": False,
            "window_opcodes": [],
            "post_i_opcodes": [],
            "forced_xy": None,
            "raw_i": None,
        }
    i_idx, i_record = i_pair
    forced_xy = (
        [int(forced.x), int(forced.y)]
        if forced.x is not None and forced.y is not None
        else None
    )
    return {
        "matched": True,
        "damage_index": damage_idx,
        "forced_index": forced_idx,
        "i_index": i_idx,
        "window_opcodes": [c.opcode for c in commands[damage_idx : i_idx + 1]],
        "post_i_opcodes": [c.opcode for c in commands[i_idx + 1 :]],
        "forced_xy": forced_xy,
        "raw_i": i_record.raw,
        "i_first_uid": target_uid,
        "i_second_uid": actor_uid,
    }


def _forced_geometry(row: dict, decision: dict, wire: dict) -> dict:
    forced_xy = wire.get("forced_xy")
    if not wire.get("matched") or forced_xy is None:
        return {
            "kind": "none",
            "dx": None,
            "dy": None,
            "distance": None,
            "direction": "none",
            "destination_preoccupied": None,
            "target_after_matches_forced": None,
        }

    tx, ty = int(row["target_x"]), int(row["target_y"])
    fx, fy = int(forced_xy[0]), int(forced_xy[1])
    dx, dy = fx - tx, fy - ty
    distance = max(abs(dx), abs(dy))

    expected_dx = _sign(tx - int(row["attack_x"]))
    expected_dy = _sign(ty - int(row["attack_y"]))
    if dx == 0 and dy == 0:
        direction = "noop"
    elif (_sign(dx), _sign(dy)) == (expected_dx, expected_dy):
        direction = "away_from_attack_anchor"
    else:
        direction = "other"

    before = list(decision.get("state_before") or [])
    target = _by_uid(before, int(row["target_uid"]))
    destination_preoccupied = None
    if target is not None:
        destination_cells = _footprint(target, x=fx, y=fy)
        blockers: set[tuple[int, int]] = set()
        for entity in before:
            if int(entity.get("uid", -1)) == int(row["target_uid"]):
                continue
            if not bool(entity.get("alive", True)) or bool(entity.get("is_hero", False)):
                continue
            if "hidden" in _abilities(entity):
                continue
            blockers.update(_footprint(entity))
        destination_preoccupied = bool(destination_cells & blockers)

    after_target = _by_uid(list(decision.get("state_after") or []), int(row["target_uid"]))
    target_after_matches_forced = None
    if after_target is not None:
        target_after_matches_forced = (
            int(after_target.get("x", 0)), int(after_target.get("y", 0))
        ) == (fx, fy)

    return {
        "kind": "changed" if distance else "same_coordinate",
        "dx": dx,
        "dy": dy,
        "distance": distance,
        "direction": direction,
        "destination_preoccupied": destination_preoccupied,
        "target_after_matches_forced": target_after_matches_forced,
    }


def _extended_row(decision: dict, row: dict) -> dict:
    before = list(decision.get("state_before") or [])
    after = list(decision.get("state_after") or [])
    actor = _by_uid(before, int(row["actor_uid"]))
    target = _by_uid(before, int(row["target_uid"]))
    target_after = _by_uid(after, int(row["target_uid"]))
    wire = _wire_details(decision)
    geometry = _forced_geometry(row, decision, wire)

    actor_owner = int(actor.get("owner", -1)) if actor is not None else None
    target_owner = int(target.get("owner", -1)) if target is not None else None
    row = dict(row)
    row.update(
        {
            "actor_owner": actor_owner,
            "target_owner": target_owner,
            "enemy_target": (
                actor_owner is not None and target_owner is not None and actor_owner != target_owner
            ),
            "target_total_hp_after_decision": _total_hp(target_after),
            "target_count_after_decision": (
                int(target_after.get("count", 0)) if target_after is not None else None
            ),
            "wire": wire,
            "geometry": geometry,
        }
    )
    return row


def _counter_strings(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _ability_set_counter(rows: list[dict]) -> dict[str, int]:
    counter = Counter(
        ",".join(sorted(str(x).lower() for x in row.get("actor_abilities", []))) or "<none>"
        for row in rows
    )
    return _counter_strings(counter)


def _compact_example(row: dict) -> dict:
    return {
        "battle_id": row["battle_id"],
        "decision_index": row["decision_index"],
        "actor_uid": row["actor_uid"],
        "target_uid": row["target_uid"],
        "actor_creature_id": row["actor_creature_id"],
        "target_creature_id": row["target_creature_id"],
        "actor_abilities": row["actor_abilities"],
        "actor_owner": row["actor_owner"],
        "target_owner": row["target_owner"],
        "forced_changed": row["forced_changed"],
        "geometry": row["geometry"],
        "wire": row["wire"],
        "zero_state_after_i": row["zero_state_after_i"],
        "retaliation": row["retaliation"],
        "raw": row["raw"],
    }


def analyze_decisions(decisions: Iterable[dict]) -> dict:
    all_melee: list[dict] = []
    battle_ids: set[str] = set()
    errors: list[str] = []

    for decision in decisions:
        battle_ids.add(str(decision.get("battle_id", "")))
        try:
            base = _attack_row(decision)
            if base is None:
                continue
            all_melee.append(_extended_row(decision, base))
        except Exception as exc:
            errors.append(
                f"{decision.get('battle_id')}:{decision.get('decision_index')}:"
                f"{type(exc).__name__}:{exc}"
            )

    carrier = [r for r in all_melee if ABILITY in set(r["actor_abilities"])]
    carrier_proc = [r for r in carrier if r["proc"]]
    carrier_no_proc = [r for r in carrier if not r["proc"]]
    controls = [r for r in all_melee if r["proc"] and ABILITY not in set(r["actor_abilities"])]
    paw_controls = [r for r in controls if PAWSTRIKE in set(r["actor_abilities"])]
    unknown_controls = [r for r in controls if PAWSTRIKE not in set(r["actor_abilities"])]
    co_carriers = [r for r in carrier if PAWSTRIKE in set(r["actor_abilities"])]
    co_carrier_proc = [r for r in co_carriers if r["proc"]]

    proc_vectors = Counter(
        (r["geometry"]["dx"], r["geometry"]["dy"])
        for r in carrier_proc
        if r["geometry"]["dx"] is not None
    )
    proc_distances = Counter(
        r["geometry"]["distance"]
        for r in carrier_proc
        if r["geometry"]["distance"] is not None
    )
    proc_directions = Counter(r["geometry"]["direction"] for r in carrier_proc)
    proc_windows = Counter("->".join(r["wire"]["window_opcodes"]) for r in carrier_proc)
    control_windows = Counter("->".join(r["wire"]["window_opcodes"]) for r in controls)
    proc_post_i = Counter("->".join(r["wire"]["post_i_opcodes"]) or "<end>" for r in carrier_proc)

    owner_relation = Counter(
        "enemy" if r["enemy_target"] else "same_or_unknown" for r in carrier_proc
    )
    target_after_match = Counter(
        str(r["geometry"]["target_after_matches_forced"]) for r in carrier_proc
    )
    destination_preoccupied = Counter(
        str(r["geometry"]["destination_preoccupied"]) for r in carrier_proc
    )

    return {
        "ability": ABILITY,
        "runtime_status": "learned_damage",
        "evidence_scope": "read_only_discriminator_audit",
        "corpus_battles_seen": len(battle_ids),
        "all_melee_attacks": len(all_melee),
        "analysis_errors": errors,
        "isolated_powerstrike": {
            "attacks": len(carrier),
            "proc_attacks": len(carrier_proc),
            "no_proc_attacks": len(carrier_no_proc),
            "ability_sets": _ability_set_counter(carrier),
            "proc_ability_sets": _ability_set_counter(carrier_proc),
            "creatures": _counter_strings(Counter(r["actor_creature_id"] for r in carrier)),
            "battles": len({r["battle_id"] for r in carrier}),
        },
        "discriminator": {
            "candidate": "server-declared pre-action actor ability tag",
            "powerstrike_pawstrike_co_carrier": {
                "attacks": len(co_carriers),
                "proc_attacks": len(co_carrier_proc),
                "battles": len({r["battle_id"] for r in co_carriers}),
                "creatures": _counter_strings(Counter(r["actor_creature_id"] for r in co_carriers)),
            },
            "same_wire_without_powerstrike": len(controls),
            "pawstrike_tagged_controls": len(paw_controls),
            "unexplained_controls": len(unknown_controls),
            "control_ability_sets": _ability_set_counter(controls),
            "control_creatures": _counter_strings(Counter(r["actor_creature_id"] for r in controls)),
        },
        "observed_consequence": {
            "zero_state_after_i": {
                "true": sum(bool(r["zero_state_after_i"]) for r in carrier_proc),
                "false": sum(not bool(r["zero_state_after_i"]) for r in carrier_proc),
            },
            "retaliation_present": {
                "true": sum(bool(r["retaliation"]) for r in carrier_proc),
                "false": sum(not bool(r["retaliation"]) for r in carrier_proc),
            },
            "owner_relation": _counter_strings(owner_relation),
            "forced_coordinate": {
                "changed": sum(bool(r["forced_changed"]) for r in carrier_proc),
                "same": sum(not bool(r["forced_changed"]) for r in carrier_proc),
                "vectors": {f"{dx},{dy}": n for (dx, dy), n in proc_vectors.most_common()},
                "distance": _counter_strings(proc_distances),
                "direction": _counter_strings(proc_directions),
                "destination_preoccupied_before": _counter_strings(destination_preoccupied),
                "target_after_matches_raw_forced": _counter_strings(target_after_match),
            },
            "wire_windows": _counter_strings(proc_windows),
            "post_i_opcode_sequences": _counter_strings(proc_post_i),
        },
        "collision_population": {
            "wire_windows": _counter_strings(control_windows),
            "examples": [_compact_example(r) for r in controls[:12]],
        },
        "temporal_holdout": _model_metrics(carrier),
        "proc_examples": [_compact_example(r) for r in carrier_proc[:20]],
        "no_proc_examples": [_compact_example(r) for r in carrier_no_proc[:10]],
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
    ap = argparse.ArgumentParser(description="Read-only Power Strike discriminator audit.")
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
