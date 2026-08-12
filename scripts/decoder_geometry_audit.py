#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from hwm_solver.evaluation.legal_coverage import _adjacent, _reachable, supports_observed
from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands

BASIC = {"WAIT", "DEFEND", "MOVE", "MELEE_ATTACK", "ATTACK", "RANGED_ATTACK"}
MELEE_FAILURES = {"melee_destination_not_reachable", "target_not_adjacent_after_move"}


def _cells(e: dict, pos: tuple[int, int] | None = None) -> set[tuple[int, int]]:
    if not e.get("alive", False) or e.get("is_hero", False) or e.get("is_hidden", False):
        return set()
    x, y = pos if pos is not None else (int(e["x"]), int(e["y"]))
    size = 2 if "big" in set(e.get("abilities", [])) else 1
    return {(x + dx, y + dy) for dx in range(size) for dy in range(size)}


def _overlap_pairs(state: list[dict]) -> set[tuple[int, int]]:
    live = [e for e in state if _cells(e)]
    out: set[tuple[int, int]] = set()
    for i, a in enumerate(live):
        for b in live[i + 1 :]:
            if (
                int(a.get("creature_id", 0)) == 760 and "statix" in set(a.get("abilities", []))
            ) or (
                int(b.get("creature_id", 0)) == 760 and "statix" in set(b.get("abilities", []))
            ):
                continue
            if _cells(a) & _cells(b):
                out.add(tuple(sorted((int(a["uid"]), int(b["uid"])))))
    return out


def _raw_melee_collisions(row: dict) -> tuple[bool, bool]:
    if row["action_type"] not in {"MELEE_ATTACK", "ATTACK"}:
        return False, False
    if row["destination_x"] is None or row["destination_y"] is None:
        return False, False
    by = {int(e["uid"]): e for e in row["state_before"]}
    actor = by.get(int(row["actor_uid"]))
    if actor is None:
        return False, False
    dest = (int(row["destination_x"]), int(row["destination_y"]))
    actor_cells = _cells(actor, dest)
    hit: set[int] = set()
    for uid, other in by.items():
        if uid == int(row["actor_uid"]):
            continue
        if actor_cells & _cells(other):
            hit.add(uid)
    if not hit:
        return False, False
    target = int(row["target_uid"]) if row["target_uid"] is not None else None
    return True, any(uid != target for uid in hit)


def _landings(row: dict, target_uid: int) -> set[tuple[int, int]]:
    state = row["state_before"]
    by = {int(e["uid"]): e for e in state}
    actor = by.get(int(row["actor_uid"]))
    target = by.get(int(target_uid))
    if actor is None or target is None:
        return set()
    current = (int(actor["x"]), int(actor["y"]))
    out: set[tuple[int, int]] = set()
    if _adjacent(actor, current, target):
        out.add(current)
    for dest in _reachable(state, actor):
        if _adjacent(actor, dest, target):
            out.add(dest)
    return out


def _damage_targets(row: dict) -> list[int]:
    out: list[int] = []
    for c in parse_commands(row["raw"]):
        if (
            c.opcode == "DAMAGE"
            and c.actor_uid == row["actor_uid"]
            and c.target_uid is not None
            and int(c.target_uid) not in out
        ):
            out.append(int(c.target_uid))
    return out


def _ownership(row: dict) -> str:
    commands = parse_commands(row["raw"])
    has_special = any(c.opcode == "SPECIAL" for c in commands)
    unresolved = bool(row.get("semantic_unresolved_opcodes"))
    if not has_special:
        return "special_free"
    return "special_unresolved" if unresolved else "special_resolved"


def _failure_detail(row: dict, reason: str) -> dict:
    by = {int(e["uid"]): e for e in row["state_before"]}
    actor = by.get(int(row["actor_uid"]))
    original = int(row["target_uid"]) if row["target_uid"] is not None else None
    landings = _landings(row, original) if original is not None else set()
    raw_dest = None
    near_raw: list[tuple[int, int]] = []
    if row["destination_x"] is not None and row["destination_y"] is not None:
        raw_dest = (int(row["destination_x"]), int(row["destination_y"]))
        near_raw = sorted(
            p for p in landings
            if max(abs(p[0] - raw_dest[0]), abs(p[1] - raw_dest[1])) <= 1
        )
    return {
        "battle": row["battle_id"],
        "decision_index": int(row["decision_index"]),
        "reason": reason,
        "action_type": row["action_type"],
        "ownership": _ownership(row),
        "special_codes": list(row.get("special_codes", [])),
        "semantic_unresolved_opcodes": list(row.get("semantic_unresolved_opcodes", [])),
        "state_semantically_exact_core": bool(row.get("state_semantically_exact_core", False)),
        "actor_uid": int(row["actor_uid"]),
        "target_uid": original,
        "destination": list(raw_dest) if raw_dest is not None else None,
        "actor_creature_id": int(actor.get("creature_id", 0)) if actor else None,
        "actor_abilities": list(actor.get("abilities", [])) if actor else [],
        "original_target_landings": len(landings),
        "near_destination_landings": len(near_raw),
        "near_destination_candidates": [list(p) for p in near_raw],
        "damage_targets": _damage_targets(row),
        "raw": row["raw"],
    }


def audit(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    battles = sorted(
        (d for d in root.iterdir() if d.is_dir() and d.name.isdigit()), key=lambda d: int(d.name)
    )
    cut = int(0.8 * len(battles))
    heldout_names = {d.name for d in battles[cut:]}

    total_decisions = 0
    final_overlap_battles = 0
    final_overlap_pairs = 0
    raw_melee_collisions = 0
    raw_melee_non_target_collisions = 0
    heldout_basic = 0
    heldout_matched = 0
    heldout_failures: Counter[str] = Counter()
    heldout_recoverable_original: Counter[str] = Counter()
    heldout_recoverable_any_damage: Counter[str] = Counter()
    heldout_alternate_target_needed: Counter[str] = Counter()
    ownership: Counter[str] = Counter()
    special_codes: Counter[str] = Counter()
    unresolved_opcodes: Counter[str] = Counter()
    landing_cardinality: Counter[str] = Counter()
    residuals: list[dict] = []

    for battle in battles:
        last_after: list[dict] | None = None
        is_heldout = battle.name in heldout_names
        for row in iter_battle_decisions(battle):
            total_decisions += 1
            last_after = row["state_after"]
            collided, non_target = _raw_melee_collisions(row)
            raw_melee_collisions += int(collided)
            raw_melee_non_target_collisions += int(non_target)

            if not is_heldout or row["side"] != "PLAYER" or row["has_unknown_command"]:
                continue
            if row["action_type"] not in BASIC:
                continue
            heldout_basic += 1
            ok, reason = supports_observed(row)
            if ok:
                heldout_matched += 1
                continue
            heldout_failures[reason] += 1
            detail = _failure_detail(row, reason)
            residuals.append(detail)
            ownership[detail["ownership"]] += 1
            special_codes.update(detail["special_codes"])
            unresolved_opcodes.update(detail["semantic_unresolved_opcodes"])
            landing_cardinality[str(detail["near_destination_landings"])] += 1

            if row["action_type"] not in {"MELEE_ATTACK", "ATTACK"} or reason not in MELEE_FAILURES:
                continue
            original = int(row["target_uid"]) if row["target_uid"] is not None else None
            original_landings = _landings(row, original) if original is not None else set()
            if original_landings:
                heldout_recoverable_original[reason] += 1
                heldout_recoverable_any_damage[reason] += 1
                continue
            for target in _damage_targets(row):
                if target == original:
                    continue
                if _landings(row, target):
                    heldout_recoverable_any_damage[reason] += 1
                    heldout_alternate_target_needed[reason] += 1
                    break

        if last_after is not None:
            pairs = _overlap_pairs(last_after)
            if pairs:
                final_overlap_battles += 1
                final_overlap_pairs += len(pairs)

    return {
        "corpus": {
            "battles": len(battles),
            "decisions": total_decisions,
            "chronological_train_battles": cut,
            "chronological_heldout_battles": len(battles) - cut,
        },
        "python_replay_final_overlap": {
            "battles": final_overlap_battles,
            "pairs": final_overlap_pairs,
        },
        "raw_melee_destination_collision": {
            "any_live_stack": raw_melee_collisions,
            "includes_non_target_stack": raw_melee_non_target_collisions,
        },
        "heldout_basic_action_representability": {
            "evaluated": heldout_basic,
            "representable": heldout_matched,
            "coverage": heldout_matched / max(1, heldout_basic),
            "failure_reasons": dict(heldout_failures),
        },
        "heldout_failed_melee_recovery": {
            "using_original_target": dict(heldout_recoverable_original),
            "using_any_actor_damage_target": dict(heldout_recoverable_any_damage),
            "alternate_damage_target_required": dict(heldout_alternate_target_needed),
        },
        "heldout_failure_taxonomy": {
            "ownership": dict(ownership),
            "special_codes": dict(special_codes),
            "semantic_unresolved_opcodes": dict(unresolved_opcodes),
            "near_destination_landing_cardinality": dict(landing_cardinality),
        },
        "heldout_residuals": residuals,
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
