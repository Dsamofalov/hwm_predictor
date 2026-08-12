#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands


def cells(entity: dict) -> set[tuple[int, int]]:
    if not entity.get("alive", False) or entity.get("is_hero", False) or entity.get("is_hidden", False):
        return set()
    x, y = int(entity["x"]), int(entity["y"])
    size = 2 if "big" in set(entity.get("abilities", [])) else 1
    return {(x + dx, y + dy) for dx in range(size) for dy in range(size)}


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
            after = row["state_after"]
            current = overlaps(after)
            for pair in sorted(current - previous):
                commands = parse_commands(row["raw"])
                record = {
                    "battle": battle.name,
                    "decision_index": int(row["decision_index"]),
                    "pair": list(pair),
                    "actor_uid": int(row["actor_uid"]),
                    "action_type": row["action_type"],
                    "side": row["side"],
                    "destination": [row["destination_x"], row["destination_y"]],
                    "special_codes": list(row.get("special_codes", [])),
                    "semantic_unresolved_opcodes": list(row.get("semantic_unresolved_opcodes", [])),
                    "has_special": any(c.opcode == "SPECIAL" for c in commands),
                    "raw": row["raw"],
                    "entities_after": [entity_summary(after, pair[0]), entity_summary(after, pair[1])],
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
