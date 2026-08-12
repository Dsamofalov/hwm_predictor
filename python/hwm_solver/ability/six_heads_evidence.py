from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities, parse_tooltips


ABILITY = "six_heads"


def _normalize(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _by_uid(state: list[dict], uid: int | None) -> dict | None:
    if uid is None:
        return None
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _cells(entity: dict) -> set[tuple[int, int]]:
    x, y = int(entity.get("x", 0)), int(entity.get("y", 0))
    side = 2 if "big" in _abilities(entity) else 1
    return {(x + dx, y + dy) for dx in range(side) for dy in range(side)}


def _adjacent(a: dict, b: dict) -> bool:
    return any(
        max(abs(ax - bx), abs(ay - by)) <= 1
        for ax, ay in _cells(a)
        for bx, by in _cells(b)
    )


def _attack_anchor(actor: dict, commands: list, primary_uid: int | None) -> tuple[dict, bool]:
    actor_uid = int(actor.get("uid", -1))
    first_primary = next(
        (
            i
            for i, command in enumerate(commands)
            if command.opcode == "DAMAGE"
            and command.actor_uid is not None
            and int(command.actor_uid) == actor_uid
            and command.target_uid is not None
            and primary_uid is not None
            and int(command.target_uid) == primary_uid
        ),
        len(commands),
    )
    anchor = dict(actor)
    moved = False
    for command in commands[:first_primary]:
        if (
            command.opcode == "MOVEMENT"
            and command.actor_uid is not None
            and int(command.actor_uid) == actor_uid
            and command.x is not None
            and command.y is not None
        ):
            anchor["x"] = int(command.x)
            anchor["y"] = int(command.y)
            moved = True
    return anchor, moved


def _claims(description: str) -> dict:
    lower = description.lower()
    return {
        "percentages": [int(x) for x in re.findall(r"(\d+)\s*%", description)],
        "integers": [int(x) for x in re.findall(r"\b(\d+)\b", description)],
        "mentions_all": any(x in lower for x in ("все", "all")),
        "mentions_12_cells": bool(re.search(r"\b12\b", description)),
        "mentions_adjacent": any(x in lower for x in ("сосед", "adjacent", "nearby")),
        "mentions_enemy": any(x in lower for x in ("враж", "enemy")),
        "mentions_simultaneous": any(x in lower for x in ("одновременно", "simultaneous")),
    }


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
    tooltip_claim_shapes: Counter[str] = Counter()
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
                tooltip_claim_shapes[json.dumps(_claims(description), ensure_ascii=False, sort_keys=True)] += 1

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
                    "tooltip_claims": _claims(description) if description else {},
                })

    carrier_melee_attacks = 0
    attack_anchor_moved = 0
    attack_anchor_shift: Counter[str] = Counter()
    candidate_target_counts: Counter[int] = Counter()
    observed_target_counts: Counter[int] = Counter()
    exact_target_set_attacks = 0
    missing_targets = 0
    extra_targets = 0
    primary_not_candidate = 0
    friendly_adjacent_stacks = 0
    friendly_damage_hits = 0
    duplicate_damage_targets = 0
    damage_ratio_to_primary: Counter[str] = Counter()
    target_ability_sets: Counter[str] = Counter()
    relevant_cocarriers: Counter[str] = Counter()
    special_codes: Counter[str] = Counter()
    exact_examples: list[dict] = []
    mismatch_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carriers = carrier_uids.get(battle_dir.name)
        if not carriers:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                if actor_uid not in carriers or str(decision.get("action_type", "")) != "MELEE_ATTACK":
                    continue
                before = list(decision.get("state_before") or [])
                actor = _by_uid(before, actor_uid)
                target_raw = decision.get("target_uid")
                primary_uid = int(target_raw) if target_raw is not None else None
                primary = _by_uid(before, primary_uid)
                if not actor or not primary:
                    continue
                commands = parse_commands(str(decision.get("raw", "")))
                anchor, moved = _attack_anchor(actor, commands, primary_uid)
                carrier_melee_attacks += 1
                if moved:
                    attack_anchor_moved += 1
                    attack_anchor_shift[
                        f"{int(anchor.get('x', 0)) - int(actor.get('x', 0))},{int(anchor.get('y', 0)) - int(actor.get('y', 0))}"
                    ] += 1
                owner = int(actor.get("owner", -1))

                candidate_entities = [
                    entity
                    for entity in before
                    if int(entity.get("uid", -1)) != actor_uid
                    and bool(entity.get("alive", False))
                    and not bool(entity.get("is_hidden", False))
                    and int(entity.get("owner", -1)) != owner
                    and _adjacent(anchor, entity)
                ]
                candidate_uids = {int(e.get("uid", -1)) for e in candidate_entities}
                friendly_adjacent_stacks += sum(
                    1
                    for entity in before
                    if int(entity.get("uid", -1)) != actor_uid
                    and bool(entity.get("alive", False))
                    and not bool(entity.get("is_hidden", False))
                    and int(entity.get("owner", -1)) == owner
                    and _adjacent(anchor, entity)
                )
                if primary_uid not in candidate_uids:
                    primary_not_candidate += 1

                for command in commands:
                    if command.opcode == "SPECIAL":
                        special_codes[str(command.code)] += 1
                damage_records = [
                    command
                    for command in commands
                    if command.opcode == "DAMAGE"
                    and command.actor_uid is not None and int(command.actor_uid) == actor_uid
                    and command.target_uid is not None
                ]
                observed_uids = {int(c.target_uid) for c in damage_records}
                duplicate_damage_targets += max(0, len(damage_records) - len(observed_uids))
                friendly_damage_hits += sum(
                    1
                    for command in damage_records
                    if (target := _by_uid(before, int(command.target_uid))) is not None
                    and int(target.get("owner", -1)) == owner
                )

                candidate_target_counts[len(candidate_uids)] += 1
                observed_target_counts[len(observed_uids)] += 1
                missing = candidate_uids - observed_uids
                extra = observed_uids - candidate_uids
                missing_targets += len(missing)
                extra_targets += len(extra)
                if candidate_uids == observed_uids:
                    exact_target_set_attacks += 1

                primary_amounts = [int(c.amount or 0) for c in damage_records if int(c.target_uid) == primary_uid]
                primary_amount = primary_amounts[0] if primary_amounts else None
                damage_rows = []
                for command in damage_records:
                    uid = int(command.target_uid)
                    target = _by_uid(before, uid)
                    abilities = sorted(_abilities(target))
                    target_ability_sets[",".join(abilities) or "<none>"] += 1
                    amount = int(command.amount or 0)
                    if primary_amount and uid != primary_uid:
                        damage_ratio_to_primary[f"{amount / primary_amount:.3f}"] += 1
                    damage_rows.append({
                        "target_uid": uid,
                        "target_owner": int(target.get("owner", -1)) if target else None,
                        "target_creature_id": int(target.get("creature_id", -1)) if target else None,
                        "target_abilities": abilities,
                        "candidate_adjacent_enemy": uid in candidate_uids,
                        "amount": amount,
                        "raw": str(command.raw),
                    })

                interesting = sorted(
                    _abilities(actor)
                    & {"six_heads", "threehead", "spray", "fire_breath", "acid_breath", "icedbreath"}
                )
                relevant_cocarriers[",".join(interesting) or "<none>"] += 1
                row = {
                    "battle_id": str(decision.get("battle_id", battle_dir.name)),
                    "decision_index": int(decision.get("decision_index", -1)),
                    "server_turn": int(decision.get("server_turn", -1)),
                    "actor_uid": actor_uid,
                    "actor_owner": owner,
                    "actor_creature_id": int(actor.get("creature_id", -1)),
                    "actor_abilities": sorted(_abilities(actor)),
                    "actor_xy_before": [int(actor.get("x", 0)), int(actor.get("y", 0))],
                    "attack_anchor_xy": [int(anchor.get("x", 0)), int(anchor.get("y", 0))],
                    "attack_anchor_moved": moved,
                    "attack_anchor_cells": sorted([list(cell) for cell in _cells(anchor)]),
                    "primary_uid": primary_uid,
                    "candidate_enemy_uids": sorted(candidate_uids),
                    "observed_damage_uids": sorted(observed_uids),
                    "missing_uids": sorted(missing),
                    "extra_uids": sorted(extra),
                    "damage": damage_rows,
                    "raw": str(decision.get("raw", "")),
                }
                if candidate_uids == observed_uids and len(exact_examples) < 40:
                    exact_examples.append(row)
                elif candidate_uids != observed_uids and len(mismatch_examples) < 80:
                    mismatch_examples.append(row)
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "raw_attack_anchor_adjacent_enemy_exact_damage_set",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carrier_uids),
        "carrier_entities": carrier_entities,
        "carrier_creatures": _counter(carrier_creatures),
        "carrier_ability_sets": _counter(carrier_ability_sets),
        "tooltip_battles": tooltip_battles,
        "tooltip_names": _counter(tooltip_names),
        "tooltip_descriptions": _counter(tooltip_descriptions),
        "tooltip_claim_shapes": [
            {"count": int(count), "claims": json.loads(raw)}
            for raw, count in tooltip_claim_shapes.most_common()
        ],
        "carrier_melee_attacks": carrier_melee_attacks,
        "attack_anchor_moved": attack_anchor_moved,
        "attack_anchor_shift": _counter(attack_anchor_shift),
        "candidate_target_counts": _counter(candidate_target_counts),
        "observed_target_counts": _counter(observed_target_counts),
        "exact_target_set_attacks": exact_target_set_attacks,
        "missing_targets": missing_targets,
        "extra_targets": extra_targets,
        "primary_not_candidate": primary_not_candidate,
        "friendly_adjacent_stacks": friendly_adjacent_stacks,
        "friendly_damage_hits": friendly_damage_hits,
        "duplicate_damage_targets": duplicate_damage_targets,
        "secondary_damage_ratio_to_primary": _counter(damage_ratio_to_primary),
        "target_ability_sets": dict(target_ability_sets.most_common(40)),
        "actor_relevant_cocarriers": _counter(relevant_cocarriers),
        "special_codes": _counter(special_codes),
        "exact_examples": exact_examples,
        "mismatch_examples": mismatch_examples,
        "parse_errors": parse_errors,
        "interpretation_guard": (
            "Geometry is anchored at the carrier's raw MOVEMENT position immediately before the primary DAMAGE, not "
            "at state_before. This audit compares actor-source DAMAGE targets against every living visible enemy footprint "
            "adjacent to that attack anchor. Mismatches still require explanation by eligibility, concurrent abilities, "
            "deaths/ordering or protocol geometry before replacing modeled_collateral with exact targeting."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Six Heads exact target-set geometry evidence.")
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
