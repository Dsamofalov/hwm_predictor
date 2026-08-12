#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


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


def audit(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted((d for d in root.iterdir() if d.is_dir() and d.name.isdigit()), key=lambda d: int(d.name))
    final_rows: list[dict] = []
    introduced_rows: list[dict] = []

    for battle in battles:
        previous: set[tuple[int, int]] = set()
        final: set[tuple[int, int]] = set()
        final_state: list[dict] | None = None
        introductions: dict[tuple[int, int], dict] = {}
        for row in iter_battle_decisions(battle):
            before = row["state_before"]
            after = row["state_after"]
            current = overlaps(after)
            for pair in sorted(current - previous):
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
