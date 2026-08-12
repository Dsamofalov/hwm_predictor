from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from hwm_solver.protocol.replay import iter_battle_decisions, parse_commands, parse_initial_entities


ABILITY = "gribbomb"


def _by_uid(state: list[dict], uid: int) -> dict | None:
    return next((e for e in state if int(e.get("uid", -1)) == int(uid)), None)


def _abilities(entity: dict | None) -> set[str]:
    if not entity:
        return set()
    return {str(x).lower() for x in (entity.get("abilities") or [])}


def _total_hp(entity: dict | None) -> int:
    if not entity or not bool(entity.get("alive", False)):
        return 0
    count = int(entity.get("count", 0))
    max_hp = max(1, int(entity.get("max_hp", 1)))
    top_hp = int(entity.get("top_hp", 0)) or max_hp
    return max(0, (count - 1) * max_hp + top_hp) if count > 0 else 0


def _cells(entity: dict) -> set[tuple[int, int]]:
    x, y = int(entity.get("x", 0)), int(entity.get("y", 0))
    big = "big" in _abilities(entity)
    side = 2 if big else 1
    return {(x + dx, y + dy) for dx in range(side) for dy in range(side)}


def _adjacent(a: dict, b: dict) -> bool:
    return any(
        max(abs(ax - bx), abs(ay - by)) <= 1
        for ax, ay in _cells(a)
        for bx, by in _cells(b)
    )


def _counter(counter: Counter) -> dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common()}


def analyze_corpus(corpus: Path) -> dict:
    root = corpus / "battles" if (corpus / "battles").is_dir() else corpus
    if not root.is_dir():
        raise FileNotFoundError(root)
    battle_dirs = [p for p in root.iterdir() if p.is_dir()]
    battle_dirs.sort(key=lambda p: (0, int(p.name)) if p.name.isdigit() else (1, p.name))

    parse_errors: list[str] = []
    carriers: dict[str, set[int]] = {}
    for battle_dir in battle_dirs:
        init_path = battle_dir / "init.txt"
        if not init_path.exists():
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
        uids = {
            int(e.uid)
            for e in entities.values()
            if ABILITY in {str(x).lower() for x in e.abilities}
        }
        if uids:
            carriers[battle_dir.name] = uids

    active_actor_deaths = 0
    active_actor_deaths_no_external_damage = 0
    active_actor_deaths_with_outgoing_damage = 0
    selfdestruct_candidates = 0
    action_types: Counter[str] = Counter()
    special_codes: Counter[str] = Counter()
    command_shapes: Counter[str] = Counter()
    candidate_target_relations: Counter[str] = Counter()
    damage_to_hp_ratio_rounded: Counter[str] = Counter()
    damaged_target_modifier_sets: Counter[str] = Counter()
    missing_adjacent_targets = 0
    extra_nonadjacent_targets = 0
    exact_adjacent_target_set_candidates = 0
    candidate_damage_hits = 0
    candidate_adjacent_living_targets = 0
    candidate_examples: list[dict] = []
    noncandidate_actor_death_examples: list[dict] = []

    for battle_dir in battle_dirs:
        carrier_uids = carriers.get(battle_dir.name)
        if not carrier_uids:
            continue
        try:
            for decision in iter_battle_decisions(battle_dir):
                actor_uid = int(decision.get("actor_uid", -1))
                if actor_uid not in carrier_uids:
                    continue
                before = list(decision.get("state_before") or [])
                after = list(decision.get("state_after") or [])
                actor_before = _by_uid(before, actor_uid)
                actor_after = _by_uid(after, actor_uid)
                if not actor_before or not bool(actor_before.get("alive", False)):
                    continue
                if actor_after is not None and bool(actor_after.get("alive", False)):
                    continue

                active_actor_deaths += 1
                action_type = str(decision.get("action_type", ""))
                action_types[action_type] += 1
                commands = parse_commands(str(decision.get("raw", "")))
                shape = "->".join(
                    c.opcode if c.opcode != "SPECIAL" else f"SPECIAL:{c.code}"
                    for c in commands
                )
                command_shapes[shape] += 1
                external_damage = [
                    c for c in commands
                    if c.opcode == "DAMAGE"
                    and c.target_uid is not None and int(c.target_uid) == actor_uid
                    and c.actor_uid is not None and int(c.actor_uid) != actor_uid
                ]
                outgoing = [
                    c for c in commands
                    if c.opcode == "DAMAGE"
                    and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                    and c.target_uid is not None and int(c.target_uid) != actor_uid
                ]
                specials = [
                    c for c in commands
                    if c.opcode == "SPECIAL"
                    and c.actor_uid is not None and int(c.actor_uid) == actor_uid
                ]
                if not external_damage:
                    active_actor_deaths_no_external_damage += 1
                if outgoing:
                    active_actor_deaths_with_outgoing_damage += 1
                is_candidate = not external_damage and bool(outgoing)
                if not is_candidate:
                    if len(noncandidate_actor_death_examples) < 20:
                        noncandidate_actor_death_examples.append(
                            {
                                "battle_id": str(decision.get("battle_id", battle_dir.name)),
                                "decision_index": int(decision.get("decision_index", -1)),
                                "server_turn": int(decision.get("server_turn", -1)),
                                "action_type": action_type,
                                "actor_uid": actor_uid,
                                "actor_total_hp_before": _total_hp(actor_before),
                                "external_damage": [str(c.raw) for c in external_damage],
                                "outgoing_damage": [str(c.raw) for c in outgoing],
                                "specials": [str(c.raw) for c in specials],
                                "shape": shape,
                                "raw": str(decision.get("raw", "")),
                            }
                        )
                    continue

                selfdestruct_candidates += 1
                for c in specials:
                    special_codes[str(c.code)] += 1

                hp_before = _total_hp(actor_before)
                adjacent = [
                    e for e in before
                    if int(e.get("uid", -1)) != actor_uid
                    and bool(e.get("alive", False))
                    and not bool(e.get("is_hidden", False))
                    and _adjacent(actor_before, e)
                ]
                adjacent_uids = {int(e.get("uid", -1)) for e in adjacent}
                damaged_uids = {int(c.target_uid) for c in outgoing if c.target_uid is not None}
                missing = sorted(adjacent_uids - damaged_uids)
                extra = sorted(damaged_uids - adjacent_uids)
                missing_adjacent_targets += len(missing)
                extra_nonadjacent_targets += len(extra)
                candidate_adjacent_living_targets += len(adjacent_uids)
                candidate_damage_hits += len(outgoing)
                if adjacent_uids == damaged_uids:
                    exact_adjacent_target_set_candidates += 1

                damage_rows = []
                for c in outgoing:
                    uid = int(c.target_uid)
                    target = _by_uid(before, uid)
                    amount = int(c.amount or 0)
                    owner_relation = "unknown"
                    if target:
                        owner_relation = "same_owner" if int(target.get("owner", -1)) == int(actor_before.get("owner", -2)) else "other_owner"
                    candidate_target_relations[owner_relation] += 1
                    abilities = sorted(_abilities(target))
                    damaged_target_modifier_sets[",".join(abilities) or "<none>"] += 1
                    if hp_before > 0:
                        damage_to_hp_ratio_rounded[f"{amount / hp_before:.3f}"] += 1
                    damage_rows.append(
                        {
                            "target_uid": uid,
                            "target_owner": int(target.get("owner", -1)) if target else None,
                            "target_creature_id": int(target.get("creature_id", -1)) if target else None,
                            "target_abilities": abilities,
                            "amount": amount,
                            "ratio_to_carrier_hp": amount / hp_before if hp_before > 0 else None,
                            "adjacent_before": uid in adjacent_uids,
                            "raw": str(c.raw),
                        }
                    )

                if len(candidate_examples) < 50:
                    candidate_examples.append(
                        {
                            "battle_id": str(decision.get("battle_id", battle_dir.name)),
                            "decision_index": int(decision.get("decision_index", -1)),
                            "server_turn": int(decision.get("server_turn", -1)),
                            "action_type": action_type,
                            "actor_uid": actor_uid,
                            "actor_owner": int(actor_before.get("owner", -1)),
                            "actor_creature_id": int(actor_before.get("creature_id", -1)),
                            "actor_abilities": sorted(_abilities(actor_before)),
                            "actor_total_hp_before": hp_before,
                            "adjacent_living_uids_before": sorted(adjacent_uids),
                            "damaged_uids": sorted(damaged_uids),
                            "missing_adjacent_uids": missing,
                            "extra_nonadjacent_uids": extra,
                            "damage": damage_rows,
                            "specials": [str(c.raw) for c in specials],
                            "shape": shape,
                            "raw": str(decision.get("raw", "")),
                        }
                    )
        except Exception as exc:
            parse_errors.append(f"{battle_dir.name}:turns:{type(exc).__name__}:{exc}")

    return {
        "ability": ABILITY,
        "evidence_scope": "active_carrier_self_death_and_adjacent_damage",
        "corpus_battle_dirs": len(battle_dirs),
        "carrier_battles": len(carriers),
        "parse_errors": parse_errors,
        "active_actor_deaths": active_actor_deaths,
        "active_actor_deaths_no_external_damage": active_actor_deaths_no_external_damage,
        "active_actor_deaths_with_outgoing_damage": active_actor_deaths_with_outgoing_damage,
        "selfdestruct_candidates": selfdestruct_candidates,
        "action_types": _counter(action_types),
        "special_codes": _counter(special_codes),
        "command_shapes": _counter(command_shapes),
        "candidate_damage_hits": candidate_damage_hits,
        "candidate_adjacent_living_targets": candidate_adjacent_living_targets,
        "exact_adjacent_target_set_candidates": exact_adjacent_target_set_candidates,
        "missing_adjacent_targets": missing_adjacent_targets,
        "extra_nonadjacent_targets": extra_nonadjacent_targets,
        "target_owner_relations": _counter(candidate_target_relations),
        "damage_to_carrier_hp_ratio_rounded": _counter(damage_to_hp_ratio_rounded),
        "damaged_target_ability_sets": dict(damaged_target_modifier_sets.most_common(40)),
        "candidate_examples": candidate_examples,
        "noncandidate_actor_death_examples": noncandidate_actor_death_examples,
        "interpretation_guard": (
            "Self-death plus outgoing damage is only a discovery signature. Exact Gribbomb semantics require "
            "the server tooltip, a carrier-specific raw activation discriminator, complete adjacent target coverage, "
            "and a target-modifier-aware Earth-damage rule."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Gribbomb self-destruct candidate semantics.")
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
