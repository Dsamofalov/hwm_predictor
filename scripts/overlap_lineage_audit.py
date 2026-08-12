#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hwm_solver.evaluation.legal_coverage import supports_observed
from hwm_solver.protocol.replay import (
    _attack_move,
    _entities_adjacent,
    _observed_anchor_blocked,
    _observed_can_place,
    _observed_entity_by_uid,
    _observed_reachable,
    iter_battle_decisions,
    parse_commands,
)


def cells_at(entity: dict, x: int | None = None, y: int | None = None) -> set[tuple[int, int]]:
    if not entity.get("alive", False) or entity.get("is_hero", False) or entity.get("is_hidden", False):
        return set()
    ex = int(entity["x"] if x is None else x)
    ey = int(entity["y"] if y is None else y)
    size = 2 if "big" in set(entity.get("abilities", [])) else 1
    return {(ex + dx, ey + dy) for dx in range(size) for dy in range(size)}


def cells(entity: dict) -> set[tuple[int, int]]:
    return cells_at(entity)


def adjacent(a: dict | None, b: dict | None) -> bool:
    if a is None or b is None:
        return False
    return any(max(abs(ax - bx), abs(ay - by)) <= 1 for ax, ay in cells(a) for bx, by in cells(b))


def overlaps(state: list[dict]) -> set[tuple[int, int]]:
    live = [e for e in state if cells(e)]
    out: set[tuple[int, int]] = set()
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            if (
                int(a.get("creature_id", 0)) == 760 and "statix" in set(a.get("abilities", []))
            ) or (
                int(b.get("creature_id", 0)) == 760 and "statix" in set(b.get("abilities", []))
            ):
                continue
            if cells(a) & cells(b):
                out.add(tuple(sorted((int(a["uid"]), int(b["uid"])))))
    return out


def entity_summary(state: list[dict], uid: int) -> dict | None:
    e = next((x for x in state if int(x["uid"]) == uid), None)
    if e is None:
        return None
    return {
        "uid": uid,
        "creature_id": int(e.get("creature_id", 0)),
        "owner": int(e.get("owner", 0)),
        "x": int(e.get("x", 0)),
        "y": int(e.get("y", 0)),
        "count": int(e.get("count", 0)),
        "alive": bool(e.get("alive", False)),
        "is_hero": bool(e.get("is_hero", False)),
        "is_hidden": bool(e.get("is_hidden", False)),
        "abilities": list(e.get("abilities", [])),
    }


def raw_destination_blockers(state: list[dict], actor_uid: int, destination: tuple[int, int] | None) -> list[dict]:
    if destination is None:
        return []
    actor = next((e for e in state if int(e["uid"]) == actor_uid), None)
    if actor is None:
        return []
    actor_cells = cells_at(actor, destination[0], destination[1])
    out: list[dict] = []
    for other in state:
        if int(other["uid"]) == actor_uid or not cells(other):
            continue
        if actor_cells & cells(other):
            summary = entity_summary(state, int(other["uid"]))
            if summary is not None:
                out.append(summary)
    return out


def blocked_special_free_melee_candidate(row: dict) -> dict | None:
    if row.get("action_type") != "MELEE_ATTACK":
        return None
    commands = parse_commands(row["raw"])
    if any(command.opcode == "SPECIAL" for command in commands):
        return None

    actor_uid = int(row["actor_uid"])
    move = _attack_move(actor_uid, commands)
    first_damage = next(
        (
            command
            for command in commands
            if command.opcode == "DAMAGE"
            and command.actor_uid == actor_uid
            and command.target_uid is not None
        ),
        None,
    )
    if move is None or move.x is None or move.y is None or first_damage is None:
        return None

    before = row["state_before"]
    actor = _observed_entity_by_uid(before, actor_uid)
    target_uid = int(first_damage.target_uid)
    target = _observed_entity_by_uid(before, target_uid)
    if actor is None or target is None:
        return None

    raw = (int(move.x), int(move.y))
    start = (int(actor.get("x", 0)), int(actor.get("y", 0)))
    if not _observed_anchor_blocked(before, actor, raw):
        return None
    if not _observed_can_place(before, actor, start):
        return None
    if not _entities_adjacent(actor, start[0], start[1], target):
        return None

    landings = [start]
    for point in sorted(_observed_reachable(before, actor)):
        if _entities_adjacent(actor, point[0], point[1], target):
            landings.append(point)
    landings = list(dict.fromkeys(landings))
    near_raw = [
        point
        for point in landings
        if max(abs(point[0] - raw[0]), abs(point[1] - raw[1])) <= 1
    ]
    damage_targets = sorted(
        {
            int(command.target_uid)
            for command in commands
            if command.opcode == "DAMAGE"
            and command.actor_uid == actor_uid
            and command.target_uid is not None
        }
    )
    observed_ok, observed_reason = supports_observed(row)
    resolved = (
        [int(row["destination_x"]), int(row["destination_y"])]
        if row.get("destination_x") is not None and row.get("destination_y") is not None
        else [None, None]
    )
    blockers = raw_destination_blockers(before, actor_uid, raw)
    actor_owner = int(actor.get("owner", 0))
    for blocker in blockers:
        blocker["same_owner_as_actor"] = int(blocker.get("owner", 0)) == actor_owner

    return {
        "battle": row["battle_id"],
        "decision_index": int(row["decision_index"]),
        "actor": entity_summary(before, actor_uid),
        "first_damage_target": entity_summary(before, target_uid),
        "damage_targets": damage_targets,
        "single_damage_target": damage_targets == [target_uid],
        "raw_marker": [raw[0], raw[1]],
        "raw_destination_blockers": blockers,
        "start_anchor": [start[0], start[1]],
        "start_legal": True,
        "start_adjacent_to_first_damage_target": True,
        "target_adjacent_legal_landings": [[x, y] for x, y in landings],
        "near_raw_target_adjacent_landings": [[x, y] for x, y in near_raw],
        "near_raw_landing_count": len(near_raw),
        "resolved_destination": resolved,
        "semantic_unresolved_opcodes": list(row.get("semantic_unresolved_opcodes", [])),
        "special_codes": list(row.get("special_codes", [])),
        "observed_action_representable": bool(observed_ok),
        "observed_action_reason": observed_reason,
        "raw": row["raw"],
    }


def audit(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((d for d in root.iterdir() if d.is_dir() and d.name.isdigit()), key=lambda d: int(d.name))
    final_rows: list[dict] = []
    introduced_rows: list[dict] = []
    blocked_marker_rows: list[dict] = []

    for battle in battles:
        previous: set[tuple[int, int]] = set()
        final: set[tuple[int, int]] = set()
        final_state: list[dict] | None = None
        introductions: dict[tuple[int, int], dict] = {}
        battle_blocked_rows: list[dict] = []
        for row in iter_battle_decisions(battle):
            before = row["state_before"]
            after = row["state_after"]
            current = overlaps(after)
            introduced = current - previous

            candidate = blocked_special_free_melee_candidate(row)
            if candidate is not None:
                actor_uid = int(row["actor_uid"])
                candidate["introduced_overlap_pairs"] = [list(pair) for pair in sorted(introduced)]
                candidate["introduced_actor_overlap"] = any(actor_uid in pair for pair in introduced)
                battle_blocked_rows.append(candidate)

            for pair in sorted(introduced):
                commands = parse_commands(row["raw"])
                actor_uid = int(row["actor_uid"])
                first_damage = next((
                    c for c in commands
                    if c.opcode == "DAMAGE" and c.actor_uid == actor_uid and c.target_uid is not None
                ), None)
                target_uid = int(first_damage.target_uid) if first_damage is not None else None
                destination = (
                    (int(row["destination_x"]), int(row["destination_y"]))
                    if row["destination_x"] is not None and row["destination_y"] is not None
                    else None
                )
                actor_before = entity_summary(before, actor_uid)
                target_before = entity_summary(before, target_uid) if target_uid is not None else None
                record = {
                    "battle": battle.name,
                    "decision_index": int(row["decision_index"]),
                    "pair": list(pair),
                    "actor_uid": actor_uid,
                    "action_type": row["action_type"],
                    "side": row["side"],
                    "destination": list(destination) if destination is not None else [None, None],
                    "special_codes": list(row.get("special_codes", [])),
                    "semantic_unresolved_opcodes": list(row.get("semantic_unresolved_opcodes", [])),
                    "has_special": any(c.opcode == "SPECIAL" for c in commands),
                    "raw": row["raw"],
                    "entities_before": [entity_summary(before, pair[0]), entity_summary(before, pair[1])],
                    "entities_after": [entity_summary(after, pair[0]), entity_summary(after, pair[1])],
                    "actor_before": actor_before,
                    "first_damage_target_uid": target_uid,
                    "first_damage_target_before": target_before,
                    "actor_before_adjacent_to_first_damage_target": adjacent(actor_before, target_before),
                    "raw_destination_blockers": raw_destination_blockers(before, actor_uid, destination),
                }
                introductions[pair] = record
                introduced_rows.append(record)
            previous = current
            final = current
            final_state = after

        for candidate in battle_blocked_rows:
            actor_uid = int(candidate["actor"]["uid"])
            candidate["actor_in_final_overlap"] = any(actor_uid in pair for pair in final)
            candidate["final_overlap_pairs_for_actor"] = [
                list(pair) for pair in sorted(final) if actor_uid in pair
            ]
            blocked_marker_rows.append(candidate)

        if final and final_state is not None:
            final_rows.append({
                "battle": battle.name,
                "final_pairs": [list(p) for p in sorted(final)],
                "final_entities": {
                    str(uid): entity_summary(final_state, uid)
                    for uid in sorted({uid for pair in final for uid in pair})
                },
                "latest_introduction_for_final_pair": [introductions.get(p) for p in sorted(final)],
            })

    return {
        "battles": len(battles),
        "final_overlap_battles": len(final_rows),
        "final_overlap_pairs": sum(len(x["final_pairs"]) for x in final_rows),
        "finals": final_rows,
        "all_overlap_introductions": introduced_rows,
        "blocked_special_free_melee_marker_candidate_count": len(blocked_marker_rows),
        "blocked_special_free_melee_marker_candidates": blocked_marker_rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", nargs="?", default="hwm_battles")
    ap.add_argument("--output")
    args = ap.parse_args()
    report = audit(Path(args.corpus))
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
