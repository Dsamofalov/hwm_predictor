from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import (
    iter_battle_decisions,
    parse_commands,
    parse_initial_entities,
)


ABILITY = "auraoffirevul"
FIRE_SCHOOL = "fire"


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _cells(entity: dict) -> set[tuple[int, int]]:
    x = int(entity.get("x", 0))
    y = int(entity.get("y", 0))
    size = 2 if "big" in _abilities(entity) else 1
    return {(x + dx, y + dy) for dx in range(size) for dy in range(size)}


def _adjacent(a: dict, b: dict) -> bool:
    return any(
        max(abs(ax - bx), abs(ay - by)) <= 1
        for ax, ay in _cells(a)
        for bx, by in _cells(b)
    )


def _spellbook_entries(magic_blob: str) -> list[dict]:
    """Parse the server-provided seven-token spellbook grammar without inventing spell semantics."""
    text = str(magic_blob or "").split("^", 1)[0]
    tok = text.split("-")
    out: list[dict] = []
    for i in range(0, len(tok) - 6, 7):
        name = tok[i]
        if not name:
            continue
        try:
            cost = int(float(tok[i + 1]))
            effect = float(tok[i + 3])
        except ValueError:
            continue
        out.append(
            {
                "name": name,
                "cost": cost,
                "level": tok[i + 2],
                "effect": effect,
                "param4": tok[i + 4],
                "param5": tok[i + 5],
                "school": tok[i + 6].lower(),
            }
        )
    return out


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def _enemy_aura_sources(state: list[dict], target: dict) -> list[dict]:
    owner = int(target.get("owner", -1))
    return [
        entity
        for entity in state
        if bool(entity.get("alive", True))
        and ABILITY in _abilities(entity)
        and int(entity.get("owner", -1)) != owner
        and _adjacent(entity, target)
    ]


def _special_shape(command, before: list[dict], fire_entries: list[dict]) -> dict:
    raw = str(command.raw)
    numeric = raw[4:] if len(raw) >= 4 else ""
    target_guess = None
    param3 = None
    amount6 = None
    if len(numeric) == 15 and numeric.isdigit():
        target_guess = int(numeric[3:6])
        param3 = int(numeric[6:9])
        amount6 = int(numeric[9:15])
    target = _by_uid(before, target_guess)
    aura_sources = _enemy_aura_sources(before, target) if target else []
    base_costs = sorted({int(e["cost"]) for e in fire_entries if int(e["cost"]) > 0})
    cost_compatible = bool(
        param3 is not None
        and param3 > 0
        and any(param3 <= base for base in base_costs)
    )
    return {
        "raw": raw,
        "code": str(command.code),
        "actor_uid": int(command.actor_uid) if command.actor_uid is not None else None,
        "target_guess_uid": target_guess,
        "target_guess_exists": target is not None,
        "target_guess_owner": int(target.get("owner", -1)) if target else None,
        "param3": param3,
        "amount6": amount6,
        "fire_spell_base_costs": base_costs,
        "cost_compatible_with_fire_spell": cost_compatible,
        "target_adjacent_enemy_fire_aura": bool(aura_sources),
        "adjacent_aura_uids": [int(e.get("uid", -1)) for e in aura_sources],
    }


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)

    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    aura_battles: set[str] = set()
    initial_firebooks: dict[tuple[str, int], list[dict]] = {}
    firebook_actor_sets: Counter[str] = Counter()
    fire_spell_names: Counter[str] = Counter()
    aura_firebook_names: Counter[str] = Counter()
    parse_errors: list[str] = []

    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        turns_path = battle_dir / "turns0.txt"
        if not init_path.exists() or not turns_path.exists():
            continue
        try:
            entities, warnings = parse_initial_entities(
                init_path.read_text(encoding="utf-8", errors="replace")
            )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:init:{type(exc).__name__}:{exc}")
            continue
        if warnings:
            parse_errors.extend(f"{battle_dir.name}:init_warning:{w}" for w in warnings)
        if any(ABILITY in set(e.abilities) for e in entities.values()):
            aura_battles.add(battle_dir.name)
        else:
            continue

        for entity in entities.values():
            entries = [
                e for e in _spellbook_entries(entity.magic_blob)
                if e["school"] == FIRE_SCHOOL
            ]
            if not entries:
                continue
            initial_firebooks[(battle_dir.name, int(entity.uid))] = entries
            firebook_actor_sets[",".join(sorted(str(x).lower() for x in entity.abilities)) or "<none>"] += 1
            for entry in entries:
                fire_spell_names[str(entry["name"])] += 1
                if ABILITY in set(entity.abilities):
                    aura_firebook_names[str(entry["name"])] += 1

    fire_actor_decisions = 0
    fire_actor_special_decisions = 0
    special_codes: Counter[str] = Counter()
    special_shapes: Counter[str] = Counter()
    explicit_damage_hits = 0
    explicit_damage_adjacent_aura_hits = 0
    candidate_cost_compatible = 0
    candidate_cost_compatible_adjacent = 0
    examples: list[dict] = []
    damage_examples: list[dict] = []

    for battle_dir in battle_dirs:
        if battle_dir.name not in aura_battles:
            continue
        try:
            decisions = iter_battle_decisions(battle_dir)
            for decision in decisions:
                battle_id = str(decision.get("battle_id", battle_dir.name))
                actor_uid = int(decision.get("actor_uid", -1))
                fire_entries = initial_firebooks.get((battle_id, actor_uid))
                if not fire_entries:
                    continue
                fire_actor_decisions += 1
                before = list(decision.get("state_before") or [])
                commands = parse_commands(str(decision.get("raw", "")))
                specials = [
                    c for c in commands
                    if c.opcode == "SPECIAL" and c.actor_uid == actor_uid
                ]
                if specials:
                    fire_actor_special_decisions += 1
                for command in specials:
                    shape = _special_shape(command, before, fire_entries)
                    special_codes[str(command.code)] += 1
                    key = (
                        f"{command.code}|len={len(str(command.raw))}|"
                        f"cost_compatible={shape['cost_compatible_with_fire_spell']}|"
                        f"target_exists={shape['target_guess_exists']}|"
                        f"adjacent_aura={shape['target_adjacent_enemy_fire_aura']}"
                    )
                    special_shapes[key] += 1
                    if shape["cost_compatible_with_fire_spell"]:
                        candidate_cost_compatible += 1
                        candidate_cost_compatible_adjacent += int(shape["target_adjacent_enemy_fire_aura"])
                    if len(examples) < 80:
                        actor = _by_uid(before, actor_uid)
                        examples.append(
                            {
                                "battle_id": battle_id,
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": str(decision.get("action_type", "")),
                                "actor_uid": actor_uid,
                                "actor_owner": int(actor.get("owner", -1)) if actor else None,
                                "actor_abilities": sorted(_abilities(actor)),
                                "fire_spellbook": fire_entries,
                                "special": shape,
                                "raw": str(decision.get("raw", "")),
                            }
                        )

                for command in commands:
                    if command.opcode != "DAMAGE" or command.actor_uid != actor_uid or command.target_uid is None:
                        continue
                    target = _by_uid(before, int(command.target_uid))
                    if target is None:
                        continue
                    explicit_damage_hits += 1
                    aura_sources = _enemy_aura_sources(before, target)
                    explicit_damage_adjacent_aura_hits += int(bool(aura_sources))
                    if len(damage_examples) < 40:
                        damage_examples.append(
                            {
                                "battle_id": battle_id,
                                "decision_index": int(decision.get("decision_index", -1)),
                                "actor_uid": actor_uid,
                                "target_uid": int(command.target_uid),
                                "damage": int(command.amount or 0),
                                "target_adjacent_enemy_fire_aura": bool(aura_sources),
                                "adjacent_aura_uids": [int(e.get("uid", -1)) for e in aura_sources],
                                "fire_spellbook": fire_entries,
                                "special_codes": [str(c.code) for c in specials],
                                "raw": str(decision.get("raw", "")),
                            }
                        )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_spellbook_special_wire_and_live_geometry",
        "corpus_battle_dirs": len(battle_dirs),
        "aura_battles": len(aura_battles),
        "fire_spellbook_actors": len(initial_firebooks),
        "fire_spell_names": _counter(fire_spell_names),
        "aura_carrier_fire_spell_names": _counter(aura_firebook_names),
        "fire_spellbook_actor_ability_sets": _counter(firebook_actor_sets),
        "fire_actor_decisions": fire_actor_decisions,
        "fire_actor_special_decisions": fire_actor_special_decisions,
        "special_codes": _counter(special_codes),
        "special_shapes": _counter(special_shapes),
        "cost_compatible_special_records": candidate_cost_compatible,
        "cost_compatible_special_records_adjacent_enemy_aura": candidate_cost_compatible_adjacent,
        "explicit_damage_hits_by_fire_spellbook_actor": explicit_damage_hits,
        "explicit_damage_hits_adjacent_enemy_aura": explicit_damage_adjacent_aura_hits,
        "special_examples": examples,
        "damage_examples": damage_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "A fire-school spellbook proves only that the actor can cast a Fire spell. "
            "SPECIAL cost compatibility and co-occurring DAMAGE are discovery signals, not truth labels. "
            "Do not apply the aura to fireattack, fireshield, magmashield, or any other non-spell fire damage "
            "without independent raw/server evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Aura of Fire Vulnerability spell applicability.")
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
