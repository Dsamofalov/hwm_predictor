from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "teleport"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carrier_uids: dict[str, set[int]] = {}
    carrier_entities = 0
    carrier_creatures: Counter[int] = Counter()
    carrier_ability_sets: Counter[str] = Counter()
    tooltip_battles = 0
    tooltip_names: Counter[str] = Counter()
    tooltip_descriptions: Counter[str] = Counter()
    init_examples: list[dict] = []

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        if not init_path.exists():
            continue
        try:
            payload = init_path.read_text(encoding="utf-8", errors="replace")
            entities, warnings = parse_initial_entities(payload)
            tooltips = parse_tooltips(payload)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:init:{type(exc).__name__}:{exc}")
            continue
        if warnings:
            parse_errors.extend(f"{battle_dir.name}:init_warning:{w}" for w in warnings)

        name = _normalize((tooltips.get("abil_names") or {}).get(ABILITY))
        description = _normalize((tooltips.get("abil_desc") or {}).get(ABILITY))
        if name or description:
            tooltip_battles += 1
            if name:
                tooltip_names[name] += 1
            if description:
                tooltip_descriptions[description] += 1

        uids: set[int] = set()
        rows: list[dict] = []
        for entity in entities.values():
            abilities = {str(x).lower() for x in entity.abilities}
            if ABILITY not in abilities:
                continue
            uid = int(entity.uid)
            uids.add(uid)
            carrier_entities += 1
            carrier_creatures[int(entity.creature_id)] += 1
            carrier_ability_sets[",".join(sorted(abilities)) or "<none>"] += 1
            rows.append({
                "uid": uid,
                "owner": int(entity.owner),
                "creature_id": int(entity.creature_id),
                "count": int(entity.count),
                "x": int(entity.x),
                "y": int(entity.y),
                "speed": float(entity.speed),
                "abilities": sorted(abilities),
            })
        if uids:
            carrier_uids[battle_dir.name] = uids
            if len(init_examples) < 25:
                init_examples.append({
                    "battle_id": battle_dir.name,
                    "carriers": rows,
                    "tooltip_name": name,
                    "tooltip_description": description,
                })

    carrier_decisions = 0
    action_types: Counter[str] = Counter()
    movement_commands = 0
    move_only_commands = 0
    melee_anchor_moves = 0
    movement_distance: Counter[int] = Counter()
    movement_vs_speed: Counter[str] = Counter()
    movement_run_modifiers: Counter[str] = Counter()
    source_special_codes: Counter[str] = Counter()
    destination_after_matches: Counter[str] = Counter()
    over_speed_examples: list[dict] = []
    movement_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                if actor_uid not in carriers:
                    continue
                carrier_decisions += 1
                action_type = str(decision.get("action_type", ""))
                action_types[action_type] += 1
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                actor_before = _by_uid(before, actor_uid)
                actor_after = _by_uid(after, actor_uid)
                if not actor_before:
                    continue
                commands = parse_commands(str(decision.get("raw", "")))
                for command in commands:
                    if command.opcode == "SPECIAL" and command.actor_uid is not None and int(command.actor_uid) == actor_uid:
                        source_special_codes[str(command.code)] += 1

                moves = [
                    command
                    for command in commands
                    if command.opcode == "MOVEMENT"
                    and command.actor_uid is not None and int(command.actor_uid) == actor_uid
                    and command.x is not None and command.y is not None
                ]
                if not moves:
                    continue
                origin = (int(actor_before.get("x", 0)), int(actor_before.get("y", 0)))
                for command in moves:
                    destination = (int(command.x), int(command.y))
                    distance = _distance(origin, destination)
                    speed = float(actor_before.get("speed", 0.0))
                    speed_floor = max(0, int(math.floor(speed)))
                    movement_commands += 1
                    if action_type == "MOVE":
                        move_only_commands += 1
                    if action_type == "MELEE_ATTACK":
                        melee_anchor_moves += 1
                    movement_distance[distance] += 1
                    movement_vs_speed[
                        "within_floor_speed" if distance <= speed_floor else "over_floor_speed"
                    ] += 1
                    movement_run_modifiers[str(actor_before.get("run_modifier", "")) or "<none>"] += 1
                    if actor_after:
                        destination_after_matches[str(
                            (int(actor_after.get("x", 0)), int(actor_after.get("y", 0))) == destination
                        )] += 1
                    row = {
                        "battle_id": str(decision.get("battle_id", battle_dir.name)),
                        "decision_index": int(decision.get("decision_index", -1)),
                        "server_turn": int(decision.get("server_turn", -1)),
                        "action_type": action_type,
                        "actor_uid": actor_uid,
                        "actor_creature_id": int(actor_before.get("creature_id", -1)),
                        "actor_abilities": sorted(_abilities(actor_before)),
                        "speed": speed,
                        "origin": list(origin),
                        "destination": list(destination),
                        "distance": distance,
                        "within_floor_speed": distance <= speed_floor,
                        "run_modifier": str(actor_before.get("run_modifier", "")),
                        "raw_move": str(command.raw),
                        "raw": str(decision.get("raw", "")),
                    }
                    if len(movement_examples) < 80:
                        movement_examples.append(row)
                    if distance > speed_floor and len(over_speed_examples) < 50:
                        over_speed_examples.append(row)
                    origin = destination
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_carrier_movement_distance_and_wire_identity",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "carrier_decisions": carrier_decisions,
        "action_types": _counter(action_types),
        "movement_commands": movement_commands,
        "move_only_commands": move_only_commands,
        "melee_anchor_moves": melee_anchor_moves,
        "movement_distance": _counter(movement_distance),
        "movement_vs_floor_speed": _counter(movement_vs_speed),
        "movement_run_modifiers": _counter(movement_run_modifiers),
        "source_special_codes": _counter(source_special_codes),
        "destination_after_matches": _counter(destination_after_matches),
        "movement_examples": movement_examples,
        "over_speed_examples": over_speed_examples,
        "init_examples": init_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Teleport is not assumed to be an activated wire. This probe only establishes whether tagged carriers use "
            "ordinary MOVEMENT/melee-anchor commands, whether observed displacement respects the server speed field, "
            "and whether a carrier-specific SPECIAL exists. Obstacle/path bypass semantics require separate board-path "
            "evidence and are not inferred from Chebyshev distance alone."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Teleport movement identity evidence.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = analyze_corpus(args.corpus)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
